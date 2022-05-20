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

	def __init__(self, buttonslevel='HIGH', rotation=0, units='F'):
		# Init Global Variables and Constants
		self.rotation = rotation
		self.units = units
		self.displayactive = False
		self.in_data = None
		self.status_data = None
		self.displaytimeout = None 
		self.displaycommand = 'splash'

		# Init Display Device, Input Device, Assets
		self._init_globals()
		self._init_assets() 
		self._init_display_device()

	def _init_globals(self):
		# Init constants and variables 
		pass

	def _init_display_device(self):
		# Init Device
		self.device = ST7789.ST7789(
			port=0,
			cs=0, 
			dc=24,
			backlight=5,
			rst=25,
			rotation=self.rotation,
			spi_speed_hz=80 * 1000 * 1000
		)
		self.WIDTH = self.device.width
		self.HEIGHT = self.device.height

		# Setup & Start Display Loop Thread 
		display_thread = threading.Thread(target=self._display_loop)
		display_thread.start()

	def _display_loop(self):
		'''
		Main display loop
		'''
		while True:
			if self.displaytimeout:
				if time.time() > self.displaytimeout:
					self.displaycommand = 'clear'

			if self.displaycommand == 'clear':
				self.displayactive = False
				self.displaytimeout = None 
				self.displaycommand = None
				self._display_clear()

			if self.displaycommand == 'splash':
				self.displayactive = True
				self._display_splash()
				self.displaytimeout = time.time() + 3
				self.displaycommand = None
				time.sleep(3) # Hold splash screen for 3 seconds

			if self.displaycommand == 'text': 
				self.displayactive = True
				self._display_text()
				self.displaycommand = None
				self.displaytimeout = time.time() + 10 

			if self.displayactive:
				if not self.displaytimeout:
					if (self.in_data is not None) and (self.status_data is not None):
						self._display_current(self.in_data, self.status_data)
			
			time.sleep(0.1)

	'''
	============== Graphics / Display / Draw Methods ============= 
	'''
	def _init_assets(self): 
		self._init_splash()

	def _init_splash(self):
		self.splash = Image.open('color-boot-splash.png')

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
		(font_width, font_height) = font.getsize(self.displaydata)
		draw.text((self.WIDTH//2 - font_width//2, self.HEIGHT//2 - font_height//2), self.displaydata, font=font, fill=255)
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
		if(self.units == 'F'):
			font = ImageFont.truetype("trebuc.ttf", 128)
		else:
			font = ImageFont.truetype("trebuc.ttf", 80)
		text = str(in_data['GrillTemp'])[:5]
		(font_width, font_height) = font.getsize(text)
		draw.text((self.WIDTH//2 - font_width//2,0), text, font=font, fill=(255,255,255))
		
		# Active Outputs F = Fan (Left), I = Igniter(Center Left), A = Auger (Center Right)
		font = ImageFont.truetype("FA-Free-Solid.otf", 48)
		if(status_data['outpins']['fan']==0):
			text = '\uf863'
			(font_width, font_height) = font.getsize(text)
			draw.text(( ((self.WIDTH//8)*1) - font_width//2, self.HEIGHT - 96), text, font=font, fill=(0,0,255))
		if(status_data['outpins']['igniter']==0):
			text = '\uf46a'
			(font_width, font_height) = font.getsize(text)
			draw.text(( ((self.WIDTH//8)*3) - font_width//2, self.HEIGHT - 96), text, font=font, fill=(255,200,0))
		if(status_data['outpins']['auger']==0):
			text = '\uf101'
			(font_width, font_height) = font.getsize(text)
			draw.text(( ((self.WIDTH//8)*5) - font_width//2, self.HEIGHT - 96), text, font=font, fill=(0,255,0))

		# Notification Indicator (Right)
		font = ImageFont.truetype("FA-Free-Solid.otf", 48)
		text = ' '
		for item in status_data['notify_req']:
			if status_data['notify_req'][item] == True:
				text = '\uf0f3'
		(font_width, font_height) = font.getsize(text)
		draw.text(( ((self.WIDTH//8)*7) - font_width//2, self.HEIGHT - 96), text, font=font, fill=(255,255,0))

		# Current Mode (Bottom Center)
		font = ImageFont.truetype("trebuc.ttf", 36)
		text = status_data['mode'] #+ ' Mode'
		(font_width, font_height) = font.getsize(text)
		draw.text((self.WIDTH//2 - font_width//2, self.HEIGHT - font_height - 4), text, font=font, fill=(255,255,255))

		self.device.display(img)

	'''
	================ Externally Available Methods ================
	'''

	def display_status(self, in_data, status_data):
		'''
		- Updates the current data for the display loop, if in a work mode 
		'''
		self.units = status_data['units']
		self.displayactive = True
		self.in_data = in_data 
		self.status_data = status_data 

	def display_splash(self):
		''' 
		- Calls Splash Screen 
		'''
		self.displaycommand = 'splash'

	def clear_display(self):
		''' 
		- Clear display and turn off backlight 
		'''
		self.displaycommand = 'clear'

	def display_text(self, text):
		''' 
		- Display some text 
		'''
		self.displaycommand = 'text'
		self.displaydata = text

	def display_network(self):
		''' 
		- Display Network IP QR Code 
		'''
		pass