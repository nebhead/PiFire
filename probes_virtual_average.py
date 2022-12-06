#!/usr/bin/env python3

'''
*****************************************
PiFire Probes Virtual Probe Averaging Module 
*****************************************

Description: 
  This module simulates an ADC/RTD Device and returns temperature data.

'''

'''
*****************************************
 Imported Libraries
*****************************************
'''

from probes_base import ProbeInterface

'''
*****************************************
 Class Definitions 
*****************************************
'''

class ReadProbes(ProbeInterface):

	def __init__(self, probe_info, device_info, units):
		super().__init__(probe_info, device_info, units)
	
	def read_all_ports(self, output_data):
		''' Find the probes to average '''
		for port in self.port_map:
			count = 0
			accumulator = 0
			for probe in self.device_info['config']['avg_probes'][port]:
				if probe in output_data['primary']:
					count += 1
					accumulator += output_data['primary'][probe]
				elif probe in output_data['food']:
					count += 1
					accumulator += output_data['food'][probe]
				elif probe in output_data['aux']:
					count += 1
					accumulator += output_data['aux'][probe]
			
			''' Get average temperature and store it in the output data structure'''
			if port == self.primary_port:
				self.output_data['primary'][self.port_map[port]] = accumulator / count
			elif port in self.food_ports:
				self.output_data['food'][self.port_map[port]] = accumulator / count
			elif port in self.aux_ports:
				self.output_data['aux'][self.port_map[port]] = accumulator / count
			
			''' Set Tr value to 0 since we are averaging temperature outputs '''
			self.output_data['tr'][self.port_map[port]] = 0

		return self.output_data

