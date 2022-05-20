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

	def __init__(self, buttonslevel='HIGH', rotation=0, units='F'):
		# Init Global Variables and Constants
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
		self.WIDTH = 128
		self.HEIGHT = 64

	def _init_display_device(self):
		# Setup & Start Display Loop Thread 
		display_thread = threading.Thread(target=self._display_loop)
		display_thread.start()

	def _display_loop(self):
		# Init Device
		pygame.init()
		# set the pygame window name 
		pygame.display.set_caption('PiFire Device Display')
		# Create Display Surface
		self.display_surface = pygame.display.set_mode(size=(self.WIDTH, self.HEIGHT), flags=pygame.SHOWN)
		self.displaycommand = 'splash'

		'''
		Main display loop
		'''
		while True:
			pygame.time.delay(100)
			events = pygame.event.get()  # Gets events (required for keypresses to be registered)

			''' Normal display loop'''
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

			if self.displaycommand == 'network':
				self.displayactive = True
				s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
				s.connect(("8.8.8.8", 80))
				networkip = s.getsockname()[0]
				if (networkip != ''):
					self._display_network(networkip)
					self.displaytimeout = time.time() + 30
					self.displaycommand = None
				else:
					self.display_text("No IP Found")

			if self.displayactive:
				if not self.displaytimeout:
					if (self.in_data is not None) and (self.status_data is not None):
						self._display_current(self.in_data, self.status_data)

	'''
	============== Graphics / Display / Draw Methods ============= 
	'''
	def _init_assets(self): 
		self._init_splash()

	def _init_splash(self):
		self.splash = Image.open('color-boot-splash.png') \
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
		(font_width, font_height) = font.getsize(self.displaydata)
		draw.text((self.WIDTH // 2 - font_width // 2, self.HEIGHT // 2 - font_height // 2), self.displaydata, font=font, fill=255)

		# Convert to PyGame and Display
		strFormat = img.mode
		size = img.size
		raw_str = img.tobytes("raw", strFormat)

		self.display_image = pygame.image.fromstring(raw_str, size, strFormat)

		self.display_surface.fill((255,255,255))
		self.display_surface.blit(self.display_image, (0, 0))

		pygame.display.update()

	def _display_network(self, networkip):
		# Create canvas
		img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=(255, 255, 255))
		img_qr = qrcode.make('http://' + networkip)
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
		if(self.units == 'F'):
			font = ImageFont.truetype("impact.ttf", 42)
		else:
			font = ImageFont.truetype("impact.ttf", 38)
		text = str(in_data['GrillTemp'])[:5]
		(font_width, font_height) = font.getsize(text)
		draw.text((self.WIDTH//2 - font_width//2,0), text, font=font, fill=(255,255,255))

		# Active Outputs F = Fan, I = Igniter, A = Auger (Upper Left)
		font = ImageFont.truetype("FA-Free-Solid.otf", 24)
		if(status_data['outpins']['fan']==0):
			text = '\uf863'
			draw.text((0, 0), text, font=font, fill=(255,255,255))
		if(status_data['outpins']['igniter']==0):
			text = '\uf46a'
			(font_width, font_height) = font.getsize(text)
			draw.text((0, 5 + (64//2 - font_height//2)), text, font=font, fill=(255,255,255))
		if(status_data['outpins']['auger']==0):
			text = '\uf101'
			(font_width, font_height) = font.getsize(text)
			draw.text((128 - font_width, 5 + (64//2 - font_height//2)), text, font=font, fill=(255,255,255))
		# Current Mode (Bottom Left)
		font = ImageFont.truetype("trebuc.ttf", 18)
		text = status_data['mode'] + ' Mode'
		(font_width, font_height) = font.getsize(text)
		draw.text((128//2 - font_width//2, 64 - font_height), text, font=font, fill=(255,255,255))
		# Notification Indicator (Upper Right)
		font = ImageFont.truetype("FA-Free-Solid.otf", 24)
		text = ' '
		for item in status_data['notify_req']:
			if status_data['notify_req'][item] == True:
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
		self.displaycommand = 'network'
