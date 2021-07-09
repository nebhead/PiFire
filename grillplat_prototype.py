#!/usr/bin/env python3

# *****************************************
# PiFire Grill Platform Prototype Interface Library
# *****************************************
#
# Description: This library simulates controlling the Grill outputs via
#  Raspberry Pi GPIOs, to a 4-channel relay
#
# *****************************************

class GrillPlatform:

	def __init__(self, outpins, inpins, triggerlevel='LOW'):
		self.outpins = outpins # { 'power' : 4, 'auger' : 14, 'fan' : 15, 'igniter' : 18 }
		self.inpins = inpins # { 'selector' : 17 }
		if triggerlevel == 'LOW': 
			# Defines for Active LOW relay
			self.RELAY_ON = 0
			self.RELAY_OFF = 1
		else:
			# Defines for Active HIGH relay
			self.RELAY_ON = 1
			self.RELAY_OFF = 0 

		self.outpins['auger'] = self.RELAY_OFF
		self.outpins['fan'] = self.RELAY_OFF
		self.outpins['igniter'] = self.RELAY_OFF
		self.outpins['power'] = self.RELAY_ON
		self.inpins['selector'] = self.RELAY_ON

	def AugerOn(self):
		self.outpins['auger'] = self.RELAY_ON

	def AugerOff(self):
		self.outpins['auger'] = self.RELAY_OFF

	def FanOn(self):
		self.outpins['fan'] = self.RELAY_ON

	def FanOff(self):
		self.outpins['fan'] = self.RELAY_OFF

	def FanToggle(self):
		if(self.outpins['fan'] == self.RELAY_ON):
			self.outpins['fan'] = self.RELAY_OFF
		else:
			self.outpins['fan'] = self.RELAY_ON

	def IgniterOn(self):
		self.outpins['igniter'] = self.RELAY_ON

	def IgniterOff(self):
		self.outpins['igniter'] = self.RELAY_OFF

	def PowerOn(self):
		self.outpins['power'] = self.RELAY_ON

	def PowerOff(self):
		self.outpins['power'] = self.RELAY_OFF

	def GetInputStatus(self):
		return (self.inpins['selector'])

	def SetInputStatus(self, value):
		self.inpins['selector'] = value

	def GetOutputStatus(self):
		self.current = {}
		for item in self.outpins:
			self.current[item] = self.outpins[item]
		return self.current
