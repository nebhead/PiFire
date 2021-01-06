#!/usr/bin/env python3

# *****************************************
# PiFire Grill Platform Prototype Interface Library
# *****************************************
#
# Description: This library simulates controlling the Grill outputs via
#  Raspberry Pi GPIOs, to a 4-channel relay
#
# *****************************************

# *****************************************
# Imported Libraries
# *****************************************

class GrillPlatform:

	def __init__(self, outpins, inpins):
		self.outpins = outpins # { 'power' : 4, 'auger' : 14, 'fan' : 15, 'igniter' : 18 }
		self.inpins = inpins # { 'selector' : 17 }
		self.outpins['auger'] = 1
		self.outpins['fan'] = 1
		self.outpins['igniter'] = 1
		self.outpins['power'] = 0
		self.inpins['selector'] = 0

	def AugerOn(self):
		self.outpins['auger'] = 0

	def AugerOff(self):
		self.outpins['auger'] = 1

	def FanOn(self):
		self.outpins['fan'] = 0

	def FanOff(self):
		self.outpins['fan'] = 1

	def FanToggle(self):
		if(self.outpins['fan'] == 0):
			self.outpins['fan'] = 1
		else:
			self.outpins['fan'] = 0

	def IgniterOn(self):
		self.outpins['igniter'] = 0

	def IgniterOff(self):
		self.outpins['igniter'] = 1

	def PowerOn(self):
		self.outpins['power'] = 0

	def PowerOff(self):
		self.outpins['power'] = 1

	def GetInputStatus(self):
		return (self.inpins['selector'])

	def SetInputStatus(self, value):
		self.inpins['selector'] = value

	def GetOutputStatus(self):
		self.current = {}
		for item in self.outpins:
			self.current[item] = self.outpins[item]
		return self.current
