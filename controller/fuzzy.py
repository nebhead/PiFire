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
#import time
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
            self.create_controller()  # This function may take several seconds on a Raspberry Pi
            #print('Fuzzy Pickle Successfully Created')
        try: 
            with open('./controller/fuzzy.pickle', 'rb') as pickle_file:
                self.fuzzy_controller = pickle.load(pickle_file)
            #print('Fuzzy Pickle Successfully Opened.')
        except: 
            self.controlLogger.exception('An exception occurred when attempting to open the fuzzy.pickle file.')
        self.set_target(0.0)

    def create_controller(self, plot=False): 
        '''
         Create fuzzy controller & save to pickle 
        '''
        if plot:
            from matplotlib import pyplot  # Only needed for development 
        
        # New Antecedent/Consequent objects hold universe variables and membership
        # functions.  Temperature ranges are in F for now, but could be scaled for C
        delta = ctrl.Antecedent(np.arange(-25, 25, 0.1), 'delta')  # The range of delta from the setpoint we care about
        current = ctrl.Antecedent(np.arange(0, 600, 1), 'current')  # The range of temperatures that we expect are possible/reasonable
        cycleratio = ctrl.Consequent(np.arange(0, 1, 0.01), 'cycleratio')  # The ratio of Auger On / Auger Off time within the time cycle (default 20s cycle)

        # Membership Function for Delta of SetPoint - Current 
        delta['pSmall'] = fuzz.trimf(delta.universe, [1,2,3])  # trimf(variable, [a,b,c] )
        delta['nSmall'] = fuzz.trimf(delta.universe, [-3,-2,-1])  # trimf(variable, [a,b,c] )

        delta['zAligned'] = fuzz.trimf(delta.universe, [-1,0,1])  # trimf(variable, [a,b,c] )
        delta['nMed'] = fuzz.gbellmf(delta.universe, 4, 2, -8)  # gbellmf(variable, width, slope, center)
        delta['pMed'] = fuzz.gbellmf(delta.universe, 4, 2, 8)  # gbellmf(variable, width, slope, center)
        delta['nLarge'] = fuzz.zmf(delta.universe, -12, -10)  # zmf(variable, foot, ceiling)
        delta['pLarge'] = fuzz.smf(delta.universe, 10, 12)  # smf(variable, foot, ceiling)
        if plot:
            delta.view()

        # Membership Function for Current Temperature 
        current['Low'] = fuzz.zmf(current.universe, 200, 210)  # zmf(variable, foot, ceiling)
        current['High'] = fuzz.smf(current.universe, 200, 210)  # smf(variable, foot, ceiling)
        if plot:
            current.view()
        # Custom membership functions can be built interactively with a familiar,
        # Pythonic API
        cycleratio['Tiny'] = fuzz.zmf(cycleratio.universe, 0, 0.2)
        cycleratio['Short'] = fuzz.trimf(cycleratio.universe, [0.2, 0.25, 0.3])
        cycleratio['Medium'] = fuzz.trimf(cycleratio.universe, [0.3, 0.4, 0.5])
        cycleratio['Long'] = fuzz.smf(cycleratio.universe, 0.5, 0.6)
        if plot:
            cycleratio.view()

        # Setup Rules List
        rules = [] 

        # Rules for ramping up 
        rules.append(ctrl.Rule(delta['pLarge'], cycleratio['Long']))
        rules.append(ctrl.Rule(delta['pMed'], cycleratio['Medium']))

        # Rules for centering 
        rules.append(ctrl.Rule(delta['pSmall'] & (current['High'] | current['Low']), cycleratio['Short']))
        rules.append(ctrl.Rule(delta['nSmall'] & (current['High'] | current['Low']), cycleratio['Tiny']))
        rules.append(ctrl.Rule(delta['zAligned'] & (current['High'] | current['Low']), cycleratio['Tiny']))

        # Rules for ramping down 
        rules.append(ctrl.Rule(delta['nLarge'] & current['High'], cycleratio['Tiny']))
        rules.append(ctrl.Rule(delta['nLarge'] & current['Low'], cycleratio['Tiny']))
        rules.append(ctrl.Rule(delta['nMed'] & current['High'], cycleratio['Short']))
        rules.append(ctrl.Rule(delta['nMed'] & current['Low'], cycleratio['Tiny']))

        # Setup System
        system = ctrl.ControlSystem(rules)
        self.fuzzy_controller = ctrl.ControlSystemSimulation(system)
    
        with open('./controller/fuzzy.pickle', 'wb') as pickle_file:
            pickle.dump(self.fuzzy_controller, pickle_file)

        if plot:
            pyplot.show()

    def update(self, current):
        if self.units == 'C':
            current = int(current * (9/5) + 32) # Celsius to Fahrenheit

        # Pass inputs to the ControlSystem using Antecedent labels with Pythonic API
        self.fuzzy_controller.input['delta'] = self.set_point - current  # Delta = Set Point - Current Temperature
        self.fuzzy_controller.input['current'] = current  # Current temperature 

        # Crunch the numbers
        self.fuzzy_controller.compute()
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
