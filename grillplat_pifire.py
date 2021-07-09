#!/usr/bin/env python3

# *****************************************
# PiFire OEM Interface Library
# *****************************************
#
# Description: This library supports 
#  controlling the PiFire Outputs, alongside 
#  the OEM controller outputs via
#  Raspberry Pi GPIOs, to a 4-channel relay
#
# *****************************************

# *****************************************
# Imported Libraries
# *****************************************

import RPi.GPIO as GPIO

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

		GPIO.setwarnings(False)
		GPIO.setmode(GPIO.BCM)
		for item in self.inpins:
			GPIO.setup(self.inpins[item], GPIO.IN, pull_up_down=GPIO.PUD_UP)
		if GPIO.input(self.inpins['selector']) == 0:
			GPIO.setup(self.outpins['power'], GPIO.OUT, initial=self.RELAY_ON)
			GPIO.setup(self.outpins['igniter'], GPIO.OUT, initial=self.RELAY_OFF)
			GPIO.setup(self.outpins['fan'], GPIO.OUT, initial=self.RELAY_OFF)
			GPIO.setup(self.outpins['auger'], GPIO.OUT, initial=self.RELAY_OFF)
		else:
			GPIO.setup(self.outpins['power'], GPIO.OUT, initial=self.RELAY_OFF)
			GPIO.setup(self.outpins['igniter'], GPIO.OUT, initial=self.RELAY_OFF)
			GPIO.setup(self.outpins['fan'], GPIO.OUT, initial=self.RELAY_OFF)
			GPIO.setup(self.outpins['auger'], GPIO.OUT, initial=self.RELAY_OFF)

	def AugerOn(self):
		GPIO.output(self.outpins['auger'], self.RELAY_ON)

	def AugerOff(self):
		GPIO.output(self.outpins['auger'], self.RELAY_OFF)

	def FanOn(self):
		GPIO.output(self.outpins['fan'], self.RELAY_ON)

	def FanOff(self):
		GPIO.output(self.outpins['fan'], self.RELAY_OFF)

	def FanToggle(self):
		if(GPIO.input(self.outpins['fan']) == self.RELAY_ON):
			GPIO.output(self.outpins['fan'], self.RELAY_OFF)
		else:
			GPIO.output(self.outpins['fan'], self.RELAY_ON)

	def IgniterOn(self):
		GPIO.output(self.outpins['igniter'], self.RELAY_ON)

	def IgniterOff(self):
		GPIO.output(self.outpins['igniter'], self.RELAY_OFF)

	def PowerOn(self):
		GPIO.output(self.outpins['power'], self.RELAY_ON)

	def PowerOff(self):
		GPIO.output(self.outpins['power'], self.RELAY_OFF)

	def GetInputStatus(self):
		return (GPIO.input(self.inpins['selector']))

	def GetOutputStatus(self):
		self.current = {}
		for item in self.outpins:
			self.current[item] = GPIO.input(self.outpins[item])
		return self.current
