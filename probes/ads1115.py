#!/usr/bin/env python3

'''
*****************************************
PiFire Probes ADS1115 Module 
*****************************************

Description: 
  This module utilizes the ADS1115 hardware and returns temperature data.
	
	Ex Device Definition: 
	
	device = {
			'device' : 'your_device_name',	# Unique name for the device
			'module' : 'ads1115',  			# Must be populated for this module to load properly
			'ports' : ['ADC0', 'ADC1', 'ADC2', 'ADC3'], # This is defined in the module, so this does not need to be defined.
			'config' : {
				'i2c_bus_addr' : '0x48'
			} 
		}
'''

'''
*****************************************
 Imported Libraries
*****************************************
'''
import logging
import math
import ADS1115
from probes.base import ProbeInterface

'''
*****************************************
 Class Definitions 
*****************************************
'''

BUSMAP = {
	'0x48' : 0x48,  # Address Pin GND
	'0x49' : 0x49,  # Address Pin VIN 
	'0x4A' : 0x4A,	# Address Pin SDA
	'0x4B' : 0x4B	# Address Pin SCL
}

class ADSDevice():
	''' ADS1115 Device Based on the ADS1115 Python Module '''
	def __init__(self, i2c_bus_addr=0x48):
		self.logger = logging.getLogger("control")
		self.ads = ADS1115.ADS1115(address=i2c_bus_addr)

	def read_voltage(self, port):
		adc_ports = {
			'ADC0' : 0, 
			'ADC1' : 1, 
			'ADC2' : 2, 
			'ADC3' : 3
		}
		try:
			voltage = self.ads.readADCSingleEnded(adc_ports[port])
		except: 
			self.logger.exception(f'Exception occurred while reading probe port {port}.  Trace dump: ')
			voltage = 0
		return voltage

class ReadProbes(ProbeInterface):

	def __init__(self, probe_info, device_info, units):
		super().__init__(probe_info, device_info, units)

	def _init_device(self):
		self.time_delay = 0.008
		self.device_info['ports'] = ['ADC0', 'ADC1', 'ADC2', 'ADC3']
		i2c_bus_addr = BUSMAP[self.device_info['config'].get('i2c_bus_addr', '0x48')]
		self.device = ADSDevice(i2c_bus_addr=i2c_bus_addr)