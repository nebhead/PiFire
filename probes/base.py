#!/usr/bin/env python3

'''
*****************************************
PiFire Probes Base Module 
*****************************************

Description: 
  This module serves as a base module for the probe devices.

'''

'''
*****************************************
 Imported Libraries
*****************************************
'''

import math
import time
from probes.temp_queue import TempQueue

'''
*****************************************
 Class Definitions 
*****************************************
'''

class ProbeInterface:

	def __init__(self, probe_info, device_info, units):
		self.units = units 
		self.device_info = device_info
		self.set_profiles(probe_info)
		self._build_port_map(probe_info)
		self._build_output_data(probe_info)
		self._build_ports()
		self.primary_port = None
		self.food_ports = []
		self.aux_ports = []
		self._discover_port_types(probe_info)
		self._init_device()

	def _init_device(self):
		self.time_delay = 0
		self.device = FakeDevice(self.port_map, self.primary_port, self.units)

	def _discover_port_types(self, probe_info):
		''' Find attached ports and identify their types '''
		for probe in probe_info:
			if probe['device'] == self.device_info['device']:
				if probe['type'] == 'Primary':
					self.primary_port = probe['port']
				if probe['type'] == 'Food':
					self.food_ports.append(probe['port'])
				if probe['type'] == 'Aux':
					self.aux_ports.append(probe['port'])

	def _build_port_map(self, probe_info):
		''' Build port mapping '''
		self.port_map = {}
		for port in self.device_info['ports']:
			for probe in probe_info:
				if (probe['device'] == self.device_info['device']) and (probe['port'] == port):
					self.port_map[port] = probe['label']

	def _build_output_data(self, probe_info):
		''' Build output data structure for probes '''
		self.output_data = {
			'primary' : {},
			'food' : {},
			'aux' : {}, 
			'tr' : {}
		}
		for probe in probe_info:
			if probe['device'] == self.device_info['device']:
				if probe['type'] == 'Primary':
					self.output_data['primary'][probe['label']] = 0
				elif probe['type'] == 'Food':
					self.output_data['food'][probe['label']] = 0
				elif probe['type'] == 'Aux':
					self.output_data['aux'][probe['label']] = 0
		''' Build output data structure for Tr tuning data '''
		for port in self.port_map:
			self.output_data['tr'][self.port_map[port]] = 0

	def _build_ports(self):
		''' Build ports objects. '''
		self.port_queues = {}
		for port in self.port_map:
			self.port_queues[port] = TempQueue(qlength=10, units=self.units)

	def _temp_to_resistance(self, temp, probe_profile):
		'''
		  Determine the resistance value Tr for the port.  
		  Prototype uses the temperature and probe profile to determine the Tr value. 
		'''
		A = probe_profile['A']
		B = probe_profile['B']
		C = probe_profile['C']

		try: 
			if self.units == 'F':
				tempK = ((temp - 32) * (5/9)) + 273.15
			else: 
				tempK = temp + 273.15

			'''
			 https://en.wikipedia.org/wiki/Steinhart%E2%80%93Hart_equation
			 Inverse of the equation, to determine Tr = Resistance Value of the thermistor
			'''

			x = (1/(2*C))*(A-(1/tempK))

			y = math.sqrt(math.pow((B/(3*C)),3)+math.pow(x,2))

			Tr = math.exp(((y-x)**(1/3)) - ((y+x)**(1/3)))
		except: 
			Tr = 0

		return Tr 

	def _voltage_to_temp(self, voltage, probe_profile):
		if(voltage > 0) and (voltage < (probe_profile['Vs'] * 1000) * 0.99):
			'''
				Voltage at the divider (i.e. input to the ADC)
			'''
			Vo = (voltage / 1000) # mV to V of ADC (at the divider)
			
			'''
			Thermistor Resistor Value Ohms (R1)
			 R1 = ( (Vin * R2) - (Vout * R2) ) / Vout
			 Tr = ((probe_profile['Vs'] * probe_profile['Rd']) - (Vo * probe_profile['Rd'])) / Vo
			 R2 = ( Vout * R1 ) / ( Vin - Vout )
			'''
			Tr = ( Vo * probe_profile['Rd']) / ( probe_profile['Vs'] - Vo )

			''' Coefficient a, b, & c values '''
			a = probe_profile['A']
			b = probe_profile['B']
			c = probe_profile['C']

			'''
		    Steinhart Hart Equation
			 1/T = A + B(ln(R)) + C(ln(R))^3
			 T = 1/(a + b[ln(ohm)] + c[ln(ohm)]^3)
			'''
			lnohm = math.log(Tr) # ln(ohms)

			t1 = (b*lnohm) # b[ln(ohm)]

			t2 = c * math.pow(lnohm,3) # c[ln(ohm)]^3

			tempK = 1/(a + t1 + t2) # calculate temperature in Kelvin

			tempC = tempK - 273.15 # Kelvin to Celsius

			tempF = tempC * (9/5) + 32 # Celsius to Farenheit
			
			''' Check bounds for realistic temperature values (0-600F), else report 0F '''
			if (tempF < 0) or (tempF > 600):
				tempF = 0

		else:
			tempF = 0.0
			tempC = 0.0
			Tr = 0

		if self.units == 'F':
			return tempF, round(Tr)  # Return Calculated Temperature and Thermistor Value in Ohms
		else: 
			return tempC, round(Tr)  # Return Calculated Temperature and Thermistor Value in Ohms

	def read_all_ports(self, output_data):
		port_values = {}

		for port in self.port_map:
			''' Read Ports from Device '''
			port_values[port] = self.device.read_voltage(port)

			''' Convert Voltage to Temperature and Tr '''
			port_values[port], self.output_data['tr'][self.port_map[port]] = self._voltage_to_temp(port_values[port], self.probe_profiles[port])

			''' Enqueue the Temperature Readings to Port Queues '''
			self.port_queues[port].enqueue(port_values[port])

			''' Get average temperature from the queue and store it in the output data structure'''
			if port == self.primary_port:
				self.output_data['primary'][self.port_map[port]] = self.port_queues[port].average()
			elif port in self.food_ports:
				self.output_data['food'][self.port_map[port]] = self.port_queues[port].average()
			elif port in self.aux_ports:
				self.output_data['aux'][self.port_map[port]] = self.port_queues[port].average()

			if self.time_delay:
				time.sleep(self.time_delay)  # Time delay, if needed for single-shot mode on some ADC's
		
		return self.output_data

	def update_units(self, units):
		self.units = 'C' if units == 'C' else 'F'
		self._init_device()

	def set_profiles(self, probe_info):
		''' Set the probe profile for each of the probes. '''
		self.probe_profiles = {}
		for port in self.device_info['ports']:
			for probe in probe_info:
				if probe['device'] == self.device_info['device'] and probe['port'] == port:
					self.probe_profiles[port] = probe['profile']

	def get_port_map(self):
		return self.port_map

class FakeDevice:

	def __init__(self, port_map, primary_port, units):
		pass 

	def read_voltage(self, port):
		pass 
