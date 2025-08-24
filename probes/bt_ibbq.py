'''
*****************************************
PiFire Bluetooth iBBQ Module 
*****************************************

Description: 
  This module connects to the iBBQ BTLE thermometer via bluetooth and returns temperature data.
  Tested with Inkbird IBT-IBT4XS. 

  	Ex Device Definition: 
	
	device_info = {
			'device' : 'your_device_name',	# Unique name for the device
			'module' : 'bt_ibt4xs',  			# Must be populated for this module to load properly
			'ports' : ['BT0', 'BT1', 'BT2', 'BT3'], # This should be defined by the user with the number of ports desired
			'config' : {
				'transient' : True
			} 
		}

	''

Credits:
    Original code derived from:
    https://github.com/8none1/pybq
    W Cooke - 2020
    @8none1
    https://github.com/8none1

Requirements:
    bluepy - 
		https://github.com/IanHarvey/bluepy
        ** sudo apt install libglib2.0-dev ** prior to installing bluepy
		.. venv/lib/python3.12/site-packages/bluepy$ sudo setcap 'cap_net_raw,cap_net_admin+eip' bluepy-helper
    A compatible BTLE iBBQ thermometer. Perhaps one of these? https://amzn.to/2ZLXyDi

'''

'''
*****************************************
 Imported Libraries
*****************************************
'''
import threading
import time
import logging
import struct  # NEW: required for battery unpack in DataDelegate

from probes.base import ProbeInterface
from bluepy.btle import *
# from icecream import ic  # For debugging

'''
*****************************************
 Class Definitions 
*****************************************
'''

class ScanDelegate(DefaultDelegate):
	def __init__(self):
		DefaultDelegate.__init__(self)
		self.logger = logging.getLogger("control")
	def handleDiscovery(self, dev, isNewDev, isNewData):
		if isNewDev:
			logger_msg = f'(ibbq) Discovered device {dev.addr}'
			# self.logger.debug(logger_msg)
			# ic(logger_msg)

class DataDelegate(DefaultDelegate):
	def __init__(self):
		DefaultDelegate.__init__(self)
		self.logger = logging.getLogger("control")
		self.probe_temps = []
		self.data_initialized = False
		self.batt_percent = None
		self.temp_handle = None       # NEW: dynamic handle for realtime temps (FFF4)
		self.info_handle = None       # NEW: dynamic handle for settings/info (FFF1)

	def set_handles(self, temp_handle, info_handle):  # NEW
		self.temp_handle = temp_handle                 # NEW
		self.info_handle = info_handle                 # NEW

	def handleNotification(self, cHandle, data):
		# NEW: use dynamic handles instead of hard-coded 48/37
		if self.temp_handle is not None and cHandle == self.temp_handle:
			# Temperature payload is 4x uint16 little-endian (tenths of °C), 0xFFFF => unplugged
			temps = [int.from_bytes(data[i:i+2], "little") for i in range(0, len(data), 2)]
			if not self.data_initialized:
				self.probe_temps = [None] * max(4, len(temps))  # NEW: init slots
				self.data_initialized = True

			for idx, item in enumerate(temps[:4]):
				if item != 0xFFFF and item != 65526:  # 0xFFFF unplugged; keep legacy 65526 check
					self.probe_temps[idx] = item / 10.0
				else:
					self.probe_temps[idx] = None

		elif self.info_handle is not None and cHandle == self.info_handle:
			# Info/Settings results (FFF1). Battery reports begin with 0x24.
			if len(data) >= 5 and data[0] == 0x24:
				# Battery format: <BHHB  (0x24, current_mV, max_mV, pad)
				try:
					header, current_voltage, max_voltage, pad = struct.unpack("<BHHB", data[:6])
					if max_voltage == 0: max_voltage = 6580
					self.batt_percent = 100 * current_voltage / max_voltage
					self.logger.debug(f'(ibbq) Battery Percent: {self.batt_percent}')
				except Exception as e:
					self.logger.debug(f'(ibbq) Battery parse error: {e} data={data.hex()}')  # NEW
			else:
				# Quietly log other status frames (e.g., 0B 01 02 01 FF FF 05 01 00 00 00 00)
				self.logger.debug(f'(ibbq) Info frame (FFF1): {data.hex()}')  # NEW

		else:
			self.logger.debug(f'(ibbq) Unknown data received from handle {cHandle}: {data}')

	def get_probe_temps(self):
		return self.probe_temps

	def get_batt_percent(self):
		return self.batt_percent

