'''
*****************************************
PiFire Bluetooth Meater ALT Module 
*****************************************

Description: 
  This module connects to the Meater BTLE thermometer via bluetooth and returns temperature data.

  	Ex Device Definition: 
	
	device_info = {
			'device' : 'your_device_name',	# Unique name for the device
			'module' : 'bt_meater_alt',  			# Must be populated for this module to load properly
			'ports' : ['BT_Tip', 'BT_Ambient'],  # 
			'config' : {
				'transient' : True
			} 
		}

	''

Credits:
	Original code derived from:
	https://github.com/kjokay/pymeater/blob/master/pymeater/meater.py
	Kjokay - April 2020
	https://github.com/kjokay
	Likely derived from: https://github.com/nathanfaber/meaterble
	Nathan Fabar - Jan 2020 

	Additional code derived from: 
	https://github.com/jcallaghan/home-assistant-config/issues/82
	https://community.home-assistant.io/t/support-for-meater-true-wireless-cooking-thermometer/513156
	https://github.com/nathanfaber/meaterble

Requirements:
	bluepy - 
		https://github.com/IanHarvey/bluepy
		https://ianharvey.github.io/bluepy-doc/
		** sudo apt install libglib2.0-dev ** prior to installing bluepy
		.. venv/lib/python3.12/site-packages/bluepy$ sudo setcap 'cap_net_raw,cap_net_admin+eip' bluepy-helper
	A compatible BTLE Meater thermometer. 

'''

'''
*****************************************
 Imported Libraries
*****************************************
'''

import threading
import time
import logging
import struct

from probes.base import ProbeInterface
from bluepy import btle
from icecream import ic  # For debugging

class BaseMeater:
	# Handle addresses for Meater Original
	HANDLE_TEMP = 0x24
	HANDLE_BATTERY = 0x28
	HANDLE_FIRMWARE = 0x22

	def __init__(self,  peripheral, characteristic_uuid):
		self.logger = logging.getLogger("control")
		self.peripheral = peripheral
		self.__tip = None
		self.__ambient = None
		self.battery_percentage = None
		self.firmware_id = None
		self.probe_id = None
		self.device_setup = False
		self.characteristic_uuid = characteristic_uuid
		self.discovered_handle_temp = self.getHandle(self.characteristic_uuid)
		if self.discovered_handle_temp is None:
			self.discovered_handle_temp = self.HANDLE_TEMP
			logger_msg = f'(Meater) No handle found for characteristic: {self.characteristic_uuid}, using default handle: {self.discovered_handle_temp}'
			self.logger.debug(logger_msg)
			ic(logger_msg)

	def getHandle(self, uuid):
		''' Get the handle for a given characteristic UUID '''
		services = self.peripheral.getServices()
		for service in services:
			characteristics = service.getCharacteristics()
			for characteristic in characteristics:
				if characteristic.uuid == uuid:
					logger_msg = f'(Meater) Found characteristic: {characteristic.uuid} with handle: {characteristic.getHandle()}'
					self.logger.debug(logger_msg)
					ic(logger_msg)
					return characteristic.getHandle()
		return None

	def bytesToInt(self, byte0, byte1):
		return (byte1 * 256) + byte0

	def convertAmbient(self, array):
		tip = self.bytesToInt(array[0], array[1])
		ra = self.bytesToInt(array[2], array[3])
		oa = self.bytesToInt(array[4], array[5])
		return int(tip+(max(0,((((ra-min(48,oa))*16)*589))/1487)))

	def readCharacteristic(self, c):
		return bytearray(self.peripheral.readCharacteristic(c))

	def update(self):
		self._read_temperature()
		self._read_battery()
		self._read_firmware()
		self._lastUpdate = time.time()

	def _read_temperature(self):
		tempBytes = self.readCharacteristic(self.discovered_handle_temp)
		self.__tip = self.bytesToInt(tempBytes[0], tempBytes[1])
		self.__ambient = self.convertAmbient(tempBytes)

	def _read_battery(self):
		batteryBytes = self.readCharacteristic(self.HANDLE_BATTERY)
		self.battery_percentage = self.bytesToInt(batteryBytes[0], batteryBytes[1])*10

	def _read_firmware(self):
		firmware_bytes = self.readCharacteristic(self.HANDLE_FIRMWARE)
		self.firmware_id, self.probe_id = str(firmware_bytes).split("_")

	@property
	def tip(self):
		return self.__tip

	@property
	def ambient(self):
		return self.__ambient

	@property
	def probe_values_C(self):
		tip = self.getTipC()
		ambient = self.getAmbientC()
		ic(tip, ambient)
		return [tip, ambient]

	def toCelsius(self, value):
		if value is None:
			return None
		return (float(value)+8.0)/16.0

	def toFahrenheit(self, value):
		if value is None:
			return None
		return ((self.toCelsius(value)*9)/5)+32.0

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

	def address(self):
		return self.device_addr

	def id(self):
		return self.probe_id

	def firmware(self):
		return self.firmware_id

