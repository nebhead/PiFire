#!/usr/bin/env python3

# *****************************************
# PiFire vl53l0x Interface Library
# *****************************************
#
# Description: This library supports getting the hopper level from the distance sensor
#
# Install Dependancies: 
#
#    sudo apt install python3-smbus
#    sudo pip3 install git+https://github.com/pimoroni/VL53L0X-python.git
#
# *****************************************

# *****************************************
# Imported Libraries
# *****************************************

import VL53L0X
import time 
from common import DebugWrite

class HopperLevel:

	def __init__(self, empty=30):
		# Create a VL53L0X object as tof (time-of-flight)
		self.tof = VL53L0X.VL53L0X(i2c_bus=1,i2c_address=0x29)
		self.empty = empty # Empty is greater than 30cm distance measured
		# Open Sensor
		self.tof.open()
		# Start ranging
		self.tof.start_ranging(VL53L0X.Vl53l0xAccuracyMode.BETTER)

	def SetLevel(self, level=100):
		# Do nothing
		return()

	def GetLevel(self):
		timing = self.tof.get_timing()
		if(timing < 20000):
			timing = 20000 # Set minimum timing

		# Read the sensor multiple times and average the result
		AvgDist = 0
		for reading in range(3):
			distance = self.tof.get_distance()
			if distance > 0:
				if AvgDist > 0:
					AvgDist = (AvgDist + distance)/2
				else: 
					AvgDist = distance 
			time.sleep(timing/1000000.00)
		
		# Convert mm to cm 
		AvgDist = AvgDist / 10 
		event = 'Average Distance Measured: ' + str(AvgDist) + 'cm'
		DebugWrite(event)
		
		# If Average Distance is less than the empty distance, calculate percentage
		if AvgDist <= self.empty: 
			level = 100 * (1 - (AvgDist / self.empty))  
		else:
			level = 0

		#self.tof.stop_ranging()
		#self.tof.close()
		
		return(int(level))