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
import time
import threading
import ST7789 as ST7789  
from PIL import Image, ImageDraw, ImageFont

'''
Display class definition
'''
class Display:

	def __init__(self, dev_pins, buttonslevel='HIGH', rotation=0, units='F'):
		# Init Global Variables and Constants
		self.dev_pins = dev_pins
		self.rotation = rotation
		self.units = units
		self.display_active = False
		self.in_data = None
		self.status_data = None
		self.display_timeout = None
		self.display_command = 'splash'

		# Init Display Device, Input Device, Assets
		self._init_globals()
		self._init_assets() 
		self._init_display_device()

	def _init_globals(self):
		# Init constants and variables 
		pass

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
			spi_speed_hz=80 * 1000 * 1000
		)
		self.WIDTH = self.device.width
		self.HEIGHT = self.device.height

		# Setup & Start Display Loop Thread 
		display_thread = threading.Thread(target=self._display_loop)
		display_thread.start()

	def _display_loop(self):
		"""
		Main display loop
		"""
		while True:
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

			if self.display_active:
				if not self.display_timeout:
					if self.in_data is not None and self.status_data is not None:
						self._display_current(self.in_data, self.status_data)
			
			time.sleep(0.1)

	'''
	============== Graphics / Display / Draw Methods ============= 
	'''
	def _init_assets(self): 
		self._init_splash()

	def _init_splash(self):
		self.splash = Image.open('static/img/display/color-boot-splash.png')

		(self.splash_width, self.splash_height) = self.splash.size
		self.splash_width *= 2
		self.splash_height *= 2

		# Resize the boot-splash
		self.splash = self.splash.resize((self.splash_width, self.splash_height))

	def _display_clear(self):
		# Create blank canvas
		img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=(0, 0, 0))
		self.device.display(img)
		# Kill the backlight to the display
		self.device.set_backlight(0)

	def _display_splash(self):
		img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=(0, 0, 0))
		# Set the position 
		position = ((self.WIDTH - self.splash_width)//2, (self.HEIGHT - self.splash_height)//2)

		# Paste the splash screen onto the canvas
		img.paste(self.splash, position)

		self.device.display(img)

	def _display_text(self):
		# Turn on Backlight (just in case it was off)
		self.device.set_backlight(1)

		# Create canvas
		img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=(0, 0, 0))

		# Create drawing object
		draw = ImageDraw.Draw(img)

		font = ImageFont.truetype("impact.ttf", 42)
		(font_width, font_height) = font.getsize(self.display_data)
		draw.text((self.WIDTH//2 - font_width//2, self.HEIGHT//2 - font_height//2), self.display_data, font=font,
				  fill=255)
		self.device.display(img)

	def _display_current(self, in_data, status_data):
		self.units = status_data['units']
		# Turn on Backlight (just in case it was off)
		self.device.set_backlight(1)

		# Create canvas
		img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=(0, 0, 0))

		# Create drawing object
		draw = ImageDraw.Draw(img)

		# Grill Temperature (Large Centered) 
		if self.units == 'F':
			font = ImageFont.truetype("trebuc.ttf", 128)
		else:
			font = ImageFont.truetype("trebuc.ttf", 80)
		label = list(in_data['probe_history']['primary'].keys())[0]
		text = str(in_data['probe_history']['primary'][label])[:5]
		(font_width, font_height) = font.getsize(text)
		draw.text((self.WIDTH//2 - font_width//2,0), text, font=font, fill=(255,255,255))
		
		# Active Outputs F = Fan (Left), I = Igniter(Center Left), A = Auger (Center Right)
		font = ImageFont.truetype("static/font/FA-Free-Solid.otf", 48)
		if status_data['outpins']['fan']:
			text = '\uf863'
			(font_width, font_height) = font.getsize(text)
			draw.text(( ((self.WIDTH//8)*1) - font_width//2, self.HEIGHT - 96), text, font=font, fill=(0,0,255))
		if status_data['outpins']['igniter']:
			text = '\uf46a'
			(font_width, font_height) = font.getsize(text)
			draw.text(( ((self.WIDTH//8)*3) - font_width//2, self.HEIGHT - 96), text, font=font, fill=(255,200,0))
		if status_data['outpins']['auger']:
			text = '\uf101'
			(font_width, font_height) = font.getsize(text)
			draw.text(( ((self.WIDTH//8)*5) - font_width//2, self.HEIGHT - 96), text, font=font, fill=(0,255,0))

		# Notification Indicator (Right)
		font = ImageFont.truetype("static/font/FA-Free-Solid.otf", 48)
		text = ' '
		for index, item in enumerate(status_data['notify_data']):
			if item['req'] and item['type'] != 'hopper':
				text = '\uf0f3'
		(font_width, font_height) = font.getsize(text)
		draw.text(( ((self.WIDTH//8)*7) - font_width//2, self.HEIGHT - 96), text, font=font, fill=(255,255,0))

		# Current Mode (Bottom Center)
		font = ImageFont.truetype("trebuc.ttf", 36)
		text = status_data['mode'] # + ' Mode'
		(font_width, font_height) = font.getsize(text)
		draw.text((self.WIDTH//2 - font_width//2, self.HEIGHT - font_height - 4), text, font=font, fill=(255,255,255))

		self.device.display(img)

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
		pass