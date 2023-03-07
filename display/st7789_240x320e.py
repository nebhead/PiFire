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
import time
import ST7789 as ST7789
from display.base_240x320 import DisplayBase
from PIL import Image
from pyky040 import pyky040

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

	def _init_input(self):
		self.input_enabled = True
		# Init constants and variables 
		clk_pin = self.dev_pins['input']['up_clk']  	# Clock - GPIO16
		dt_pin = self.dev_pins['input']['down_dt']  	# DT - GPIO20
		sw_pin = self.dev_pins['input']['enter_sw'] 	# Switch - GPIO21
		self.input_event = None
		self.input_counter = 0

		# Init Menu Structures
		self._init_menu()

		# Init Device
		self.encoder = pyky040.Encoder(CLK=clk_pin, DT=dt_pin, SW=sw_pin)
		self.encoder.setup(scale_min=0, scale_max=100, step=1, inc_callback=self._inc_callback,
						   dec_callback=self._dec_callback, sw_callback=self._click_callback, polling_interval=200)

		# Setup & Start Input Thread 
		encoder_thread = threading.Thread(target=self.encoder.watch)
		encoder_thread.start()
		
	'''
	============== Input Callbacks ============= 
	'''
	
	def _click_callback(self):
		self.input_event='ENTER'

	def _inc_callback(self, v):
		self.input_event='UP'
		self.input_counter += 1

	def _dec_callback(self, v):
		self.input_event='DOWN'
		self.input_counter += 1

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

	'''
	 ====================== Input & Menu Code ========================
	'''
	def _event_detect(self):
		"""
		Called to detect input events from encoder
		"""
		command = self.input_event  # Save to variable to prevent spurious changes 
		if command:
			self.display_timeout = None  # If something is being displayed i.e. text, network, splash then override this

			if command != 'ENTER' and self.input_counter == 0:
				return
			else: 
				if command not in ['UP', 'DOWN', 'ENTER']:
					return

				self.display_command = None
				self.display_data = None
				self.input_event=None
				self.menu_active = True
				self.menu_time = time.time()
				self._menu_display(command)
				self.input_counter = 0
