'''
*****************************************
PiFire Bluetooth Weber iGrill Module (Bleak Alt)
*****************************************

Description:
  This module connects to Weber iGrill BTLE thermometers using the Bleak library
  and returns temperature data.

  Supported model families (service UUID detection):
    - iGrill mini
    - iGrill mini v2
    - iGrill v2
    - iGrill v202
    - iGrill v3

  Ex Device Definition:

    device_info = {
      'device' : 'your_device_name',
      'module' : 'bt_igrill_alt',
      'ports' : ['BT0', 'BT1', 'BT2', 'BT3'],
      'config' : {
        'transient' : True,
        'hardware_id' : ''
      }
    }

Requirements:
  bleak - https://github.com/hbldh/bleak
  A compatible Weber iGrill BTLE thermometer.

Notes:
  - This initial implementation supports authentication, battery, and probe temps.
  - iGrill v3 propane level is intentionally not implemented in this module yet.
'''

import asyncio
import logging
import threading
import time
from typing import List, Optional

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError

from probes.base import ProbeInterface


class iGrill_Device:
	# Discovery/model service UUIDs
	MINI_SERVICE_UUID = "63c70000-4a82-4261-95ff-92cf32477861"
	MINIV2_SERVICE_UUID = "9d610c43-ae1d-41a9-9b09-3c7ecd5c6035"
	V2_SERVICE_UUID = "a5c50000-f186-4bd6-97f2-7ebacba0d708"
	V202_SERVICE_UUID = "ada7590f-2e6d-469e-8f7b-1822b386a5e9"
	V3_SERVICE_UUID = "6e910000-58dc-41c7-943f-518b278cea88"

	MODEL_SERVICE_UUIDS = {
		MINI_SERVICE_UUID: "iGrill_mini",
		MINIV2_SERVICE_UUID: "iGrill_mini_v2",
		V2_SERVICE_UUID: "iGrillv2",
		V202_SERVICE_UUID: "iGrillv202",
		V3_SERVICE_UUID: "iGrillv3",
	}

	# Authentication and system characteristics
	AUTH_SERVICE_UUID = "64ac0000-4a4b-4b58-9f37-94d3c52ffdf7"
	FIRMWARE_VERSION_UUID = "64ac0001-4a4b-4b58-9f37-94d3c52ffdf7"
	APP_CHALLENGE_UUID = "64ac0002-4a4b-4b58-9f37-94d3c52ffdf7"
	DEVICE_CHALLENGE_UUID = "64ac0003-4a4b-4b58-9f37-94d3c52ffdf7"
	DEVICE_RESPONSE_UUID = "64ac0004-4a4b-4b58-9f37-94d3c52ffdf7"

	# Probe/units characteristics
	TEMP_UNITS_UUID = "06ef0001-2e06-4b79-9e33-fce2c42805ec"
	PROBE_UUIDS = [
		"06ef0002-2e06-4b79-9e33-fce2c42805ec",
		"06ef0004-2e06-4b79-9e33-fce2c42805ec",
		"06ef0006-2e06-4b79-9e33-fce2c42805ec",
		"06ef0008-2e06-4b79-9e33-fce2c42805ec",
	]

	# Standard BLE battery characteristic
	BATTERY_LEVEL_UUID = "00002a19-0000-1000-8000-00805f9b34fb"

	# Known iGrill app challenge payload used by open-source implementations.
	APP_CHALLENGE_PAYLOAD = bytes([0] * 16)
	UNITS_IMPERIAL = bytes([0])
	UNITS_METRIC = bytes([1])

	def __init__(self, port_map, primary_port, units, transient=True, hardware_id=None):
		self.logger = logging.getLogger("control")
		self.transient = transient
		self.port_map = port_map
		self.primary_port = primary_port
		self.units = units
		self.hardware_id = hardware_id

		self.device_setup = False
		self.sensor_thread_active = False
		self.model_id = None
		self.battery_percentage = None
		self.firmware_id = None
		self.probe_values_C: List[Optional[float]] = [None, None, None, None]

		self.status = {
			'battery_percentage': self.battery_percentage,
			'battery_charging': True if self.battery_percentage == 0 else False,
			'connected': self.device_setup,
			'hardware_id': self.hardware_id,
			'firmware_id': self.firmware_id,
			'probe_id': self.model_id,
		}

		self._state_lock = threading.Lock()
		self._stop_event = threading.Event()
		self._loop = None
		self._client = None

		self.device_thread = threading.Thread(target=self._run_ble_loop, daemon=True)
		self.device_thread.start()

	def _run_ble_loop(self):
		self._loop = asyncio.new_event_loop()
		asyncio.set_event_loop(self._loop)
		self._loop.run_until_complete(self._connection_loop())

	async def _connection_loop(self):
		while not self._stop_event.is_set():
			try:
				if self.hardware_id is None:
					self.hardware_id = await self._discover_device()

				if self.hardware_id is None:
					self.logger.debug('(iGrill Alt) No iGrill probe found, sleeping 10s')
					await asyncio.sleep(10)
					continue

				await self._connect_and_stream(self.hardware_id)
			except Exception as e:
				self.logger.error(f'(iGrill Alt) Error in connection loop: {e}')
				with self._state_lock:
					self.sensor_thread_active = False
					self.device_setup = False
					self.probe_values_C = [None, None, None, None]
				await asyncio.sleep(5)

	def _extract_advertised_uuids(self, device):
		uuid_values = set()
		try:
			metadata = getattr(device, 'metadata', {}) or {}
			for value in metadata.get('uuids', []) or []:
				uuid_values.add(str(value).lower())
		except Exception:
			pass
		return uuid_values

	async def _discover_device(self):
		try:
			self.logger.debug('(iGrill Alt) Starting scan...')
			devices = await BleakScanner.discover(timeout=6.0)
			if not devices:
				return None

			candidates = []
			for entry in devices:
				name = (entry.name or '').lower()
				adv_uuids = self._extract_advertised_uuids(entry)
				model_match = None
				for service_uuid, model_name in self.MODEL_SERVICE_UUIDS.items():
					if service_uuid in adv_uuids:
						model_match = model_name
						break

				if model_match is not None or 'igrill' in name:
					candidates.append((entry, model_match))

			if not candidates:
				return None

			# Choose best RSSI candidate to improve stability when many devices are nearby.
			best_entry, model_match = max(candidates, key=lambda item: item[0].rssi if item[0].rssi is not None else -999)
			self.logger.debug(f'(iGrill Alt) Found iGrill device {best_entry.address} model={model_match} rssi={best_entry.rssi}')
			if model_match is not None:
				self.model_id = model_match
			return best_entry.address
		except Exception as e:
			self.logger.error(f'(iGrill Alt) Error scanning for iGrill device: {e}')
			return None

	def _disconnected_callback(self, _client):
		self.logger.debug('(iGrill Alt) Device disconnected')
		with self._state_lock:
			self.device_setup = False
			self.sensor_thread_active = False
			self.probe_values_C = [None, None, None, None]

	async def _safe_read(self, client, uuid):
		try:
			data = await client.read_gatt_char(uuid)
			return bytearray(data)
		except Exception:
			return None

	async def _safe_write(self, client, uuid, payload):
		try:
			await client.write_gatt_char(uuid, payload, response=True)
		except BleakError:
			await client.write_gatt_char(uuid, payload, response=False)

	def _parse_probe_bytes(self, data):
		if not data or len(data) < 2:
			return None

		# iGrill reports disconnected probes with high-byte sentinel 0xF8.
		if data[1] == 0xF8:
			return None

		raw_value = int.from_bytes(data[:2], byteorder='little', signed=True)
		return float(raw_value)

	def _probe_callback_factory(self, index):
		def _probe_callback(_char, data):
			value_c = self._parse_probe_bytes(bytearray(data))
			with self._state_lock:
				if index < len(self.probe_values_C):
					self.probe_values_C[index] = value_c
		return _probe_callback

	def _battery_callback(self, _char, data):
		battery = None
		try:
			if data and len(data) > 0:
				battery = max(0, min(100, int(data[0])))
		except Exception:
			battery = None
		with self._state_lock:
			self.battery_percentage = battery

	async def _resolve_model_service(self, client):
		try:
			services = client.services
		except Exception:
			services = await client.get_services()

		service_uuids = {str(s.uuid).lower() for s in services}
		for service_uuid, model_name in self.MODEL_SERVICE_UUIDS.items():
			if service_uuid in service_uuids:
				self.model_id = model_name
				return service_uuid
		return None

	async def _authenticate(self, client):
		await self._safe_write(client, self.APP_CHALLENGE_UUID, self.APP_CHALLENGE_PAYLOAD)
		await asyncio.sleep(0.2)
		device_challenge = await self._safe_read(client, self.DEVICE_CHALLENGE_UUID)
		if not device_challenge:
			raise BleakError('Failed to read iGrill device challenge')
		await self._safe_write(client, self.DEVICE_RESPONSE_UUID, bytes(device_challenge))

	async def _read_firmware(self, client):
		firmware_bytes = await self._safe_read(client, self.FIRMWARE_VERSION_UUID)
		if not firmware_bytes:
			return
		try:
			self.firmware_id = firmware_bytes.decode('utf-8', errors='ignore').strip('\x00')
		except Exception:
			self.firmware_id = str(firmware_bytes)

	async def _configure_temperature_units(self, client):
		# Keep iGrill on metric units so probe_values_C remains a true Celsius cache.
		await self._safe_write(client, self.TEMP_UNITS_UUID, self.UNITS_METRIC)

	async def _prime_probe_values(self, client):
		for idx, uuid in enumerate(self.PROBE_UUIDS):
			data = await self._safe_read(client, uuid)
			value_c = self._parse_probe_bytes(data)
			with self._state_lock:
				self.probe_values_C[idx] = value_c

	async def _prime_battery_value(self, client):
		battery_data = await self._safe_read(client, self.BATTERY_LEVEL_UUID)
		if battery_data and len(battery_data) > 0:
			with self._state_lock:
				self.battery_percentage = max(0, min(100, int(battery_data[0])))

	async def _connect_and_stream(self, address):
		self.logger.debug(f'(iGrill Alt) Connecting to device: {address}')
		async with BleakClient(address, disconnected_callback=self._disconnected_callback) as client:
			self._client = client
			if not client.is_connected:
				raise BleakError('Failed to connect to iGrill device')

			await self._resolve_model_service(client)
			await self._authenticate(client)
			await self._read_firmware(client)
			await self._configure_temperature_units(client)

			# Register notifications for live updates.
			for idx, probe_uuid in enumerate(self.PROBE_UUIDS):
				try:
					await client.start_notify(probe_uuid, self._probe_callback_factory(idx))
				except Exception as e:
					self.logger.debug(f'(iGrill Alt) Probe notify setup failed for {probe_uuid}: {e}')

			try:
				await client.start_notify(self.BATTERY_LEVEL_UUID, self._battery_callback)
			except Exception as e:
				self.logger.debug(f'(iGrill Alt) Battery notify setup failed: {e}')

			await self._prime_probe_values(client)
			await self._prime_battery_value(client)

			with self._state_lock:
				self.device_setup = True
				self.sensor_thread_active = True

			while client.is_connected and not self._stop_event.is_set():
				await asyncio.sleep(1)

			with self._state_lock:
				self.sensor_thread_active = False
				self.device_setup = False
				self.probe_values_C = [None, None, None, None]

			for probe_uuid in self.PROBE_UUIDS:
				try:
					await client.stop_notify(probe_uuid)
				except Exception:
					pass
			try:
				await client.stop_notify(self.BATTERY_LEVEL_UUID)
			except Exception:
				pass

	def get_port_values(self):
		with self._state_lock:
			values = list(self.probe_values_C)
			if len(values) < 4:
				values.extend([None] * (4 - len(values)))
			return values

	def get_status(self):
		with self._state_lock:
			if self.battery_percentage is not None:
				self.status['battery_percentage'] = self.battery_percentage if (self.battery_percentage > 0 and self.device_setup) else None
				self.status['battery_charging'] = True if (self.battery_percentage == 0 and self.device_setup) else False
			else:
				self.status['battery_percentage'] = self.battery_percentage
				self.status['battery_charging'] = False
			self.status['connected'] = self.device_setup
			self.status['hardware_id'] = self.hardware_id
			self.status['firmware_id'] = str(self.firmware_id)
			self.status['probe_id'] = str(self.model_id)
			return self.status


class ReadProbes(ProbeInterface):
	def __init__(self, probe_info, device_info, units):
		self.hardware_id = device_info['config'].get('hardware_id', None)
		if self.hardware_id == '':
			self.hardware_id = None
		super().__init__(probe_info, device_info, units)

	def _init_device(self):
		self.time_delay = 0
		self.device = iGrill_Device(self.port_map, self.primary_port, self.units, transient=self.transient, hardware_id=self.hardware_id)

	def read_all_ports(self, output_data):
		port_values = {}
		probe_values_C = self.device.get_port_values()

		if len(probe_values_C) >= len(self.port_map):
			for index, port in enumerate(self.port_map):
				port_values[port] = probe_values_C[index] if self.units == 'C' else self._to_fahrenheit(probe_values_C[index])
				output_value = port_values[port]

				self.output_data['tr'][self.port_map[port]] = 0

				if port == self.primary_port:
					self.output_data['primary'][self.port_map[port]] = output_value
				elif port in self.food_ports:
					self.output_data['food'][self.port_map[port]] = output_value
				elif port in self.aux_ports:
					self.output_data['aux'][self.port_map[port]] = output_value

				if self.time_delay:
					time.sleep(self.time_delay)

		return self.output_data
