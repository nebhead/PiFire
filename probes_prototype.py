#!/usr/bin/env python3

'''
*****************************************
PiFire Probes Prototype Module 
*****************************************

Description: 
  This module simulates an ADC/RTD Device and returns temperature data.

'''

'''
*****************************************
 Imported Libraries
*****************************************
'''

import random
from probes_base import ProbeInterface

'''
*****************************************
 Class Definitions 
*****************************************
'''

class ProtoDevice():
	''' Create a test devices that returns values for testing '''
	def __init__(self, port_map, primary_port, units):
		self.port_value = {}
		self.primary_port = primary_port
		self.units = units 
		''' Set initial voltages 
			Primary Probe Voltages based on the PT-1000-Grill-Probe-OEM profile 
			Other Probe Voltages based on the Thermoworks-Pro-Series-HeaterMeter profile		
		'''
		for port in port_map:
			if port == self.primary_port:
				self.port_value[port] = 316
			else: 
				self.port_value[port] = 3000

		self.maxPrimaryVoltage = 550
		self.minPrimaryVoltage = 300
		self.maxFoodVoltage = 1300
		self.minFoodVoltage = 3200
		self.primaryChangeFactor = 2
		self.otherChangeFactor = 10

	def read_voltage(self, port):
		seed = random.randint(0,9)
		if port == self.primary_port:
			if seed > 7 and self.port_value[port] < self.maxPrimaryVoltage:
				self.port_value[port] += self.primaryChangeFactor
			elif seed < 1 and self.port_value[port] > self.minPrimaryVoltage:
				self.port_value[port] -= self.primaryChangeFactor
		else:
			if seed > 7 and self.port_value[port] > self.maxFoodVoltage:
				self.port_value[port] -= self.otherChangeFactor
			elif seed < 1 and self.port_value[port] < self.minFoodVoltage:
				self.port_value[port] += self.otherChangeFactor

		return self.port_value[port]

class ReadProbes(ProbeInterface):

	def __init__(self, probe_info, device_info, units):
		super().__init__(probe_info, device_info, units)

	def _init_device(self):
		self.time_delay = 0
		self.device = ProtoDevice(self.port_map, self.primary_port, self.units)
