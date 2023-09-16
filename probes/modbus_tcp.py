#!/usr/bin/env python3

'''
*****************************************
PiFire Probes Modbus TCP Module 
*****************************************

Description: 
  This module reads data from a Modbus TCP device and returns temperature data.
	
	Ex Device Definition: 
	
	device = {
			'device' : 'your_device_name',	# Unique name for the device
			'module' : 'modbus_tcp',  		# Must be populated for this module to load properly
			'ports' : ['register1'], 		# This should be defined by the user with the number of ports desired
			'config' : {} 
				# need to add modbus config parameters here.
		}

	Note: This modbus_tcp module reads the temperature of a modbus device directly and does not use the probe profiles.  


'''

'''
*****************************************
 Imported Libraries
*****************************************
'''

from probes.base import ProbeInterface
from pymodbus.client import ModbusTcpClient

'''
*****************************************
 Class Definitions 
*****************************************
'''

class ReadProbes(ProbeInterface):

	def __init__(self, probe_info, device_info, units):
		super().__init__(probe_info, device_info, units)
		self.client = ModbusTcpClient('10.10.10.50')
		
		

	def read_all_ports(self, output_data):
		for port in self.port_map:
			try:
				self.client.connect()
				self.result = self.client.read_holding_registers(100, 4, 1)
				self.output_data['primary'][self.port_map[port]] = self.result.registers[0]/10
				# self.output_data['primary'][self.port_map[port]] = self.client.read_holding_registers(100, 1, unit=1)/10
				''' Set Tr value to 0 since we are averaging temperature outputs '''
				self.output_data['tr'][self.port_map[port]] = 0
				self.client.close()
			except:
				print("Modbus Probe exception occured.")
		return self.output_data