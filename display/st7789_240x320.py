#!/usr/bin/env python3
'''
*****************************************
PiFire Display Interface Library
*****************************************

 Description: 
   This library supports using
 the ST7789 display with resolution.
 This module utilizes the Pimoroni libraries
 to interface this display.

*****************************************
'''

'''
 Imported Libraries
'''
import threading
import ST7789 as ST7789
from display.base_240x320 import DisplayBase
from PIL import Image

'''
Display class definition
'''
class Display(DisplayBase):

	def __init__(self, dev_pins, buttonslevel='HIGH', rotation=0, units='F'):
		super().__init__(dev_pins, buttonslevel, rotation, units)

	def _init_display_device(self):
		# Init Device
		dc_pin = self.dev_pins['display']['dc']
		bl_pin = self.dev_pins['display']['led']
		rst_pin = self.dev_pins['display']['rst']

		self.device = ST7789.ST7789(
			port=0,
			cs=0,
			dc=dc_pin,
			backlight=bl_pin,
			rst=rst_pin,
			rotation=self.rotation,
			width=320,
			height=240,
			spi_speed_hz=60 * 1000 * 1000
		)
		self.WIDTH = self.device.width
		self.HEIGHT = self.device.height

		# Setup & Start Display Loop Thread
		display_thread = threading.Thread(target=self._display_loop)
		display_thread.start()

	'''
	============== Graphics / Display / Draw Methods ============= 
	'''

	def _display_clear(self):
		# Create blank canvas
		img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=(0, 0, 0))
		self.device.display(img)
		# Kill the backlight to the display
		self.device.set_backlight(0)

	def _display_canvas(self, canvas):
		# Display canvas to screen for ST7789
		# Turn on Backlight (just in case it was off)
		self.device.set_backlight(1)
		self.device.display(canvas)
