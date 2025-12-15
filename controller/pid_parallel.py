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

 PID controller based on Parallel (ideal) PID form https://en.wikipedia.org/wiki/PID_controller#Ideal_versus_standard_PID_form
   u   = Kp*e(t)+ Ki*INT + Kd*de/dt = controller output
  Kp   = Proportional coefficient
  Ki   = Integration coefficient
  Kd   = Derivative coefficient
  de   = Change in Error
  dt   = Change in Time
  INT  = Historic cumulative value of errors
  e(t) = Current Error = Set Point - Current Temp

  
  Configuration Defaults: 
  "config": {
      "Kp": 0.0265,
      "Ki": 0.0002284,
      "Kd": .529
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
log_level = logging.DEBUG
eventLogger = create_logger('events', filename='./logs/events.log', messageformat='%(asctime)s [%(levelname)s] %(message)s', level=log_level)

'''
Class Definition
'''
class Controller(ControllerBase):
	def __init__(self, config, units, cycle_data):
		super().__init__(config, units, cycle_data)
		self.function_list.append('set_gains') 
		self.function_list.append('get_k')
		
		
		self.clamping = config.get('Clamping', True)

		self.p = 0.0
		self.i = 0.0
		self.d = 0.0
		self.u = 0

		self.last_update = time.time()
		self.error = 0.0
		self.error_last = 0.0
		self.set_point = 0

		self.derv = 0.0
		self.inter = 0.0
		self._calculate_gains(config.get('Kp', 0.01), config.get('Ki', 0.000055), config.get('Kd', 0.45))
		self.clamping = config.get('Clamping', True)
		self.set_target(0.0)

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
		if self.clamping:		
			if not ((abs(self.u) >= 1) and (self.i * self.u > 0)):
				eventLogger.debug('Not clamping integrator.')
			else:
				eventLogger.debug('clamping integrator.')
				self.inter -= error * dt
		
		eventLogger.debug('PID Update... error: ' + str(error) + ', p: ' + str(self.p) + ', i: ' + str(self.i) + ', d: ' + str(self.d) + ', pid: ' + str(self.u))

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

	def set_gains(self, kp, ki, kd):
		self._calculate_gains(kp,ki,kd)

	def set_config(self, config):
		self.clamping = config.get('Clamping', True)
		self._calculate_gains(config.get('Kp', 0.01), config.get('Ki', 0.000055), config.get('Kd', 0.45))
		self.error = 0.0
		self.inter = 0.0
		self.derv = 0.0

	def _calculate_gains(self, kp, ki, kd):
		self.kp = -1 * kp
		self.ki = -1 * ki
		self.kd = -1 * kd

	def get_k(self):
		return self.kp, self.ki, self.kd
	
