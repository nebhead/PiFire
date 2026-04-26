'''
*****************************************
PiFire Bluetooth iBBQ Module (Bleak Alt)
*****************************************

Description:
  This module connects to iBBQ/xBBQ BTLE thermometers using the Bleak library
  and returns temperature data.

  Ex Device Definition:

    device_info = {
      'device' : 'your_device_name',
      'module' : 'bt_ibbq_alt',
      'ports' : ['BT0', 'BT1', 'BT2', 'BT3', 'BT4', 'BT5'],
      'config' : {
        'transient' : True,
        'num_probes' : 6,
      }
    }

Requirements:
  bleak - https://github.com/hbldh/bleak
  A compatible BTLE iBBQ/xBBQ thermometer.
'''

import asyncio
import logging
import struct
import threading
import time

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError

from probes.base import ProbeInterface


class iBBQState:
	"""Shared parsed state populated from Bleak notification callbacks."""

	def __init__(self, logger):
		self.logger = logger
		self.probe_temps = []
		self.batt_percent = None
		self.data_initialized = False

	def handle_temp_notification(self, data):
		temps = [int.from_bytes(data[i:i + 2], "little") for i in range(0, len(data), 2)]
		if not self.data_initialized:
			self.probe_temps = [None] * len(temps)
			self.data_initialized = True

		for idx, item in enumerate(temps):
			if item not in (0xFFFF, 65526):
				self.probe_temps[idx] = item / 10.0
			else:
				self.probe_temps[idx] = None

	def handle_info_notification(self, data):
		if len(data) >= 6 and data[0] == 0x24:
			try:
				_, current_voltage, max_voltage, _ = struct.unpack("<BHHB", data[:6])
				if max_voltage == 0:
					max_voltage = 6580
				self.batt_percent = 100 * current_voltage / max_voltage
				self.logger.debug(f'(ibbq_alt) Battery Percent: {self.batt_percent}')
			except Exception as e:
				self.logger.debug(f'(ibbq_alt) Battery parse error: {e} data={data.hex()}')
		else:
			self.logger.debug(f'(ibbq_alt) Info frame (FFF1): {data.hex()}')


