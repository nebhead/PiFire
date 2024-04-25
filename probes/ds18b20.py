#!/usr/bin/env python3

'''
*****************************************
PiFire Probes DS18B20 Module 
*****************************************

Description: 
  This module utilizes the DS18B20 hardware and returns temperature data.
	Depends on: pip install w1thermsensor

	Note: Still experimental.  Expects this device to be connected to GPIO 6 (Pin 31)
	  Edit /boot/config.txt to add: 
	  	dtoverlay=w1-gpio,gpiopin=6,pullup="y"
	  
	Ex Device Definition: 
	
	device = {
			'device' : 'your_device_name',	# Unique name for the device
			'module' : 'ds18b20',  # Must be populated for this module to load properly
			'ports' : ['DS0'],    			# This is defined in the module, so this does not need to be defined.
			'config' : {} 
		}

'''

'''
*****************************************
 Imported Libraries
*****************************************
'''
import logging 
import time
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
		try:
			self.init_device()
			self.check_availability()
		except:
			''' Device is unavailable for some reason '''
			self.logger.info('DS18B20 device wasn\'t initialized because it was not found.')
			pass 

	def init_device(self):	
		self.sensor = W1ThermSensor()

	def check_availability(self):
		for sensor in self.sensor.get_available_sensors([Sensor.DS18B20]):
			self.available = True 
		return self.available

	@property
	def temperature(self):
		return self.sensor.get_temperature()

class ReadProbes(ProbeInterface):

	def __init__(self, probe_info, device_info, units):
		super().__init__(probe_info, device_info, units)
		self.logger = logging.getLogger("control")

	def _init_device(self):
		self.time_delay = 0
		self.device_info['ports'] = ['DS0']
		try:
			self.device = DS18B20_Device()
		except:
			self.logger.error('Something went wrong when trying to initialize the DS18B20 device.')

	def read_all_ports(self, output_data):
		''' Check availability '''
		if self.device.check_availability():
			''' Read temperature from device '''
			tempC = round(self.device.temperature, 1)
			tempF = int(tempC * (9/5) + 32) # Celsius to Fahrenheit
		else: 
			''' Device not available '''
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