#!/usr/bin/env python3

'''
*****************************************
PiFire Probes MAX31865 Adafruit Module 
*****************************************

Description: 
  This module utilizes the MAX31865 hardware and returns temperature data.
	Depends on: pip3 install adafruit-circuitpython-max31865 

	Ex Device Definition: 
	
	device = {
			'device' : 'your_device_name',	# Unique name for the device
			'module' : 'max31865_adafruit',  		# Must be populated for this module to load properly
			'ports' : ['RTD0'],    			# This is defined in the module, so this does not need to be defined.
			'config' : {
				'cs' : 'D6', 			    # SPI Chip Select GPIO (defaults to D6)
				'rtd_nominal' : 1000, 		# RTD Nominal (Defaults to 1000)
				'ref_resistor' : 4300, 		# Reference Resistor (Defaults to 4300)
				'wires' : 2					# Number of RTD Probe Wires (Defaults to 2)
			} 
		}

'''

'''
*****************************************
 Imported Libraries
*****************************************
'''
import logging 
import time
import board
import digitalio
import adafruit_max31865
from probes.base import ProbeInterface

LOOKUP_TABLE = {
	'D2' : board.D2,
	'D3' : board.D3,
	'D4' : board.D4,
	'D5' : board.D5,
	'D6' : board.D6,
	'D12' : board.D12,
	'D13' : board.D13,
	'D14' : board.D14,
	'D15' : board.D15,
	'D16' : board.D16,
	'D17' : board.D17,
	'D18' : board.D18,
	'D19' : board.D19,
	'D20' : board.D20,
	'D21' : board.D21,
	'D22' : board.D22,
	'D23' : board.D23,
	'D24' : board.D24,
	'D25' : board.D25,
	'D26' : board.D26,
	'D27' : board.D27,
}

'''
*****************************************
 Class Definitions 
*****************************************
'''

class RTDDevice():
	''' MAX31865 Device Based on the Adafruit Module '''
	def __init__(self, cs, rtd_nominal=1000, ref_resistor=4300, wires=2):
		self.wires = wires

		# RTD Constants
		self.rtd_nominal = rtd_nominal
		self.ref_resistor = ref_resistor

		self.spi = board.SPI()
		self.cs = digitalio.DigitalInOut(LOOKUP_TABLE[cs])  # Chip select of the MAX31865 board.
		self.sensor = adafruit_max31865.MAX31865(self.spi, self.cs, rtd_nominal=self.rtd_nominal, ref_resistor=self.ref_resistor, wires=self.wires)

	@property
	def temperature(self):
		return self.sensor.temperature
	
	@property
	def resistance(self): 
		return self.sensor.resistance

class ReadProbes(ProbeInterface):

	def __init__(self, probe_info, device_info, units):
		super().__init__(probe_info, device_info, units)

	def _init_device(self):
		self.time_delay = 0
		self.device_info['ports'] = ['RTD0']
		cs = self.device_info['config'].get('cs', 'D6')
		rtd_nominal = int(self.device_info['config'].get('rtd_nominal', 1000))
		ref_resistor = int(self.device_info['config'].get('ref_resistor', 4300))
		wires = int(self.device_info['config'].get('wires', 2))
		self.device = RTDDevice(cs, rtd_nominal, ref_resistor, wires)

	def read_all_ports(self, output_data):
		''' Read temperature from device '''
		tempC = round(self.device.temperature, 1)
		tempF = int(tempC * (9/5) + 32) # Celsius to Fahrenheit
		port = self.device_info['ports'][0]

		''' Read resistance from device '''
		self.output_data['tr'][self.port_map[port]] = self.device.resistance

		''' Get average temperature from the queue and store it in the output data structure'''
		if port == self.primary_port:
			self.output_data['primary'][self.port_map[port]] = tempF if self.units == 'F' else tempC
		elif port in self.food_ports:
			self.output_data['food'][self.port_map[port]] = tempF if self.units == 'F' else tempC
		elif port in self.aux_ports:
			self.output_data['aux'][self.port_map[port]] = tempF if self.units == 'F' else tempC
		
		return self.output_data