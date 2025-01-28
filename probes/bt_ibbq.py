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

from probes.base import ProbeInterface
from bluepy.btle import *
#from icecream import ic  # For debugging

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
			logger_msg = f'Discovered device {dev.addr}'
			#self.logger.debug(logger_msg)
			#ic(logger_msg)

class DataDelegate(DefaultDelegate):
	def __init__(self):
		DefaultDelegate.__init__(self)
		self.logger = logging.getLogger("control")
		self.probe_temps = []
		self.data_initialized = False
		self.batt_percent = None

	def handleNotification(self, cHandle, data):
		if cHandle == 48:
			# this is temperature data!  48 is the handle of the probes characteristic XXX check terminology
			temps = [int.from_bytes(data[i:i+2], "little") for i in range(0,len(data),2)]
			
			if not self.data_initialized:
				for i in range(len(temps)):
					self.probe_temps.append(None)
				self.data_initialized = True

			# Note: "0xFF" or 65526 means the probe is not connected and so should be ignored.
			#self.logger.debug(f'Temps(C) [BT0, BT1, BT2, BT3]: {temps}')
			for idx, item in enumerate(temps):
				if item != 65526: # This is what gets reported when the probe isn't plugged in.
					item = item / 10 # Value in Celsius
					self.probe_temps[idx] = item
				else:
					self.probe_temps[idx] = None

		elif cHandle == 37:
			# this is battery data!
			# The first byte is a header and should always be 0x24
			# It looks like the last byte is always zero
			# The other bytes should be for current voltage and max voltage
			# Thanks @sil for the help with the struct
			header, current_voltage, max_voltage,pad = struct.unpack("<BHHB", data)
			if max_voltage == 0: max_voltage = 6580 # XXX check this
			self.batt_percent = 100 * current_voltage / max_voltage
			logger_msg = f'Battery Percent: {self.batt_percent}'
			self.logger.debug(logger_msg) # (batt_percent)
			#ic(logger_msg)

		else:
			self.logger.debug(f'Unknown data received from handle {cHandle}: {data}')

	def get_probe_temps(self):
		return self.probe_temps

	def get_batt_percent(self):
		return self.batt_percent

