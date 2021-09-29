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
from RPi import GPIO
from common import ReadControl, WriteControl  # Common Library for WebUI and Control Program

class Display:

	def __init__(self, buttonslevel='HIGH'):
		self.serial = i2c(port=1, address=0x3C)
		self.device = ssd1306(self.serial)
		self.menuactive = False
		self.menutime = 0
		self.menuitem = ''
		# Init GPIO for button input, setup callbacks
		self.up = 16 	# UP - GPIO16
		self.down = 20	# DOWN - GPIO20
		self.enter = 21 # ENTER - GPIO21 

		GPIO.setmode(GPIO.BCM)
		GPIO.setup(self.up, GPIO.IN)
		GPIO.setup(self.down, GPIO.IN)
		GPIO.setup(self.enter, GPIO.IN)

		#GPIO.add_event_detect(self.up, GPIO.FALLING, callback=self.UpCallback, bouncetime=300)  
		#GPIO.add_event_detect(self.down, GPIO.FALLING, callback=self.DownCallback, bouncetime=300) 
		#GPIO.add_event_detect(self.enter, GPIO.FALLING, callback=self.EnterCallback, bouncetime=300)

		# ==== Buttons Setup =====
		if buttonslevel == 'HIGH':
			# Defines for input buttons level HIGH
			self.BUTTON_INPUT = 0
		else:
			# Defines for input buttons level LOW
			self.BUTTON_INPUT = 1

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

		self.DisplaySplash()
		time.sleep(3) # Keep the splash up for three seconds on boot-up - you can certainly disable this if you want 

	def DisplayStatus(self, in_data, status_data):
		if (self.menuactive == True) and (time.time() - self.menutime > 5):
			self.menuactive = False
			self.menu['current']['mode'] = 'none'
			self.menu['current']['option'] = 0
			print('Menu Inactive')
			self.ClearDisplay()

		if (self.menuactive == False):
			with canvas(self.device) as draw:
				try:
					# Grill Temperature (Large Centered) 
					font = ImageFont.truetype("impact.ttf", 42)
					text = str(in_data['GrillTemp'])[:5]
					(font_width, font_height) = font.getsize(text)
					draw.text((128//2 - font_width//2,0), text, font=font, fill=255)
					# Active Outputs F = Fan, I = Igniter, A = Auger (Upper Left)
					font = ImageFont.truetype("FA-Free-Solid.otf", 24)
					if(status_data['outpins']['fan']==0):
						text = '\uf863'
						draw.text((0, 0), text, font=font, fill=255)
					if(status_data['outpins']['igniter']==0):
						text = '\uf46a'
						(font_width, font_height) = font.getsize(text)
						draw.text((0, 5 + (64//2 - font_height//2)), text, font=font, fill=255)
					if(status_data['outpins']['auger']==0):
						text = '\uf101'
						(font_width, font_height) = font.getsize(text)
						draw.text((128 - font_width, 5 + (64//2 - font_height//2)), text, font=font, fill=255)
					# Current Mode (Bottom Left)
					font = ImageFont.truetype("trebuc.ttf", 18)
					text = status_data['mode'] + ' Mode'
					(font_width, font_height) = font.getsize(text)
					draw.text((128//2 - font_width//2, 64 - font_height), text, font=font, fill=255)
					# Notification Indicator (Upper Right)
					font = ImageFont.truetype("FA-Free-Solid.otf", 24)
					text = ' '
					for item in status_data['notify_req']:
						if status_data['notify_req'][item] == True:
							text = '\uf0f3'
					(font_width, font_height) = font.getsize(text)
					draw.text((128 - font_width, 0), text, font=font, fill=255)

				except:
					now = str(datetime.datetime.now())
					now = now[0:19] # Truncate the microseconds
					print(str(now) + ' Error displaying status.')

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

	# OnScreen Menu Controls

	def EventDetect(self):
		if(GPIO.input(self.up) == self.BUTTON_INPUT):
			self.UpCallback(self.up)

		if(GPIO.input(self.down) == self.BUTTON_INPUT):
			self.DownCallback(self.down)

		if(GPIO.input(self.enter) == self.BUTTON_INPUT):
			self.EnterCallback(self.enter)

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

		if(self.menu['current']['mode'] == 'grill_hold_value'):
			print(f"Grill Set Point = {self.menu['current']['option']}")
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
				font = ImageFont.truetype("FA-Free-Solid.otf", 30)
				text = '\uf0dc' # FontAwesome Icon Sort (Up/Down Arrows)
				(font_width, font_height) = font.getsize(text)
				draw.text(((128 - font_width), (64//2 - font_height//2)), text, font=font, fill=255)
		elif(self.menu['current']['mode'] != 'none'):
			with canvas(self.device) as draw:
				# Menu Option (Large Top Center) 
				index = 0
				selected = 'undefined'
				for item in self.menu[self.menu['current']['mode']]:
					if(index == self.menu['current']['option']):
						selected = item 
						break
					index += 1
				font = ImageFont.truetype("FA-Free-Solid.otf", 42)
				text = self.menu[self.menu['current']['mode']][selected]['icon']
				(font_width, font_height) = font.getsize(text)
				draw.text((128//2 - font_width//2,0), text, font=font, fill=255)
				# Draw a Plus Icon over the top of the Smoke Icon
				if(selected == 'SmokePlus'): 
					font = ImageFont.truetype("FA-Free-Solid.otf", 32)
					text = '\uf067' # FontAwesome Icon for PLUS 
					(font_width, font_height) = font.getsize(text)
					draw.text((128//2 - font_width//2,4), text, font=font, fill=0)
				
				# Current Mode (Bottom Center)
				font = ImageFont.truetype("trebuc.ttf", 18)
				text = self.menu[self.menu['current']['mode']][selected]['displaytext']
				(font_width, font_height) = font.getsize(text)
				draw.text((128//2 - font_width//2, 64 - font_height), text, font=font, fill=255)

				# Up / Down Arrows (Middle Right)
				font = ImageFont.truetype("FA-Free-Solid.otf", 30)
				text = '\uf0dc' # FontAwesome Icon Sort (Up/Down Arrows)
				(font_width, font_height) = font.getsize(text)
				draw.text(((128 - font_width), (64//2 - font_height//2)), text, font=font, fill=255)

