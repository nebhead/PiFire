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
from gpiozero import Button

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
		# Init GPIO for button input, setup callbacks: Uncomment to utilize GPIO input
		self.up = self.dev_pins['input']['up_clk'] 		# UP - GPIO16
		self.down = self.dev_pins['input']['down_dt']	# DOWN - GPIO20
		self.enter = self.dev_pins['input']['enter_sw'] # ENTER - GPIO21
		self.debounce_ms = 500  # number of milliseconds to debounce input
		self.input_event = None
		self.input_counter = 0

		# ==== Buttons Setup =====
		self.pull_up = self.buttonslevel == 'HIGH'

		self.up_button = Button(pin=self.up, pull_up=self.pull_up, hold_time=0.25, hold_repeat=True)
		self.down_button = Button(pin=self.down, pull_up=self.pull_up, hold_time=0.25, hold_repeat=True)
		self.enter_button = Button(pin=self.enter, pull_up=self.pull_up)

		# Init Menu Structures
		self._init_menu()
		
		self.up_button.when_pressed = self._up_callback
		self.down_button.when_pressed = self._down_callback
		self.enter_button.when_pressed = self._enter_callback
		self.up_button.when_held = self._up_callback
		self.down_button.when_held = self._down_callback

	'''
	============== Input Callbacks ============= 
	'''
	def _enter_callback(self):
		self.input_event='ENTER'

	def _up_callback(self, held=False):
		self.input_event='UP'

	def _down_callback(self, held=False):
		self.input_event='DOWN'

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
		Called to detect input events from buttons.
		"""
		command = self.input_event  # Save to variable to prevent spurious changes 
		if command:
			self.display_timeout = None  # If something is being displayed i.e. text, network, splash then override this

			if command not in ['UP', 'DOWN', 'ENTER']:
				return

			self.display_command = None
			self.display_data = None
			self.input_event=None
			self.menu_active = True
			self.menu_time = time.time()
			self._menu_display(command)
			self.input_counter = 0