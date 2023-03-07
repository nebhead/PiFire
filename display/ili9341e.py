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
import time
import threading
from luma.core.interface.serial import spi
from luma.lcd.device import ili9341
from display.base_240x320 import DisplayBase
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
		led_pin = self.dev_pins['display']['led']
		rst_pin = self.dev_pins['display']['rst']

		self.serial = spi(port=0, device=0, gpio_DC=dc_pin, gpio_RST=rst_pin, bus_speed_hz=32000000,
						  reset_hold_time=0.2, reset_release_time=0.2)
		self.device = ili9341(self.serial, active_low=False, width=320, height=240, gpio_LIGHT=led_pin,
							  rotate=self.rotation)

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
		self.device.clear()
		self.device.backlight(False)
		self.device.hide()

	def _display_canvas(self, canvas):
		# Display Image
		self.device.backlight(True)
		self.device.show()
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
