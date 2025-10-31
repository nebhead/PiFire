#!/usr/bin/env python3
'''
*****************************************
PiFire Display Interface Library
*****************************************

 Description: 
   This library supports using
 the ST7789V display with resolution.
 This module utilizes the a forked/experimental 
 library to interface this display.
 (https://github.com/mander1000/st7789-python)
 As such, your mileage may vary.  

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

	def __init__(self, dev_pins, buttonslevel='HIGH', rotation=0, units='F', config={}):
		self.config = config
		super().__init__(dev_pins, buttonslevel, rotation, units, config)

	def _init_display_device(self):
		# Init Device
		dc_pin = self.dev_pins['display']['dc']
		bl_pin = self.dev_pins['display']['led']
		rst_pin = self.dev_pins['display']['rst']
		spi_device = self.config.get('spi_device', 0)

		self.device = ST7789.ST7789(
			0, # PORT
			spi_device, # SPI Device Number (0 or 1)
			dc_pin, # DC Pin
			spi_cs=spi_device,
			backlight=bl_pin,
			rst=rst_pin,
			width=320,
			height=240,
			rotation=self.rotation,
			spi_speed_hz=60 * 1000 * 1000,
			variant=2 # VARIANT_ST7789V
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
		self.device.display(canvas.convert(mode="RGB"))
