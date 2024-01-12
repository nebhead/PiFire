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
from w1thermsensor import W1ThermSensor, Unit
from probes.base import ProbeInterface
import RPi.GPIO as GPIO

'''
*****************************************
 Class Definitions 
*****************************************
'''

class DS18B20_Device():
	''' DS18B20 Device Utilizing the w1thermsensor module '''
	def __init__(self):
		self.logger = logging.getLogger("control")
		# Setup software pull-up which will wake the device connected
		GPIO.setmode(GPIO.BCM)
		GPIO.setup(6, GPIO.IN, pull_up_down=GPIO.PUD_UP)

		time.sleep(4)  # Give time for the kernel to connect to the 1-wire bus and get the device IDs
		self.sensor = W1ThermSensor()

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
			raise

	def read_all_ports(self, output_data):
		''' Read temperature from device '''
		tempC = round(self.device.temperature, 1)
		tempF = int(tempC * (9/5) + 32) # Celsius to Fahrenheit
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