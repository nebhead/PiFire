#!/usr/bin/env python3
'''
*****************************************
PiFire Display Interface Library
*****************************************

 Description: 
   This library supports using 
 the ILI9341 display with 240Hx320W resolution.
 This module utilizes Luma.LCD to interface 
 this display. 

*****************************************
'''

'''
 Imported Libraries
'''
import threading
from luma.core.interface.serial import spi
from luma.lcd.device import ili9341
from display.base_240x320 import DisplayBase

'''
Display class definition
'''
class Display(DisplayBase):

	def __init__(self, dev_pins, buttonslevel='HIGH', rotation=0, units='F'):
		super().__init__(dev_pins, buttonslevel, rotation, units)

	def _init_display_device(self):
		# Init Device
		dc_pin = self.dev_pins['display']['dc']
		led_pin = self.dev_pins['display']['led']
		rst_pin = self.dev_pins['display']['rst']

		self.serial = spi(port=0, device=0, gpio_DC=dc_pin, gpio_RST=rst_pin, bus_speed_hz=32000000,
						  reset_hold_time=0.2, reset_release_time=0.2)
		self.device = ili9341(self.serial, active_low=False, width=320, height=240, gpio_LIGHT=led_pin,
							  rotate=self.rotation)

		# Setup & Start Display Loop Thread 
		display_thread = threading.Thread(target=self._display_loop)
		display_thread.start()

	'''
	============== Graphics / Display / Draw Methods ============= 
	'''

	def _display_clear(self):
		self.device.clear()
		self.device.backlight(False)
		self.device.hide()

	def _display_canvas(self, canvas):
		# Display Image
		self.device.backlight(True)
		self.device.show()
		self.device.display(canvas)
