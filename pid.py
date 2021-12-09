#!/usr/bin/env python3

# *****************************************
# PiFire PID Controller
# *****************************************
#
# Description: This object will be used to calculate PID for maintaining
# temperature in the grill.
#
# This software was developed by GitHub user DBorello as part of his excellent
# PiSmoker project: https://github.com/DBorello/PiSmoker
#
# Adapted for PiFire
#
# PID controller based on proportional band in standard PID form https://en.wikipedia.org/wiki/PID_controller#Ideal_versus_standard_PID_form
#   u = Kp (e(t)+ 1/Ti INT + Td de/dt)
#  PB = Proportional Band
#  Ti = Goal of eliminating in Ti seconds
#  Td = Predicts error value at Td in seconds

# *****************************************

# *****************************************
# Imported Libraries
# *****************************************
import time
from common import ReadSettings

# *****************************************
# Class Definition
# *****************************************
class PID:
	def __init__(self,  PB, Ti, Td):
		self.CalculateGains(PB,Ti,Td)

		self.P = 0.0
		self.I = 0.0
		self.D = 0.0
		self.u = 0

		settings = ReadSettings()
		self.Center = settings['cycle_data']['center']

		self.Derv = 0.0
		self.Inter = 0.0
		self.Inter_max = abs(self.Center/self.Ki)

		self.Last = 150

		self.setTarget(0.0)

	def CalculateGains(self,PB,Ti,Td):
		self.Kp = -1/PB
		self.Ki = self.Kp/Ti
		self.Kd = self.Kp*Td

	def update(self, Current):
		#P
		error = Current - self.setPoint
		self.P = self.Kp*error + self.Center #P = 1 for PB/2 under setPoint, P = 0 for PB/2 over setPoint

		#I
		dT = time.time() - self.LastUpdate
		#if self.P > 0 and self.P < 1: #Ensure we are in the PB, otherwise do not calculate I to avoid windup
		self.Inter += error*dT
		self.Inter = max(self.Inter, -self.Inter_max)
		self.Inter = min(self.Inter, self.Inter_max)

		self.I = self.Ki * self.Inter

		#D
		self.Derv = (Current - self.Last)/dT
		self.D = self.Kd * self.Derv

		#PID
		self.u = self.P + self.I + self.D

		#Update for next cycle
		self.error = error
		self.Last = Current
		self.LastUpdate = time.time()

		return self.u

	def	setTarget(self, setPoint):
		self.setPoint = setPoint
		self.error = 0.0
		self.Inter = 0.0
		self.Derv = 0.0
		self.LastUpdate = time.time()

	def setGains(self, PB, Ti, Td):
		self.CalculateGains(PB,Ti,Td)
		self.Inter_max = abs(self.Center/self.Ki)

	def getK(self):
		return self.Kp, self.Ki, self.Kd
