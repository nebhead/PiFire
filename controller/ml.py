#!/usr/bin/env python3

'''
*****************************************
 PiFire Machine Learning Controller
*****************************************

 Description: This object uses machine learning (with SKLearn) for maintaining
 temperature in the grill.

  Configuration Defaults: 
  "config": {
   }

*****************************************
'''

'''
Imported Libraries

Depends on SciKit-Learn
sudo pip3 install scikit-learn
'''
import time
from controller.base import ControllerBase 
from sklearn.linear_model import LinearRegression
from joblib import dump, load

'''
Class Definition
'''
class Controller(ControllerBase):
	def __init__(self, config, units, cycle_data):
		super().__init__(config, units, cycle_data)
		try:
			self.model = load('./controller/ml_model.joblib')
		except: 
			''' Error loading model '''
			raise
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

		rate_of_change = (current - self.last_temp) / cycle_time  # Rate of Change

		cycle_ratio = self.model.predict([[current, self.set_point, rate_of_change]])

		return cycle_ratio[0]

	def set_target(self, set_point):
		self.set_point = set_point
		if self.units == 'C':
			self.set_point = int(set_point * (9/5) + 32)  # Convert to Fahrenheit

	def supported_functions(self):
		function_list = [
			'update', 
	        'set_target'
        ]
		return function_list
