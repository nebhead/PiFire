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

from gpiozero import OutputDevice
from gpiozero import PWMOutputDevice
from gpiozero import Button
from gpiozero.threads import GPIOThread

class GrillPlatform:

	def __init__(self, out_pins, in_pins, trigger_level='LOW', dc_fan=False, frequency=100):
		self.out_pins = out_pins # { 'power' : 4, 'auger' : 14, 'fan' : 15, 'dc_fan' : 26, 'igniter' : 18, 'pwm' : 13 }
		self.in_pins = in_pins # { 'selector' : 17 }
		self.dc_fan = dc_fan
		self.frequency = frequency
		self.current = {}

		self.selector = Button(self.in_pins['selector'])

		active_high = trigger_level == 'HIGH'

		if dc_fan:
			self._ramp_thread = None
			self.fan = OutputDevice(self.out_pins['dc_fan'], active_high=active_high, initial_value=False)
			self.pwm = PWMOutputDevice(self.out_pins['pwm'], active_high=active_high, frequency=self.frequency)
		else:
			self.fan = OutputDevice(self.out_pins['fan'], active_high=active_high, initial_value=False)

		self.auger = OutputDevice(self.out_pins['auger'], active_high=active_high, initial_value=False)
		self.igniter = OutputDevice(self.out_pins['igniter'], active_high=active_high, initial_value=False)
		self.power = OutputDevice(self.out_pins['power'], active_high=active_high, initial_value=False)

	def auger_on(self):
		self.auger.on()

	def auger_off(self):
		self.auger.off()

	def fan_on(self, duty_cycle=100):
		self.fan.on()
		if self.dc_fan:
			self._stop_ramp()
			self.set_duty_cycle(duty_cycle)

	def fan_off(self):
		self.fan.off()
		if self.dc_fan:
			self.pwm.off()

	def fan_toggle(self):
		self.fan.toggle()

	def set_duty_cycle(self, percent):
		# PWM signal is controlled by a transistor to supply 5v so logic is inverted and supplied as float
		# between 0.0 and 1.0 with 0.0 being fully on and 1.0 being off
		self._stop_ramp()
		duty_cycle = float((100 - percent) / 100.0)
		self.pwm.value = duty_cycle

	def pwm_fan_ramp(self, on_time=5, min_duty_cycle=20, max_duty_cycle=100):
		self.fan.on()
		self._start_ramp(on_time=on_time, min_duty_cycle=min_duty_cycle, max_duty_cycle=max_duty_cycle)

	def set_pwm_frequency(self, frequency=30):
		self.pwm.frequency = frequency

	def igniter_on(self):
		self.igniter.on()

	def igniter_off(self):
		self.igniter.off()

	def power_on(self):
		self.power.on()

	def power_off(self):
		self.power.off()

	def get_input_status(self):
		return self.selector.is_active

	def get_output_status(self):
		self.current = {}
		self.current['auger'] = self.auger.is_active
		self.current['igniter'] = self.igniter.is_active
		self.current['power'] = self.power.is_active
		self.current['fan'] = self.fan.is_active
		if self.dc_fan:
			self.current['pwm'] = 100 - (self.pwm.value * 100)
			self.current['frequency'] = self.pwm.frequency
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
			self.pwm.value = round(value, 4)
			if self._ramp_thread.stopping.wait(delay):
				break
