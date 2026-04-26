'''
*****************************************
PiFire Bluetooth Meater Module (Bleak Alt)
*****************************************

Description:
  This module connects to Meater BTLE thermometers using the Bleak library
  and returns temperature data.

  Supports: Meater Original, Meater Plus, and Meater Pro models.

  Ex Device Definition:

    device_info = {
      'device' : 'your_device_name',
      'module' : 'bt_meater_alt',
      'ports' : ['BT_Tip', 'BT_Ambient'],
      'config' : {
        'transient' : True
      }
    }

Requirements:
  bleak - https://github.com/hbldh/bleak
  A compatible BTLE Meater thermometer.

Adding Support for New Meater Models:
  If you have a new Meater model and it's not connecting properly:
  1. Check the ic() debug output (already in code) for discovered service/characteristic UUIDs
  2. Add any new UUIDs to the BaseMeater class _UUID_CANDIDATES lists
  3. Or submit the output showing all services/characteristics to help expand support
'''

import asyncio
import logging
import struct
import threading
import time

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError

from probes.base import ProbeInterface
# from icecream import ic  # For debugging


class BaseMeater:
	# Legacy handle addresses used by existing bluepy implementation.
	# Note: Bleak uses UUID-based lookup instead of handles, which is more portable across models.
	# If a new Meater model is encountered, enable ic() debugging (uncomment in __init__)
	# and post the output of all discovered service UUIDs and characteristics.
	# Then add the new UUIDs to the appropriate _UUID_CANDIDATES lists below.
	HANDLE_TEMP = 31
	HANDLE_BATTERY = 35
	HANDLE_FIRMWARE = 22

	TEMP_UUID = "7edda774-045e-4bbf-909b-45d1991a2876"
	BATTERY_UUID_CANDIDATES = [
		"2adb4877-68d8-4884-bd3c-d83853bf27b8",  # Meater Original (primary)
		"00002a19-0000-1000-8000-00805f9b34fb",  # Standard BLE Battery Level
		"b3e02c20-85be-4d1e-8da8-30cd88aaf0d4",  # Meater alternative (if discovered)
	]
	FIRMWARE_UUID_CANDIDATES = [
		"00002a28-0000-1000-8000-00805f9b34fb",  # Standard BLE Software Revision String
		"00002a26-0000-1000-8000-00805f9b34fb",  # Standard BLE Firmware Revision String
	]

	def __init__(self, client, services):
		self.logger = logging.getLogger("control")
		self.client = client
		self.services = services
		self.__tip = None
		self.__ambient = None
		self.battery_percentage = None
		self.firmware_id = None
		self.probe_id = None
		self.device_setup = False

		self.temp_char = self._find_temp_char()
		# Prefer UUID matching over handle matching for model/firmware portability.
		self.battery_char = self._find_char_by_uuid_candidates(self.BATTERY_UUID_CANDIDATES)
		if self.battery_char is None:
			self.battery_char = self._find_char_by_handle(self.HANDLE_BATTERY)

		self.firmware_char = self._find_char_by_handle(self.HANDLE_FIRMWARE)
		if self.firmware_char is None:
			self.firmware_char = self._find_char_by_uuid_candidates(self.FIRMWARE_UUID_CANDIDATES)

		# ic(self.temp_char, self.battery_char, self.firmware_char)

		if self.temp_char is None:
			logger_msg = f'(Meater Alt) No temp characteristic found, fallback handle expected: {self.HANDLE_TEMP}'
			self.logger.debug(logger_msg)
			# ic(logger_msg)

	def _iter_characteristics(self):
		for service in self.services:
			# ic(f'(Meater Alt) Service: {service.uuid}')
			for characteristic in service.characteristics:
				# ic(f'  Characteristic: UUID={characteristic.uuid} handle={characteristic.handle}')
				yield characteristic

	def _iter_meater_characteristics(self):
		"""Iterate only over characteristics in the Meater proprietary service."""
		meater_service_uuid = "a75cc7fc-c956-488f-ac2a-2dbc08b63a04"
		for service in self.services:
			if str(service.uuid).lower() == meater_service_uuid:
				for characteristic in service.characteristics:
					yield characteristic

	def _find_temp_char(self):
		for characteristic in self._iter_characteristics():
			if str(characteristic.uuid).lower() == self.TEMP_UUID:
				logger_msg = f'(Meater Alt) Found temp characteristic: {characteristic.uuid} handle: {characteristic.handle}'
				self.logger.debug(logger_msg)
				# ic(logger_msg)
				return characteristic
		return self._find_char_by_handle(self.HANDLE_TEMP)

	def _find_char_by_handle(self, handle):
		# ic(f'(Meater Alt) Searching for handle {handle}')
		for characteristic in self._iter_characteristics():
			if characteristic.handle == handle:
				logger_msg = f'(Meater Alt) Found handle {handle} as UUID {characteristic.uuid}'
				self.logger.debug(logger_msg)
				# ic(logger_msg)
				return characteristic
		# ic(f'(Meater Alt) Handle {handle} NOT found')
		return None

	def _find_char_by_uuid_candidates(self, uuid_candidates):
		# ic(f'(Meater Alt) Searching for UUID candidates: {uuid_candidates}')
		# Build lookup once, then resolve in candidate priority order.
		char_by_uuid = {}
		for characteristic in self._iter_characteristics():
			char_by_uuid[str(characteristic.uuid).lower()] = characteristic

		for candidate_uuid in uuid_candidates:
			characteristic = char_by_uuid.get(candidate_uuid)
			if characteristic is not None:
				logger_msg = f'(Meater Alt) Found preferred characteristic {candidate_uuid} handle: {characteristic.handle}'
				self.logger.debug(logger_msg)
				# ic(logger_msg)
				return characteristic
		# ic(f'(Meater Alt) No UUID candidates matched')
		return None

	def bytesToInt(self, byte0, byte1):
		return (byte1 * 256) + byte0

	def _normalize_battery_percentage(self, battery_bytes, source_uuid):
		"""Parse known battery formats and return a sane percentage in the range 0-100."""
		if not battery_bytes:
			return None

		uuid_text = str(source_uuid).lower() if source_uuid else ""
		raw_le16 = None
		if len(battery_bytes) >= 2:
			raw_le16 = self.bytesToInt(battery_bytes[0], battery_bytes[1])

		# Standard BLE Battery Level characteristic: one byte, 0-100.
		if uuid_text == "00002a19-0000-1000-8000-00805f9b34fb":
			pct = battery_bytes[0]
		# Meater-specific battery characteristic has been observed as little-endian 0-100.
		elif uuid_text == "2adb4877-68d8-4884-bd3c-d83853bf27b8":
			if raw_le16 is None:
				pct = battery_bytes[0]
			elif raw_le16 <= 10:
				# Some Meater firmwares appear to report in 10% steps (for example 9 => 90%).
				pct = raw_le16 * 10
			elif raw_le16 <= 100:
				pct = raw_le16
			elif raw_le16 <= 1000 and raw_le16 % 10 == 0:
				# Some firmwares may report tenths of a percent.
				pct = raw_le16 // 10
			else:
				# Fallback for unknown variants; keeps value bounded.
				pct = battery_bytes[0]
		else:
			# Generic fallback heuristics for unknown battery UUIDs.
			if raw_le16 is None:
				pct = battery_bytes[0]
			elif raw_le16 <= 100:
				pct = raw_le16
			elif raw_le16 <= 1000 and raw_le16 % 10 == 0:
				pct = raw_le16 // 10
			else:
				pct = battery_bytes[0]

		return max(0, min(100, int(pct)))

	def convertAmbient(self, array):
		tip = self.bytesToInt(array[0], array[1])
		ra = self.bytesToInt(array[2], array[3])
		oa = self.bytesToInt(array[4], array[5])
		return int(tip + (max(0, ((((ra - min(48, oa)) * 16) * 589)) / 1487)))

	async def readCharacteristic(self, char_obj):
		if char_obj is None:
			return None
		try:
			data = await self.client.read_gatt_char(char_obj)
			return bytearray(data)
		except Exception as e:
			logger_msg = f'(Meater Alt) Read attempt failed: {e}'
			self.logger.debug(logger_msg)
			return None

	async def update(self):
		await self._read_temperature()
		await self._read_battery()
		await self._read_firmware()
		self._lastUpdate = time.time()

	async def _read_temperature(self):
		tempBytes = await self.readCharacteristic(self.temp_char)
		if not tempBytes or len(tempBytes) < 6:
			# ic('(Meater Alt) Temperature read failed or insufficient bytes', tempBytes)
			return
		self.logger.debug(f'(Meater Alt) Temperature bytes: {tempBytes}')
		# ic(tempBytes)
		self.__tip = self.bytesToInt(tempBytes[0], tempBytes[1])
		self.__ambient = self.convertAmbient(tempBytes)
		# ic(self.__tip, self.__ambient)

	async def _read_battery(self):
		batteryBytes = await self.readCharacteristic(self.battery_char)
		if not batteryBytes:
			# ic('(Meater Alt) Battery read failed')
			return
		# ic(batteryBytes)
		try:
			source_uuid = getattr(self.battery_char, "uuid", None) if self.battery_char else None
			source_handle = getattr(self.battery_char, "handle", None) if self.battery_char else None
			raw_le16 = self.bytesToInt(batteryBytes[0], batteryBytes[1]) if len(batteryBytes) >= 2 else batteryBytes[0]
			self.battery_percentage = self._normalize_battery_percentage(batteryBytes, source_uuid)
			# ic(f'(Meater Alt) Battery source uuid={source_uuid} handle={source_handle}')
			# ic(f'(Meater Alt) Battery raw_le16={raw_le16}')
			# ic(self.battery_percentage)
		except Exception as e:
			logger_msg = f'(Meater Alt) Battery parse error: {e}'
			self.logger.debug(logger_msg)
			# ic(logger_msg)

	async def _read_firmware(self):
		firmware_bytes = await self.readCharacteristic(self.firmware_char)
		if not firmware_bytes:
			return
		try:
			firmware_text = firmware_bytes.decode("utf-8", errors="ignore").strip("\x00")
		except Exception:
			firmware_text = str(firmware_bytes)

		# ic(firmware_text)
		if "_" in firmware_text:
			parts = firmware_text.split("_", 1)
			self.firmware_id = parts[0]
			self.probe_id = parts[1]
		else:
			self.firmware_id = firmware_text
			if self.probe_id is None:
				self.probe_id = "None"
		# ic(self.firmware_id, self.probe_id)

	@property
	def tip(self):
		return self.__tip

	@property
	def ambient(self):
		return self.__ambient

	@property
	def probe_values_C(self):
		tip = round(self.getTipC(), 1) if self.getTipC() is not None else None
		ambient = round(self.getAmbientC(), 1) if self.getAmbientC() is not None else None
		# ic(tip, ambient)
		return [tip, ambient]

	def toCelsius(self, value):
		if value is None:
			return None
		return (float(value) + 8.0) / 16.0

	def toFahrenheit(self, value):
		if value is None:
			return None
		return ((self.toCelsius(value) * 9) / 5) + 32.0

	def getTipF(self):
		return self.toFahrenheit(self.__tip)

	def getTipC(self):
		return self.toCelsius(self.__tip)

	def getAmbientF(self):
		return self.toFahrenheit(self.__ambient)

	def getAmbientC(self):
		return self.toCelsius(self.__ambient)

	def battery(self):
		return self.battery_percentage

	def id(self):
		return self.probe_id

	def firmware(self):
		return self.firmware_id


