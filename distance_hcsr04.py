#!/usr/bin/env python3

# *****************************************
# PiFire hcsr04 Interface Library
# *****************************************
#
# Description: This library supports getting the hopper level from the distance sensor
#  NOTE: This library hasn't been tested with real hardware yet and is provided for testing.  
#
# Library dependancy installation instructions:
#  sudo pip3 install hcsr04sensor
#
# *****************************************

# *****************************************
# Imported Libraries
# *****************************************

from hcsr04sensor import sensor
import time 

class HopperLevel:

	def __init__(self, empty=30):
		self.empty = empty # Empty is greater than 30cm distance measured
		# (NOTE: This is a 5V device and must be connected to 5V VCC)
		self.trig_pin = 23 # Modify to match design
		# (NOTE: This pin (echo_pin) must have a resistor divider to reduce the voltage to tolerable levels)
		# (Details: https://www.linuxnorth.org/hcsr04sensor/)
		self.echo_pin = 27 # Modify to match design 
		
		# Default values
		# unit = 'metric'
		# temperature = 20 (room temp in Celsius)

		#  Create a distance reading with the hcsr04 sensor module
		self.ultrasonic = sensor.Measurement(self.trig_pin, self.echo_pin)

	def SetLevel(self, level=100):
		# Do nothing
		return()

	def GetLevel(self):
		AvgDist = self.ultrasonic.raw_distance()  # Average Distance in cm
		
		# If Average Distance is less than the empty distance, calculate percentage
		if AvgDist <= self.empty: 
			level = 100 * (1 - (AvgDist / self.empty))  
		else:
			level = 0

		return(int(level))