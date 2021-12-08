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

	def __init__(self, grill_probe_profile, probe_01_profile, probe_02_profile, units='F'):
		self.SetProfiles(grill_probe_profile, probe_01_profile, probe_02_profile)

		self.adc_data = {}
		self.units = units 
		if self.units == 'F':
			self.adc_data['GrillTemp'] = 55		# Fake starting temperature for prototype only
			self.adc_data['Probe1Temp'] = 32	# Fake starting temperature for prototype only
			self.adc_data['Probe2Temp'] = 42	# Fake starting temperature for prototype only
		else:
			self.adc_data['GrillTemp'] = 12		# Fake starting temperature for prototype only
			self.adc_data['Probe1Temp'] = 0	# Fake starting temperature for prototype only
			self.adc_data['Probe2Temp'] = 5.5	# Fake starting temperature for prototype only


	def SetProfiles(self, grill_probe_profile, probe_01_profile, probe_02_profile):
		self.grill_probe_profile = grill_probe_profile
		self.probe_01_profile = probe_01_profile
		self.probe_02_profile = probe_02_profile

	def adctotemp(self, temp, probe_profile):
		# Since this is just a prototype module, and data is simulated, this function is used to determine the resistance value
		A = probe_profile['A']
		B = probe_profile['B']
		C = probe_profile['C']

		try: 
			if self.units == 'F':
				tempK = ((temp - 32) * (5/9)) + 273.15
			else: 
				tempK = temp + 273.15

			# https://en.wikipedia.org/wiki/Steinhart%E2%80%93Hart_equation
			# Inverse of the equation, to determine Tr = Resistance Value of the thermistor

			x = (1/(2*C))*(A-(1/tempK))

			y = math.sqrt(math.pow((B/(3*C)),3)+math.pow(x,2))

			Tr = math.exp(((y-x)**(1/3)) - ((y+x)**(1/3)))
		except: 
			Tr = 0

		return Tr 

	def ReadAllPorts(self):
		# This is my attemp at making a psuedo-random temperature that will generally rise
		adc_value = [0,0,0] # Using this to populate random numbers from 0-9

		for index in range(3):
			adc_value[index] = random.randint(0,9)

		if self.units == 'F':
			maxGrillTemp = 425 
			minGrillTemp = 50 
			maxProbeTemp = 220 
			minProbeTemp = 32 
			changeFactor = 1
		else: 
			maxGrillTemp = 220 
			minGrillTemp = 10 
			maxProbeTemp = 105
			minProbeTemp = 0
			changeFactor = 0.5

		if (adc_value[0] > 7) and (self.adc_data['GrillTemp'] < maxGrillTemp):
			self.adc_data['GrillTemp'] += changeFactor # raise temperature by changeFactor degree
		elif (adc_value[0] < 1) and (self.adc_data['GrillTemp'] > minGrillTemp):
			self.adc_data['GrillTemp'] -= changeFactor # reduce temperature by changeFactor degree

		if (adc_value[1] > 7) and (self.adc_data['Probe1Temp'] < maxProbeTemp):
			self.adc_data['Probe1Temp'] += changeFactor # raise temperature by changeFactor degree
		elif (adc_value[1] < 1) and (self.adc_data['Probe1Temp'] > minProbeTemp):
			self.adc_data['Probe1Temp'] -= changeFactor # reduce temperature by changeFactor degree

		if (adc_value[2] > 7) and (self.adc_data['Probe2Temp'] < maxProbeTemp):
			self.adc_data['Probe2Temp'] += changeFactor # raise temperature by changeFactor degree
		elif (adc_value[2] < 1) and (self.adc_data['Probe2Temp'] > minProbeTemp):
			self.adc_data['Probe2Temp'] -= changeFactor # reduce temperature by changeFactor degree

		# Thermistor data is not useful in prototype mode
		self.adc_data['GrillTr'] = self.adctotemp(self.adc_data['GrillTemp'], self.grill_probe_profile) # Resistance of Grill Thermistor
		self.adc_data['Probe1Tr'] = self.adctotemp(self.adc_data['Probe1Temp'], self.probe_01_profile) # Resistance of Probe Thermistor
		self.adc_data['Probe2Tr'] = self.adctotemp(self.adc_data['Probe2Temp'], self.probe_02_profile) # Resistance of Probe Thermistor

		return (self.adc_data)

	def update_units(self, units):
		if units == 'C':
			self.units = 'C'
			self.adc_data['GrillTemp'] = 12		# Fake starting temperature for prototype only
			self.adc_data['Probe1Temp'] = 0	 	# Fake starting temperature for prototype only
			self.adc_data['Probe2Temp'] = 5.5	# Fake starting temperature for prototype only
		else: 
			self.units = 'F'
			self.adc_data['GrillTemp'] = 55		# Fake starting temperature for prototype only
			self.adc_data['Probe1Temp'] = 32	# Fake starting temperature for prototype only
			self.adc_data['Probe2Temp'] = 42	# Fake starting temperature for prototype only
