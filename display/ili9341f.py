'''
*****************************************
PiFire Display Interface Library
*****************************************

 Description: This library supports using ILI9341 TFT Flex Display 
 on the Raspberry Pi. 

*****************************************
'''

'''
 Imported Libraries
'''
import time
#import multiprocessing
import threading
#from pygame import image as PyImage

from luma.core.interface.serial import spi
from luma.lcd.device import ili9341
from gpiozero import Button
from pyky040 import pyky040

from PIL import Image, ImageFilter
from display.base_flex import DisplayBase
from display.flexobject import FlexObject
from display.flexrect import Rect

'''
Dummy backlight class for prototyping 
'''
class DummyBacklight():
	def __init__(self):
		self.brightness = 100
		self.power = True
		self.fade_duration = 1

'''
Display class definition
'''
class Display(DisplayBase):

	def __init__(self, dev_pins, buttonslevel='HIGH', rotation=0, units='F', config={}):
		# Set display profile based on rotation
		self.rotation = config.get('rotation', 0)
		if self.rotation in [0, 2]:
			self.display_profile = 'profile_1'
		else:
			self.display_profile = 'profile_2'
		self.config = config
		super().__init__(dev_pins, buttonslevel, rotation, units, config)
		self.eventLogger.debug('Display Initialized.')

	def _init_display_device(self):
		# Init Device
		dc_pin = self.dev_pins['display']['dc']
		led_pin = self.dev_pins['display']['led']
		rst_pin = self.dev_pins['display']['rst']
		spi_device = self.config.get('spi_device', 0)

		if self.rotation in [0, 2]:
			translated_width = self.WIDTH
			translated_height = self.HEIGHT
		else:
			translated_width = self.HEIGHT
			translated_height = self.WIDTH

		#self.eventLogger.debug(f'Display Rotation: {self.rotation}')
		#self.eventLogger.debug(f'Display Width: {translated_width}')
		#self.eventLogger.debug(f'Display Height: {translated_height}')

		self.serial = spi(port=0, device=spi_device, gpio_DC=dc_pin, gpio_RST=rst_pin, bus_speed_hz=32000000,
						  reset_hold_time=0.2, reset_release_time=0.2)
		self.device = ili9341(self.serial, active_low=False, width=translated_width, height=translated_height, gpio_LIGHT=led_pin,
							  rotate=self.rotation)

		# Setup & Start Display Loop Worker
		display_worker = threading.Thread(target=self._display_loop)
		display_worker.start()

	def _init_input(self):
		self.input_enabled = True
		self.input_event = None
		self.touch_pos = (0,0)
		self.DEBOUNCE = 100  # ms

		if 'touch' in self.config['input_types_supported']:
			# TODO: Implement Touch Input
			self.eventLogger.debug('Touch Initialized.')
		
		if 'button' in self.config['input_types_supported']:
			# Init GPIO for button input, setup callbacks: Uncomment to utilize GPIO input
			self.up = self.dev_pins['input']['up_clk'] 		# UP - GPIO16
			self.down = self.dev_pins['input']['down_dt']	# DOWN - GPIO20
			self.enter = self.dev_pins['input']['enter_sw'] # ENTER - GPIO21
			self.debounce_ms = 500  # number of milliseconds to debounce input
			self.input_counter = 0

			# ==== Buttons Setup =====
			self.pull_up = self.buttonslevel == 'HIGH'

			self.up_button = Button(pin=self.up, pull_up=self.pull_up, hold_time=0.25, hold_repeat=True)
			self.down_button = Button(pin=self.down, pull_up=self.pull_up, hold_time=0.25, hold_repeat=True)
			self.enter_button = Button(pin=self.enter, pull_up=self.pull_up)

			self.up_button.when_pressed = self._up_callback
			self.down_button.when_pressed = self._down_callback
			self.enter_button.when_pressed = self._enter_callback
			self.up_button.when_held = self._up_callback
			self.down_button.when_held = self._down_callback
			self.eventLogger.debug('Buttons Initialized.')
		
		if 'encoder' in self.config['input_types_supported']:
			# Init constants and variables 
			clk_pin = self.dev_pins['input']['up_clk']  	# Clock - GPIO16
			dt_pin = self.dev_pins['input']['down_dt']  	# DT - GPIO20
			sw_pin = self.dev_pins['input']['enter_sw'] 	# Switch - GPIO21
			self.input_event = None
			self.input_counter = 0
			self.last_direction = None
			self.last_movement_time = 0
			self.enter_received = False

			# Init Device
			self.encoder = pyky040.Encoder(CLK=clk_pin, DT=dt_pin, SW=sw_pin)
			self.encoder.setup(scale_min=0, scale_max=100, step=1, inc_callback=self._inc_callback,
							dec_callback=self._dec_callback, sw_callback=self._click_callback, polling_interval=200)

			# Setup & Start Input Thread 
			encoder_thread = threading.Thread(target=self.encoder.watch)
			encoder_thread.start()
			self.eventLogger.debug('Encoder Initialized.')

		if 'none' in self.config['input_types_supported']:
			self.input_enabled = False
			self.eventLogger.debug('Input Disabled.')

	def _display_loop(self):
		"""
		Main display loop worker
		"""
		self.display_loop_active = True

		''' Display the Splash Screen on Startup '''
		self._display_splash()
		time.sleep(self.SPLASH_DELAY * 0.001)
		self._display_clear()

		self.command = None 
		self.display_active = None
		self.display_timeout = None
		self.display_init = True 
		self.display_updated = False

		self.dash_object_list = []

		refresh_data = 0 

		''' Display Loop '''
		while self.display_loop_active:
			''' Fetch display data every 200ms '''
			now = time.time()
			if now - refresh_data > 0.2:
				self._fetch_data()
				refresh_data = now
			
			''' Normal display loop'''
			if self.input_enabled:
				self._event_detect()

			if self.display_active != None: 

				if self.display_timeout:
					if time.time() > self.display_timeout:
						self.display_timeout = None
						self.display_active = None
						self.display_init = True

				if self.display_active == 'home':
					if self.display_init:
						''' Initialize Home Screen '''
						self._build_objects(self.background)
						self.display_init = False
						self.display_updated = True

				elif self.display_active == 'dash':
					if self.display_init:
						''' Initialize Dash Screen '''
						if self.dash_object_list == []:
							self._init_dash()
						self._restore_dash_objects()
						self._update_dash_objects()
						self.display_init = False
						self.display_updated = True
					else:
						self._update_dash_objects()
					self._display_background()

				elif self.display_active is not None:
					if (('menu_' in self.display_active) or ('input_' in self.display_active)) and self.display_init:
						''' Initialize Menu / Input Dialog '''
						self._display_menu_background()
						self._build_objects(self.menu_background)
						self.display_init = False
						self.display_updated = True
					
				''' Draw all objects. Perform any animations that need to be displayed. '''
				self._draw_objects()

				if self.display_updated:
					self._display_canvas()
					self.display_update = False 

			else:
				if self.display_init:
					self._display_clear()
					self.display_init = False
					if not self.HOME_ENABLED:
						self.display_active = 'dash'
						self._init_dash()
						self.display_active = None

			time.sleep(1 / self.FRAMERATE)

		#self.eventLogger.debug('Display Loop Ended.')

	'''
	============== Graphics / Display / Draw Methods ============= 
	'''

	def _wake_display(self):
		#self.eventLogger.debug('_wake_display() called.')
		self.device.backlight(True)
		self.device.show()
	
	def _sleep_display(self):
		self.device.backlight(False)
		self.device.hide()

	def _display_clear(self):
		#self.eventLogger.debug('_display_clear() called.')
		self.device.clear()
		self.device.backlight(False)
		self.device.hide()

	def _display_canvas(self):
		# Display Image
		self.device.backlight(True)
		self.device.show()
		self.device.display(self.display_canvas.convert(mode="RGB"))

	def _display_background(self):
		self.display_canvas.paste(self.background, (0,0))

	def _capture_background(self):
		self.menu_background = self.display_canvas.filter(ImageFilter.GaussianBlur(radius = 5))

	def _display_menu_background(self):
		self.display_canvas.paste(self.menu_background, (0,0))

	def _init_dash(self):
		self._init_framework()
		self._configure_dash()
		self._build_objects(None)
		self._build_dash_map()
		self._store_dash_objects()
	
	'''
	 ====================== Input & Menu Code ========================
	'''
	def _debounce(self):
		time.sleep(self.DEBOUNCE * 0.001)

	''' Button Callbacks '''
	
	def _enter_callback(self):
		self.input_event='ENTER'
		#self.eventLogger.debug('Enter Button Pressed.')

	def _up_callback(self, held=False):
		self.input_event='UP'
		#self.eventLogger.debug('Up Button Pressed.')

	def _down_callback(self, held=False):
		self.input_event='DOWN'
		#self.eventLogger.debug('Down Button Pressed.')

	''' Encoder Callbacks '''

	def _click_callback(self):
		self.input_event = 'ENTER'
		self.enter_received = True

	def _inc_callback(self, v):
		current_time = time.time()
		if self.last_direction is None or self.last_direction == 'DOWN' or current_time - self.last_movement_time > 0.5:
			if not self.enter_received:
				self.input_event = 'DOWN'
				self.input_counter += 1
			self.last_direction = 'DOWN'
			self.last_movement_time = current_time
			if time.time() - self.last_movement_time < 0.3:
				if self.enter_received:
					self.enter_received = False
					return  # if enter command is received during this time, execute the enter command and not the down

	def _dec_callback(self, v):
		current_time = time.time()
		if self.last_direction is None or self.last_direction == 'UP' or current_time - self.last_movement_time > 0.5:
			if not self.enter_received:
				self.input_event = 'UP'
				self.input_counter += 1
			self.last_direction = 'UP'
			self.last_movement_time = current_time
			if time.time() - self.last_movement_time < 0.3:
				if self.enter_received:
					self.enter_received = False
					return  # if enter command is received during this time, execute the enter command and not the up

	def _event_detect(self):
		"""
		Called to detect input events from buttons, encoder, touch, etc.
		"""
		user_input = self.input_event  # Save to variable to prevent spurious changes 
		self.command = None
		if user_input:
			#self.eventLogger.debug(f'User input: {user_input}')
			if self.display_timeout is not None:
				self.display_timeout = time.time() + self.TIMEOUT
			if user_input not in ['UP', 'DOWN', 'ENTER', 'TOUCH']:
				self.input_event = None 
				self.touch_pos = (0,0)
				return
			elif user_input == 'TOUCH' and self.input_touch:
				self._process_touch()
			elif user_input in ['UP', 'DOWN', 'ENTER'] and (self.input_button or self.input_encoder):
				self._process_button()

			# Clear the input event and touch_pos
			self.input_event = None
			self.touch_pos = (0,0)

	def _process_button(self):
		self._debounce()
		if self.display_active:
			if 'dash' in self.display_active:
				'''
				Process dash button events
				'''
				self._capture_background()
				self._store_dash_objects()
				if self.status_data['mode'] == 'Stop':
					self.display_active = 'menu_main'
				elif self.status_data['mode'] in ['Startup', 'Reignite', 'Smoke', 'Hold', 'Shutdown']:
					self.display_active = 'menu_main_active_normal'
				elif self.status_data['mode'] == 'Monitor':
					self.display_active = 'menu_main_active_monitor' 
				elif self.status_data['mode'] == 'Recipe':
					self.display_active = 'menu_main_active_recipe'
				else:
					self.display_active = 'menu_main'
				self.display_init = True
			elif 'menu_' in self.display_active:
				'''
				Process menu button events
				'''
				objectData = self.display_object_list[0].get_object_data()
				button_selected = objectData['data'].get('button_selected', None)
				button_list = objectData.get('button_list', [])

				if button_selected is not None and button_list != []:
					if self.input_event == 'UP':
						if button_selected <= 1:
							objectData['data']['button_selected'] = len(button_list) - 1  # Note: button_list has extra close_menu entry at index 0 
						else:
							objectData['data']['button_selected'] -= 1
						self.display_object_list[0].update_object_data(updated_objectData = objectData)
					elif self.input_event == 'DOWN':
						if len(button_list) - 1 > button_selected:
							objectData['data']['button_selected'] += 1
						else:
							objectData['data']['button_selected'] = 1
						self.display_object_list[0].update_object_data(updated_objectData = objectData)
					elif self.input_event == 'ENTER':
						if 'cmd_' in objectData['button_list'][button_selected]:
							self.command = objectData['button_list'][button_selected]
							if objectData.get('button_value', False):
								self.command_data = objectData['button_value'][button_selected]
							else:
								self.command_data = None 
							self._command_handler()
						elif objectData['button_list'][button_selected] == 'menu_close':
							self.display_active = 'dash'
							self.display_init = True
						elif ('menu_' in objectData['button_list'][button_selected]) or ('input_' in objectData['button_list'][button_selected]):
							if self.display_active == 'dash':
								self._capture_background()
								self._store_dash_objects()
							if ('input_' in self.display_active) and ('input_' in objectData['button_list'][button_selected]) and ('button_value' in list(objectData.keys())):
								self.input_origin = objectData['button_value'][button_selected]
							self.display_active = objectData['button_list'][button_selected]
							self.display_init = True
						elif 'button_' in button_selected:
							objectData['data']['input'] = objectData['button_list'][button_selected].replace('button_', '')
							self.display_object_list[0].update_object_data(updated_objectData=objectData)
				elif self.input_event == 'ENTER' and button_selected == None:
					self.display_active = 'dash'
					self.display_init = True
			elif 'input_' in self.display_active:
				'''
				Process input button events
				'''
				objectData = self.display_object_list[0].get_object_data()
				if self.input_event == 'UP':
					objectData['data']['input'] = 'up'
					self.display_object_list[0].update_object_data(updated_objectData=objectData)
				if self.input_event == 'DOWN':
					objectData['data']['input'] = 'down'
					self.display_object_list[0].update_object_data(updated_objectData=objectData)
				if self.input_event == 'ENTER':
					self.command = objectData['command']
					self._command_handler()
					self.display_active = 'dash'
					self.display_init = True
		else:
			'''
			Wake the display & go to home/dash
			'''					
			self._wake_display()
			self.display_active = 'home' if self.HOME_ENABLED else 'dash'
			self.display_init = True
			self.display_timeout = time.time() + self.TIMEOUT

	def _process_touch(self):
		if self.display_active:
			'''
			Loop through current displayed objects and check for touch collisions
			'''
			for pointer, object in enumerate(self.display_object_list):
				objectData = object.get_object_data()
				for index, touch_area in enumerate(objectData['touch_areas']):
					if touch_area.collidepoint(self.touch_pos):
						#print(f'You touched {objectData["button_list"][index]}.')
						if 'cmd_' in objectData['button_list'][index]:
							self.command = objectData['button_list'][index]
							if objectData.get('button_value', False):
								self.command_data = objectData['button_value'][index]
							else:
								self.command_data = None 
							self._command_handler()
						elif objectData['button_list'][index] == 'menu_close':
							self.display_active = 'dash'
							self.display_init = True
						elif ('menu_' in objectData['button_list'][index]) or ('input_' in objectData['button_list'][index]):
							if self.display_active == 'dash':
								self._capture_background()
								self._store_dash_objects()
							if ('input_' in objectData['button_list'][index]) and ('button_value' in list(objectData.keys())):
								self.input_origin = objectData['button_value'][index]
							self.display_active = objectData['button_list'][index]
							self.display_init = True
						elif 'button_' in objectData['button_list'][index]:
							objectData['data']['input'] = objectData['button_list'][index].replace('button_', '')
							self.display_object_list[pointer].update_object_data(updated_objectData=objectData)

		else:
			'''
			Wake the display & go to home/dash
			'''					
			self._wake_display()
			self.display_active = 'home' if self.HOME_ENABLED else 'dash'
			self.display_init = True
			self.display_timeout = time.time() + self.TIMEOUT
	