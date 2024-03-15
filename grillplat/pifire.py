#!/usr/bin/env python3

# *****************************************
# PiFire OEM Interface Library
# *****************************************
#
# Description: This library supports 
#  controlling the PiFire Outputs, alongside 
#  the OEM controller outputs via
#  Raspberry Pi GPIOs, to a 4-channel relay
#
# *****************************************

# *****************************************
# Imported Libraries
# *****************************************

import subprocess
from common import is_float, create_logger
from gpiozero import OutputDevice
from gpiozero import Button

class GrillPlatform:

	def __init__(self, outpins, inpins, triggerlevel='LOW'):
		self.logger = create_logger('control')
		self.outpins = outpins # { 'power' : 4, 'auger' : 14, 'fan' : 15, 'igniter' : 18 }
		self.inpins = inpins # { 'selector' : 17 }
		self.current = {}

		self.selector = Button(self.inpins['selector'])

		active_high = triggerlevel == 'HIGH'

		self.fan = OutputDevice(self.outpins['fan'], active_high=active_high, initial_value=False)
		self.auger = OutputDevice(self.outpins['auger'], active_high=active_high, initial_value=False)
		self.igniter = OutputDevice(self.outpins['igniter'], active_high=active_high, initial_value=False)
		self.power = OutputDevice(self.outpins['power'], active_high=active_high, initial_value=False)

	def auger_on(self):
		self.auger.on()

	def auger_off(self):
		self.auger.off()

	def fan_on(self):
		self.fan.on()

	def fan_off(self):
		self.fan.off()

	def fan_toggle(self):
		self.fan.toggle()

	def igniter_on(self):
		self.igniter.on()

	def igniter_off(self):
		self.igniter.off()

	def power_on(self):
		self.power.on()

	def power_off(self):
		self.power.off()

	def get_input_status(self):
		return self.selector.value

	def get_output_status(self):
		self.current = {}
		self.current['auger'] = self.auger.is_active
		self.current['igniter'] = self.igniter.is_active
		self.current['power'] = self.power.is_active
		self.current['fan'] = self.fan.is_active
		return self.current
	
	'''
	System Commands 
	'''

	def supported_commands(self, arglist):
		supported_commands = [
			'check_throttled',
			'check_wifi_quality',
			'check_cpu_temp',
			'supported_commands'
		]

		data = {
			'result' : 'OK',
			'message' : 'Supported commands listed in "data".',
			'data' : {
				'supported_cmds' : supported_commands
			}
		}
		return data

	def check_throttled(self, arglist):
		"""Checks for under-voltage and throttling using vcgencmd.

		Returns:
			(bool, bool): A tuple of (under_voltage, throttled) indicating their status.
		"""

		output = subprocess.check_output(["vcgencmd", "get_throttled"])
		status_str = output.decode("utf-8").strip()[10:]  # Extract the numerical value
		status_int = int(status_str, 16)  # Convert from hex to decimal

		under_voltage = bool(status_int & 0x10000)  # Check bit 16 for under-voltage
		throttled = bool(status_int & 0x5)  # Check bits 0 and 2 for active throttling

		if under_voltage or throttled:
			message = 'WARNING: Under-voltage or throttled situation detected'
		else:
			message = 'No under-voltage or throttling detected.'

		data = {
			'result' : 'OK',
			'message' : message,
			'data' : {
				'cpu_under_voltage' : under_voltage,
				'cpu_throttled' : throttled
			}
		}
		self.logger.debug(f'Check Throttled Called. [data = {data}]')
		return data


	def check_wifi_quality(self, arglist):
		"""Checks the Wi-Fi signal quality on a Raspberry Pi and returns the percentage value (or None if not connected)."""
		data = {
			'result' : 'ERROR',
			'message' : 'Unable to obtain wifi quality data.',
			'data' : {}
		}

		try:
			# Use iwconfig to get the signal quality
			output = subprocess.check_output(["iwconfig", "wlan0"])
			lines = output.decode("utf-8").splitlines()

			# Find the line containing "Link Quality" and extract the relevant part
			for line in lines:
				if "Link Quality=" in line:
					quality_str = line.split("=")[1].strip()  # Isolate the part after "="
					quality_parts = quality_str.split(" ")[0]  # Extract only the first part before spaces

					try:
						quality_value, quality_max = quality_parts.split("/")  # Split for numerical values
						percentage = (int(quality_value) / int(quality_max)) * 100
						data['result'] = 'OK'
						data['message'] = 'Successfully obtained wifi quality data.'
						data['data']['wifi_quality_value'] = int(quality_value)
						data['data']['wifi_quality_max'] = int(quality_max)
						data['data']['wifi_quality_percentage'] = round(percentage, 2)  # Round to two decimal places

					except ValueError:
						# Handle cases where the value might not be directly convertible to an integer
						pass

		except subprocess.CalledProcessError:
			# Handle errors, such as iwconfig not being found or wlan0 not existing
			self.logger.debug(f'Check Throttled had a subprocess error')
			pass

		self.logger.debug(f'Check Throttled Called. [data = {data}]')
		return data

	def check_cpu_temp(self, arglist):
		output = subprocess.check_output(["vcgencmd", "measure_temp"])
		temp = output.decode("utf-8").replace("temp=","").replace("'C", "").replace("\n", "")

		if is_float(temp):
			temp = float(temp)
		else:
			temp = 0.0

		data = {
			'result' : 'OK',
			'message' : 'Success.',
			'data' : {
				'cpu_temp' : float(temp)
			}
		}
		self.logger.debug(f'Check CPU Temp Called. [data = {data}]')
		return data