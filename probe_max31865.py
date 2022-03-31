import logging.config
import math
import time

import spidev

# Start logging
logger = logging.getLogger(__name__)

# Register and other constant values:

_RTD_A = 3.9083e-3
_RTD_B = -5.775e-7


# Datasheet https://datasheets.maximintegrated.com/en/ds/MAX31865.pdf
class MAX31865:

	def __init__(self, cs, rtd_nominal=100,
				 ref_resistor=430.0,
				 wires=2):

		self.cs = cs
		self.wires = wires

		# RTD Constants
		self.rtd_nominal = rtd_nominal
		self.ref_resistor = ref_resistor
		self.A = 3.90830e-3
		self.B = -5.775e-7

		# Setup SPI
		self.spi = spidev.SpiDev()
		self.spi.open(0, 1)
		self.spi.max_speed_hz = 7629
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
			logger.debug('Fault Detected SPI %i', self.cs)
			self.get_fault()

		adc = ((msb << 8) + lsb) >> 1  # Shift MSB up 8 bits, add to LSB, remove fault bit (last bit)
		return adc

	@property
	def resistance(self):
		"""Read the resistance of the RTD and return its value in Ohms."""
		resistance = self.read_rtd()
		resistance /= 32768
		resistance *= self.ref_resistor
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
			logger.debug('Fault SPI %i: RTD High Threshold', self.cs)
		if fault & 0b01000000:
			logger.debug('Fault SPI %i: RTD Low Threshold', self.cs)
		if fault & 0b00100000:
			logger.debug('Fault SPI %i: REFIN- > 0.85 x V_BIAS', self.cs)
		if fault & 0b0001000:
			logger.debug('Fault SPI %i: REFIN- < 0.85 x V_BIAS (FORCE- Open)', self.cs)
		if fault & 0b00001000:
			logger.debug('Fault SPI %i: RTDIN- < 0.85 x V_BIAS (FORCE- Open)', self.cs)
		if fault & 0b00000100:
			logger.debug('Fault SPI %i: Overvoltage/undervoltage fault', self.cs)

	def close(self):
		self.spi.close()


max_probe = MAX31865(1, 100, 430.0, True)


def probe_max31865_read(units='F'):
	if units == 'F':
		return max_probe.fahrenheit_resistance
	else:
		return max_probe.celsius_resistance
