#!/usr/bin/env python3

'''
*****************************************
PiFire Probes MAX31865 Module 
*****************************************

Description: 
  This module utilizes the MAX31865 hardware and returns temperature data.  
  Credit to Adafruit (https://github.com/adafruit/Adafruit_CircuitPython_MAX31865) for much of this code.
  While the code here was contributed by another user, it does appear that much of it was borrowed originally
  from the Adafruit module.  The only difference, it appears, is that this module uses spidev instead of 
  the circuitpython modules. 

	Depends on: spidev

	Ex Device Definition: 
	
	device = {
			'device' : 'your_device_name',	# Unique name for the device
			'module' : 'max31865',  		# Must be populated for this module to load properly
			'ports' : ['RTD0'],    			# This is defined in the module, so this does not need to be defined.
			'config' : {
				'cs' : 1, 					# SPI Chip Select (Defaults to 1)
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
import spidev
import time
import math
from probes.base import ProbeInterface

'''
*****************************************
 Class Definitions 
*****************************************
'''
# Register and other constant values
_RTD_A = 3.9083e-3
_RTD_B = -5.775e-7

class RTDDevice():
	''' MAX31865 Device Init '''
	def __init__(self, cs, rtd_nominal=1000, ref_resistor=4300, wires=2):
		self.logger = logging.getLogger("control")
		self.cs = cs
		self.wires = wires

		# RTD Constants
		self.rtd_nominal = rtd_nominal
		self.ref_resistor = ref_resistor

		# Setup SPI
		self.spi = spidev.SpiDev()
		self.spi.open(0, self.cs)
		self.spi.max_speed_hz = 5000
		self.spi.mode = 0b01

		self.config()
	
	def config(self):
		# Config
		# V_Bias (1=on)
		# Conversion Mode (1 = Auto)
		# 1-Shot
		# 3-Wire (0 = Off)
		# Fault Detection (2 Bits)
		# Fault Detection
		# Fault Status
		# 50/60Hz (0 = 60 Hz)
		if self.wires == 3:
			config = 0b11010010  # 0xD2
		else:
			config = 0b11000010  # 0xC2

		self.spi.xfer2([0x80, config])
		time.sleep(0.25)
		t = self.temperature

	def read_rtd(self):
		msb = self.spi.xfer2([0x01, 0x00])[1]
		lsb = self.spi.xfer2([0x02, 0x00])[1]

		# Check fault
		if lsb & 0b00000001:
			self.get_fault()

		adc = ((msb << 8) + lsb) >> 1  # Shift MSB up 8 bits, add to LSB, remove fault bit (last bit)
		return adc

	@property
	def resistance(self):
		"""Read the resistance of the RTD and return its value in Ohms."""
		try:
			resistance = self.read_rtd()
			resistance /= 32768
			resistance *= self.ref_resistor
		except: 
			self.logger.exception(f'Exception occurred while reading probe port {self.device_info["ports"][0]}.  Trace dump: ')
			resistance = 0
		return resistance

	@property
	def fahrenheit(self):
		return (self.celsius - 32) / 1.8

	@property
	def fahrenheit_resistance(self):
		celsius, resistance = self.celsius_resistance
		return (celsius - 32) / 1.8, resistance

	@property
	def temperature(self):
		return self.celsius

	@property
	def celsius(self):
		return self.celsius_resistance[0]

	@property
	def celsius_resistance(self):
		"""Read the temperature of the sensor and return its value in degrees
		Celsius.
		"""
		# This math originates from:
		# http://www.analog.com/media/en/technical-documentation/application-notes/AN709_0.pdf
		# To match the naming from the app note we tell lint to ignore the Z1-4
		# naming.
		# pylint: disable=invalid-name
		raw_reading = self.resistance
		Z1 = -_RTD_A
		Z2 = _RTD_A * _RTD_A - (4 * _RTD_B)
		Z3 = (4 * _RTD_B) / self.rtd_nominal
		Z4 = 2 * _RTD_B
		temp = Z2 + (Z3 * raw_reading)
		temp = (math.sqrt(temp) + Z1) / Z4
		if temp >= 0:
			return temp, temp

		# For the following math to work, nominal RTD resistance must be normalized to 100 ohms
		raw_reading /= self.rtd_nominal
		raw_reading *= 100

		rpoly = raw_reading
		temp = -242.02
		temp += 2.2228 * rpoly
		rpoly *= raw_reading  # square
		temp += 2.5859e-3 * rpoly
		rpoly *= raw_reading  # ^3
		temp -= 4.8260e-6 * rpoly
		rpoly *= raw_reading  # ^4
		temp -= 2.8183e-8 * rpoly
		rpoly *= raw_reading  # ^5
		temp += 1.5243e-10 * rpoly
		return temp, raw_reading

	def get_fault(self):
		fault = self.spi.xfer2([0x07, 0x00])[1]

		if fault & 0b10000000:
			self.logger.debug('Fault SPI %i: RTD High Threshold', self.cs)
		if fault & 0b01000000:
			self.logger.debug('Fault SPI %i: RTD Low Threshold', self.cs)
		if fault & 0b00100000:
			self.logger.debug('Fault SPI %i: REFIN- > 0.85 x V_BIAS', self.cs)
		if fault & 0b0001000:
			self.logger.debug('Fault SPI %i: REFIN- < 0.85 x V_BIAS (FORCE- Open)', self.cs)
		if fault & 0b00001000:
			self.logger.debug('Fault SPI %i: RTDIN- < 0.85 x V_BIAS (FORCE- Open)', self.cs)
		if fault & 0b00000100:
			self.logger.debug('Fault SPI %i: Overvoltage/undervoltage fault', self.cs)

	def close(self):
		self.spi.close()

class ReadProbes(ProbeInterface):

	def __init__(self, probe_info, device_info, units):
		super().__init__(probe_info, device_info, units)

	def _init_device(self):
		self.time_delay = 0
		self.device_info['ports'] = ['RTD0']
		cs = int(self.device_info['config'].get('cs', 1))
		rtd_nominal = int(self.device_info['config'].get('rtd_nominal', 1000))
		ref_resistor = int(self.device_info['config'].get('ref_resistor', 4300))
		wires = int(self.device_info['config'].get('wires', 2))
		self.device = RTDDevice(cs, rtd_nominal, ref_resistor, wires)

	def read_all_ports(self, output_data):
		''' Read temperature from device '''
		tempC = round(self.device.temperature, 1)
		tempF = int(tempC * (9/5) + 32) # Celsius to Farenheit
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