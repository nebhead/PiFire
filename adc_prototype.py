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
		self.GrillTemp = 125	# Fake starting temperature for prototype only
		self.Probe1Temp = 32	# Fake starting temperature for prototype only
		self.Probe2Temp = 42	# Fake starting temperature for prototype only

	def SetProfiles(self, grill_probe_profile, probe_01_profile, probe_02_profile):
		self.grill_probe_profile = grill_probe_profile
		self.probe_01_profile = probe_01_profile
		self.probe_02_profile = probe_02_profile

	def adctotemp(self, adc_value, probe_profile):
		if(adc_value > 0) and (adc_value < (probe_profile['Vs'] * 1000)):
			# Voltage at the divider (i.e. input to the ADC)
			Vo = (adc_value / 1000) # mV to V of ADC (at the divider)

			# Thermistor Resistor Value Ohms (R1)
			# R1 = ( (Vin * R2) - (Vout * R2) ) / Vout
			# Tr = ((probe_profile['Vs'] * probe_profile['Rd']) - (Vo * probe_profile['Rd'])) / Vo
			# R2 = ( Vout * R1 ) / ( Vin - Vout )
			Tr = ( Vo * probe_profile['Rd']) / ( probe_profile['Vs'] - Vo )

			# Coefficient a, b, & c values

			a = probe_profile['A']
			b = probe_profile['B']
			c = probe_profile['C']

		    #Steinhart Hart Equation

			# 1/T = A + B(ln(R)) + C(ln(R))^3

		    # T = 1/(a + b[ln(ohm)] + c[ln(ohm)]^3)

			lnohm = math.log(Tr) # ln(ohms)

			t1 = (b*lnohm) # b[ln(ohm)]

			t2 = c * math.pow(lnohm,3) # c[ln(ohm)]^3

			tempK = 1/(a + t1 + t2) # calculate temperature in Kelvin

			tempC = tempK - 273.15 # Kelvin to Celsius

			tempF = tempC * (9/5) + 32 # Celsius to Farenheit

		else:
			tempF = 0.0

		return tempF

	def ReadAllPorts(self):
		# This is my attemp at making a psuedo-random temperature that will generally rise
		adc_value = [0,0,0] # Using this to populate random numbers from 0-9

		for index in range(3):
			adc_value[index] = random.randint(0,9)

		if (adc_value[0] > 7) and (self.GrillTemp < 425):
			self.GrillTemp += 1 # raise temperature by 1 degree
		elif (adc_value[0] < 1) and (self.GrillTemp > 125):
			self.GrillTemp -= 1 # reduce temperature by 1 degree

		if (adc_value[1] > 7) and (self.Probe1Temp < 200):
			self.Probe1Temp += 1 # raise temperature by 1 degree
		elif (adc_value[1] < 1) and (self.Probe1Temp > 32):
			self.Probe1Temp -= 1 # reduce temperature by 1 degree

		if (adc_value[2] > 7) and (self.Probe2Temp < 250):
			self.Probe2Temp += 1 # raise temperature by 1 degree
		elif (adc_value[2] < 1) and (self.Probe2Temp > 32):
			self.Probe2Temp -= 1 # reduce temperature by 1 degree

		return (self.GrillTemp, self.Probe1Temp, self.Probe2Temp)