class iBBQ_Device():
	def __init__(self, port_map, primary_port, units, transient=True, hardware_id=None):
		self.logger = logging.getLogger("control")
		self.transient = transient
		self.port_map = port_map
		self.primary_port = primary_port
		self.battery_percentage = None

		self.units = units 
		self.debug = True
		self.device_ready = False
		self.device_setup = False

		self.port_values = []
		self.probe_values_C = []
		
		self.hardware_id = hardware_id

		self.status = {
			'battery_percentage' : self.battery_percentage,
			'battery_charging' : True if self.battery_percentage == 0 else False,
			'connected' : self.device_setup,
			'hardware_id' : self.hardware_id
		}

		self.sensor_thread_active = False

		self.device_thread = threading.Thread(target=self._setup_device)
		self.device_thread.start()

		self.sensor_thread = threading.Thread(target=self._sensing_loop)
		self.sensor_thread.start()
	
	def _setup_device(self):
		''' Bluetooth iBBQ Device Class '''
		# iBBQ static commands
		CREDENTIALS_MESSAGE  = bytearray.fromhex("21 07 06 05 04 03 02 01 b8 22 00 00 00 00 00")
		REALTIME_DATA_ENABLE = bytearray.fromhex("0B 01 00 00 00 00")
		UNITS_FAHRENHEIT     = bytearray.fromhex("02 01 00 00 00 00")
		UNITS_CELSIUS        = bytearray.fromhex("02 00 00 00 00 00")
		BATTERY_LEVEL        = bytearray.fromhex("08 24 00 00 00 00")
		# iBBQ static service
		MAIN_SERVICE         = 0xFFF0 # Service which provides the characteristics 
		CCCD_UUID            = 0x2902 # We have to write here to enable notifications. bluepy doesn't do this for us. See the "show_all_descriptors" XXX Fix me
		# iBBQ static characteristics
		SETTINGS_RESULTS     = 0xFFF1
		PAIR_UUID            = 0xFFF2
		HISTORY_UUID         = 0xFFF3 # Don't know how this works, here for completeness
		REALTIMEDATA_UUID    = 0xFFF4
		CMD_UUID             = 0xFFF5
		# Static hex little endian ones and zeros
		ON                   = bytearray.fromhex("01 00")
		OFF                  = bytearray.fromhex("00 00")

		# NEW: Additional observed xBBQ initialization messages (safe on older units)
		XBBQ_MSG_0823        = bytearray.fromhex("08 23 00 00 00 00")  # NEW
		XBBQ_MSG_0824        = bytearray.fromhex("08 24 00 00 00 00")  # NEW
		XBBQ_MSG_0825        = bytearray.fromhex("08 25 00 00 00 00")  # NEW
		SECURE_MODE          = bytearray.fromhex("02 01 00 00 00 00")  # NEW
		
		while True:
			try:
				if self.hardware_id == None:
					bbqs={}
					scanner = Scanner().withDelegate(ScanDelegate())
					devices = scanner.scan(10.0)

					for dev in devices:
						# self.logger.info(f'(ibbq) Device {dev.addr}, RSSI={dev.rssi}dB')
						for (adtype, desc, value) in dev.getScanData():
							# Accept both legacy "iBBQ" and newer "xBBQ" advertising names
							if desc == 'Complete Local Name' and value in ('iBBQ', 'xBBQ'):  # NEW
								bbqs[dev.rssi] = dev
								logger_msg = f'(ibbq) Found Inkbird device {value} at address {dev.addr}. RSSI {dev.rssi}'  # NEW (generic label)
								self.logger.info(logger_msg)

					# We should now have a dict of bbq devices, let's sort by rssi and choose the one with the best connection
					if len(bbqs) > 0:
						bbq = bbqs[sorted(bbqs.keys(), reverse=True)[0]].addr
						logger_msg = f'(ibbq) Using Inkbird device {bbq}'  # NEW (generic label)
						self.logger.debug(logger_msg)
						# ic(logger_msg)
						self.hardware_id = bbq
					else:
						logger_msg = f'(ibbq) No iBBQ/xBBQ devices found'  # NEW
						# self.logger.debug(logger_msg)
						# ic(logger_msg)
			except Exception as e:
				self.device_setup = False
				self.hardware_id = None
				logger_msg = f'(ibbq) Error scanning for iBBQ/xBBQ devices: {e}. Might be related to bluetooth permissions.'  # NEW
				self.logger.debug(logger_msg)
				# ic(logger_msg)
				time.sleep(10)
				continue

			if self.hardware_id != None and self.device_setup == False:
				# ic("Setting up iBBQ device thread active")
				try:
					self.ibbq_device = Peripheral(self.hardware_id)
					self.main_service = self.ibbq_device.getServiceByUUID(MAIN_SERVICE)
					self.ibbq_delegate = DataDelegate()
					self.ibbq_device.setDelegate(self.ibbq_delegate)

					# Resolve characteristics up front so we can capture their runtime handles  # NEW
					realtime_characteristic = self.main_service.getCharacteristics(REALTIMEDATA_UUID)[0]      # NEW
					settingsresult_characteristic = self.main_service.getCharacteristics(SETTINGS_RESULTS)[0]  # NEW

					# First we have to log in (legacy method remains for back-compat)
					login_characteristic = self.main_service.getCharacteristics(PAIR_UUID)[0]
					login_characteristic.write(CREDENTIALS_MESSAGE) # Send the magic bytes to login

					# Optionally get a full list (historically helped notifications)
					_ = self.ibbq_device.getCharacteristics()
					_ = self.main_service.getDescriptors()

					# --- Enable CCCDs BEFORE init writes to avoid missing early frames (xBBQ-friendly) ---  # NEW
					temperature_cccd = realtime_characteristic.getDescriptors(forUUID=CCCD_UUID)[0]          # NEW
					temperature_cccd.write(ON)                                                              # NEW
					settingsresults_cccd = settingsresult_characteristic.getDescriptors(forUUID=CCCD_UUID)[0]# NEW
					settingsresults_cccd.write(ON)                                                          # NEW

					# Hand the actual value handles to the delegate (no hard-coded numbers)  # NEW
					self.ibbq_delegate.set_handles(realtime_characteristic.getHandle(),
					                               settingsresult_characteristic.getHandle())              # NEW

					# --- xBBQ compatibility: send observed init sequence (harmless on older units) ---
					settings_characteristic = self.main_service.getCharacteristics(CMD_UUID)[0]
					try:
						settings_characteristic.write(XBBQ_MSG_0823, withResponse=True)  # NEW
						settings_characteristic.write(XBBQ_MSG_0824, withResponse=True)  # NEW
						settings_characteristic.write(XBBQ_MSG_0825, withResponse=True)  # NEW
						settings_characteristic.write(REALTIME_DATA_ENABLE, withResponse=True)  # NEW
						settings_characteristic.write(SECURE_MODE, withResponse=True)  # NEW
					except Exception as _e:
						pass  # NEW

					# The device logs all temperature in degrees C, but we can fix that for you (affects on-device display)
					if self.units == "F":
						settings_characteristic.write(UNITS_FAHRENHEIT, withResponse=True)
					else:
						settings_characteristic.write(UNITS_CELSIUS, withResponse=True)

					# Ask for battery (report comes as a 0x24 frame on FFF1)
					settings_characteristic.write(BATTERY_LEVEL, withResponse=True)

					time.sleep(1)
					self.device_setup = True
					logger_msg = f'(ibbq) iBBQ/xBBQ device setup complete.'  # NEW
					self.logger.debug(logger_msg)
					# ic(logger_msg)
				except Exception as e:  # NEW: log the reason
					logger_msg = f'(ibbq) Failed to setup iBBQ/xBBQ device: {e}'  # NEW
					self.logger.debug(logger_msg)
					# ic(logger_msg)
					self.device_setup = False
					# self.hardware_id = None

			time.sleep(10)

	def _sensing_loop(self):
		# ic('Starting iBBQ sensor loop')
		while True:
			if self.device_setup:
				self.sensor_thread_active = True
				# ic("Sensor Loop Active!")
				try:
					while self.sensor_thread_active:
						if self.ibbq_device.waitForNotifications(1):
							self.probe_values_C = self.ibbq_delegate.get_probe_temps()
							self.battery_percentage = self.ibbq_delegate.get_batt_percent()
					
					logger_msg = f'(ibbq) Sensor thread inactive.'
					self.logger.debug(logger_msg)
					self.sensor_thread_active = False
					# self.device_setup = False
					# self.hardware_id = None

				except BTLEDisconnectError:
					logger_msg = f'(ibbq) iBBQ/xBBQ device has gone away...'  # NEW
					self.logger.debug(logger_msg)
					# ic(logger_msg)
					# Clean up
					self.sensor_thread_active = False
					self.device_setup = False
					# self.hardware_id = None
				except Exception as e:
					logger_msg = f'(ibbq) Error in sensor loop: {e}'
					self.logger.debug(logger_msg)
					# ic(logger_msg)
					self.sensor_thread_active = False
					self.device_setup = False
					# self.hardware_id = None
			else:
				time.sleep(1)

	def get_port_values(self):
		if not self.device_setup or not self.sensor_thread_active:
			if len(self.probe_values_C) > 0:
				for i in range(len(self.probe_values_C)):
					self.probe_values_C[i] = None

		return self.probe_values_C

	def get_status(self):
		"""
		Return the current status of the iBBQ device

		Returns
		-------
		status : dict
			A dictionary containing the current status of the iBBQ device.
			Contains the following keys:
				- battery_percentage : int
					The current battery percentage of the iBBQ device
				- battery_charging : boolean
					True if the iBBQ device is currently charging, False otherwise
				- connected : boolean
					True if the iBBQ device is currently connected, False otherwise
				- hardware_id : string
					The hardware_id of the iBBQ device
		"""
		if self.battery_percentage is not None:
			self.status['battery_percentage'] = self.battery_percentage if (self.battery_percentage > 0 and self.device_setup) else None
			self.status['battery_charging'] = True if (self.battery_percentage == 0 and self.device_setup) else False # Reads zero when charging
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
		# ic(self.port_map)
		# ic(self.output_data)

	def _init_device(self):
		self.time_delay = 0
		self.device = iBBQ_Device(self.port_map, self.primary_port, self.units, transient=self.transient, hardware_id=self.hardware_id)

	def read_all_ports(self, output_data):
		port_values = {}

		probe_values_C = self.device.get_port_values()
		# ic(probe_values_C) # Debugging only	

		if len(probe_values_C) >= len(self.port_map):
			for index, port in enumerate(self.port_map):
				''' Read Ports from Device '''
				port_values[port] = probe_values_C[index] if self.units == 'C' else self._to_fahrenheit(probe_values_C[index])
				# output_value = port_values[port] if port_values[port] != None else 0 # If the read value is None, pass that to the output
				output_value = port_values[port]

				''' Output Tr '''
				self.output_data['tr'][self.port_map[port]] = 0  # resistance NA

				''' Get average temperature from the queue and store it in the output data structure'''
				if port == self.primary_port:
					self.output_data['primary'][self.port_map[port]] = output_value
				elif port in self.food_ports:
					self.output_data['food'][self.port_map[port]] = output_value
				elif port in self.aux_ports:
					self.output_data['aux'][self.port_map[port]] = output_value

				if self.time_delay:
					time.sleep(self.time_delay)  # Time delay, if needed for single-shot mode on some ADC's
		
		return self.output_data
