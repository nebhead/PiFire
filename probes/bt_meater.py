'''
*****************************************
PiFire Bluetooth Meater Module 
*****************************************

Description: 
  This module connects to the Meater BTLE thermometer via bluetooth and returns temperature data.

  	Ex Device Definition: 
	
	device_info = {
			'device' : 'your_device_name',	# Unique name for the device
			'module' : 'bt_meater',  		# Must be populated for this module to load properly
			'ports' : ['BT0'],  			# Currently only tip temperature from one probe is supported.   
			'config' : {
				'transient' : True
			} 
		}

	''

Credits:
    Contributors:
        - Nathan Faber
        - Eric Thomas
        - Tim O'Brien

Requirements:
	The simplepyble python module.
    A compatible Meater thermometer. 
'''

'''
*****************************************
 Imported Libraries
*****************************************
'''
import simplepyble
import threading
import time
import logging
import struct

from probes.base import ProbeInterface
from icecream import ic  # For debugging

'''
*****************************************
 Class Definitions 
*****************************************
'''
class Meater:
	def __init__(self, peripheral, scan_time=5000):
		"""
		Initialize the Meater class.

		Parameters
		----------
		scan_time : int, optional
			Time in milliseconds to scan for the Meater probe. Defaults to 5000.
		"""
		self.logger = logging.getLogger("control")
		self.is_connected = False
		self.scan_time = scan_time
		self.peripheral = peripheral
		self.data = None

	def toCelsius(self, value):
		"""
			Converts a given value to Celsius.

			Parameters
			----------
			value : numeric
				The value to be converted to Celsius.

			Returns
			-------
			float
				The converted temperature in Celsius.
		"""
		return (float(value) + 8.0) / 16.0

	def toFahrenheit(self, value):
		"""
			Converts a given value to Fahrenheit.

			Parameters
			----------
			value : numeric
				The value to be converted to Fahrenheit.

			Returns
			-------
			float
				The converted temperature in Fahrenheit.
		"""
		return ((self.toCelsius(value) * 9) / 5) + 32.0

	def bytesToInt(self, byte0, byte1):
		"""
		Converts a byte string to an integer.

		Parameters
		----------
		byte0 : int
			The first byte of the byte string.
		byte1 : int
			The second byte of the byte string.

		Returns
		-------
		int
			The converted integer.
		"""
		return byte1 * 256 + byte0

	def convertAmbient(self, array):
		"""
			Converts an array of bytes to an integer.

			Parameters
			----------
			array : array
				The array of bytes to be converted.

			Returns
			-------
			int
				The converted integer.
		"""
		tip = self.bytesToInt(array[0], array[1])
		ra = self.bytesToInt(array[2], array[3])
		oa = self.bytesToInt(array[4], array[5])
		return int(tip + (max(0, ((((ra - min(48, oa)) * 16) * 589)) / 1487)))

	def getAmbient(self):
		"""
			Returns the ambient temperature in Fahrenheit.
		"""
		ambientTemp = self.convertAmbient(self.data)
		return self.toFahrenheit(ambientTemp)

	def getAmbientC(self):
		"""
			Returns the ambient temperature in Fahrenheit.
		"""
		ambientTemp = self.convertAmbient(self.data)
		return self.toCelsius(ambientTemp)

	def getTip(self):
		"""
		Returns the tip temperature in Fahrenheit.
		"""
		if self.data is None:
			return None
		tipTemp = self.bytesToInt(self.data[0], self.data[1])
		return self.toFahrenheit(tipTemp)

	def getTipC(self):
		"""
		Returns the tip temperature in Celsius.
		"""
		if self.data is None:
			return None
		tipTemp = self.bytesToInt(self.data[0], self.data[1])
		return self.toCelsius(tipTemp)

	def printTemps(self):
		"""
			Prints the ambient and tip temperatures.
		"""
		event = f"Ambient: {self.getAmbient()} \N{DEGREE SIGN}F Tip: {self.getTip()} \N{DEGREE SIGN}F"
		ic(event)
		self.logger.debug(event)

	def disconnect(self):
		"""
		Disconnects from the Meater probe.
		"""
		self.peripheral.disconnect()
		self.is_connected = False

	def notification_handler(self, data):
		"""
			This is a callback function that is called whenever a notification is received from the Meater probe.
			It is responsible for storing the received data and printing it to the console.
		"""
		self.data = data
		#self.printTemps()

	def getTemps(self):
		"""
			Returns the ambient and tip temperatures.
		"""
		return self.getAmbient(), self.getTip()

	def subscribe_to_temps(self):
		"""
		Subscribes to notifications from the Meater probe to receive temperature data.

		This method registers a callback function to handle temperature data notifications
		from the Meater probe. It listens to specific characteristic UUIDs for temperature 
		data updates. If there is an error during the subscription process, an error message 
		is printed.
		
		char uuids:
			a75cc7fc-c956-488f-ac2a-2dbc08b63a04
			7edda774-045e-4bbf-909b-45d1991a2876

		Note:
			Ensure that the peripheral is connected before calling this method.
		"""        
		
		try:
			contents = self.peripheral.notify(
				"a75cc7fc-c956-488f-ac2a-2dbc08b63a04",
				"7edda774-045e-4bbf-909b-45d1991a2876",
				lambda data: self.notification_handler(data),
			)
			
		except Exception as e:
			#ic(f"Notify Attempt failed: {e}")
			self.logger.debug(f"Notify Attempt failed: {e}")