class iBBQ_Device():
	def __init__(self, port_map, primary_port, units, transient=True):
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
		
		self.hardware_id = None

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
		
		while True:
			if self.hardware_id == None:
				bbqs={}
				scanner = Scanner().withDelegate(ScanDelegate())
				devices = scanner.scan(10.0)

				for dev in devices:
					#self.logger.info(f'Device {dev.addr}, RSSI={dev.rssi}dB')
					for (adtype, desc, value) in dev.getScanData():
						if desc == 'Complete Local Name' and value == 'iBBQ':
							bbqs[dev.rssi] = dev
							logger_msg = f'Found iBBQ device {value} at address {dev.addr}. RSSI {dev.rssi}'
							self.logger.info(logger_msg)

				# We should now have a dict of bbq devices, let's sort by rssi and choose the one with the best connection
				if len(bbqs) > 0:
					bbq = bbqs[sorted(bbqs.keys(), reverse=True)[0]].addr
					logger_msg = f'Using iBBQ device {bbq}'
					self.logger.debug(logger_msg)
					#ic(logger_msg)
					self.hardware_id = bbq
				else:
					logger_msg = f'No iBBQ devices found'
					#self.logger.debug(logger_msg)
					#ic(logger_msg)

			if self.hardware_id != None and self.device_setup == False:
				#ic("Setting up iBBQ device thread active")
				try:
					self.ibbq_device = Peripheral(self.hardware_id)
					self.main_service = self.ibbq_device.getServiceByUUID(MAIN_SERVICE)
					self.ibbq_delegate = DataDelegate()
					self.ibbq_device.setDelegate(self.ibbq_delegate)

					# First we have to log in
					login_characteristic = self.main_service.getCharacteristics(PAIR_UUID)[0]
					login_characteristic.write(CREDENTIALS_MESSAGE) # Send the magic bytes to login

					# Scan the device for all the services.  You don't seem to need to do both
					# of these, but you do _have_ to do one of them.  If you don't then the notifications
					# don't work and you won't get a temperature reading.  Doing both for the sake of it.
					bbq_characteristic = self.ibbq_device.getCharacteristics()
					main_descriptors = self.main_service.getDescriptors()

					# Then we have to enable real time data collection
					settings_characteristic = self.main_service.getCharacteristics(CMD_UUID)[0]
					settings_characteristic.write(REALTIME_DATA_ENABLE, withResponse=True)

					# The device logs all temperature in degrees c, but we can fix that for you.  Here we change the display units, and in the DataDelegate function we convert the temps
					if self.units == "F":
						settings_characteristic.write(UNITS_FAHRENHEIT, withResponse=True)
					else:
						settings_characteristic.write(UNITS_CELSIUS, withResponse=True)

					# And we have to switch on notifications for the realtime characteristic.
					# UUID 2902 is the standard descriptor UUID for CCCD which we need to write to in order
					# to have data sent to us.  You can switch the services on and off with 0100 and 0000.
					# The CCCD descriptor is on the REALTIMEDATA_UUID - which means it controls the data for the probes.
					realtime_characteristic = self.main_service.getCharacteristics(REALTIMEDATA_UUID)[0] # This is where the temperature data lives.
					temperature_cccd = realtime_characteristic.getDescriptors(forUUID=CCCD_UUID)[0] # This wasn't in the docs, but was in the source. It still took me all day to work it out.
					# Now all we need to do is write a 1 (little endian) to it, and it will start sending data!  Easy when you know how.
					temperature_cccd.write(ON)

					# Let's see if we can get the battery level out of this thing as well.
					# This is supposed to be read on 0xFFF1 SETTINGS_RESULTS.
					settings_characteristic.write(BATTERY_LEVEL, withResponse=True)
					# Then we need to do the same as before and get the CCCD descriptor and switch on notifications.
					# Battery notifications are sent about every 5 mins
					settingsresult_characteristic = self.main_service.getCharacteristics(SETTINGS_RESULTS)[0]
					settingsresults_cccd = settingsresult_characteristic.getDescriptors(forUUID=CCCD_UUID)[0]
					settingsresults_cccd.write(ON)
					time.sleep(1)
					self.device_setup = True
					logger_msg = f'iBBQ device setup complete.'
					self.logger.debug(logger_msg)
					#ic(logger_msg)
				except:
					logger_msg = f'Failed to setup iBBQ device.'
					self.logger.debug(logger_msg)
					#ic(logger_msg)
					self.device_setup = False
					self.hardware_id = None

			time.sleep(10)

	def _sensing_loop(self):
		#ic('Starting iBBQ sensor loop')
		while True:
			if self.device_setup:
				self.sensor_thread_active = True
				#ic("Sensor Loop Active!")
				try:
					while self.sensor_thread_active:
						if self.ibbq_device.waitForNotifications(1):
							self.probe_values_C = self.ibbq_delegate.get_probe_temps()
							self.battery_percentage = self.ibbq_delegate.get_batt_percent()

				except BTLEDisconnectError:
					logger_msg = f'iBBQ device has gone away...'
					self.logger.debug(logger_msg)
					#ic(logger_msg)
					# Clean up
					self.sensor_thread_active = False
					self.device_setup = False
					self.hardware_id = None
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
		super().__init__(probe_info, device_info, units)
		#ic(self.port_map)
		#ic(self.output_data)

	def _init_device(self):
		self.time_delay = 0
		self.device = iBBQ_Device(self.port_map, self.primary_port, self.units, transient=self.transient)

	def read_all_ports(self, output_data):
		port_values = {}

		probe_values_C = self.device.get_port_values()
		#ic(probe_values_C) # Debugging only	

		if len(probe_values_C) >= len(self.port_map):
			for index, port in enumerate(self.port_map):
				''' Read Ports from Device '''
				port_values[port] = probe_values_C[index] if self.units == 'C' else self._to_fahrenheit(probe_values_C[index])
				#output_value = port_values[port] if port_values[port] != None else 0 # If the read value is None, pass that to the output
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