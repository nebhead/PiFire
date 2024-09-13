#!/usr/bin/env python3

'''
*****************************************
PiFire Probes Disabled Module 
*****************************************

Description: 
  This module is loaded in the case where the probes complex is disabled. 
	
	Ex Device Definition: 
	
	device_info = {
			'device' : 'your_device_name',	# Unique name for the device
			'module' : 'disabled',  		# Must be populated for this module to load properly
			'ports' : ['ADC0', 'RTD0', etc... ], # This should be defined by the user with the number of ports desired
			'config' : {} 
		}
'''

'''
*****************************************
 Imported Libraries
*****************************************
'''

from probes.base import ProbeInterface

'''
*****************************************
 Class Definitions 
*****************************************
'''

class ReadProbes(ProbeInterface):

	def __init__(self, probe_info, device_info, units):
		super().__init__(probe_info, device_info, units)

	def _init_device(self):
		pass

	def read_all_ports(self, output_data):
		for port in self.port_map:
			self.output_data['tr'][self.port_map[port]] = 0

			''' Get average temperature from the queue and store it in the output data structure'''
			if port == self.primary_port:
				self.output_data['primary'][self.port_map[port]] = 0
			elif port in self.food_ports:
				self.output_data['food'][self.port_map[port]] = 0
			elif port in self.aux_ports:
				self.output_data['aux'][self.port_map[port]] = 0
		
		return self.output_data
