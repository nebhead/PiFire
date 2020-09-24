#!/usr/bin/env python3

# *****************************************
# PiFire ADC Prototype Interface Library
# *****************************************
#
# Description: This library simulates getting temperature in F from an generic ADC
#
# *****************************************

# *****************************************
# Imported Libraries
# *****************************************

import time
import math
import random

class ReadADC:

	def __init__(self, grill_probe_profile, probe_01_profile, probe_02_profile):
		self.SetProfiles(grill_probe_profile, probe_01_profile, probe_02_profile)

		self.adc_data = {}
		self.adc_data['GrillTemp'] = 55		# Fake starting temperature for prototype only
		self.adc_data['Probe1Temp'] = 32	# Fake starting temperature for prototype only
		self.adc_data['Probe2Temp'] = 42	# Fake starting temperature for prototype only

	def SetProfiles(self, grill_probe_profile, probe_01_profile, probe_02_profile):
		self.grill_probe_profile = grill_probe_profile
		self.probe_01_profile = probe_01_profile
		self.probe_02_profile = probe_02_profile

	def adctotemp(self, adc_value, probe_profile):
		# Since this is just a prototype module, and data is simulated, this function is not used. 
		tempF = 100
		Tr = 1000
		return tempF, Tr 

	def ReadAllPorts(self):
		# This is my attemp at making a psuedo-random temperature that will generally rise
		adc_value = [0,0,0] # Using this to populate random numbers from 0-9

		for index in range(3):
			adc_value[index] = random.randint(0,9)

		if (adc_value[0] > 7) and (self.adc_data['GrillTemp'] < 425):
			self.adc_data['GrillTemp'] += 1 # raise temperature by 1 degree
		elif (adc_value[0] < 1) and (self.adc_data['GrillTemp'] > 50):
			self.adc_data['GrillTemp'] -= 1 # reduce temperature by 1 degree

		if (adc_value[1] > 7) and (self.adc_data['Probe1Temp'] < 200):
			self.adc_data['Probe1Temp'] += 1 # raise temperature by 1 degree
		elif (adc_value[1] < 1) and (self.adc_data['Probe1Temp'] > 32):
			self.adc_data['Probe1Temp'] -= 1 # reduce temperature by 1 degree

		if (adc_value[2] > 7) and (self.adc_data['Probe2Temp'] < 250):
			self.adc_data['Probe2Temp'] += 1 # raise temperature by 1 degree
		elif (adc_value[2] < 1) and (self.adc_data['Probe2Temp'] > 32):
			self.adc_data['Probe2Temp'] -= 1 # reduce temperature by 1 degree

		# Thermistor data is not useful in prototype mode
		self.adc_data['GrillTr'] = 0 # Resistance of Grill Thermistor
		self.adc_data['Probe1Tr'] = 0 # Resistance of Probe Thermistor
		self.adc_data['Probe2Tr'] = 0 # Resistance of Probe Thermistor

		return (self.adc_data)