class Meater_Pro:
	def __init__(self, peripheral, scan_time=5000):
		"""
		Initialize the Meater class.

		Parameters
		----------
		scan_time : int, optional
			Time in milliseconds to scan for the Meater probe. Defaults to 5000.
		"""
		self.logger = logging.getLogger("control")
		self.is_connected = False
		self.scan_time = scan_time
		self.peripheral = peripheral
		self.internal_temps = None
		self.ambient_temp = None
		self.data = None

	def toCelsius(self, value):
		"""
			Converts a given value to Celsius.

			Parameters
			----------
			value : numeric
				The value to be converted to Celsius.

			Returns
			-------
			float
				The converted temperature in Celsius.
		"""
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

	def printTemps(self):
		"""
			Prints the ambient and tip temperatures.
		"""
		logger_msg = f'Ambient: {self.getAmbient()} \N{DEGREE SIGN}F Tip Sensors(1-5): {self.getTips()}'
		self.logger.debug(logger_msg)	
		#ic(logger_msg)

	def disconnect(self):
		"""
			Disconnects from the Meater probe.
		"""
		self.peripheral.disconnect()
		self.is_connected = False

	def notification_handler(self, data):
		"""
			This is a callback function that is called whenever a notification is received from the Meater probe.
			It is responsible for storing the received data and printing it to the console.
		"""

		self.data = data
		self.convert_to_temperatures(self.data)
		#self.printTemps()

	def subscribe_to_temps(self):
		"""
		Subscribes to notifications from the Meater probe to receive temperature data.

		This method registers a callback function to handle temperature data notifications
		from the Meater probe. It listens to specific characteristic UUIDs for temperature 
		data updates. If there is an error during the subscription process, an error message 
		is printed.

		char uuids:
			c9e2746c-59f1-4e54-a0dd-e1e54555cf8b,
			7edda774-045e-4bbf-909b-45d1991a2876

		Note:
			Ensure that the peripheral is connected before calling this method.
		"""

		try:
			contents = self.peripheral.notify(
				"c9e2746c-59f1-4e54-a0dd-e1e54555cf8b",
				"7edda774-045e-4bbf-909b-45d1991a2876",
				lambda data: self.notification_handler(data),
			)
		except Exception as e:
			logger_msg = f"Notify Attempt failed: {e}"
			self.logger.debug(logger_msg)
			#ic(f"Notify Attempt failed: {e}")


class MeaterProbeHandler():
	def __init__(self):
		self.peripheral = None
		self.logger = logging.getLogger("control")

	def connect(self, connectedAddresses):
		"""
		Connects to the Meater probe.

		Returns
		-------
		int
			peripheral address on success, -1 on failure.
		"""
		# Get a list of adapters
		adapters = simplepyble.Adapter.get_adapters()

		# If there are no adapters found then exit
		if len(adapters) == 0:
			#ic("No BTLE adapters found")
			self.logger.debug("No BTLE adapters found")
			return -1

		adapter = adapters[0]
		adapter.set_callback_on_scan_start(lambda: self.logger.debug("Scan started."))
		adapter.set_callback_on_scan_stop(lambda: self.logger.debug("Scan complete."))

		# Scan for 5 seconds
		adapter.scan_for(5000)
		peripherals = adapter.scan_get_results()

		for choice in range(len(peripherals)):
			self.peripheral = peripherals[choice]
			try:
				if "meater" in self.peripheral.identifier().lower() and self.peripheral.address() not in connectedAddresses:
					self.peripheral.connect()
					#ic("Connected to peripheral " + self.peripheral.identifier())
					logger_msg = f"Connected to peripheral {self.peripheral.identifier()}"
					self.logger.debug(logger_msg)
					self.is_connected = True
					return self.peripheral.address()

			except:
				#ic("Failed to connect to probe ")
				logger_msg = f"Failed to connect to probe {self.peripheral.identifier()}"
				self.logger.debug(logger_msg)
				pass
		logger_msg = "Meater probe not found"
		self.logger.debug(logger_msg)
		#ic(logger_msg)
        
	def checkProperties(self):
		logger_msg = "Successfully connected to " + self.peripheral.identifier()
		self.logger.debug(logger_msg)
		#ic(logger_msg)
		services = self.peripheral.services()
		
		if 'c9e2746c-59f1-4e54-a0dd-e1e54555cf8b' in [s.uuid() for s in services]:
			return Meater_Pro(self.peripheral)
		elif 'a75cc7fc-c956-488f-ac2a-2dbc08b63a04' in [s.uuid() for s in services]:
			return Meater(self.peripheral)
		else:
			return None
		
