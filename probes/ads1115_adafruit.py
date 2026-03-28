#!/usr/bin/env python3

'''
*****************************************
PiFire Probes ADS1115 Adafruit Module 
*****************************************

Description: 
  This module utilizes the adafruit ADS1115 hardware and returns temperature data.
	
	Ex Device Definition: 
	
	device = {
			'device' : 'your_device_name',	# Unique name for the device
			'module' : 'ads1115_adafruit',	# Must be populated for this module to load properly
			'ports' : ['ADC0', 'ADC1', 'ADC2', 'ADC3'], # This is defined in the module, so this does not need to be defined.
			'config' : {
				'ADC0_rd': '10000',
            	'ADC1_rd': '10000',
            	'ADC2_rd': '10000',
            	'ADC3_rd': '10000',
            	'i2c_bus_addr': '0x48',
            	'voltage_ref': '3.28'
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
import board
import busio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
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
	''' ADS1115 Device Based on the Adafruit Module '''
	def __init__(self, i2c_bus_addr=0x48):
		self.logger = logging.getLogger("control")
		# Create the I2C bus
		self.i2c = busio.I2C(board.SCL, board.SDA)
		# Create the ADC object using the I2C bus
		self.ads = ADS.ADS1115(self.i2c, address=i2c_bus_addr)
		self.status = {}
		self._error_count = 0
		self._error_reported = False

	def read_voltage(self, port):
		adc_ports = {
			'ADC0' : ADS.P0,
			'ADC1' : ADS.P1,
			'ADC2' : ADS.P2,
			'ADC3' : ADS.P3
		}
		try:
			read_data = AnalogIn(self.ads, adc_ports[port])
			voltage = math.floor(read_data.voltage * 1000)
			if self._error_count > 0:
				self._error_count = 0
				self._error_reported = False
				self.logger.info(f'ADS1115 I2C communication recovered on port {port}.')
		except Exception as e:
			self.logger.exception(f'Exception occurred while reading probe port {port}.  Trace dump: ')
			self._error_count += 1
			if not self._error_reported:
				self._error_reported = True
				self.status['error'] = f'I2C communication error on ADS1115 (port {port}): {type(e).__name__}. ' \
					f'Probe readings may be unavailable. Check wiring and connections.'
			voltage = 0
		return voltage

	def get_status(self):
		return self.status

class ReadProbes(ProbeInterface):

	def __init__(self, probe_info, device_info, units):
		super().__init__(probe_info, device_info, units)

	def _init_device(self):
		self.time_delay = 0.008
		self.device_info['ports'] = ['ADC0', 'ADC1', 'ADC2', 'ADC3']
		i2c_bus_addr = BUSMAP[self.device_info['config'].get('i2c_bus_addr', '0x48')]
		self.device = ADSDevice(i2c_bus_addr=i2c_bus_addr)