class iBBQ_Device:
	# Full 128-bit UUIDs used by Bleak
	SETTINGS_RESULTS_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"
	PAIR_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"
	REALTIMEDATA_UUID = "0000fff4-0000-1000-8000-00805f9b34fb"
	CMD_UUID = "0000fff5-0000-1000-8000-00805f9b34fb"

	# iBBQ command payloads
	CREDENTIALS_MESSAGE = bytearray.fromhex("21 07 06 05 04 03 02 01 b8 22 00 00 00 00 00")
	REALTIME_DATA_ENABLE = bytearray.fromhex("0B 01 00 00 00 00")
	UNITS_FAHRENHEIT = bytearray.fromhex("02 01 00 00 00 00")
	UNITS_CELSIUS = bytearray.fromhex("02 00 00 00 00 00")
	BATTERY_LEVEL = bytearray.fromhex("08 24 00 00 00 00")
	XBBQ_MSG_0823 = bytearray.fromhex("08 23 00 00 00 00")
	XBBQ_MSG_0824 = bytearray.fromhex("08 24 00 00 00 00")
	XBBQ_MSG_0825 = bytearray.fromhex("08 25 00 00 00 00")
	SECURE_MODE = bytearray.fromhex("02 01 00 00 00 00")

	def __init__(self, port_map, primary_port, units, transient=True, hardware_id=None):
		self.logger = logging.getLogger("control")
		self.transient = transient
		self.port_map = port_map
		self.primary_port = primary_port
		self.units = units
		self.hardware_id = hardware_id

		self.debug = True
		self.device_ready = False
		self.device_setup = False
		self.sensor_thread_active = False

		self.port_values = []
		self.probe_values_C = []
		self.battery_percentage = None

		self.status = {
			'battery_percentage': self.battery_percentage,
			'battery_charging': True if self.battery_percentage == 0 else False,
			'connected': self.device_setup,
			'hardware_id': self.hardware_id,
		}

		self._state = iBBQState(self.logger)
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
					self.logger.debug('(ibbq_alt) No iBBQ/xBBQ devices found')
					await asyncio.sleep(10)
					continue

				await self._connect_and_stream(self.hardware_id)
			except Exception as e:
				self.logger.debug(f'(ibbq_alt) Connection loop error: {e}')
				self.device_setup = False
				self.sensor_thread_active = False
				await asyncio.sleep(5)

	async def _discover_device(self):
		try:
			devices = await BleakScanner.discover(timeout=10.0)
			matches = [dev for dev in devices if dev.name in ('iBBQ', 'xBBQ')]
			if not matches:
				return None

			best = max(matches, key=lambda d: d.rssi if d.rssi is not None else -999)
			self.logger.info(f'(ibbq_alt) Found Inkbird device {best.name} at address {best.address}. RSSI {best.rssi}')
			self.logger.debug(f'(ibbq_alt) Using Inkbird device {best.address}')
			return best.address
		except Exception as e:
			self.logger.debug(f'(ibbq_alt) Error scanning for iBBQ/xBBQ devices: {e}')
			return None

	def _disconnected_callback(self, _client):
		self.logger.debug('(ibbq_alt) Device disconnected')
		self.device_setup = False
		self.sensor_thread_active = False

	def _temp_callback(self, _char, data):
		with self._state_lock:
			self._state.handle_temp_notification(bytearray(data))
			self.probe_values_C = list(self._state.probe_temps)

	def _info_callback(self, _char, data):
		with self._state_lock:
			self._state.handle_info_notification(bytearray(data))
			self.battery_percentage = self._state.batt_percent

	async def _safe_write(self, client, uuid, payload):
		try:
			await client.write_gatt_char(uuid, payload, response=True)
		except BleakError:
			await client.write_gatt_char(uuid, payload, response=False)

	async def _connect_and_stream(self, address):
		self.logger.debug(f'(ibbq_alt) Connecting to {address}')
		async with BleakClient(address, disconnected_callback=self._disconnected_callback) as client:
			self._client = client
			if not client.is_connected:
				raise BleakError('Failed to connect to iBBQ/xBBQ device')

			await client.start_notify(self.REALTIMEDATA_UUID, self._temp_callback)
			await client.start_notify(self.SETTINGS_RESULTS_UUID, self._info_callback)

			await self._safe_write(client, self.PAIR_UUID, self.CREDENTIALS_MESSAGE)

			# Observed xBBQ init sequence; harmless on older devices.
			for payload in (
				self.XBBQ_MSG_0823,
				self.XBBQ_MSG_0824,
				self.XBBQ_MSG_0825,
				self.REALTIME_DATA_ENABLE,
				self.SECURE_MODE,
			):
				await self._safe_write(client, self.CMD_UUID, payload)

			if self.units == 'F':
				await self._safe_write(client, self.CMD_UUID, self.UNITS_FAHRENHEIT)
			else:
				await self._safe_write(client, self.CMD_UUID, self.UNITS_CELSIUS)

			await self._safe_write(client, self.CMD_UUID, self.BATTERY_LEVEL)

			self.device_setup = True
			self.sensor_thread_active = True
			self.logger.debug('(ibbq_alt) iBBQ/xBBQ device setup complete.')

			while client.is_connected and not self._stop_event.is_set():
				await asyncio.sleep(1)

			self.device_setup = False
			self.sensor_thread_active = False
			try:
				await client.stop_notify(self.REALTIMEDATA_UUID)
			except Exception:
				pass
			try:
				await client.stop_notify(self.SETTINGS_RESULTS_UUID)
			except Exception:
				pass

	def get_port_values(self):
		with self._state_lock:
			if not self.device_setup or not self.sensor_thread_active:
				if len(self.probe_values_C) > 0:
					self.probe_values_C = [None for _ in self.probe_values_C]
			return list(self.probe_values_C)

	def get_status(self):
		if self.battery_percentage is not None:
			self.status['battery_percentage'] = self.battery_percentage if (self.battery_percentage > 0 and self.device_setup) else None
			self.status['battery_charging'] = True if (self.battery_percentage == 0 and self.device_setup) else False
		else:
			self.status['battery_percentage'] = self.battery_percentage
			self.status['battery_charging'] = False
		self.status['connected'] = self.device_setup
		self.status['hardware_id'] = self.hardware_id
		return self.status


class ReadProbes(ProbeInterface):
	def __init__(self, probe_info, device_info, units):
		self.hardware_id = device_info['config'].get('hardware_id', None)
		if self.hardware_id == '':
			self.hardware_id = None
		super().__init__(probe_info, device_info, units)

	def _init_device(self):
		self.time_delay = 0
		self.device = iBBQ_Device(self.port_map, self.primary_port, self.units, transient=self.transient, hardware_id=self.hardware_id)

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
