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

from gpiozero import OutputDevice
from gpiozero import Button

class GrillPlatform:

	def __init__(self, outpins, inpins, triggerlevel='LOW'):
		self.outpins = outpins # { 'power' : 4, 'auger' : 14, 'fan' : 15, 'igniter' : 18 }
		self.inpins = inpins # { 'selector' : 17 }
		self.current = {}

		self.selector = Button(self.inpins['selector'])

		active_high = triggerlevel == 'HIGH'

		self.fan = OutputDevice(self.outpins['fan'], active_high=active_high, initial_value=False)
		self.auger = OutputDevice(self.outpins['auger'], active_high=active_high, initial_value=False)
		self.igniter = OutputDevice(self.outpins['igniter'], active_high=active_high, initial_value=False)
		self.power = OutputDevice(self.outpins['power'], active_high=active_high, initial_value=False)

	def auger_on(self):
		self.auger.on()

	def auger_off(self):
		self.auger.off()

	def fan_on(self):
		self.fan.on()

	def fan_off(self):
		self.fan.off()

	def fan_toggle(self):
		self.fan.toggle()

	def igniter_on(self):
		self.igniter.on()

	def igniter_off(self):
		self.igniter.off()

	def power_on(self):
		self.power.on()

	def power_off(self):
		self.power.off()

	def get_input_status(self):
		return self.selector.value

	def get_output_status(self):
		self.current = {}
		self.current['auger'] = self.auger.is_active
		self.current['igniter'] = self.igniter.is_active
		self.current['power'] = self.power.is_active
		self.current['fan'] = self.fan.is_active
		return self.current
