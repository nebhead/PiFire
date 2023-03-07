#!/usr/bin/env python3
'''
*****************************************
PiFire Display Interface Library
*****************************************

 Description: 
   This library supports using 
 the SSD1306 display with 64Hx128W resolution.
 This module utilizes Luma.LCD to interface 
 this display. This module also utilizes  
 buttons for input. 

*****************************************
'''

'''
 Imported Libraries
'''
import time
import socket
import qrcode
import threading
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306
from PIL import Image, ImageDraw, ImageFont
from common import read_control, write_control  # Common Library for WebUI and Control Program
from gpiozero import Button

'''
Display class definition
'''
class Display:

	def __init__(self, dev_pins, buttonslevel='HIGH', rotation=0, units='F'):
		# Init Global Variables and Constants
		self.dev_pins = dev_pins
		self.buttonslevel = buttonslevel
		self.units = units
		self.display_active = False
		self.in_data = None
		self.status_data = None
		self.display_timeout = None
		self.display_command = 'splash'

		# Init Display Device, Input Device, Assets
		self._init_globals()
		self._init_assets() 
		self._init_input()
		self._init_display_device()

	def _init_globals(self):
		# Init constants and variables 
		self.WIDTH = 128
		self.HEIGHT = 64
		self.SIZE = (128, 64)
		self.DEVICE_MODE = 1

	def _init_display_device(self):
		# Init Device
		self.serial = i2c(port=1, address=0x3C)
		self.device = ssd1306(self.serial)

		# Setup & Start Display Loop Thread 
		display_thread = threading.Thread(target=self._display_loop)
		display_thread.start()

	def _init_input(self):
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

	def _init_menu(self):
		self.menu_active = False
		self.menu_time = 0
		self.menu_item = ''

		self.menu = {}

		self.menu['inactive'] = {
			# List of options for the 'inactive' menu.  This is the initial menu when smoker is not running.
			'Startup': {
				'displaytext': 'Startup',
				'icon': '\uf04b'  # FontAwesome Play Icon
			},
			'Monitor': {
				'displaytext': 'Monitor',
				'icon': '\uf530'  # FontAwesome Glasses Icon
			},
			'Stop': {
				'displaytext': 'Stop',
				'icon': '\uf04d'  # FontAwesome Stop Icon
			},
			'Network': {
				'displaytext': 'IP QR Code',
				'icon': '\uf1eb'  # FontAwesome Wifi Icon
			}
		}

		self.menu['active'] = {
			# List of options for the 'active' menu.  This is the second level menu of options while running.
			'Shutdown': {
				'displaytext': 'Shutdown',
				'icon': '\uf11e'  # FontAwesome Finish Icon
			},
			'Hold': {
				'displaytext': 'Hold',
				'icon': '\uf76b'  # FontAwesome Temperature Low Icon
			},
			'Smoke': {
				'displaytext': 'Smoke',
				'icon': '\uf0c2'  # FontAwesome Cloud Icon
			},
			'Stop': {
				'displaytext': 'Stop',
				'icon': '\uf04d'  # FontAwesome Stop Icon
			},
			'SmokePlus': {
				'displaytext': 'Toggle Smoke+',
				'icon': '\uf0c2'  # FontAwesome Cloud Icon
			},
			'Network': {
				'displaytext': 'IP QR Code',
				'icon': '\uf1eb'  # FontAwesome Wifi Icon
			}
		}
		self.menu['current'] = {}
		self.menu['current']['mode'] = 'none'  # Current Menu Mode (inactive, active)
		self.menu['current']['option'] = 0  # Current option in current mode

	def _display_loop(self):
		"""
		Main display loop
		"""
		while True:
			self._event_detect()

			if self.display_timeout:
				if time.time() > self.display_timeout:
					self.display_command = 'clear'

			if self.display_command == 'clear':
				self.display_active = False
				self.display_timeout = None
				self.display_command = None
				self._display_clear()

			if self.display_command == 'splash':
				self.display_active = True
				self._display_splash()
				self.display_timeout = time.time() + 3
				self.display_command = None
				time.sleep(3) # Hold splash screen for 3 seconds

			if self.display_command == 'text':
				self.display_active = True
				self._display_text()
				self.display_command = None
				self.display_timeout = time.time() + 10

			if self.display_command == 'network':
				self.display_active = True
				s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
				s.connect(("8.8.8.8", 80))
				network_ip = s.getsockname()[0]
				if network_ip != '':
					self._display_network(network_ip)
					self.display_timeout = time.time() + 30
					self.display_command = None
				else:
					self.display_text("No IP Found")

			if self.menu_active and not self.display_timeout:
				if time.time() - self.menu_time > 5:
					self.menu_active = False
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					self.display_command = 'clear'
			elif not self.display_timeout and self.display_active:
				if self.in_data is not None and self.status_data is not None:
					self._display_current(self.in_data, self.status_data)
			
			time.sleep(0.1)

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
	def _init_assets(self): 
		self._init_splash()

	def _init_splash(self):
		self.splash = Image.open('static/img/display/color-boot-splash.png') \
			.transform(self.SIZE, Image.AFFINE, (1, 0, 0, 0, 1, 0), Image.BILINEAR) \
			.convert("L")  # \ .convert(self.DEVICE_MODE)
		self.splashSize = self.splash.size

	def _display_clear(self):
		self.device.clear()

	def _display_splash(self):
		screen = Image.new('1', (self.WIDTH, self.HEIGHT), color=0)
		screen.paste(self.splash, (32, 0, self.splashSize[0]+32, self.splashSize[1]))
		self.device.display(screen)

	def _display_text(self):
		with canvas(self.device) as draw:
			font = ImageFont.truetype("impact.ttf", 42)
			(font_width, font_height) = font.getsize(self.display_data)
			draw.text((128//2 - font_width//2, 64//2 - font_height//2), self.display_data, font=font, fill=255)


	def _display_network(self, network_ip):
		# Create canvas
		img = Image.new('1', (self.WIDTH, self.HEIGHT), color=1)
		img_qr = qrcode.make('http://' + network_ip)
		img_qr_width, img_qr_height = img_qr.size
		img_qr_width *= 2
		img_qr_height *= 2
		w = min(self.WIDTH, self.HEIGHT)
		new_image = img_qr.resize((w, w))
		position = (int((self.WIDTH/2)-(w/2)), 0)
		img.paste(new_image, position)
		# Display Image
		self.device.display(img)

	def _display_current(self, in_data, status_data):
		with canvas(self.device) as draw:
			# Grill Temperature (Large Centered) 
			if self.units == 'F':
				font = ImageFont.truetype("impact.ttf", 42)
			else:
				font = ImageFont.truetype("impact.ttf", 38)
			label = list(in_data['probe_history']['primary'].keys())[0]
			text = str(in_data['probe_history']['primary'][label])[:5]
			(font_width, font_height) = font.getsize(text)
			draw.text((128//2 - font_width//2,0), text, font=font, fill=255)
			# Active Outputs F = Fan, I = Igniter, A = Auger (Upper Left)
			font = ImageFont.truetype("static/font/FA-Free-Solid.otf", 24)
			if status_data['outpins']['fan']:
				text = '\uf863'
				draw.text((0, 0), text, font=font, fill=255)
			if status_data['outpins']['igniter']:
				text = '\uf46a'
				(font_width, font_height) = font.getsize(text)
				draw.text((0, 5 + (64//2 - font_height//2)), text, font=font, fill=255)
			if status_data['outpins']['auger']:
				text = '\uf101'
				(font_width, font_height) = font.getsize(text)
				draw.text((128 - font_width, 5 + (64//2 - font_height//2)), text, font=font, fill=255)
			# Current Mode (Bottom Left)
			font = ImageFont.truetype("trebuc.ttf", 18)
			text = status_data['mode'] + ' Mode'
			(font_width, font_height) = font.getsize(text)
			draw.text((128//2 - font_width//2, 64 - font_height), text, font=font, fill=255)
			# Notification Indicator (Upper Right)
			font = ImageFont.truetype("static/font/FA-Free-Solid.otf", 24)
			text = ' '
			for index, item in enumerate(status_data['notify_data']):
				if item['req'] and item['type'] != 'hopper':
					text = '\uf0f3'
			(font_width, font_height) = font.getsize(text)
			draw.text((128 - font_width, 0), text, font=font, fill=255)

	'''
	 ====================== Input & Menu Code ========================
	'''
	def _event_detect(self):
		"""
		Called to detect input events from buttons, encoder, touch, etc.
		"""
		if self.input_event:
			command = self.input_event  # Put into variable, just in case an interrupt changes this value spuriously
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

	def _menu_display(self, action):
		self.display_active = True
		# If menu is not currently being displayed, check mode and draw menu
		if self.menu['current']['mode'] == 'none':
			control = read_control()
			# If in an inactive mode
			if control['mode'] == 'Stop' or control['mode'] == 'Error' or control['mode'] == 'Monitor':
				self.menu['current']['mode'] = 'inactive'
			else:  # Use the active menu
				self.menu['current']['mode'] = 'active'
			self.menu['current']['option'] = 0 # Set the menu option to the very first item in the list 
		# If selecting the 'grill_hold_value', take action based on button press was
		elif self.menu['current']['mode'] == 'grill_hold_value':
			if self.units == 'F':
				stepValue = 5  # change in temp each time button pressed 
				minTemp = 120 # minimum temperature set for hold
				maxTemp = 500 # maximum temperature set for hold
			else:
				stepValue = 2  # change in temp each time button pressed 
				minTemp = 50 # minimum temperature set for hold
				maxTemp = 260 # maximum temperature set for hold

			# Speed up step count if input is faster
			if self.input_counter < 3:
				pass
			elif self.input_counter < 7: 
				stepValue *= 4
			else:
				stepValue *= 6 

			if action == 'DOWN':
				self.menu['current']['option'] -= stepValue	# Step down by stepValue degrees
				if self.menu['current']['option'] <= minTemp:
					self.menu['current']['option'] = maxTemp # Roll over to maxTemp if you go less than 120. 
			elif action == 'UP':
				self.menu['current']['option'] += stepValue	# Step up by stepValue degrees
				if self.menu['current']['option'] > maxTemp:
					self.menu['current']['option'] = minTemp # Roll over to minTemp if you go greater than 500. 
			elif action == 'ENTER':
				control = read_control()
				control['primary_setpoint'] = self.menu['current']['option']
				control['updated'] = True
				control['mode'] = 'Hold'
				write_control(control, origin='display')
				self.menu['current']['mode'] = 'none'
				self.menu['current']['option'] = 0
				self.menu_active = False
				self.menu_time = 0
				self.clear_display()
		# If selecting either active menu items or inactive menu items, take action based on what the button press was
		else: 
			if action == 'DOWN':
				self.menu['current']['option'] -= 1
				if self.menu['current']['option'] < 0: # Check to make sure we haven't gone past 0
					self.menu['current']['option'] = len(self.menu[self.menu['current']['mode']])-1
				temp_value = self.menu['current']['option']
				temp_mode = self.menu['current']['mode']
				index = 0
				selected = 'undefined'
				for item in self.menu[temp_mode]:
					if index == temp_value:
						selected = item 
						break
					index += 1
			elif action == 'UP':
				self.menu['current']['option'] += 1
				# Check to make sure we haven't gone past the end of the menu
				if self.menu['current']['option'] == len(self.menu[self.menu['current']['mode']]):
					self.menu['current']['option'] = 0
				temp_value = self.menu['current']['option']
				temp_mode = self.menu['current']['mode']
				index = 0
				selected = 'undefined'
				for item in self.menu[temp_mode]:
					if index == temp_value:
						selected = item 
						break
					index += 1
			elif action == 'ENTER':
				index = 0
				selected = 'undefined'
				for item in self.menu[self.menu['current']['mode']]:
					if index == self.menu['current']['option']:
						selected = item 
						break
					index += 1
				# Inactive Mode Items
				if selected == 'Startup':
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					self.menu_active = False
					self.menu_time = 0
					control = read_control()
					control['updated'] = True
					control['mode'] = 'Startup'
					write_control(control, origin='display')
				elif selected == 'Monitor':
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					self.menu_active = False
					self.menu_time = 0
					control = read_control()
					control['updated'] = True
					control['mode'] = 'Monitor'
					write_control(control, origin='display')
				elif selected == 'Stop':
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					self.menu_active = False
					self.menu_time = 0
					self.clear_display()
					control = read_control()
					control['updated'] = True
					control['mode'] = 'Stop'
					write_control(control, origin='display')
				# Active Mode
				elif selected == 'Shutdown':
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					self.menu_active = False
					self.menu_time = 0
					self.clear_display()
					control = read_control()
					control['updated'] = True
					control['mode'] = 'Shutdown'
					write_control(control, origin='display')
				elif selected == 'Hold':
					self.menu['current']['mode'] = 'grill_hold_value'
					if self.units == 'F':
						self.menu['current']['option'] = 225  # start at 225 for F
					else: 
						self.menu['current']['option'] = 100  # start at 100 for C
				elif selected == 'Smoke':
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					self.menu_active = False
					self.menu_time = 0
					self.clear_display()
					control = read_control()
					control['updated'] = True
					control['mode'] = 'Smoke'
					write_control(control, origin='display')
				elif selected == 'SmokePlus':
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					self.menu_active = False
					self.menu_time = 0
					self.clear_display()
					control = read_control()
					if control['s_plus']:
						control['s_plus'] = False
					else:
						control['s_plus'] = True
					write_control(control, origin='display')
				elif selected == 'Network':
					self.display_network()

		if self.menu['current']['mode'] == 'grill_hold_value':
			with canvas(self.device) as draw:
				# Grill Temperature (Large Centered) 
				font = ImageFont.truetype("impact.ttf", 42)
				text = str(self.menu['current']['option'])
				(font_width, font_height) = font.getsize(text)
				draw.text((128//2 - font_width//2,0), text, font=font, fill=255)

				# Current Mode (Bottom Center)
				font = ImageFont.truetype("trebuc.ttf", 18)
				text = "Grill Set Point"
				(font_width, font_height) = font.getsize(text)
				draw.text((128//2 - font_width//2, 64 - font_height), text, font=font, fill=255)

				# Up / Down Arrows (Middle Right)
				font = ImageFont.truetype("static/font/FA-Free-Solid.otf", 30)
				text = '\uf0dc' # FontAwesome Icon Sort (Up/Down Arrows)
				(font_width, font_height) = font.getsize(text)
				draw.text(((128 - font_width), (64//2 - font_height//2)), text, font=font, fill=255)
		elif self.menu['current']['mode'] != 'none':
			with canvas(self.device) as draw:
				# Menu Option (Large Top Center) 
				index = 0
				selected = 'undefined'
				for item in self.menu[self.menu['current']['mode']]:
					if index == self.menu['current']['option']:
						selected = item 
						break
					index += 1
				font = ImageFont.truetype("static/font/FA-Free-Solid.otf", 42)
				text = self.menu[self.menu['current']['mode']][selected]['icon']
				(font_width, font_height) = font.getsize(text)
				draw.text((128//2 - font_width//2,0), text, font=font, fill=255)
				# Draw a Plus Icon over the top of the Smoke Icon
				if selected == 'SmokePlus':
					font = ImageFont.truetype("static/font/FA-Free-Solid.otf", 32)
					text = '\uf067' # FontAwesome Icon for PLUS 
					(font_width, font_height) = font.getsize(text)
					draw.text((128//2 - font_width//2,4), text, font=font, fill=0)
				
				# Current Mode (Bottom Center)
				font = ImageFont.truetype("trebuc.ttf", 18)
				text = self.menu[self.menu['current']['mode']][selected]['displaytext']
				(font_width, font_height) = font.getsize(text)
				draw.text((128//2 - font_width//2, 64 - font_height), text, font=font, fill=255)

				# Up / Down Arrows (Middle Right)
				font = ImageFont.truetype("static/font/FA-Free-Solid.otf", 30)
				text = '\uf0dc' # FontAwesome Icon Sort (Up/Down Arrows)
				(font_width, font_height) = font.getsize(text)
				draw.text(((128 - font_width), (64//2 - font_height//2)), text, font=font, fill=255)


	'''
	================ Externally Available Methods ================
	'''

	def display_status(self, in_data, status_data):
		"""
		- Updates the current data for the display loop, if in a work mode
		"""
		self.units = status_data['units']
		self.display_active = True
		self.in_data = in_data 
		self.status_data = status_data 

	def display_splash(self):
		"""
		- Calls Splash Screen
		"""
		self.display_command = 'splash'

	def clear_display(self):
		"""
		- Clear display and turn off backlight
		"""
		self.display_command = 'clear'

	def display_text(self, text):
		"""
		- Display some text
		"""
		self.display_command = 'text'
		self.display_data = text

	def display_network(self):
		"""
		- Display Network IP QR Code
		"""
		self.display_command = 'network'
