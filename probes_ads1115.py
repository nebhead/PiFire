#!/usr/bin/env python3

'''
*****************************************
PiFire Probes ADS1115 Module 
*****************************************

Description: 
  This module utilizes the ADS1115 hardware and returns temperature data.

'''

'''
*****************************************
 Imported Libraries
*****************************************
'''
import math
import ADS1115
from probes_base import ProbeInterface

'''
*****************************************
 Class Definitions 
*****************************************
'''

class ADSDevice():
	''' ADS1115 Device Based on the Adafruit Module '''
	def __init__(self):
		self.ads = ADS1115.ADS1115()

	def read_voltage(self, port):
		adc_ports = {
			'ADC0' : 0, 
			'ADC1' : 1, 
			'ADC2' : 2, 
			'ADC3' : 3
		}
		voltage = self.ads.readADCSingleEnded(adc_ports[port])
		return voltage

class ReadProbes(ProbeInterface):

	def __init__(self, probe_info, device_info, units):
		super().__init__(probe_info, device_info, units)

	def _init_device(self):
		self.time_delay = 0
		self.device_info['ports'] = ['ADC0', 'ADC1', 'ADC2', 'ADC3']
		self.device = ADSDevice()