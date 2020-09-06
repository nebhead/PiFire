#!/usr/bin/env python3

# *****************************************
# PiFire ADS1115 Interface Library
# *****************************************
#
# Description: This library supports getting temperature in F from the ADS1115
#
# *****************************************

# *****************************************
# Imported Libraries
# *****************************************

import ADS1115
import time
import math
import datetime

class ReadADC:

	def __init__(self, grill_probe_profile, probe_01_profile, probe_02_profile):
		self.ads = ADS1115.ADS1115()
		self.SetProfiles(grill_probe_profile, probe_01_profile, probe_02_profile)

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
			#print('Probe: ' + probe_profile['name'])
			#print('Probe Resistance: ' + str(Tr))
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
		adc_value = [0,0,0]

		try:
			for index in range(3):
				time.sleep(0.05)
				adc_value[index] = self.ads.readADCSingleEnded(index)
		except:
			now = str(datetime.datetime.now())
			now = now[0:19] # Truncate the microseconds
			print(str(now) + ' Error Reading Temperature.')
			return(0,0,0)

		GrillTemp = self.adctotemp(adc_value[0], self.grill_probe_profile)
		#print('Grill Temp = ' + str(GrillTemp) + 'F')
		Probe1Temp = self.adctotemp(adc_value[1], self.probe_01_profile)
		#print('Probe 1 Temp = ' + str(Probe1Temp) + 'F')
		Probe2Temp = self.adctotemp(adc_value[2], self.probe_02_profile)
		#print('Probe 2 Temp = ' + str(Probe2Temp) + 'F')

		return (GrillTemp, Probe1Temp, Probe2Temp)
