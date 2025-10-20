#!/usr/bin/env python3

'''
*****************************************
 PiFire PID Controller Base Class
*****************************************

 Description: Base class for the controller.  Inherited by all controller
 modules in this package.  

*****************************************
'''

'''
Imported Libraries
'''
import time

'''
Class Definition
'''

class ControllerBase:
	def __init__(self, config, units, cycle_data):
		self.config = config
		self.units = units
		self.cycle_data = cycle_data
		self.function_list = [
			'update', 
	        'set_target', 
	        'get_config',
			'set_config',
			'set_cycle_data', 
			'set_units'	
        ]

	def update(self, current):
		'''
		Input:
	        current :: Current temperature
	    Output:
            cycle_ratio(u) :: Raw Cycle Ratio
	    '''
		return 0.0

	def set_target(self, set_point):
		'''
		Input:
	        set_point :: Temperature Target
	    '''
		self.set_point = set_point
		self.last_update = time.time()
	
	def get_config(self):
		return self.config
	
	def set_config(self, config):
		'''
		Input:
	        config :: Configuration Dictionary
	    '''
		self.config = config

	def set_cycle_data(self, cycle_data):
		'''
		Input:
	        cycle_data :: Cycle Data Dictionary
	    '''
		self.cycle_data = cycle_data

	def set_units(self, units):
		'''
		Input:
	        units :: Units Dictionary
	    '''
		self.units = units

	def supported_functions(self):
		return self.function_list