class Meater_Device():
	def __init__(self, port_map, primary_port, units, transient=True):
		self.logger = logging.getLogger("control")
		self.transient = transient
		self.port_map = port_map
		self.primary_port = primary_port
		self.probe_values_F = []
		self.units = units 
		self.debug = True
		self.device_ready = False

		self.port_values = []
	
		self.address = None
		self.device_setup = False
		self.sensor_thread_active = False

		self.device_thread = threading.Thread(target=self._setup_device)
		self.device_thread.start()

		self.sensor_thread = threading.Thread(target=self._sensing_loop)
		self.sensor_thread.start()
	
	def _setup_device(self):
		while True:
			connectedAddresses = []
			if self.address == None:
				try:
					self.probeHandler = MeaterProbeHandler()
					self.address = self.probeHandler.connect(connectedAddresses)
					connectedAddresses.append(self.address)
				except:
					self.address = None
					logger_msg = f'Failed to connect to Meater probe.'
					self.logger.debug(logger_msg)
					#ic(logger_msg)

			if self.address != None and self.device_setup == False:
				#ic("Setting up Meater device thread active")
				try:
					''' Setup Meater Device Here '''
					self.probe = self.probeHandler.checkProperties()
					self.probe.subscribe_to_temps()
					self.device_setup = True
					logger_msg = f'Meater device setup complete.'
					self.logger.debug(logger_msg)
					#ic(logger_msg)
				except:
					logger_msg = f'Failed to setup Meater device.'
					self.logger.debug(logger_msg)
					#ic(logger_msg)
					self.device_setup = False
					self.address = None

			time.sleep(10)

	def _sensing_loop(self):
		#logger_msg = f'Starting Meater sensor loop'
		#self.logger.debug(logger_msg)
		#ic(logger_msg)
		while True:
			if self.device_setup:
				self.sensor_thread_active = True
				#logger_msg = f"Sensor Loop Active!"
				#self.logger.debug(logger_msg)
				#ic(logger_msg)
				try:
					while self.sensor_thread_active:
						time.sleep(0.5)
						self.probe_values_F = [self.probe.getTip()] # Temporarily get temp in F
						#logger_msg = f'Probe Values (sensing loop): {self.probe_values_F}'
						#self.logger.debug(logger_msg)
						#ic(logger_msg)

				except:
					logger_msg = f'Meater device has gone away...'
					self.logger.debug(logger_msg)
					#ic(logger_msg)
					# Clean up
					self.sensor_thread_active = False
					self.device_setup = False
					self.hardware_id = None
					self.probe_values_F = []
			else:
				time.sleep(1)

	def get_port_values(self):
		if len(self.probe_values_F) > 0:
			return self.probe_values_F
		else:
			return None
			
class ReadProbes(ProbeInterface):
	def __init__(self, probe_info, device_info, units):
		super().__init__(probe_info, device_info, units)
		#ic(self.port_map)
		#ic(self.output_data)

	def _init_device(self):
		self.time_delay = 0
		self.device = Meater_Device(self.port_map, self.primary_port, self.units, transient=self.transient)

	def read_all_ports(self, output_data):
		port_values = {}

		probe_values_F = self.device.get_port_values()
		#ic(probe_values_F) # Debugging only	
		#logger_msg = f'Probe Values (read_all_ports): {probe_values_F}'
		#self.logger.debug(logger_msg)

		if probe_values_F == None:
			probe_values_F = []
			for _ in range(len(self.port_map)):
				probe_values_F.append(None)
		if len(probe_values_F) >= len(self.port_map):
			for index, port in enumerate(self.port_map):
				''' Read Ports from Device '''
				port_values[port] = int(probe_values_F[index]) if self.units == 'F' else self._to_celsius(probe_values_F[index]) 
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