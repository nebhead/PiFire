#!/usr/bin/env python3

# *****************************************
# PiFire Traeger Interface Library
# *****************************************
#
# Description: This library supports 
#  controlling the PiFire Outputs, alongside 
#  the Traeger outputs via
#  Raspberry Pi GPIOs, to a 4-channel relay
#
# *****************************************

# *****************************************
# Imported Libraries
# *****************************************

import RPi.GPIO as GPIO

class GrillPlatform:

	def __init__(self, outpins, inpins):
		self.outpins = outpins # { 'power' : 4, 'auger' : 14, 'fan' : 15, 'igniter' : 18 }
		self.inpins = inpins # { 'selector' : 17 }
		GPIO.setwarnings(False)
		GPIO.setmode(GPIO.BCM)
		for item in self.inpins:
			GPIO.setup(self.inpins[item], GPIO.IN, pull_up_down=GPIO.PUD_UP)
		if GPIO.input(self.inpins['selector']) == 0:
			GPIO.setup(self.outpins['power'], GPIO.OUT, initial=0)
			GPIO.setup(self.outpins['igniter'], GPIO.OUT, initial=1)
			GPIO.setup(self.outpins['fan'], GPIO.OUT, initial=1)
			GPIO.setup(self.outpins['auger'], GPIO.OUT, initial=1)
		else:
			GPIO.setup(self.outpins['power'], GPIO.OUT, initial=1)
			GPIO.setup(self.outpins['igniter'], GPIO.OUT, initial=1)
			GPIO.setup(self.outpins['fan'], GPIO.OUT, initial=1)
			GPIO.setup(self.outpins['auger'], GPIO.OUT, initial=1)

	def AugerOn(self):
		GPIO.output(self.outpins['auger'], 0)

	def AugerOff(self):
		GPIO.output(self.outpins['auger'], 1)

	def FanOn(self):
		GPIO.output(self.outpins['fan'], 0)

	def FanOff(self):
		GPIO.output(self.outpins['fan'], 1)

	def FanToggle(self):
		if(GPIO.input(self.outpins['fan']) == 0):
			GPIO.output(self.outpins['fan'], 1)
		else:
			GPIO.output(self.outpins['fan'], 0)

	def IgniterOn(self):
		GPIO.output(self.outpins['igniter'], 0)

	def IgniterOff(self):
		GPIO.output(self.outpins['igniter'], 1)

	def PowerOn(self):
		GPIO.output(self.outpins['power'], 0)

	def PowerOff(self):
		GPIO.output(self.outpins['power'], 1)

	def GetInputStatus(self):
		return (GPIO.input(self.inpins['selector']))

	def GetOutputStatus(self):
		self.current = {}
		for item in self.outpins:
			self.current[item] = GPIO.input(self.outpins[item])
		return self.current
