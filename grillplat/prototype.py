#!/usr/bin/env python3

# *****************************************
# PiFire Prototype Interface Library
# *****************************************
#
# Description: This library simulates
# 	controlling the Grill outputs via
# 	GPIOs, to a 4-channel relay and/or DC Fan
#
# *****************************************

"""
	==============================
	  Imported Libraries
	==============================
"""

from gpiozero.threads import GPIOThread
from common import is_float, create_logger

"""
	==============================
	  Class Definition
	==============================
"""

class GrillPlatform:

	def __init__(self, config):
		self.logger = create_logger('control')
		try:
			self.out_pins = config.get('outputs', None)  # Pins to control the PiFire outputs 
			self.in_pins = config.get('inputs', None)  # Pins for input 
			self.dc_fan = config.get('dc_fan', False)  # Save state for DC Fan
			self.frequency = config.get('frequency', 100)  # Save configured fan frequency 
			self.standalone = config.get('standalone', True)  # Save configured state for Standalone
			self.current = {}
		except:
			self.logger.error('Error parsing platform configuration.  Check your settings.json file.')

		if self.dc_fan:
			self._ramp_thread = None
			self.out_pins['pwm'] = 100

		self.out_pins['auger'] = False
		self.out_pins['fan'] = False
		self.out_pins['igniter'] = False
		self.out_pins['power'] = False
		self.in_pins['selector'] = False

	def auger_on(self):
		self.out_pins['auger'] = True

	def auger_off(self):
		self.out_pins['auger'] = False

	def fan_on(self, duty_cycle=100):
		self.out_pins['fan'] = True
		if self.dc_fan:
			self._stop_ramp()
			self.set_duty_cycle(duty_cycle)

	def fan_off(self):
		self.out_pins['fan'] = False

	def fan_toggle(self):
		if(self.out_pins['fan']):
			self.out_pins['fan'] = False
		else:
			self.out_pins['fan'] = True

	def set_duty_cycle(self, percent):
		# PWM signal is controlled by a transistor to supply 5v so logic is inverted and supplied as
		# float between 0.0 and 1.0 with 0.0 being fully on and 1.0 being off
		self._stop_ramp()
		duty_cycle = float((100 - percent) / 100.0)
		self.out_pins['pwm'] = duty_cycle
		#print('Set PWM Speed ' + str(percent))

	def pwm_fan_ramp(self, on_time=5, min_duty_cycle=20, max_duty_cycle=100):
		self.out_pins['fan'] = True
		self._start_ramp(on_time=on_time, min_duty_cycle=min_duty_cycle, max_duty_cycle=max_duty_cycle)

	def set_pwm_frequency(self, frequency=100):
		self.frequency = frequency

	def igniter_on(self):
		self.out_pins['igniter'] = True

	def igniter_off(self):
		self.out_pins['igniter'] = False

	def power_on(self):
		self.out_pins['power'] = True

	def power_off(self):
		self.out_pins['power'] = False

	def get_input_status(self):
		return (self.in_pins['selector'])

	def set_input_status(self, value):
		self.in_pins['selector'] = value

	def get_output_status(self):
		self.current = {}
		self.current['auger'] = self.out_pins['auger']
		self.current['igniter'] = self.out_pins['igniter']
		self.current['power'] = self.out_pins['power']
		self.current['fan'] = self.out_pins['fan']
		if self.dc_fan:
			self.current['pwm'] = 100 - (self.out_pins['pwm'] * 100)
			self.current['frequency'] = self.frequency
		return self.current

	def _start_ramp(self, on_time, min_duty_cycle, max_duty_cycle, background=True):
		self._stop_ramp()
		self._ramp_thread = GPIOThread(self._ramp_device, (on_time, min_duty_cycle, max_duty_cycle))
		self._ramp_thread.start()
		if not background:
			self._ramp_thread.join()
			self._ramp_thread = None

	def _stop_ramp(self):
		if self._ramp_thread:
			self._ramp_thread.stop()
			self._ramp_thread = None

	def _ramp_device(self, on_time, min_duty_cycle, max_duty_cycle, fps=25):
		duty_cycle = max_duty_cycle / 100
		sequence = []
		sequence += [
			(1 - (i * (duty_cycle / fps) / on_time), 1 / fps)
			for i in range(int((fps * on_time) * (min_duty_cycle / max_duty_cycle)), int(fps * on_time))
		]
		sequence.append((1.0 - duty_cycle, 1 / fps))
		for value, delay in sequence:
			percent = round(float(100 - (value * 100)), 4)
			self.out_pins['pwm'] = percent
			#print('Set PWM Speed ' + str(percent))
			if self._ramp_thread.stopping.wait(delay):
				break
	
	def cleanup(self):
		self.power_off()
		self.igniter_off()
		self.auger_off()
		self.fan_off()

	# MARK: System Platform Commands
	"""
	==============================
	  System / Platform Commands 
	==============================
	
		Commands callable by outside processes to get status or information, for the platform.  
	
	"""

	def supported_commands(self, arglist):
		supported_commands = [
			'check_throttled',
			'check_wifi_quality',
			'check_cpu_temp',
			'supported_commands',
			'check_alive',
			'scan_bluetooth'
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
		under_voltage = False
		throttled = False

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
		return data
	
	def check_wifi_quality(self, arglist):
		"""Checks the Wi-Fi signal quality on a Raspberry Pi and returns the value (or None if not connected)."""
		# Return None if not connected or if there was an error

		data = {
			'result' : 'OK',
			'message' : 'Success.',
			'data' : {
				'wifi_quality_value' : 60,
				'wifi_quality_max' : 70,
				'wifi_quality_percentage' : 80
			}
		}
		return data

	def check_cpu_temp(self, arglist):
		temp = '40.0'
		
		if is_float(temp):
			temp = float(temp)
		else:
			temp = 0.0
		
		data = {
			'result' : 'OK',
			'message' : 'Success.',
			'data' : {
				'cpu_temp' : temp
			}
		}
		return data
	
	def check_alive(self, arglist):
		'''
		 Simple check to see if the platform is up and running. 
		'''
		
		data = {
			'result' : 'OK',
			'message' : 'The control script is running.',
			'data' : {}
		}
		return data

	def scan_bluetooth(self, arglist):
		'''
		 Scan for bluetooth device addresses
		'''
		from bluepy import btle
		#print('[DEBUG] Imported bluepy...')
		scanner = btle.Scanner()
		#print('[DEBUG] Created scanner object...')
		bt_devices = []

		for entry in scanner.scan(5):
			name = entry.getValueText(9)
			if name is None:
				name = 'Unknown'
			hw_id = entry.addr
			info = ''
			bt_devices.append({'name':name, 'hw_id':hw_id, 'info':info})
			#print(f'[DEBUG] Found device: {name} ({hw_id})')
		
		data = {
			'result' : 'OK',
			'message' : 'The control script is running.',
			'data' : {
				'bt_devices' : bt_devices
			}
		}
		return data