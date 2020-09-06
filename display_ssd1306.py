#!/usr/bin/env python3

# *****************************************
# PiFire Display Interface Library
# *****************************************
#
# Description: This library supports using the SSD1306 as a display.
#
# *****************************************

# *****************************************
# Imported Libraries
# *****************************************
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306
from PIL import Image, ImageDraw, ImageFont
import datetime
import time

class Display:

	def __init__(self):
		self.serial = i2c(port=1, address=0x3C)
		self.device = ssd1306(self.serial)
		self.DisplaySplash()
		time.sleep(3) # Keep the splash up for three seconds on boot-up - you can certainly disable this if you want 

	def DisplayTemp(self, temp):
		with canvas(self.device) as draw:
			font = ImageFont.truetype("impact.ttf", 42)
			text = str(temp)[:5]
			(font_width, font_height) = font.getsize(text)
			try:
				draw.text((128//2 - font_width//2, 64//2 - font_height//2), text, font=font, fill=255)
			except:
				now = str(datetime.datetime.now())
				now = now[0:19] # Truncate the microseconds
				print(str(now) + ' Error displaying temperature.')

	def DisplaySplash(self):
		frameSize = (128, 64)
		screen = Image.new('1', (frameSize), color=0)
		splash = Image.open('color-boot-splash.png') \
			.transform(self.device.size, Image.AFFINE, (1, 0, 0, 0, 1, 0), Image.BILINEAR) \
			.convert("L") \
			.convert(self.device.mode)

		splashSize = splash.size

		screen.paste(splash, (32, 0, splashSize[0]+32, splashSize[1]))
		try:
			self.device.display(screen)
		except:
			now = str(datetime.datetime.now())
			now = now[0:19] # Truncate the microseconds
			print(str(now) + ' Error displaying splash.')

	def ClearDisplay(self):
		try:
			self.device.clear()
		except:
			now = str(datetime.datetime.now())
			now = now[0:19] # Truncate the microseconds
			print(str(now) + ' Error clearing display.')

	def DisplayText(self, text):
		with canvas(self.device) as draw:
			font = ImageFont.truetype("impact.ttf", 42)
			(font_width, font_height) = font.getsize(text)
			try:
				draw.text((128//2 - font_width//2, 64//2 - font_height//2), text, font=font, fill=255)
			except:
				now = str(datetime.datetime.now())
				now = now[0:19] # Truncate the microseconds
				print(str(now) + ' Error displaying text.')
