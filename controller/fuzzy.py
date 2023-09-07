#!/usr/bin/env python3

'''
*****************************************
 PiFire Fuzzy Logic Controller
*****************************************

 Description: This object will be used to calculate cycle ratio for maintaining
 temperature in the grill.

 This Fuzzy Logic Controller is based off of the work of Sci-Kit Fuzzy's implementation. 
 Due to the computational limitations of the Raspberry Pi Zero (or others), the first run 
 of this module will setup the controller object, which will then be stored in a pickled 
 file.  This way, the fuzzy controller does not need to be recalculated every time the 
 object is instantiated.  

 To Install Dependencies in Raspbian: 
   sudo apt install -y python3-scipy  # Required version for Raspberry Pi functionality
   sudo pip3 install scikit-fuzzy  # Base module installation for Fuzzy Logic
   sudo apt-get install libatlas-base-dev   # For Numpy Compatibility 
 
*****************************************
'''

'''
Imported Libraries
'''
import time
from controller.base import ControllerBase
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
import pickle
import pathlib 
import logging
from common.common import create_logger

'''
Class Definition
'''
class Controller(ControllerBase):
    def __init__(self, config, units, cycle_data):
        super().__init__(config, units, cycle_data)
        self.controlLogger = create_logger('control', filename='./logs/control.log', level=logging.ERROR)

        pickle_path = pathlib.Path('./controller/fuzzy.pickle')
        if not pathlib.Path.exists(pickle_path):
            import subprocess
            command = ['python', 'update_fuzzy.py']
            update_fuzzy = subprocess.run(command)

        try: 
            with open('./controller/fuzzy.pickle', 'rb') as pickle_file:
                self.fuzzy_controller = pickle.load(pickle_file)
            #print('Fuzzy Pickle Successfully Opened.')
        except: 
            self.controlLogger.exception('An exception occurred when attempting to open the fuzzy.pickle file.')
        self.set_target(0.0)
        self.last_temp = -99
        self.last_time = time.time()
        self.cycle_time = cycle_data['HoldCycleTime']

    def update(self, current):
        if self.units == 'C':
            current = int(current * (9/5) + 32) # Celsius to Fahrenheit

        now = time.time()

        cycle_time = now - self.last_time

        self.last_time = now 

        if self.last_temp == -99:
            self.last_temp == current
            cycle_time = self.cycle_time

        # Pass inputs to the ControlSystem using Antecedent labels with Pythonic API
        self.fuzzy_controller.input['delta'] = self.set_point - current  # Delta = Set Point - Current Temperature
        self.fuzzy_controller.input['current'] = current  # Current temperature
        self.fuzzy_controller.input['rate_of_change'] = (current - self.last_temp) / cycle_time  # Rate of Change

        # Crunch the numbers
        self.fuzzy_controller.compute()

        # Set last temp to current temp 
        self.last_temp = current 

        # Return the Cycle Ratio Computed 
        return self.fuzzy_controller.output["cycleratio"]

    def set_target(self, set_point):
        self.set_point = set_point
        if self.units == 'C':
            self.set_point = int(set_point * (9/5) + 32)  # Convert to Fahrenheit
        #self.last_update = time.time()
	
    def supported_functions(self):
        function_list = [
			'update', 
	        'set_target', 
	        'get_config',
            'create_controller'
        ]
        return function_list
