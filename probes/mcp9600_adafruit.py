#!/usr/bin/env python3

'''
*****************************************
PiFire Probes MCP9600 Adafruit Module 
*****************************************

Description: 
  This module utilizes the MCP9600 hardware and returns temperature data.
	Depends on: pip3 install adafruit-circuitpython-mcp9600 

	Ex Device Definition: 
	
	device = {
			'device' : 'your_device_name',	# Unique name for the device
			'module' : 'mcp9600_adafruit',  # Must be populated for this module to load properly
			'ports' : ['KTT0'],    			# This is defined in the module, so this does not need to be defined.
			'config' : {
				'i2c_bus_addr' : '0x67'		# I2C Bus Address
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
import board
import busio
from adafruit_bus_device.i2c_device import I2CDevice
from adafruit_mcp9600 import MCP9600
from probes.base import ProbeInterface

BUSMAP = {
	'0x67' : 0x67,  # Default
	'0x66' : 0x66,  # J1 Closed
	'0x65' : 0x65,	# J2 Closed
	'0x64' : 0x64,	# J1 & J2 Closed
	'0x60' : 0x60	# ADDR to GND 
}


'''
*****************************************
 Class Definitions 
*****************************************
'''

class KTTDevice():
	''' MCP9600 Device Based on the Adafruit Module '''
	def __init__(self, i2c_bus_addr=0x67):
		self.logger = logging.getLogger("control")

		# Create the I2C bus
		self.i2c = busio.I2C(board.SCL, board.SDA)

		self.sensor = MCP9600(self.i2c)

	@property
	def temperature(self):
		return self.sensor.temperature

class ReadProbes(ProbeInterface):

	def __init__(self, probe_info, device_info, units):
		super().__init__(probe_info, device_info, units)

	def _init_device(self):
		self.time_delay = 0
		self.device_info['ports'] = ['KTT0']
		i2c_bus_addr = BUSMAP[self.device_info['config'].get('i2c_bus_addr', '0x48')]
		self.device = KTTDevice(i2c_bus_addr=i2c_bus_addr)

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