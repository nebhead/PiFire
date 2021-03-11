#!/usr/bin/env python3

# *****************************************
# PiFire Display Interface Library
# *****************************************
#
# Description: This library supports using pygame 
# on your development PC for debug and development 
# purposes. Likely only works in an desktop 
# environment.  Tested on Ubuntu 20.04.  
#
# Edit the WIDTH / HEIGHT constants below to 
# simulate your screen size. 
# 
# Dependancies:
#   sudo pip3 install pygame Pillow 
#   sudo apt install ttf-mscorefonts-installer
#
# *****************************************

# *****************************************
# Imported Libraries
# *****************************************
import pygame  
from PIL import Image, ImageDraw, ImageFont
import time

class Display:

	def __init__(self):
		# Set Display Width and Height.  Modify for your needs.   
		self.WIDTH = 240
		self.HEIGHT = 240
		# Activate PyGame
		pygame.init()

		# Create Display Surface
		self.display_surface = pygame.display.set_mode((self.WIDTH, self.HEIGHT )) 

		# set the pygame window name 
		pygame.display.set_caption('PiFire Device Display')

		self.DisplaySplash()
		time.sleep(3) # Keep the splash up for three seconds on boot-up - you can certainly disable this if you want 


	def DisplayStatus(self, in_data, status_data):
		# Create canvas
		img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=(0, 0, 0))

		# Create drawing object
		draw = ImageDraw.Draw(img)

		# Grill Temperature (Large Centered) 
		#font = ImageFont.truetype("impact.ttf", 100)
		font = ImageFont.truetype("trebuc.ttf", 128)
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

		# Convert to PyGame and Display
		strFormat = img.mode
		size = img.size
		raw_str = img.tobytes("raw", strFormat)

		self.display_image = pygame.image.fromstring(raw_str, size, strFormat)

		self.display_surface.fill((255,255,255))
		self.display_surface.blit(self.display_image, (0, 0))

		pygame.display.update() 


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

		# Convert to PyGame and Display
		strFormat = img.mode
		size = img.size
		raw_str = img.tobytes("raw", strFormat)
		self.display_image = pygame.image.fromstring(raw_str, size, strFormat)

		self.display_surface.fill((255,255,255))
		self.display_surface.blit(self.display_image, (0, 0))

		pygame.display.update() 


	def ClearDisplay(self):
		# Fill with black
		self.display_surface.fill((0,0,0))
		pygame.display.update() 


	def DisplayText(self, text):
		# Create canvas
		img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=(0, 0, 0))

		# Create drawing object
		draw = ImageDraw.Draw(img)

		font = ImageFont.truetype("impact.ttf", 42)
		(font_width, font_height) = font.getsize(text)
		draw.text((self.WIDTH//2 - font_width//2, self.HEIGHT//2 - font_height//2), text, font=font, fill=255)

		# Convert to PyGame and Display
		strFormat = img.mode
		size = img.size
		raw_str = img.tobytes("raw", strFormat)

		self.display_image = pygame.image.fromstring(raw_str, size, strFormat)

		self.display_surface.fill((255,255,255))
		self.display_surface.blit(self.display_image, (0, 0))

		pygame.display.update() 

	def EventDetect(self):
		return()