class MeaterOriginal(BaseMeater):
	def __init__(self, client, services):
		super().__init__(client, services)


class MeaterPro(BaseMeater):
	def __init__(self, client, services):
		super().__init__(client, services)

	def toCelsius(self, value):
		if value is None:
			return None
		if value > 0:
			return (value + 8) / 32
		if value < 0:
			return (value - 8) / 32
		return 0

	def toFahrenheitInternals(self, temps):
		if temps is None:
			return None
		for i in range(len(temps)):
			temps[i] = temps[i] * 9 / 5 + 32
		return temps

	def toFahrenheitAmbient(self, temp):
		return temp * 9 / 5 + 32

	def get_short(self, data, offset):
		return struct.unpack_from("<h", data, offset)[0]

	def ambient_correction(self, ambient_temp, internal_temp):
		return int(internal_temp + ((ambient_temp - internal_temp) * 1.2))

	def convert_to_temperatures(self, data):
		self.internal_temps = [
			self.toCelsius(self.get_short(data, 0)),
			self.toCelsius(self.get_short(data, 2)),
			self.toCelsius(self.get_short(data, 4)),
			self.toCelsius(self.get_short(data, 6)),
			self.toCelsius(self.get_short(data, 8)),
		]

		self.ambient_temp = self.toCelsius(self.get_short(data, 10))
		self.ambient_correction(self.ambient_temp, self.internal_temps[4])

	def getAmbient(self):
		return self.toFahrenheitAmbient(self.ambient_temp)

	def getAmbientC(self):
		return self.ambient_temp

	def getTips(self):
		return self.toFahrenheitInternals(self.internal_temps)

	def getTip(self):
		internal_temps = self.toFahrenheitInternals(self.internal_temps)
		return min(internal_temps)

	def getTipC(self):
		return min(self.internal_temps)

	async def _read_temperature(self):
		tempBytes = await self.readCharacteristic(self.temp_char)
		if not tempBytes or len(tempBytes) < 12:
			# ic('(Meater Alt Pro) Temperature read failed or insufficient bytes', tempBytes)
			return
		# ic(tempBytes)
		self.convert_to_temperatures(tempBytes)
		# ic(self.internal_temps, self.ambient_temp)


