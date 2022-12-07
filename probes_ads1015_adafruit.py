#!/usr/bin/env python3

'''
*****************************************
PiFire Probes ADS1015 Adafruit Module 
*****************************************

Description: 
  This module utilizes the adafruit ADS1015 hardware and returns temperature data.
	
	Ex Device Definition: 
	
	device = {
			'device' : 'your_device_name',	# Unique name for the device
			'module' : 'ads1015_adafruit',	# Must be populated for this module to load properly
			'ports' : ['ADC0', 'ADC1', 'ADC2', 'ADC3'], # This is defined in the module, so this does not need to be defined.
			'config' : {} 
		}
'''

'''
*****************************************
 Imported Libraries
*****************************************
'''
import math
import board
import busio
import adafruit_ads1x15.ads1015 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from probes_base import ProbeInterface

'''
*****************************************
 Class Definitions 
*****************************************
'''

class ADSDevice():
	''' ADS1115 Device Based on the Adafruit Module '''
	def __init__(self):
		# Create the I2C bus
		self.i2c = busio.I2C(board.SCL, board.SDA)
		# Create the ADC object using the I2C bus
		self.ads = ADS.ADS1015(self.i2c)

	def read_voltage(self, port):
		adc_ports = {
			'ADC0' : ADS.P0, 
			'ADC1' : ADS.P1, 
			'ADC2' : ADS.P2, 
			'ADC3' : ADS.P3
		}
		read_data = AnalogIn(self.ads, adc_ports[port])
		voltage = math.floor(read_data.voltage * 1000)
		return voltage

class ReadProbes(ProbeInterface):

	def __init__(self, probe_info, device_info, units):
		super().__init__(probe_info, device_info, units)

	def _init_device(self):
		self.time_delay = 0
		self.device_info['ports'] = ['ADC0', 'ADC1', 'ADC2', 'ADC3']
		self.device = ADSDevice()