class MeaterOriginal(BaseMeater):
	def __init__(self, peripheral, characteristic_uuid):
		super().__init__(peripheral, characteristic_uuid)

class MeaterPro(BaseMeater):
	def __init__(self, peripheral, characteristic_uuid):
		super().__init__(peripheral, characteristic_uuid)
	
	def toCelsius(self, value):
		if value is None:
			return None
		if value > 0:
			return (value + 8) / 32
		if value < 0:
			return (value - 8) / 32
		return 0

	def toFahrenheitInternals(self, temps):
		"""
			Converts an array of temperatures to Fahrenheit.

			Parameters
			----------
			temps : array-like
				An array of temperatures to be converted to Fahrenheit.

			Returns
			-------
			array-like
				The array of temperatures converted to Fahrenheit.
		"""
		if temps is None:
			return None
		for i in range(len(temps)):
			temps[i] = temps[i] * 9 / 5 + 32
		return temps

	def toFahrenheitAmbient(self, temp):
		"""
			Converts a temperature in Celsius to Fahrenheit.

			Parameters
			----------
			temp : numeric
				The temperature to be converted to Fahrenheit.

			Returns
			-------
			float
				The converted temperature in Fahrenheit.
		"""
		return temp * 9 / 5 + 32

	def get_short(self, data, offset):
		"""
		Extracts a short integer from a byte array at the specified offset.

		Parameters
		----------
		data : bytes
			The byte array from which to extract the short integer.
		offset : int
			The offset within the byte array to start extraction.

		Returns
		-------
		int
			The extracted short integer.
		"""
		return struct.unpack_from("<h", data, offset)[0]	

	def ambient_correction(self, ambient_temp, internal_temp):
		"""
		Applies a correction to the internal temperature reading based on the ambient temperature.

		Parameters
		----------
		ambient_temp : int
			The ambient temperature reading.
		internal_temp : int
			The internal temperature reading to be corrected.

		Returns
		-------
		int
			The corrected internal temperature reading.
		"""
		return (int)(internal_temp + ((ambient_temp - internal_temp) * 1.2))

	def convert_to_temperatures(self, data):
		"""
		Converts a byte array of temperatures from the Meater probe into a list of Celsius temperatures.

		Parameters
		----------
		data : bytes
			The byte array of temperatures to be converted.

		Notes
		-----
		The byte array is assumed to contain 5 short integers representing the internal temperatures of the Meater probe, followed by a short integer representing the ambient temperature of the probe.

		The internal temperatures are corrected for the ambient temperature before being converted to Celsius.
		"""
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
		"""
			Returns the ambient temperature in Fahrenheit.
		"""
		return self.toFahrenheitAmbient(self.ambient_temp)
	
	def getAmbientC(self):
		"""
			Returns the ambient temperature in Celsius.
		"""
		return self.ambient_temp

	def getTips(self):
		"""
			Returns the tip temperatures(1-5) in Fahrenheit.
		"""
		return self.toFahrenheitInternals(self.internal_temps)

	def getTip(self):
		"""
			Returns the tip temperature (smallest value from tip sensors 1-5) in Fahrenheit.
		"""
		internal_temps = self.toFahrenheitInternals(self.internal_temps)
		# Return the smallest value in list internal_temps
		return min(internal_temps)

	def getTipC(self):
		"""
			Returns the tip temperature (smallest value from tip sensors 1-5) in Celsius.
		"""
		return min(self.internal_temps)

	def _read_temperature(self):
		tempBytes = self.readCharacteristic(self.discovered_handle_temp)
		self.convert_to_temperatures(tempBytes)


