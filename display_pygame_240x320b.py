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
# This module uses button input from PyGame and requires a special test harness (not currently provided). 
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
from common import ReadControl, WriteControl  # Common Library for WebUI and Control Program

class Display:

	def __init__(self, buttonslevel='HIGH'):
		# Set Display Width and Height.  Modify for your needs.   
		self.WIDTH = 320
		self.HEIGHT = 240
		# Activate PyGame
		pygame.init()

		# Create Display Surface
		self.display_surface = pygame.display.set_mode((self.WIDTH, self.HEIGHT)) 

		# set the pygame window name 
		pygame.display.set_caption('PiFire Device Display')

		self.DisplaySplash()
		time.sleep(0.5) # Keep the splash up for three seconds on boot-up - you can certainly disable this if you want

		# ==== Buttons Setup =====
		if buttonslevel == 'HIGH':
			# Defines for input buttons level HIGH
			self.BUTTON_INPUT = 0
		else:
			# Defines for input buttons level LOW
			self.BUTTON_INPUT = 1

		# ==== Menu Setup =====
		self.displayactive = False
		self.menuactive = False
		self.menutime = 0
		self.menuitem = ''

		self.menu = {}

		self.menu['inactive'] = { # List of options for the 'inactive' menu.  This is the initial menu when smoker is not running. 
			'Startup' : {
				'displaytext' : 'Startup',
				'icon' : '\uf04b' # FontAwesome Play Icon
			},
			'Monitor' : {
				'displaytext' : 'Monitor',
				'icon' : '\uf530' # FontAwesome Glasses Icon
				},
			'Stop' : {
				'displaytext' : 'Stop',
				'icon' : '\uf04d' # FontAwesome Stop Icon
			}
		} 
		self.menu['active'] = { # List of options for the 'active' menu.  This is the second level menu of options while running.
			'Shutdown' : {
				'displaytext' : 'Shutdown',
				'icon' : '\uf11e' # FontAwesome Finish Icon
			}, 
			'Hold' : {
				'displaytext' : 'Hold',
				'icon' : '\uf76b' # FontAwesome Temperature Low Icon
			}, 
			'Smoke' : {
				'displaytext' : 'Smoke',
				'icon' : '\uf0c2' # FontAwesome Cloud Icon
			}, 
			'Stop' : {
				'displaytext' : 'Stop',
				'icon' : '\uf04d' # FontAwesome Stop Icon
			},
			'SmokePlus' : {
				'displaytext' : 'Toggle Smoke+',
				'icon' : '\uf0c2' # FontAwesome Cloud Icon
			} 
		 } 
		self.menu['current'] = {}
		self.menu['current']['mode'] = 'none'	# Current Menu Mode (inactive, active)
		self.menu['current']['option'] = 0 # Current option in current mode 

		# Init GPIO for button input, setup callbacks: Uncomment to utilize GPIO input
		#self.up = 16 	# UP - GPIO16
		#self.down = 20	# DOWN - GPIO20
		#self.enter = 21 # ENTER - GPIO21 

		#GPIO.setmode(GPIO.BCM)
		#GPIO.setup(self.up, GPIO.IN, pull_up_down=GPIO.PUD_UP)
		#GPIO.setup(self.down, GPIO.IN, pull_up_down=GPIO.PUD_UP)
		#GPIO.setup(self.enter, GPIO.IN, pull_up_down=GPIO.PUD_UP)

		#GPIO.add_event_detect(self.up, GPIO.FALLING, callback=self.UpCallback, bouncetime=300)  
		#GPIO.add_event_detect(self.down, GPIO.FALLING, callback=self.DownCallback, bouncetime=300) 
		#GPIO.add_event_detect(self.enter, GPIO.FALLING, callback=self.EnterCallback, bouncetime=300) 


	def DisplayStatus(self, in_data, status_data):
		self.displayactive = True
		# Create canvas
		img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=(0, 0, 0))

		background = Image.open('background.jpg')

		# Resize the boot-splash
		background = background.resize((self.WIDTH, self.HEIGHT))

		# Set the position 
		position = (0,0)

		# Paste the splash screen onto the canvas
		img.paste(background, position)

		# Create drawing object
		draw = ImageDraw.Draw(img)

		# Grill Temp Circle
		draw.ellipse((80, 10, 240, 170), fill=(50, 50, 50)) # Grey Background Circle
		endpoint = ((360*in_data['GrillTemp']) // 600) + 90
		draw.pieslice((80, 10, 240, 170), start=90, end=endpoint, fill=(200, 0, 0)) # Red Arc for Temperature
		if (in_data['GrillSetPoint'] > 0):
			setpoint = ((360*in_data['GrillSetPoint']) // 600) + 90
			draw.pieslice((80, 10, 240, 170), start=setpoint-2, end=setpoint+2, fill=(255, 255, 0)) # Yellow Arc for SetPoint
		draw.ellipse((90, 20, 230, 160), fill=(0, 0, 0)) # Black Circle for Center

		# Grill Temp Label
		font = ImageFont.truetype("trebuc.ttf", 16)
		text = "Grill"
		(font_width, font_height) = font.getsize(text)
		draw.text((self.WIDTH//2 - font_width//2,20), text, font=font, fill=(255,255,255))

		# Grill Set Point (Small Centered Top)
		if (in_data['GrillSetPoint'] > 0):
			font = ImageFont.truetype("trebuc.ttf", 16)
			text = ">" + str(in_data['GrillSetPoint'])[:5] + "<"
			(font_width, font_height) = font.getsize(text)
			draw.text((self.WIDTH//2 - font_width//2, 45 - font_height//2), text, font=font, fill=(0,200,255))

		# Grill Temperature (Large Centered) 
		font = ImageFont.truetype("trebuc.ttf", 80)
		text = str(in_data['GrillTemp'])[:5]
		(font_width, font_height) = font.getsize(text)
		draw.text((self.WIDTH//2 - font_width//2,40), text, font=font, fill=(255,255,255))

		# Draw Grill Temp Scale Label
		text = "°F"
		font = ImageFont.truetype("trebuc.ttf", 24)
		(font_width, font_height) = font.getsize(text)
		draw.text((self.WIDTH//2 - font_width//2, self.HEIGHT//2 - font_height//2 + 10), text, font=font, fill=(255, 255, 255))

		# PROBE1 Temp Circle
		draw.ellipse((10, self.HEIGHT//2 + 10, 110, self.HEIGHT//2 + 110), fill=(50, 50, 50))
		endpoint = ((360*in_data['Probe1Temp']) // 300) + 90
		draw.pieslice((10, self.HEIGHT//2 + 10, 110, self.HEIGHT//2 + 110), start=90, end=endpoint, fill=(3, 161, 252))
		if (in_data['Probe1SetPoint'] > 0):
			setpoint = ((360*in_data['Probe1SetPoint']) // 300) + 90
			draw.pieslice((10, self.HEIGHT//2 + 10, 110, self.HEIGHT//2 + 110), start=setpoint-2, end=setpoint+2, fill=(255, 255, 0)) # Yellow Arc for SetPoint
		draw.ellipse((20, self.HEIGHT//2 + 20, 100, self.HEIGHT//2 + 100), fill=(0, 0, 0))

		# PROBE1 Temp Label
		font = ImageFont.truetype("trebuc.ttf", 16)
		text = "Probe-1"
		(font_width, font_height) = font.getsize(text)
		draw.text((60 - font_width//2, self.HEIGHT//2 + 40 - font_height//2), text, font=font, fill=(255,255,255))

		# PROBE1 Temperature (Large Centered) 
		font = ImageFont.truetype("trebuc.ttf", 36)
		text = str(in_data['Probe1Temp'])[:5]
		(font_width, font_height) = font.getsize(text)
		draw.text((60 - font_width//2, self.HEIGHT//2 + 60 - font_height//2), text, font=font, fill=(255,255,255))

		# PROBE1 Set Point (Small Centered Bottom)
		if (in_data['Probe1SetPoint'] > 0):
			font = ImageFont.truetype("trebuc.ttf", 16)
			text = ">" + str(in_data['Probe1SetPoint'])[:5] + "<"
			(font_width, font_height) = font.getsize(text)
			draw.text((60 - font_width//2, self.HEIGHT//2 + 85 - font_height//2), text, font=font, fill=(0,200,255))

		# PROBE2 Temp Circle
		draw.ellipse((self.WIDTH - 110, self.HEIGHT//2 + 10, self.WIDTH - 10, self.HEIGHT//2 + 110), fill=(50, 50, 50))
		endpoint = ((360*in_data['Probe2Temp']) // 300) + 90
		draw.pieslice((self.WIDTH - 110, self.HEIGHT//2 + 10, self.WIDTH - 10, self.HEIGHT//2 + 110), start=90, end=endpoint, fill=(3, 161, 252))
		if (in_data['Probe2SetPoint'] > 0):
			setpoint = ((360*in_data['Probe2SetPoint']) // 300) + 90
			draw.pieslice((self.WIDTH - 110, self.HEIGHT//2 + 10, self.WIDTH - 10, self.HEIGHT//2 + 110), start=setpoint-2, end=setpoint+2, fill=(255, 255, 0)) # Yellow Arc for SetPoint
		draw.ellipse((self.WIDTH - 100, self.HEIGHT//2 + 20, self.WIDTH - 20, self.HEIGHT//2 + 100), fill=(0, 0, 0))

		# PROBE2 Temp Label
		font = ImageFont.truetype("trebuc.ttf", 16)
		text = "Probe-2"
		(font_width, font_height) = font.getsize(text)
		draw.text((self.WIDTH - 60 - font_width//2, self.HEIGHT//2 + 40 - font_height//2), text, font=font, fill=(255,255,255))

		# PROBE2 Temperature (Large Centered) 
		font = ImageFont.truetype("trebuc.ttf", 36)
		text = str(in_data['Probe2Temp'])[:5]
		(font_width, font_height) = font.getsize(text)
		draw.text((self.WIDTH - 60 - font_width//2, self.HEIGHT//2 + 60 - font_height//2), text, font=font, fill=(255,255,255))

		# PROBE2 Set Point (Small Centered Bottom)
		if (in_data['Probe2SetPoint'] > 0):
			font = ImageFont.truetype("trebuc.ttf", 16)
			text = ">" + str(in_data['Probe2SetPoint'])[:5] + "<"
			(font_width, font_height) = font.getsize(text)
			draw.text((self.WIDTH - 60 - font_width//2, self.HEIGHT//2 + 85 - font_height//2), text, font=font, fill=(0,200,255))

		# Active Outputs 
		font = ImageFont.truetype("FA-Free-Solid.otf", 36)
		if(status_data['outpins']['fan']==0):
			#F = Fan (Upper Left), 40x40, origin 10,10
			text = '\uf863'
			(font_width, font_height) = font.getsize(text)
			draw = self.rounded_rectangle(draw, (self.WIDTH//8 - 22, self.HEIGHT//6 - 22, self.WIDTH//8 + 22, self.HEIGHT//6 + 22), 5, (0, 100, 255))
			draw = self.rounded_rectangle(draw, (self.WIDTH//8 - 20, self.HEIGHT//6 - 20, self.WIDTH//8 + 20, self.HEIGHT//6 + 20), 5, (0, 0, 0))
			draw.text((self.WIDTH//8 - font_width//2 + 1, self.HEIGHT//6 - font_height//2), text, font=font, fill=(0,100,255))
		if(status_data['outpins']['igniter']==0):
			# I = Igniter(Center Right)
			text = '\uf46a'
			(font_width, font_height) = font.getsize(text)
			draw = self.rounded_rectangle(draw, (7*(self.WIDTH//8) - 22, self.HEIGHT//2.5 - 22, 7*(self.WIDTH//8) + 22, self.HEIGHT//2.5 + 22), 5, (255, 200, 0))
			draw = self.rounded_rectangle(draw, (7*(self.WIDTH//8) - 20, self.HEIGHT//2.5 - 20, 7*(self.WIDTH//8) + 20, self.HEIGHT//2.5 + 20), 5, (0, 0, 0))
			draw.text((7*(self.WIDTH//8) - font_width//2, self.HEIGHT//2.5 - font_height//2), text, font=font, fill=(255,200,0))
		if(status_data['outpins']['auger']==0):
			# A = Auger (Center Left)
			text = '\uf101'
			(font_width, font_height) = font.getsize(text)
			draw = self.rounded_rectangle(draw, (self.WIDTH//8 - 22, self.HEIGHT//2.5 - 22, self.WIDTH//8 + 22, self.HEIGHT//2.5 + 22), 5, (0, 255, 0))
			draw = self.rounded_rectangle(draw, (self.WIDTH//8 - 20, self.HEIGHT//2.5 - 20, self.WIDTH//8 + 20, self.HEIGHT//2.5 + 20), 5, (0, 0, 0))
			draw.text((self.WIDTH//8 - font_width//2 + 1, self.HEIGHT//2.5 - font_height//2 - 2), text, font=font, fill=(0,255,0))

		# Notification Indicator (Right)
		show_notify_indicator = False
		for item in status_data['notify_req']:
			if status_data['notify_req'][item] == True:
				show_notify_indicator = True
		if(show_notify_indicator == True):
			font = ImageFont.truetype("FA-Free-Solid.otf", 36)
			text = '\uf0f3'
			(font_width, font_height) = font.getsize(text)
			draw = self.rounded_rectangle(draw, (7*(self.WIDTH//8) - 22, self.HEIGHT//6 - 22, 7*(self.WIDTH//8) + 22, self.HEIGHT//6 + 22), 5, (255,255,0))
			draw = self.rounded_rectangle(draw, (7*(self.WIDTH//8) - 20, self.HEIGHT//6 - 20, 7*(self.WIDTH//8) + 20, self.HEIGHT//6 + 20), 5, (0, 0, 0))
			draw.text((7*(self.WIDTH//8) - font_width//2 + 1, self.HEIGHT//6 - font_height//2), text, font=font, fill=(255,255,0))

		# Smoke Plus Inidicator
		if(status_data['s_plus'] == True) and ((status_data['mode']=='Smoke') or (status_data['mode']=='Hold')):
			draw = self.rounded_rectangle(draw, (7*(self.WIDTH//8) - 22, self.HEIGHT//2.5 - 22, 7*(self.WIDTH//8) + 22, self.HEIGHT//2.5 + 22), 5, (150, 0, 255))
			draw = self.rounded_rectangle(draw, (7*(self.WIDTH//8) - 20, self.HEIGHT//2.5 - 20, 7*(self.WIDTH//8) + 20, self.HEIGHT//2.5 + 20), 5, (0, 0, 0))
			font = ImageFont.truetype("FA-Free-Solid.otf", 32)
			text = '\uf0c2' # FontAwesome Icon for Cloud (Smoke)
			(font_width, font_height) = font.getsize(text)
			draw.text((7*(self.WIDTH//8) - font_width//2, self.HEIGHT//2.5 - font_height//2), text, font=font, fill=(100,0,255))
			font = ImageFont.truetype("FA-Free-Solid.otf", 24)
			text = '\uf067' # FontAwesome Icon for PLUS 
			(font_width, font_height) = font.getsize(text)
			draw.text((7*(self.WIDTH//8) - font_width//2, self.HEIGHT//2.5 - font_height//2 + 3), text, font=font, fill=(0,0,0))

		# Grill Hopper Level (Lower Center)
		font = ImageFont.truetype("trebuc.ttf", 16)
		text = "Hopper:" + str(status_data['hopper_level']) + "%"
		(font_width, font_height) = font.getsize(text)
		if(status_data['hopper_level'] > 70): 
			hopper_color = (0,255,0)
		elif(status_data['hopper_level'] > 30): 
			hopper_color = (255,150,0)
		else:
			hopper_color = (255,0,0)
		draw = self.rounded_rectangle(draw, (self.WIDTH//2 - font_width//2 - 7, 156 - font_height//2, self.WIDTH//2 + font_width//2 + 7, 166 + font_height//2), 5, hopper_color)
		draw = self.rounded_rectangle(draw, (self.WIDTH//2 - font_width//2 - 5, 158 - font_height//2, self.WIDTH//2 + font_width//2 + 5, 164 + font_height//2), 5, (0,0,0))
		draw.text((self.WIDTH//2 - font_width//2, 160 - font_height//2), text, font=font, fill=hopper_color)

		# Current Mode (Bottom Center)
		font = ImageFont.truetype("trebuc.ttf", 36)
		text = status_data['mode'] #+ ' Mode'
		(font_width, font_height) = font.getsize(text)
		draw = self.rounded_rectangle(draw, (self.WIDTH//2 - font_width//2 - 7, self.HEIGHT - font_height - 2, self.WIDTH//2 + font_width//2 + 7, self.HEIGHT-2), 5, (3, 161, 252))
		draw = self.rounded_rectangle(draw, (self.WIDTH//2 - font_width//2 - 5, self.HEIGHT - font_height, self.WIDTH//2 + font_width//2 + 5, self.HEIGHT-4), 5, (255,255,255))
		draw.text((self.WIDTH//2 - font_width//2, self.HEIGHT - font_height - 6), text, font=font, fill=(0,0,0))

		# Convert to PyGame and Display
		strFormat = img.mode
		size = img.size
		raw_str = img.tobytes("raw", strFormat)

		self.display_image = pygame.image.fromstring(raw_str, size, strFormat)

		self.display_surface.fill((255,255,255))
		self.display_surface.blit(self.display_image, (0, 0))

		pygame.display.update() 


	def DisplaySplash(self):
		self.displayactive = True
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
		self.displayactive = False
		# Fill with black
		self.display_surface.fill((0,0,0))
		pygame.display.update() 


	def DisplayText(self, text):
		self.displayactive = True
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
	
	def rounded_rectangle(self, draw, xy, rad, fill=None):
		x0, y0, x1, y1 = xy
		draw.rectangle([ (x0, y0 + rad), (x1, y1 - rad) ], fill=fill)
		draw.rectangle([ (x0 + rad, y0), (x1 - rad, y1) ], fill=fill)
		draw.pieslice([ (x0, y0), (x0 + rad * 2, y0 + rad * 2) ], 180, 270, fill=fill)
		draw.pieslice([ (x1 - rad * 2, y1 - rad * 2), (x1, y1) ], 0, 90, fill=fill)
		draw.pieslice([ (x0, y1 - rad * 2), (x0 + rad * 2, y1) ], 90, 180, fill=fill)
		draw.pieslice([ (x1 - rad * 2, y0), (x1, y0 + rad * 2) ], 270, 360, fill=fill)
		return(draw)

	# ====================== Menu Code ========================

	def EventDetect(self):
		keys = pygame.key.get_pressed()  # This will give us a dictonary where each key has a value of 1 or 0. Where 1 is pressed and 0 is not pressed.
		if(keys[pygame.K_UP]):
			print('Up pressed.')
			self.UpCallback(16)
		if(keys[pygame.K_DOWN]):
			print('Down pressed.')
			self.DownCallback(20)
		if(keys[pygame.K_RETURN]):
			print('Enter pressed.')
			self.EnterCallback(21)
		if(self.displayactive == False) and (self.menutime > 10):
			self.ClearDisplay()

	def UpCallback(self, pin):
		self.menuactive = True
		self.menutime = time.time()
		self.MenuDisplay('up')
	
	def DownCallback(self, pin):
		self.menuactive = True
		self.menutime = time.time()
		self.MenuDisplay('down')
	
	def EnterCallback(self, pin): 
		self.menuactive = True
		self.menutime = time.time()
		self.MenuDisplay('enter')

	def MenuDisplay(self, action):
		# If menu is not currently being displayed, check mode and draw menu
		if(self.menu['current']['mode'] == 'none'):  
			control = ReadControl()
			if (control['mode'] == 'Stop' or control['mode'] == 'Error' or control['mode'] == 'Monitor'): # If in an inactive mode
				self.menu['current']['mode'] = 'inactive'
			else:  # Use the active menu
				self.menu['current']['mode'] = 'active'
			self.menu['current']['option'] = 0 # Set the menu option to the very first item in the list 
			print('Menu Active')
		# If selecting the 'grill_hold_value', take action based on button press was
		elif(self.menu['current']['mode'] == 'grill_hold_value'):
			if(action == 'down'):
				self.menu['current']['option'] -= 5	# Step up by 5 degrees
				if(self.menu['current']['option'] <= 120):
					self.menu['current']['option'] = 500 # Roll over to 500F if you go less than 120. 
			elif(action == 'up'):
				self.menu['current']['option'] += 5	# Step up by 5 degrees
				if(self.menu['current']['option'] > 500):
					self.menu['current']['option'] = 120 # Roll over to 120F if you go greater than 500. 
			elif(action == 'enter'):
				control = ReadControl()
				control['setpoints']['grill'] = self.menu['current']['option']
				control['updated'] = True
				control['mode'] = 'Hold'
				WriteControl(control)
				self.menu['current']['mode'] = 'none'
				self.menu['current']['option'] = 0
				self.menuactive = False
				self.menutime = 0
				self.ClearDisplay()
		# If selecting either active menu items or inactive menu items, take action based on what the button press was
		else: 
			if(action == 'down'):
				self.menu['current']['option'] -= 1
				if(self.menu['current']['option'] < 0): # Check to make sure we haven't gone past 0
					self.menu['current']['option'] = len(self.menu[self.menu['current']['mode']])-1
				tempvalue = self.menu['current']['option']
				tempmode = self.menu['current']['mode']
				index = 0
				selected = 'undefined'
				for item in self.menu[tempmode]:
					if(index == tempvalue):
						selected = item 
						break
					index += 1
				print(f"Down pressed. Mode = {self.menu['current']['mode']} Value = {self.menu['current']['option']} Selected = {selected}")
			elif(action == 'up'):
				self.menu['current']['option'] += 1
				if(self.menu['current']['option'] == len(self.menu[self.menu['current']['mode']])): # Check to make sure we haven't gone past the end of the menu
					self.menu['current']['option'] = 0
				tempvalue = self.menu['current']['option']
				tempmode = self.menu['current']['mode']
				index = 0
				selected = 'undefined'
				for item in self.menu[tempmode]:
					if(index == tempvalue):
						selected = item 
						break
					index += 1
				print(f"Up pressed. Mode = {self.menu['current']['mode']} Value = {self.menu['current']['option']} Selected = {selected}")
			elif(action == 'enter'):
				print(f"Enter pressed. Value = {self.menu['current']['option']}")
				index = 0
				selected = 'undefined'
				for item in self.menu[self.menu['current']['mode']]:
					if(index == self.menu['current']['option']):
						selected = item 
						break
					index += 1
				# Inactive Mode Items
				if(selected == 'Startup'):
					print('Startup Selected')
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					self.menuactive = False
					self.menutime = 0
					control = ReadControl()
					control['updated'] = True
					control['mode'] = 'Startup'
					WriteControl(control)
				elif(selected == 'Monitor'):
					print('Monitor Selected')
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					self.menuactive = False
					self.menutime = 0
					control = ReadControl()
					control['updated'] = True
					control['mode'] = 'Monitor'
					WriteControl(control)
				elif(selected == 'Stop'):
					print('Stop Selected')
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					self.menuactive = False
					self.menutime = 0
					self.ClearDisplay()
					control = ReadControl()
					control['updated'] = True
					control['mode'] = 'Stop'
					WriteControl(control)
				# Active Mode
				elif(selected == 'Shutdown'):
					print('Shutdown Selected')
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					self.menuactive = False
					self.menutime = 0
					self.ClearDisplay()
					control = ReadControl()
					control['updated'] = True
					control['mode'] = 'Shutdown'
					WriteControl(control)
				elif(selected == 'Hold'):
					print('Hold Selected')
					self.menu['current']['mode'] = 'grill_hold_value'
					self.menu['current']['option'] = 225
				elif(selected == 'Smoke'):
					print('Smoke Selected')
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					self.menuactive = False
					self.menutime = 0
					self.ClearDisplay()
					control = ReadControl()
					control['updated'] = True
					control['mode'] = 'Smoke'
					WriteControl(control)
				elif(selected == 'SmokePlus'):
					print('Smoke Plus Selected')
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					self.menuactive = False
					self.menutime = 0
					self.ClearDisplay()
					control = ReadControl()
					if(control['s_plus'] == True):
						control['s_plus'] = False
					else:
						control['s_plus'] = True
					WriteControl(control)

		# Create canvas
		img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=(0, 0, 0))

		background = Image.open('background.jpg')

		# Resize the boot-splash
		background = background.resize((self.WIDTH, self.HEIGHT))

		# Set the position 
		position = (0,0)

		# Paste the splash screen onto the canvas
		img.paste(background, position)

		# Create drawing object
		draw = ImageDraw.Draw(img)

		if(self.menu['current']['mode'] == 'grill_hold_value'):
			print(f"Grill Set Point = {self.menu['current']['option']}")

			# Grill Temperature (Large Centered) 
			font = ImageFont.truetype("trebuc.ttf", 120)
			text = str(self.menu['current']['option'])
			(font_width, font_height) = font.getsize(text)
			draw.text((self.WIDTH//2 - font_width//2,self.HEIGHT//3 - font_height//2), text, font=font, fill=(255,255,255))

			# Current Mode (Bottom Center)
			font = ImageFont.truetype("trebuc.ttf", 36)
			text = "Grill Set Point"
			(font_width, font_height) = font.getsize(text)
			# Draw Black Rectangle
			draw.rectangle([ (0,(self.HEIGHT//8)*6) , (self.WIDTH, self.HEIGHT) ], fill=(0,0,0))
			# Draw White Line/Rectangle
			draw.rectangle([ (0,(self.HEIGHT//8)*6) , (self.WIDTH, ((self.HEIGHT//8)*6)+2) ], fill=(255,255,255))
			# Draw Text
			draw.text((self.WIDTH//2 - font_width//2, (self.HEIGHT//8)*6.25), text, font=font, fill=(255,255,255))

			# Up / Down Arrows (Middle Right)
			font = ImageFont.truetype("FA-Free-Solid.otf", 80)
			text = '\uf0dc' # FontAwesome Icon Sort (Up/Down Arrows)
			(font_width, font_height) = font.getsize(text)
			draw.text(((self.WIDTH - (font_width//2)**1.3), (self.HEIGHT//2.5 - font_height//2)), text, font=font, fill=(255,255,255))

		elif(self.menu['current']['mode'] != 'none'):
			# Menu Option (Large Top Center) 
			index = 0
			selected = 'undefined'
			for item in self.menu[self.menu['current']['mode']]:
				if(index == self.menu['current']['option']):
					selected = item 
					break
				index += 1
			font = ImageFont.truetype("FA-Free-Solid.otf", 120)
			text = self.menu[self.menu['current']['mode']][selected]['icon']
			(font_width, font_height) = font.getsize(text)
			draw.text((self.WIDTH//2 - font_width//2,self.HEIGHT//2.5 - font_height//2), text, font=font, fill=(255,255,255))
			# Draw a Plus Icon over the top of the Smoke Icon
			if(selected == 'SmokePlus'): 
				font = ImageFont.truetype("FA-Free-Solid.otf", 80)
				text = '\uf067' # FontAwesome Icon for PLUS 
				(font_width, font_height) = font.getsize(text)
				draw.text((self.WIDTH//2 - font_width//2,self.HEIGHT//2.5 - font_height//2), text, font=font, fill=(0,0,0))
			
			# Current Mode (Bottom Center)
			font = ImageFont.truetype("trebuc.ttf", 36)
			text = self.menu[self.menu['current']['mode']][selected]['displaytext']
			(font_width, font_height) = font.getsize(text)
			# Draw Black Rectangle
			draw.rectangle([ (0,(self.HEIGHT//8)*6) , (self.WIDTH, self.HEIGHT) ], fill=(0,0,0))
			# Draw White Line/Rectangle
			draw.rectangle([ (0,(self.HEIGHT//8)*6) , (self.WIDTH, ((self.HEIGHT//8)*6)+2) ], fill=(255,255,255))
			# Draw Text
			draw.text((self.WIDTH//2 - font_width//2, (self.HEIGHT//8)*6.25), text, font=font, fill=(255,255,255))

			# Up / Down Arrows (Middle Right)
			font = ImageFont.truetype("FA-Free-Solid.otf", 80)
			text = '\uf0dc' # FontAwesome Icon Sort (Up/Down Arrows)
			(font_width, font_height) = font.getsize(text)
			draw.text(((self.WIDTH - (font_width//2)**1.3), (self.HEIGHT//2.5 - font_height//2)), text, font=font, fill=(255,255,255))

		# Convert to PyGame and Display
		strFormat = img.mode
		size = img.size
		raw_str = img.tobytes("raw", strFormat)

		self.display_image = pygame.image.fromstring(raw_str, size, strFormat)

		self.display_surface.fill((255,255,255))
		self.display_surface.blit(self.display_image, (0, 0))

		pygame.display.update() 