class Meater_Device:
	MEATER_PRO_SERVICE_UUID = "c9e2746c-59f1-4e54-a0dd-e1e54555cf8b"
	MEATER_ORIGINAL_SERVICE_UUID = "a75cc7fc-c956-488f-ac2a-2dbc08b63a04"

	def __init__(self, port_map, primary_port, units, transient=True, hardware_id=None):
		self.logger = logging.getLogger("control")
		self.transient = transient
		self.port_map = port_map
		self.primary_port = primary_port
		self.units = units
		self.debug = True
		self.device_setup = False
		self.meater_type = None

		self.probe_values_C = []
		self.battery_percentage = None
		self.hardware_id = hardware_id
		self.firmware_id = None
		self.probe_id = None

		self.status = {
			'battery_percentage': self.battery_percentage,
			'battery_charging': True if self.battery_percentage == 0 else False,
			'connected': self.device_setup,
			'hardware_id': self.hardware_id,
			'firmware_id': self.firmware_id,
			'probe_id': self.probe_id,
		}

		self.sensor_thread_active = False
		self.meater = None
		self._state_lock = threading.Lock()
		self._stop_event = threading.Event()
		self._loop = None

		self.device_thread = threading.Thread(target=self._run_ble_loop, daemon=True)
		self.device_thread.start()

	def _run_ble_loop(self):
		# ic('(Meater Alt) BLE loop thread started')
		self._loop = asyncio.new_event_loop()
		asyncio.set_event_loop(self._loop)
		self._loop.run_until_complete(self._connection_loop())

	async def _connection_loop(self):
		# ic('(Meater Alt) Connection loop started')
		while not self._stop_event.is_set():
			try:
				if self.hardware_id is None:
					self.hardware_id = await self._discover_device()
					# ic(self.hardware_id)

				if self.hardware_id is None:
					# ic('(Meater Alt) No device found, sleeping 10s')
					await asyncio.sleep(10)
					continue

				# ic(f'(Meater Alt) Attempting connection to {self.hardware_id}')
				await self._connect_and_stream(self.hardware_id)
			except Exception as e:
				logger_msg = f'(Meater Alt) Error in connection loop: {e}'
				self.logger.error(logger_msg)
				# ic(logger_msg)
				with self._state_lock:
					self.sensor_thread_active = False
					self.device_setup = False
					self.meater = None
				await asyncio.sleep(5)

	async def _discover_device(self):
		try:
			self.logger.debug('(Meater Alt) Starting scan...')
			# ic('(Meater Alt) Starting scan...')
			devices = await BleakScanner.discover(timeout=5.0)
			# ic(f'(Meater Alt) Scan found {len(devices)} device(s)')
			for entry in devices:
				name = entry.name
				# ic(f'(Meater Alt) Scanned: {name} / {entry.address}')
				if name is not None and 'meater+' in name.lower():
					# ic(f'(Meater Alt) Skipping base station: {name}')
					continue
				if name is not None and 'meater' in name.lower():
					logger_msg = f'(Meater Alt) Found a Meater Probe at address {entry.address}'
					self.logger.debug(logger_msg)
					# ic(logger_msg)
					self.logger.debug('(Meater Alt) Stopping scan.')
					return entry.address
			self.logger.debug('(Meater Alt) No Meater probe found')
			# ic('(Meater Alt) No Meater probe found in scan results')
			return None
		except Exception as e:
			logger_msg = f'(Meater Alt) Error scanning for device: {e}'
			self.logger.error(logger_msg)
			# ic(logger_msg)
			return None

	async def _connect_and_stream(self, address):
		self.logger.debug(f'(Meater Alt) Connecting to device: {address}')
		# ic(f'(Meater Alt) Connecting to device: {address}')
		async with BleakClient(address, mtu_size=512) as client:
			# ic(f'(Meater Alt) client.is_connected = {client.is_connected}')
			if not client.is_connected:
				raise BleakError('Failed to connect to Meater device')

			services = client.services
			service_uuids = {str(s.uuid).lower() for s in services}
			# ic(f'(Meater Alt) Discovered service UUIDs: {service_uuids}')

			with self._state_lock:
				if self.MEATER_PRO_SERVICE_UUID in service_uuids:
					self.meater_type = 'MEATER_PRO'
					self.meater = MeaterPro(client, services)
					self.logger.debug('(Meater Alt) Meater Pro setup complete')
					# ic('(Meater Alt) Meater Pro setup complete')
				elif self.MEATER_ORIGINAL_SERVICE_UUID in service_uuids:
					self.meater_type = 'MEATER_ORIGINAL'
					self.meater = MeaterOriginal(client, services)
					self.logger.debug('(Meater Alt) Meater Original setup complete')
					# ic('(Meater Alt) Meater Original setup complete')
				else:
					self.meater_type = None
					self.meater = None
					self.device_setup = False
					# ic('(Meater Alt) Meater type could not be determined from services')

				if self.meater is None:
					raise BleakError('Unable to determine Meater type from services')

				self.device_setup = True
				self.sensor_thread_active = True
				# ic('(Meater Alt) Device setup complete, streaming loop starting')

			while client.is_connected and not self._stop_event.is_set():
				await self._update_state()
				await asyncio.sleep(1)

			# ic('(Meater Alt) Client disconnected, exiting stream loop')
			with self._state_lock:
				self.sensor_thread_active = False
				self.device_setup = False
				self.meater = None

	async def _update_state(self):
		with self._state_lock:
			meater = self.meater

		if meater is None:
			return

		await meater.update()

		with self._state_lock:
			self.probe_values_C = meater.probe_values_C
			self.battery_percentage = meater.battery()
			self.firmware_id = meater.firmware()
			self.probe_id = meater.id()
			# ic(self.probe_values_C, self.battery_percentage, self.firmware_id, self.probe_id)

	def get_port_values(self):
		with self._state_lock:
			return list(self.probe_values_C)

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
			self.status['probe_id'] = str(self.probe_id)
			return self.status


class ReadProbes(ProbeInterface):
	def __init__(self, probe_info, device_info, units):
		self.hardware_id = device_info['config'].get('hardware_id', None)
		if self.hardware_id == '':
			self.hardware_id = None
		super().__init__(probe_info, device_info, units)
		# ic(self.port_map)
		# ic(self.output_data)

	def _init_device(self):
		self.time_delay = 0
		self.device = Meater_Device(self.port_map, self.primary_port, self.units, transient=self.transient, hardware_id=self.hardware_id)

	def read_all_ports(self, output_data):
		port_values = {}

		probe_values_C = self.device.get_port_values()
		# ic(probe_values_C)

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
