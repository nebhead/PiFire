#!/usr/bin/env python3

'''
*****************************************
 PiFire PID Controller
*****************************************

 Description: This object will be used to calculate PID for maintaining
 temperature in the grill.  This controller adds basic clamping to prevent windup.
 When the output is saturated (either below 0 or above 1) then we do not increase the integral output.
 https://info.erdosmiller.com/blog/pid-anti-windup-techniques

 This controller was originally developed by GitHub user DBorello as part of his excellent
 PiSmoker project: https://github.com/DBorello/PiSmoker and modified by GitHub user markalston.

 PID controller based on proportional band in standard PID form https://en.wikipedia.org/wiki/PID_controller#Ideal_versus_standard_PID_form
   u   = Kp (e(t)+ 1/Ti INT + Td de/dt) = controller output
  PB   = Proportional Band
  Kp   = Proportional Gain = 1/PB
  Ti   = Integration Time constant
  Td   = Derivative Time Constant
  de   = Change in Error
  dt   = Change in Time
  INT  = Historic cumulative value of errors
  e(t) = Current Error = Set Point - Current Temp

  
  Configuration Defaults: 
  "config": {
      "PB": 30.0,
      "Td": 20.0,
      "Ti": 120.0
   }

*****************************************
'''

'''
Imported Libraries
'''
import time
import logging
from common import create_logger
from controller.base import ControllerBase 

eventLogger = create_logger('events', filename='/tmp/events.log', messageformat='%(asctime)s [%(levelname)s] %(message)s', level=log_level)

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

		self.last_update = time.time()
		self.error = 0.0
		self.error_last = 0.0
		self.set_point = 0

		self.center = config['center']

		self.derv = 0.0
		self.inter = 0.0

		self.set_target(0.0)

	def _calculate_gains(self, pb, ti, td):
		if pb == 0:
			self.kp = 0
		else:
			self.kp = -1 / pb
		if ti == 0:
			self.ki = 0
		else:
			self.ki = self.kp / ti
		self.kd = self.kp * td
		eventLogger.debug('kp: ' + str(self.kp) + ', ki: ' + str(self.ki) + ', kd: ' + str(self.kd))

	def update(self, current):
		# dt
		dt = time.time() - self.last_update

		# P
		error = current - self.set_point
		self.p = self.kp * error

		# I
		self.inter += error * dt
		self.i = self.ki * self.inter

		# D
		self.derv = (error - self.error_last) / dt
		self.d = self.kd * self.derv

		# PID
		self.u = self.p + self.i + self.d

		# Clamping anti-windup method. 
		# Stops integration when the sum of the block components exceeds the output limits 
		# and the integrator output and block input have the same sign. 
		# Resumes integration when either the sum of the block components exceeds the output limits 
		# and the integrator output and block input have opposite sign or the sum no longer exceeds the output limits.
		# 
		# Implemented via reversing the addition to self.inter above if we are clamping.		
		if not ((abs(self.u) >= 1) and (self.i * self.u > 0)):
			eventLogger.debug('Not clamping integrator.')
		else:
			eventLogger.debug('clamping integrator.')
			self.inter -= error * dt
		
		eventLogger.debug('PID Update... error: ' + str(error) + ', p: ' + str(self.p) + ', i: ' + str(self.i) + ', d: ' + str(self.d))

		# Update for next cycle
		self.error_last = error
		self.last_update = time.time()

		return self.u

	def set_target(self, set_point):
		self.set_point = set_point
		self.error = 0.0
		self.inter = 0.0
		self.derv = 0.0
		self.last_update = time.time()

	def set_gains(self, pb, ti, td):
		self._calculate_gains(pb,ti,td)


	def get_k(self):
		return self.kp, self.ki, self.kd
	
	def supported_functions(self):
		function_list = [
			'update', 
	        'set_target', 
	        'get_config', 
			'set_gains', 
			'get_k'
        ]
		return function_list