class Meater_Device():
	def __init__(self, port_map, primary_port, units, transient=True):
		self.logger = logging.getLogger("control")
		self.transient = transient
		self.port_map = port_map
		self.primary_port = primary_port
		self.units = units 
		self.debug = True
		self.device = None
		self.device_setup = False
		self.meater_type = None

		self.probe_values_C = []
		self.battery_percentage = None  # Battery percentage remaining on the probe
		self.hardware_id = None  # The address of the Meater Probe
		self.firmware_id = None  # The firmware version of the Meater Probe
		self.probe_id = None  # The probe ID of the Meater Probe, which should be etched on the probe (1-4)?

		self.status = {
			'battery_percentage' : self.battery_percentage,
			'battery_charging' : True if self.battery_percentage == 0 else False,
			'connected' : self.device_setup,
			'hardware_id' : self.hardware_id,
			'firmware_id' : self.firmware_id,
			'probe_id' : self.probe_id
		}

		self.sensor_thread_active = False

		self.device_thread = threading.Thread(target=self._setup_device)
		self.device_thread.start()

		self.sensor_thread = threading.Thread(target=self._sensing_loop)
		self.sensor_thread.start()

		self.meater = None  # Will hold the specific Meater instance

	def _setup_device(self):
		''' Bluetooth Meater Device Class '''
		while True:
			''' Scan for a Meater Probe '''
			if self.hardware_id is None:
				try:
					scanner = btle.Scanner()

					for entry in scanner.scan(5):
						name = entry.getValueText(9)
						logger_msg = f'(Meater) Scanned Peripheral: {name} at address {entry.addr}'
						self.logger.debug(logger_msg)
						ic(logger_msg)

						if(name is not None and 'meater+' in name.lower()):
							continue # Skip Meater+ devices as those are the base station devices and should be turned off
						elif(name is not None and 'meater' in name.lower()):
							self.hardware_id = entry.addr
							logger_msg = f'(Meater) Found a Meater Probe at address {entry.addr}'
							self.logger.debug(logger_msg)
							ic(logger_msg)
							break

				except Exception as e:
					logger_msg = f'Error setting up device: {e}'
					self.logger.error(logger_msg)
					ic(logger_msg)
					time.sleep(10)

			''' If we found the Hardware ID and it hasn't been setup, then setup the Meater Probe '''
			if self.hardware_id is not None and self.device_setup is False:
				# Connect to the Meater Probe 
				try:
					self.device = btle.Peripheral(self.hardware_id)
					logger_msg = f'(Meater) Connected to device: {self.hardware_id}'
					self.logger.debug(logger_msg)
					ic(logger_msg)

				except Exception as e:
					logger_msg = f'(Meater) Error connecting to device: {e}'
					self.logger.debug(logger_msg)
					ic(logger_msg)
					self.device_setup = False
					self.device = None
					#raise e

				try:
					# We can determine if this is a Meater Original or Meater Pro (AKA Meater 2 Plus) by the service UUID
					temp_handle = '7edda774-045e-4bbf-909b-45d1991a2876'
					services =self.device.getServices()
					for service in services:
						if service.uuid == 'c9e2746c-59f1-4e54-a0dd-e1e54555cf8b':
							self.meater_type = 'MEATER_PRO'
							self.meater = MeaterPro(self.device, temp_handle)
							self.device_setup = True
							logger_msg = f'(Meater) Meater Pro setup complete'
							self.logger.debug(logger_msg)
							ic(logger_msg)
							break
						elif service.uuid == 'a75cc7fc-c956-488f-ac2a-2dbc08b63a04':
							self.meater_type = 'MEATER_ORIGINAL'
							self.meater = MeaterOriginal(self.device, temp_handle)
							self.device_setup = True
							logger_msg = f'(Meater) Meater Original setup complete'
							self.logger.debug(logger_msg)
							ic(logger_msg)
							break
						else:
							self.meater_type = None
							self.meater = None
							self.device_setup = False
							#break
				except Exception as e:
					logger_msg = f'(Meater) Error determining meater type: {e}'
					self.logger.debug(logger_msg)
					ic(logger_msg)
			
			time.sleep(10)

	def _sensing_loop(self):
		''' Bluetooth Meater Device Class '''
		while True:
			if self.device_setup:
				self.sensor_thread_active = True
				logger_msg = f'(Meater) Sensor thread active.'
				self.logger.debug(logger_msg)
				ic(logger_msg)

				try:
					while self.sensor_thread_active:
						self.update()
						time.sleep(1)
				except Exception as e:
					logger_msg = f'(Meater) Error in sensing loop: {e}'
					self.logger.error(logger_msg)
					ic(logger_msg)
					self.sensor_thread_active = False
					self.device_setup = False
					self.hardware_id = None
					self.device = None
			time.sleep(1)

	def update(self):
		if self.meater:
			self.meater.update()
			self.probe_values_C = self.meater.probe_values_C
			self.battery_percentage = self.meater.battery_percentage()
			self.firmware_id = self.meater.firmware_id()
			self.probe_id = self.meater.probe_id()

	def get_port_values(self):
		return self.probe_values_C

	def get_status(self): 
		if self.battery_percentage is not None:
			self.status['battery_percentage'] = self.battery_percentage if (self.battery_percentage > 0 and self.device_setup) else None
			self.status['battery_charging'] = True if (self.battery_percentage == 0 and self.device_setup) else False # Reads zero when charging
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
		super().__init__(probe_info, device_info, units)
		ic(self.port_map)
		ic(self.output_data)

	def _init_device(self): 
		self.time_delay = 0
		self.device = Meater_Device(self.port_map, self.primary_port, self.units, transient=self.transient)

	def read_all_ports(self, output_data):
		port_values = {}

		probe_values_C = self.device.get_port_values()
		ic(probe_values_C) # Debugging only	

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