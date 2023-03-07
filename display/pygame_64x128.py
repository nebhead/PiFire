#!/usr/bin/env python3
'''
*****************************************
PiFire Display Interface Library
*****************************************

 Description: This library supports using pygame 
 on your Linux development PC for debug and development 
 purposes. Only works in an graphical desktop 
 environment.  Tested on Ubuntu 20.04.  

*****************************************
'''

'''
 Imported Libraries
'''
import time
import socket
import qrcode
import threading
import pygame 
from PIL import Image, ImageDraw, ImageFont

'''
Display class definition
'''
class Display:

	def __init__(self, dev_pins, buttonslevel='HIGH', rotation=0, units='F'):
		# Init Global Variables and Constants
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
		self.WIDTH = 128
		self.HEIGHT = 64

	def _init_display_device(self):
		# Setup & Start Display Loop Thread 
		display_thread = threading.Thread(target=self._display_loop)
		display_thread.start()

	def _display_loop(self):
		"""
		Main display loop
		"""
		# Init Device
		pygame.init()
		# set the pygame window name 
		pygame.display.set_caption('PiFire Device Display')
		# Create Display Surface
		self.display_surface = pygame.display.set_mode(size=(self.WIDTH, self.HEIGHT), flags=pygame.SHOWN)
		self.display_command = 'splash'

		while True:
			pygame.time.delay(100)
			events = pygame.event.get()  # Gets events (required for key presses to be registered)

			''' Normal display loop'''
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

			if self.display_active:
				if not self.display_timeout:
					if self.in_data is not None and self.status_data is not None:
						self._display_current(self.in_data, self.status_data)

	'''
	============== Graphics / Display / Draw Methods ============= 
	'''
	def _init_assets(self): 
		self._init_splash()

	def _init_splash(self):
		self.splash = Image.open('static/img/display/color-boot-splash.png') \
			.transform((self.WIDTH, self.HEIGHT), Image.AFFINE, (1, 0, 0, 0, 1, 0), Image.BILINEAR) \
			.convert("L") \
			.convert("1")

		self.splashSize = self.splash.size

	def _rounded_rectangle(self, draw, xy, rad, fill=None):
		x0, y0, x1, y1 = xy
		draw.rectangle([(x0, y0 + rad), (x1, y1 - rad)], fill=fill)
		draw.rectangle([(x0 + rad, y0), (x1 - rad, y1)], fill=fill)
		draw.pieslice([(x0, y0), (x0 + rad * 2, y0 + rad * 2)], 180, 270, fill=fill)
		draw.pieslice([(x1 - rad * 2, y1 - rad * 2), (x1, y1)], 0, 90, fill=fill)
		draw.pieslice([(x0, y1 - rad * 2), (x0 + rad * 2, y1)], 90, 180, fill=fill)
		draw.pieslice([(x1 - rad * 2, y0), (x1, y0 + rad * 2)], 270, 360, fill=fill)
		return (draw)

	def _display_clear(self):
		self.display_surface.fill((0,0,0))
		pygame.display.update() 

	def _display_splash(self):
		# Create canvas
		screen = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=0)

		screen.paste(self.splash, (32, 0, self.splashSize[0]+32, self.splashSize[1]))

		# Convert to PyGame and Display
		strFormat = screen.mode
		size = screen.size
		raw_str = screen.tobytes("raw", strFormat)
		self.display_image = pygame.image.fromstring(raw_str, size, strFormat)

		self.display_surface.fill((255,255,255))
		self.display_surface.blit(self.display_image, (0, 0))

		pygame.display.update() 

	def _display_text(self):
		# Create canvas
		img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=(0, 0, 0))

		# Create drawing object
		draw = ImageDraw.Draw(img)

		font = ImageFont.truetype("impact.ttf", 42)
		(font_width, font_height) = font.getsize(self.display_data)
		draw.text((self.WIDTH // 2 - font_width // 2, self.HEIGHT // 2 - font_height // 2), self.display_data,
				  font=font, fill=255)

		# Convert to PyGame and Display
		strFormat = img.mode
		size = img.size
		raw_str = img.tobytes("raw", strFormat)

		self.display_image = pygame.image.fromstring(raw_str, size, strFormat)

		self.display_surface.fill((255,255,255))
		self.display_surface.blit(self.display_image, (0, 0))

		pygame.display.update()

	def _display_network(self, network_ip):
		# Create canvas
		img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=(255, 255, 255))
		img_qr = qrcode.make('http://' + network_ip)
		img_qr_width, img_qr_height = img_qr.size
		img_qr_width *= 2
		img_qr_height *= 2
		w = min(self.WIDTH, self.HEIGHT)
		new_image = img_qr.resize((w, w))
		position = (int((self.WIDTH/2)-(w/2)), 0)
		img.paste(new_image, position)

		# Convert to PyGame and Display
		strFormat = img.mode
		size = img.size
		raw_str = img.tobytes("raw", strFormat)

		self.display_image = pygame.image.fromstring(raw_str, size, strFormat)

		self.display_surface.fill((255,255,255))
		self.display_surface.blit(self.display_image, (0, 0))

		pygame.display.update()

	def _display_current(self, in_data, status_data):
		self.units = status_data['units']
		# Create canvas
		img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=(0, 0, 0))

		# Create drawing object
		draw = ImageDraw.Draw(img)

		# Grill Temperature (Large Centered) 
		if self.units == 'F':
			font = ImageFont.truetype("impact.ttf", 42)
		else:
			font = ImageFont.truetype("impact.ttf", 38)
		label = list(in_data['probe_history']['primary'].keys())[0]
		text = str(in_data['probe_history']['primary'][label])[:5]
		(font_width, font_height) = font.getsize(text)
		draw.text((self.WIDTH//2 - font_width//2,0), text, font=font, fill=(255,255,255))

		# Active Outputs F = Fan, I = Igniter, A = Auger (Upper Left)
		font = ImageFont.truetype("static/font/FA-Free-Solid.otf", 24)
		if status_data['outpins']['fan']:
			text = '\uf863'
			draw.text((0, 0), text, font=font, fill=(255,255,255))
		if status_data['outpins']['igniter']:
			text = '\uf46a'
			(font_width, font_height) = font.getsize(text)
			draw.text((0, 5 + (64//2 - font_height//2)), text, font=font, fill=(255,255,255))
		if status_data['outpins']['auger']:
			text = '\uf101'
			(font_width, font_height) = font.getsize(text)
			draw.text((128 - font_width, 5 + (64//2 - font_height//2)), text, font=font, fill=(255,255,255))
		# Current Mode (Bottom Left)
		font = ImageFont.truetype("trebuc.ttf", 18)
		text = status_data['mode'] + ' Mode'
		(font_width, font_height) = font.getsize(text)
		draw.text((128//2 - font_width//2, 64 - font_height), text, font=font, fill=(255,255,255))
		# Notification Indicator (Upper Right)
		font = ImageFont.truetype("static/font/FA-Free-Solid.otf", 24)
		text = ' '
		for index, item in enumerate(status_data['notify_data']):
			if item['req'] and item['type'] != 'hopper':
				text = '\uf0f3'
		(font_width, font_height) = font.getsize(text)
		draw.text((self.WIDTH - font_width, 0), text, font=font, fill=(255,255,255))

		# Convert to PyGame and Display
		strFormat = img.mode
		size = img.size
		raw_str = img.tobytes("raw", strFormat)

		self.display_image = pygame.image.fromstring(raw_str, size, strFormat)

		self.display_surface.fill((255,255,255))
		self.display_surface.blit(self.display_image, (0, 0))

		pygame.display.update() 

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
