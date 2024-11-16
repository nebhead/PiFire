#!/usr/bin/env python3

'''
*****************************************
 PiFire PID Controller
*****************************************

 Description: This object will be used to calculate PID for maintaining
 temperature in the grill.

 This software was developed by GitHub user DBorello as part of his excellent
 PiSmoker project: https://github.com/DBorello/PiSmoker

 Adapted for PiFire

 PID controller based on proportional band in standard PID form https://en.wikipedia.org/wiki/PID_controller#Ideal_versus_standard_PID_form
   u = Kp (e(t)+ 1/Ti INT + Td de/dt)
  PB = Proportional Band
  Ti = Goal of eliminating in Ti seconds
  Td = Predicts error value at Td in seconds
  
  Configuration Defaults: 
  "config": {
      "PB": 60.0,
      "Td": 45.0,
      "Ti": 180.0,
      "center": 0.5
   }

*****************************************
'''

'''
Imported Libraries
'''
import time
import math
from controller.base import ControllerBase 


'''
Class Definition
'''
class Controller(ControllerBase):
	def __init__(self, config, units, cycle_data):
		super().__init__(config, units, cycle_data)
			
		self._calculate_gains(config['PB'], config['Ti'], config['Td'])

		self.p = 0.0
		self.i = 0.0
		self.d = 0.0
		self.u = 0

		self.pb = config['PB']

		self.units = units

		self.last_update = time.time()
		self.last_set_time = time.time()
		self.error = 0.0
		self.set_point = 0

		self.center = 0.5
		self.center_factor = config['center_factor']
		
		self.tau = config['tau']
		self.theta	= config['theta']
		
		self.stable_window = config['stable_window']
		self.cycle_time = cycle_data['HoldCycleTime']

		self.derv = 0.0
		self.inter = 0.0

		self.last = 150
		self.start_change_temp = 0.0
		self.new_target = False

		self.set_target(0.0)

	def _calculate_gains(self, pb, ti, td):
		self.kp = -1 / pb
		self.ki = self.kp / ti
		self.kd = self.kp * td

	def update(self, current):
		# Elapsed time since last update
		current_time = time.time()
		dt = current_time - self.last_update
	
		# Fix self.last being set to 0.0 on set point change
		if self.last == 0.0 and self.new_target:
			self.last = current
	
		# Error Calculation
		error = current - self.set_point
	
		# Rate of Change Calculation
		self.roc = (current - self.last) / dt  # Rate of change in Degrees per second
	
		# Predict future temperature and error
		predicted_temp = current + (self.roc * self.theta) * (1 - math.exp(-dt / self.tau))
		predicted_error = predicted_temp - self.set_point

		# Disable Smith Predictor within stable window
		if abs(error) <= self.stable_window and not self.new_target:
			predicted_error = error
	
		# Determine output
		if predicted_error < -self.pb:
			self.u = 1.0
		# The second half of this OR statement allows the controller to fall to the set point without bouncing the temp off of it.
		elif (predicted_error > self.stable_window) or (self.new_target and self.set_point < current):
			self.u = 0.0
		else:
			# Reset integral term when current temperature first reaches or exceeds set point after a set point change
			if self.new_target and abs(error) <= 3:
				self.new_target = False
	
			# Reset integral term if error is outside stable window to avoid windup
			if abs(error) > self.stable_window:
				self.inter = 0.0
	
			# Reset derivative term if error is outside PB/2
			if abs(error) > self.pb / 2:
				self.derv = 0.0
	
			# P
			self.p = self.kp * predicted_error + self.center
	
			# I
			# Reset integral if the system has not reached halfway to the set point within 3 cycles. Prevents overshoots on small set point changes.
			if self.new_target and (current_time - self.last_set_time) >= self.cycle_time * 3 and abs(error) <= abs(self.start_change_temp - self.set_point) / 2:
				self.inter = 0.0
			
			self.inter += predicted_error * dt
			self.i = self.ki * self.inter
			self.i = max(min(self.i, self.center), -self.center)
	
			# D
			self.derv = (predicted_temp - self.last) / dt
			self.d = self.kd * self.derv
	
			# PID
			self.u = self.p + self.i + self.d
	
		# Update for next cycle
		self.error = error
		self.last = current
		self.last_update = current_time
	
		return self.u
	
	def set_target(self, set_point):
		self.set_point = set_point
		self.error = 0.0
		self.inter = 0.0
		self.derv = 0.0
		self.last_update = time.time()
		self.last_set_time = time.time()
		self.start_change_temp = self.last
		self.new_target = True
		# Dynamically set self.center depending on set_point. Higher centers are needed to achieve higher temps, lower centers for lower temps.
		if self.units == "F":
			if set_point <= 240:
				self.center = set_point * self.center_factor
			else:
				self.center = set_point * self.center_factor * 1.2
		elif self.units == "C":
			self.center = set_point * self.center_factor * 2.3
    
	def set_gains(self, pb, ti, td):
		self._calculate_gains(pb,ti,td)
		self.inter_max = abs(self.center / self.ki)

	def get_k(self):
		return self.kp, self.ki, self.kd
	
	def supported_functions(self):
		function_list = [
			'update', 
	        'set target', 
	        'get_config', 
			'set_gainss', 
			'get_k'
        ]
		return function_list