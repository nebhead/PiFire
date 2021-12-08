#!/usr/bin/env python3

# *****************************************
# PiFire Display Interface Library
# *****************************************
#
# Description: This library supports using the 
# ST7789 SPI display with the __Pimoroni__ libraries.
#
# Dependancies: (Pimoroni ST7789 Library, Pillow, Numpy)
# sudo apt-get update
# sudo apt-get install python3-rpi.gpio python3-spidev python3-pip python3-pil python3-numpy
# sudo pip3 install st7789
#
# *****************************************

# *****************************************
# Imported Libraries
# *****************************************
import ST7789 as ST7789  
from PIL import Image, ImageDraw, ImageFont
import datetime
import time

class Display:

	def __init__(self, units='F'):
		self.device = ST7789.ST7789(
			port=0,
			cs=0, 
			dc=24,
			backlight=5,
			rst=25,
			rotation=0,
			spi_speed_hz=80 * 1000 * 1000
		)

		self.units = units 
		
		self.WIDTH = self.device.width
		self.HEIGHT = self.device.height

		self.DisplaySplash()
		time.sleep(3) # Keep the splash up for three seconds on boot-up - you can certainly disable this if you want 

	def DisplayStatus(self, in_data, status_data):
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

		try:
			self.device.display(img)
		except:
			now = str(datetime.datetime.now())
			now = now[0:19] # Truncate the microseconds
			print(str(now) + ' ERROR displaying status.')

	def DisplaySplash(self):
		# Create canvas
		img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=(0, 0, 0))

		splash = Image.open('color-boot-splash.png')

		(splash_width, splash_height) = splash.size
		splash_width *= 2
		splash_height *= 2

		# Resize the boot-splash
		splash = splash.resize((splash_width, splash_height))

		# Set the position 
		position = ((self.WIDTH - splash_width)//2, (self.HEIGHT - splash_height)//2)

		# Paste the splash screen onto the canvas
		img.paste(splash, position)

		self.device.display(img)

	def ClearDisplay(self):
		try:
			# Create blank canvas
			img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=(0, 0, 0))
			self.device.display(img)
			# Kill the backlight to the display
			self.device.set_backlight(0)
		except:
			now = str(datetime.datetime.now())
			now = now[0:19] # Truncate the microseconds
			print(str(now) + ' Error clearing display.')

	def DisplayText(self, text):
		# Turn on Backlight (just in case it was off)
		self.device.set_backlight(1)

		# Create canvas
		img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=(0, 0, 0))

		# Create drawing object
		draw = ImageDraw.Draw(img)

		font = ImageFont.truetype("impact.ttf", 42)
		(font_width, font_height) = font.getsize(text)
		draw.text((self.WIDTH//2 - font_width//2, self.HEIGHT//2 - font_height//2), text, font=font, fill=255)
		try: 
			self.device.display(img)
		except:
			now = str(datetime.datetime.now())
			now = now[0:19] # Truncate the microseconds
			print(str(now) + ' Error displaying text.')

	def EventDetect(self):
		return()