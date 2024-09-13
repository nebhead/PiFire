#!/usr/bin/env python3

'''
*****************************************
PiFire Probes DS18B20 Module 
*****************************************

Description: 
  This module utilizes the DS18B20 hardware and returns temperature data.
	Depends on: pip install w1thermsensor
	Details on this module can be found here: https://github.com/timofurrer/w1thermsensor 

	Note: This device is not recommended (currently) for anything other than a reference probe.  Thus, the recommendation
		is to utilize this probe for calibrating / tuning probe profiles only. PiFire will operate best if it is added to 
		the configuration only when needed to do calibration, then removed from the configuration during normal usage.  
		This prevents the probe from being queried every time the temperature is read from other devices.  However, if it is 
		left enabled, the probe can be hot-plugged and should read temperatures when attached and initialized by the kernel.  
		Set this probe to AUX in the configuration wizard so that it does not appear in the user interface.  
	
	Note: Expects this device to be connected to a specific GPIO Pin defined in config.txt, 
		should be pulled up through a physical 4.7-10k pull-up to 3.3V.  Removed the passive pull-up 
		code from this version going forward.  

	  Edit /boot/config.txt (or /boot/firmware/config.txt) to add: 
	  	dtoverlay=w1-gpio,gpiopin=[pin_number]

		(This is automatically added by the configuration wizard / board configuration tool)

	Ex Device Definition: 
	
	device_info = {
			'device' : 'your_device_name',	# Unique name for the device
			'module' : 'ds18b20',  # Must be populated for this module to load properly
			'ports' : ['DS0'],    			# This is defined in the module, so this does not need to be defined.
			'config' : {
				'transient' = 'True'
			}
		}

'''

'''
*****************************************
 Imported Libraries
*****************************************
'''
import logging 
import time
import threading
from w1thermsensor import W1ThermSensor, Unit, Sensor 
from probes.base import ProbeInterface

'''
*****************************************
 Class Definitions 
*****************************************
'''

class DS18B20_Device():
	''' DS18B20 Device Utilizing the w1thermsensor module '''
	def __init__(self):
		self.logger = logging.getLogger("control")
		self.available = False
		self.initialized = False
		self.temperature_C = None

		try:
			self.init_device()
		except:
			''' Device is unavailable for some reason '''
			self.logger.info('DS18B20 device wasn\'t initialized because it was not found.')
		
		# Setup & Start Sensor Loop Thread
		self.sensor_thread_active = True 
		self.sensor_thread_update = True  # Get initial temperature from sensor 
		self.sensor_thread = threading.Thread(target=self._sensing_loop)
		self.sensor_thread.start()

	def init_device(self):	
		try:
			self.sensor = W1ThermSensor()
			self.available = True
			self.initialized = True
		except:
			self.available = False
			self.initialized = False 

	def check_availability(self):
		try:
			if not self.initialized:
				self.init_device()
			for sensor in self.sensor.get_available_sensors([Sensor.DS18B20]):
				self.available = True
		except:
			self.available = False 
		return self.available

	def _sensing_loop(self):
		while self.sensor_thread_active:
			if self.sensor_thread_update:
				try:
					if not self.initialized:
						self.init_device()
					else:
						self.temperature_C = self.sensor.get_temperature()
				except:
					self.temperature_C = None
					self.available = False
				
				self.sensor_thread_update = False 
			time.sleep(0.1)

	@property
	def temperature(self):
		self.sensor_thread_update = True
		return self.temperature_C

class ReadProbes(ProbeInterface):

	def __init__(self, probe_info, device_info, units):
		super().__init__(probe_info, device_info, units)
		self.logger = logging.getLogger("control")

	def _init_device(self):
		self.time_delay = 0
		self.device_info['ports'] = ['DS0']
		self.device = DS18B20_Device()

	def read_all_ports(self, output_data):
		''' Read temperature from device '''
		tempC = self.device.temperature
		if tempC is not None:
			tempC = round(tempC, 1)
			tempF = int(tempC * (9/5) + 32) # Celsius to Fahrenheit
		else:
			tempC = None
			tempF = None
		port = self.device_info['ports'][0]

		''' Read resistance from device '''
		self.output_data['tr'][self.port_map[port]] = 0  # resistance NA

		''' Get average temperature from the queue and store it in the output data structure'''
		if port == self.primary_port:
			self.output_data['primary'][self.port_map[port]] = tempF if self.units == 'F' else tempC
		elif port in self.food_ports:
			self.output_data['food'][self.port_map[port]] = tempF if self.units == 'F' else tempC
		elif port in self.aux_ports:
			self.output_data['aux'][self.port_map[port]] = tempF if self.units == 'F' else tempC
		
		return self.output_data