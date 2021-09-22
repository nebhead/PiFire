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
from common import WriteLog

class HopperLevel:

	def __init__(self, empty=22, full=4):
		self.empty = empty # Empty is greater than 30cm distance measured
		self.full = full # Full is less than or equal to the minimum full distance.
		
		if self.empty <= self.full:
			event = 'ERROR: Invalid Hopper Level Configuration Empty Level <= Full Level (forcing defaults)'
			WriteLog(event)
			# Set defaults that are valid
			self.empty = 22
			self.full = 4
		self.__startsensor()

	def __startsensor(self):
		# Create a VL53L0X object as tof (time-of-flight)
		self.tof = VL53L0X.VL53L0X(i2c_bus=1,i2c_address=0x29)
		# Open Sensor
		self.tof.open()
		# Start ranging
		self.tof.start_ranging(VL53L0X.Vl53l0xAccuracyMode.BETTER)

	def __stopsensor(self):
		self.tof.stop_ranging()
		self.tof.close()

	def SetLevel(self, level=100):
		# Do nothing
		return()

	def GetLevel(self):
		timing = self.tof.get_timing()
		if(timing < 20000):
			timing = 20000 # Set minimum timing

		# Read the sensor multiple times and average the result
		AvgDist = 0
		start_time = time.time()

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
		WriteLog(event)	

		# If Average Distance is less than the full distance, we are at 100%
		if AvgDist <= self.full: 
			level = 100
		# If Average Distance is less than the empty distance, calculate percentage
		elif AvgDist <= self.empty:
			capacity = self.empty - self.full
			adjusted_ratio = (self.empty / capacity) * 100 
			level = adjusted_ratio * (1 - (AvgDist / self.empty))  
		# If Average Distance is higher than empty distance, report 0 level
		else:
			level = 0

		# If it took a long time to get sensor data, then the sensor might be having issues
		if(time.time() - start_time > 0.5):
			self.__startsensor()  # Attempt re-init of sensor
			event = 'Warning: The TOF sensor took longer than normal to get a reading.  Re-initializing the sensor.'
			WriteLog(event)	
	
		return(int(level))