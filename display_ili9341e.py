#!/usr/bin/env python3

# *****************************************
# PiFire Display Interface Library
# *****************************************
#
# Description: This library supports using 
# the ILI9341 display with 240Wx320H resolution.
# This module utilizes Luma.LCD to interface 
# this display.  
# 
# Dependancies:
#   sudo pip3 install Pillow 
#   sudo apt install ttf-mscorefonts-installer
#   sudo pip3 install luma.lcd
#
# *****************************************

# *****************************************
# Imported Libraries
# *****************************************
from luma.core.interface.serial import spi

from luma.lcd.device import ili9341
from PIL import Image, ImageDraw, ImageFont
import time
import socket
import qrcode
from common import ReadControl, WriteControl  # Common Library for WebUI and Control Program
from pyky040 import pyky040
import spidev


class Display:

	def __init__(self, units='F'):
		# Set Display Width and Height.  Modify for your needs.
		self.WIDTH = 320
		self.HEIGHT = 240
		# Init Device
		self.serial = spi(port=0, device=0, gpio_DC=24, gpio_RST=25, bus_speed_hz=32000000, reset_hold_time=0.2, reset_release_time=0.2)
		self.device = ili9341(self.serial, active_low=False, width=self.WIDTH, height=self.HEIGHT, gpio_LIGHT=5)
		# Init GPIO for button input, setup callbacks: Uncomment to utilize GPIO input
		self.up = 16  # UP - GPIO16
		self.down = 20  # DOWN - GPIO20
		self.enter = 21  # ENTER - GPIO21

		self.units = units

		self.btn_event = None

		self.my_encoder = pyky040.Encoder(CLK=16, DT=20, SW=21)
		self.my_encoder.setup(scale_min=0, scale_max=100, step=1, inc_callback=self.inc_callback,
							  dec_callback=self.dec_callback,
							  sw_callback=self.click_callback, polling_interval=1)

		import threading
		my_thread = threading.Thread(target=self.my_encoder.watch)

		# Launch the thread
		my_thread.start()

		# ==== Menu Setup =====
		self.displayactive = False
		self.menuactive = False
		self.menutime = 0
		self.menuitem = ''

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
			'Wifi': {
				'displaytext': 'WIFI',
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
			'Wifi': {
				'displaytext': 'WIFI',
				'icon': '\uf1eb'  # FontAwesome Wifi Icon
			}
		}
		self.menu['current'] = {}
		self.menu['current']['mode'] = 'none'  # Current Menu Mode (inactive, active)
		self.menu['current']['option'] = 0  # Current option in current mode

		# Display Splash Screen
		self.DisplaySplash()
		time.sleep(0.5)  # Delay for splash screen on boot-up - you can certainly disable this if you want

		# Clear display on startup
		self.ClearDisplay()

	def click_callback(self):
		self.btn_event='CLICK'

	def inc_callback(self,v):
		self.btn_event='UP'

	def dec_callback(self,v):
		self.btn_event='DOWN'

	def DisplayStatus(self, in_data, status_data):
		self.units = status_data['units']  # Update units in case there was a change since instantiation
		self.displayactive = True

		if (self.menuactive == True) and (time.time() - self.menutime > 5):
			self.menuactive = False
			self.menu['current']['mode'] = 'none'
			self.menu['current']['option'] = 0
			print('Menu Inactive')
		# self.ClearDisplay()

		if (self.menuactive == False):
			# Create canvas
			img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=(0, 0, 0))

			background = Image.open('background.jpg')

			# Resize the boot-splash
			background = background.resize((self.WIDTH, self.HEIGHT))

			# Set the position
			position = (0, 0)

			# Paste the splash screen onto the canvas
			img.paste(background, position)

			# Create drawing object
			draw = ImageDraw.Draw(img)

			# Grill Temp Circle
			draw.ellipse((80, 10, 240, 170), fill=(50, 50, 50))  # Grey Background Circle
			if in_data['GrillTemp'] < 0:
				endpoint = 0
			elif self.units == 'F':
				endpoint = ((360 * in_data['GrillTemp']) // 600) + 90
			else:
				endpoint = ((360 * in_data['GrillTemp']) // 300) + 90
			draw.pieslice((80, 10, 240, 170), start=90, end=endpoint, fill=(200, 0, 0))  # Red Arc for Temperature
			if (in_data['GrillSetPoint'] > 0):
				if self.units == 'F':
					setpoint = ((360 * in_data['GrillSetPoint']) // 600) + 90
				else:
					setpoint = ((360 * in_data['GrillSetPoint']) // 300) + 90
				draw.pieslice((80, 10, 240, 170), start=setpoint - 2, end=setpoint + 2,
							  fill=(255, 255, 0))  # Yellow Arc for SetPoint
			draw.ellipse((90, 20, 230, 160), fill=(0, 0, 0))  # Black Circle for Center

			# Grill Temp Label
			font = ImageFont.truetype("trebuc.ttf", 16)
			text = "Grill"
			(font_width, font_height) = font.getsize(text)
			draw.text((self.WIDTH // 2 - font_width // 2, 20), text, font=font, fill=(255, 255, 255))

			# Grill Set Point (Small Centered Top)
			if (in_data['GrillSetPoint'] > 0):
				font = ImageFont.truetype("trebuc.ttf", 16)
				text = ">" + str(in_data['GrillSetPoint'])[:5] + "<"
				(font_width, font_height) = font.getsize(text)
				draw.text((self.WIDTH // 2 - font_width // 2, 45 - font_height // 2), text, font=font,
						  fill=(0, 200, 255))

			# Grill Temperature (Large Centered)
			if (self.units == 'F'):
				font = ImageFont.truetype("trebuc.ttf", 80)
				text = str(in_data['GrillTemp'])[:5]
				(font_width, font_height) = font.getsize(text)
				draw.text((self.WIDTH // 2 - font_width // 2, 40), text, font=font, fill=(255, 255, 255))
			else:
				font = ImageFont.truetype("trebuc.ttf", 55)
				text = str(in_data['GrillTemp'])[:5]
				(font_width, font_height) = font.getsize(text)
				draw.text((self.WIDTH // 2 - font_width // 2, 56), text, font=font, fill=(255, 255, 255))

			# Draw Grill Temp Scale Label
			text = "°" + self.units
			font = ImageFont.truetype("trebuc.ttf", 24)
			(font_width, font_height) = font.getsize(text)
			draw.text((self.WIDTH // 2 - font_width // 2, self.HEIGHT // 2 - font_height // 2 + 10), text, font=font,
					  fill=(255, 255, 255))

			# PROBE1 Temp Circle
			draw.ellipse((10, self.HEIGHT // 2 + 10, 110, self.HEIGHT // 2 + 110), fill=(50, 50, 50))
			if in_data['Probe1Temp'] < 0:
				endpoint = 0
			elif self.units == 'F':
				endpoint = ((360 * in_data['Probe1Temp']) // 300) + 90
			else:
				endpoint = ((360 * in_data['Probe1Temp']) // 150) + 90
			draw.pieslice((10, self.HEIGHT // 2 + 10, 110, self.HEIGHT // 2 + 110), start=90, end=endpoint,
						  fill=(3, 161, 252))
			if (in_data['Probe1SetPoint'] > 0):
				if self.units == 'F':
					setpoint = ((360 * in_data['Probe1SetPoint']) // 300) + 90
				else:
					setpoint = ((360 * in_data['Probe1SetPoint']) // 150) + 90
				draw.pieslice((10, self.HEIGHT // 2 + 10, 110, self.HEIGHT // 2 + 110), start=setpoint - 2,
							  end=setpoint + 2, fill=(255, 255, 0))  # Yellow Arc for SetPoint
			draw.ellipse((20, self.HEIGHT // 2 + 20, 100, self.HEIGHT // 2 + 100), fill=(0, 0, 0))

			# PROBE1 Temp Label
			font = ImageFont.truetype("trebuc.ttf", 16)
			text = "Probe-1"
			(font_width, font_height) = font.getsize(text)
			draw.text((60 - font_width // 2, self.HEIGHT // 2 + 40 - font_height // 2), text, font=font,
					  fill=(255, 255, 255))

			# PROBE1 Temperature (Large Centered)
			if (self.units == 'F'):
				font = ImageFont.truetype("trebuc.ttf", 36)
			else:
				font = ImageFont.truetype("trebuc.ttf", 30)
			text = str(in_data['Probe1Temp'])[:5]
			(font_width, font_height) = font.getsize(text)
			draw.text((60 - font_width // 2, self.HEIGHT // 2 + 60 - font_height // 2), text, font=font,
					  fill=(255, 255, 255))

			# PROBE1 Set Point (Small Centered Bottom)
			if (in_data['Probe1SetPoint'] > 0):
				font = ImageFont.truetype("trebuc.ttf", 16)
				text = ">" + str(in_data['Probe1SetPoint'])[:5] + "<"
				(font_width, font_height) = font.getsize(text)
				draw.text((60 - font_width // 2, self.HEIGHT // 2 + 85 - font_height // 2), text, font=font,
						  fill=(0, 200, 255))

			# PROBE2 Temp Circle
			draw.ellipse((self.WIDTH - 110, self.HEIGHT // 2 + 10, self.WIDTH - 10, self.HEIGHT // 2 + 110),
						 fill=(50, 50, 50))
			if in_data['Probe2Temp'] < 0:
				endpoint = 0
			elif self.units == 'F':
				endpoint = ((360 * in_data['Probe2Temp']) // 300) + 90
			else:
				endpoint = ((360 * in_data['Probe2Temp']) // 150) + 90
			draw.pieslice((self.WIDTH - 110, self.HEIGHT // 2 + 10, self.WIDTH - 10, self.HEIGHT // 2 + 110), start=90,
						  end=endpoint, fill=(3, 161, 252))
			if (in_data['Probe2SetPoint'] > 0):
				if self.units == 'F':
					setpoint = ((360 * in_data['Probe2SetPoint']) // 300) + 90
				else:
					setpoint = ((360 * in_data['Probe2SetPoint']) // 150) + 90
				draw.pieslice((self.WIDTH - 110, self.HEIGHT // 2 + 10, self.WIDTH - 10, self.HEIGHT // 2 + 110),
							  start=setpoint - 2, end=setpoint + 2, fill=(255, 255, 0))  # Yellow Arc for SetPoint
			draw.ellipse((self.WIDTH - 100, self.HEIGHT // 2 + 20, self.WIDTH - 20, self.HEIGHT // 2 + 100),
						 fill=(0, 0, 0))

			# PROBE2 Temp Label
			font = ImageFont.truetype("trebuc.ttf", 16)
			text = "Probe-2"
			(font_width, font_height) = font.getsize(text)
			draw.text((self.WIDTH - 60 - font_width // 2, self.HEIGHT // 2 + 40 - font_height // 2), text, font=font,
					  fill=(255, 255, 255))

			# PROBE2 Temperature (Large Centered)
			if (self.units == 'F'):
				font = ImageFont.truetype("trebuc.ttf", 36)
			else:
				font = ImageFont.truetype("trebuc.ttf", 30)
			text = str(in_data['Probe2Temp'])[:5]
			(font_width, font_height) = font.getsize(text)
			draw.text((self.WIDTH - 60 - font_width // 2, self.HEIGHT // 2 + 60 - font_height // 2), text, font=font,
					  fill=(255, 255, 255))

			# PROBE2 Set Point (Small Centered Bottom)
			if (in_data['Probe2SetPoint'] > 0):
				font = ImageFont.truetype("trebuc.ttf", 16)
				text = ">" + str(in_data['Probe2SetPoint'])[:5] + "<"
				(font_width, font_height) = font.getsize(text)
				draw.text((self.WIDTH - 60 - font_width // 2, self.HEIGHT // 2 + 85 - font_height // 2), text,
						  font=font, fill=(0, 200, 255))

			# Active Outputs
			font = ImageFont.truetype("FA-Free-Solid.otf", 36)
			if (status_data['outpins']['fan'] == 0):
				# F = Fan (Upper Left), 40x40, origin 10,10
				text = '\uf863'
				(font_width, font_height) = font.getsize(text)
				draw = self.rounded_rectangle(draw, (
					self.WIDTH // 8 - 22, self.HEIGHT // 6 - 22, self.WIDTH // 8 + 22, self.HEIGHT // 6 + 22), 5,
											  (0, 100, 255))
				draw = self.rounded_rectangle(draw, (
					self.WIDTH // 8 - 20, self.HEIGHT // 6 - 20, self.WIDTH // 8 + 20, self.HEIGHT // 6 + 20), 5,
											  (0, 0, 0))
				draw.text((self.WIDTH // 8 - font_width // 2 + 1, self.HEIGHT // 6 - font_height // 2), text, font=font,
						  fill=(0, 100, 255))
			if (status_data['outpins']['igniter'] == 0):
				# I = Igniter(Center Right)
				text = '\uf46a'
				(font_width, font_height) = font.getsize(text)
				draw = self.rounded_rectangle(draw, (
					7 * (self.WIDTH // 8) - 22, self.HEIGHT // 2.5 - 22, 7 * (self.WIDTH // 8) + 22,
					self.HEIGHT // 2.5 + 22), 5, (255, 200, 0))
				draw = self.rounded_rectangle(draw, (
					7 * (self.WIDTH // 8) - 20, self.HEIGHT // 2.5 - 20, 7 * (self.WIDTH // 8) + 20,
					self.HEIGHT // 2.5 + 20), 5, (0, 0, 0))
				draw.text((7 * (self.WIDTH // 8) - font_width // 2, self.HEIGHT // 2.5 - font_height // 2), text,
						  font=font, fill=(255, 200, 0))
			if (status_data['outpins']['auger'] == 0):
				# A = Auger (Center Left)
				text = '\uf101'
				(font_width, font_height) = font.getsize(text)
				draw = self.rounded_rectangle(draw, (
					self.WIDTH // 8 - 22, self.HEIGHT // 2.5 - 22, self.WIDTH // 8 + 22, self.HEIGHT // 2.5 + 22), 5,
											  (0, 255, 0))
				draw = self.rounded_rectangle(draw, (
					self.WIDTH // 8 - 20, self.HEIGHT // 2.5 - 20, self.WIDTH // 8 + 20, self.HEIGHT // 2.5 + 20), 5,
											  (0, 0, 0))
				draw.text((self.WIDTH // 8 - font_width // 2 + 1, self.HEIGHT // 2.5 - font_height // 2 - 2), text,
						  font=font, fill=(0, 255, 0))

			# Notification Indicator (Right)
			show_notify_indicator = False
			for item in status_data['notify_req']:
				if status_data['notify_req'][item] == True:
					show_notify_indicator = True
			if (show_notify_indicator == True):
				font = ImageFont.truetype("FA-Free-Solid.otf", 36)
				text = '\uf0f3'
				(font_width, font_height) = font.getsize(text)
				draw = self.rounded_rectangle(draw, (
					7 * (self.WIDTH // 8) - 22, self.HEIGHT // 6 - 22, 7 * (self.WIDTH // 8) + 22,
					self.HEIGHT // 6 + 22),
											  5, (255, 255, 0))
				draw = self.rounded_rectangle(draw, (
					7 * (self.WIDTH // 8) - 20, self.HEIGHT // 6 - 20, 7 * (self.WIDTH // 8) + 20,
					self.HEIGHT // 6 + 20),
											  5, (0, 0, 0))
				draw.text((7 * (self.WIDTH // 8) - font_width // 2 + 1, self.HEIGHT // 6 - font_height // 2), text,
						  font=font, fill=(255, 255, 0))

			# Smoke Plus Inidicator
			if (status_data['s_plus'] == True) and (
					(status_data['mode'] == 'Smoke') or (status_data['mode'] == 'Hold')):
				draw = self.rounded_rectangle(draw, (
					7 * (self.WIDTH // 8) - 22, self.HEIGHT // 2.5 - 22, 7 * (self.WIDTH // 8) + 22,
					self.HEIGHT // 2.5 + 22), 5, (150, 0, 255))
				draw = self.rounded_rectangle(draw, (
					7 * (self.WIDTH // 8) - 20, self.HEIGHT // 2.5 - 20, 7 * (self.WIDTH // 8) + 20,
					self.HEIGHT // 2.5 + 20), 5, (0, 0, 0))
				font = ImageFont.truetype("FA-Free-Solid.otf", 32)
				text = '\uf0c2'  # FontAwesome Icon for Cloud (Smoke)
				(font_width, font_height) = font.getsize(text)
				draw.text((7 * (self.WIDTH // 8) - font_width // 2, self.HEIGHT // 2.5 - font_height // 2), text,
						  font=font, fill=(100, 0, 255))
				font = ImageFont.truetype("FA-Free-Solid.otf", 24)
				text = '\uf067'  # FontAwesome Icon for PLUS
				(font_width, font_height) = font.getsize(text)
				draw.text((7 * (self.WIDTH // 8) - font_width // 2, self.HEIGHT // 2.5 - font_height // 2 + 3), text,
						  font=font, fill=(0, 0, 0))

			# Grill Hopper Level (Lower Center)
			font = ImageFont.truetype("trebuc.ttf", 16)
			text = "Hopper:" + str(status_data['hopper_level']) + "%"
			(font_width, font_height) = font.getsize(text)
			if (status_data['hopper_level'] > 70):
				hopper_color = (0, 255, 0)
			elif (status_data['hopper_level'] > 30):
				hopper_color = (255, 150, 0)
			else:
				hopper_color = (255, 0, 0)
			draw = self.rounded_rectangle(draw, (
				self.WIDTH // 2 - font_width // 2 - 7, 156 - font_height // 2, self.WIDTH // 2 + font_width // 2 + 7,
				166 + font_height // 2), 5, hopper_color)
			draw = self.rounded_rectangle(draw, (
				self.WIDTH // 2 - font_width // 2 - 5, 158 - font_height // 2, self.WIDTH // 2 + font_width // 2 + 5,
				164 + font_height // 2), 5, (0, 0, 0))
			draw.text((self.WIDTH // 2 - font_width // 2, 160 - font_height // 2), text, font=font, fill=hopper_color)

			# Current Mode (Bottom Center)
			font = ImageFont.truetype("trebuc.ttf", 36)
			text = status_data['mode']  # + ' Mode'
			(font_width, font_height) = font.getsize(text)
			draw = self.rounded_rectangle(draw, (
				self.WIDTH // 2 - font_width // 2 - 7, self.HEIGHT - font_height - 2,
				self.WIDTH // 2 + font_width // 2 + 7,
				self.HEIGHT - 2), 5, (3, 161, 252))
			draw = self.rounded_rectangle(draw, (
				self.WIDTH // 2 - font_width // 2 - 5, self.HEIGHT - font_height, self.WIDTH // 2 + font_width // 2 + 5,
				self.HEIGHT - 4), 5, (255, 255, 255))
			draw.text((self.WIDTH // 2 - font_width // 2, self.HEIGHT - font_height - 6), text, font=font,
					  fill=(0, 0, 0))

			# Display Image
			self.device.backlight(True)
			self.device.show()
			self.device.display(img)

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
		position = ((self.WIDTH - splash_width) // 2, (self.HEIGHT - splash_height) // 2)

		# Paste the splash screen onto the canvas
		img.paste(splash, position)

		# Display Image
		self.device.backlight(True)
		self.device.show()
		self.device.display(img)

	def ClearDisplay(self):
		if self.menuactive:
			return
		self.displayactive = False
		self.device.clear()
		self.device.backlight(False)
		self.device.hide()

	# Kill the backlight to the display

	def DisplayText(self, text):
		self.displayactive = True
		# Create canvas
		img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=(0, 0, 0))

		# Create drawing object
		draw = ImageDraw.Draw(img)

		font = ImageFont.truetype("impact.ttf", 42)
		(font_width, font_height) = font.getsize(text)
		draw.text((self.WIDTH // 2 - font_width // 2, self.HEIGHT // 2 - font_height // 2), text, font=font, fill=255)

		# Display Image
		self.device.backlight(True)
		self.device.show()
		self.device.display(img)

	def DisplayNetwork(self):
		self.displayactive = True

		s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		s.connect(("8.8.8.8", 80))
		networkip = s.getsockname()[0]

		if (networkip != ''):
			# Create canvas
			img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=(255, 255, 255))

			img_qr = qrcode.make('http://' + networkip)

			img_qr_width, img_qr_height = img_qr.size
			img_qr_width *= 2
			img_qr_height *= 2

			w = min(self.WIDTH, self.HEIGHT)

			new_image = img_qr.resize((w, w))

			# position = ((self.WIDTH - img_qr_width)//2, (self.HEIGHT - img_qr_height)//2)

			position = (0, 0)

			img.paste(new_image, position)

			# Display Image
			self.device.backlight(True)
			self.device.show()
			self.device.display(img)

			time.sleep(30)

			# Clear display after timeout
			self.ClearDisplay()
		else:
			self.DisplayText("No IP Found")
			time.sleep(10)
			# Clear display	after timeout
			self.ClearDisplay()

	def rounded_rectangle(self, draw, xy, rad, fill=None):
		x0, y0, x1, y1 = xy
		draw.rectangle([(x0, y0 + rad), (x1, y1 - rad)], fill=fill)
		draw.rectangle([(x0 + rad, y0), (x1 - rad, y1)], fill=fill)
		draw.pieslice([(x0, y0), (x0 + rad * 2, y0 + rad * 2)], 180, 270, fill=fill)
		draw.pieslice([(x1 - rad * 2, y1 - rad * 2), (x1, y1)], 0, 90, fill=fill)
		draw.pieslice([(x0, y1 - rad * 2), (x0 + rad * 2, y1)], 90, 180, fill=fill)
		draw.pieslice([(x1 - rad * 2, y0), (x1, y0 + rad * 2)], 270, 360, fill=fill)
		return (draw)

	# ====================== Menu Code ========================


	def EventDetect(self):

		if self.btn_event:
			print(self.btn_event)
			if self.btn_event == 'UP':
				self.UpCallback(self.up)
			elif self.btn_event == 'DOWN':
				self.DownCallback(self.down)
			elif self.btn_event == 'CLICK':
				self.EnterCallback(self.enter)
			elif self.btn_event == 'D_CLICK':
				self.HoldCallback(self.down)
			self.btn_event=None

		if not self.displayactive and time.time() - self.menutime > 10 and self.menuactive:
			print('EventDetect display timeout turn off')
			self.menuactive = False
			self.menu['current']['mode'] = 'none'
			self.menu['current']['option'] = 0
			print('Menu Inactive')
			self.ClearDisplay()

	def UpCallback(self, pin):
		self.menuactive = True
		self.MenuDisplay('up')
		self.menutime = time.time()

	def DownCallback(self, pin):
		self.menuactive = True
		self.MenuDisplay('down')
		self.menutime = time.time()

	def EnterCallback(self, pin):
		self.menuactive = True
		self.MenuDisplay('enter')
		self.menutime = time.time()

	def HoldCallback(self, pin):
		self.menuactive = True
		self.DisplayNetwork()
		self.menutime = time.time()

	def MenuDisplay(self, action):
		# If menu is not currently being displayed, check mode and draw menu
		if (self.menu['current']['mode'] == 'none'):
			control = ReadControl()
			if (control['mode'] == 'Stop' or control['mode'] == 'Error' or control[
				'mode'] == 'Monitor'):  # If in an inactive mode
				self.menu['current']['mode'] = 'inactive'
			else:  # Use the active menu
				self.menu['current']['mode'] = 'active'
			self.menu['current']['option'] = 0  # Set the menu option to the very first item in the list
			print('Menu Active')
		# If selecting the 'grill_hold_value', take action based on button press was
		elif (self.menu['current']['mode'] == 'grill_hold_value'):
			if (self.units == 'F'):
				stepValue = 5  # change in temp each time button pressed
				minTemp = 120  # minimum temperature set for hold
				maxTemp = 500  # maximum temperature set for hold
			else:
				stepValue = 2  # change in temp each time button pressed
				minTemp = 50  # minimum temperature set for hold
				maxTemp = 260  # maximum temperature set for hold
			if (action == 'down'):
				self.menu['current']['option'] -= stepValue  # Step down by stepValue degrees
				if (self.menu['current']['option'] <= minTemp):
					self.menu['current']['option'] = maxTemp  # Roll over to maxTemp if you go less than 120.
			elif (action == 'up'):
				self.menu['current']['option'] += stepValue  # Step up by stepValue degrees
				if (self.menu['current']['option'] > maxTemp):
					self.menu['current']['option'] = minTemp  # Roll over to minTemp if you go greater than 500.
			elif (action == 'enter'):
				control = ReadControl()
				control['setpoints']['grill'] = self.menu['current']['option']
				control['updated'] = True
				control['mode'] = 'Hold'
				WriteControl(control)
				self.menu['current']['mode'] = 'none'
				self.menu['current']['option'] = 0
				self.menuactive = False
				self.menutime = 0
			# self.ClearDisplay()
		# If selecting either active menu items or inactive menu items, take action based on what the button press was
		else:
			if (action == 'down'):
				self.menu['current']['option'] -= 1
				if (self.menu['current']['option'] < 0):  # Check to make sure we haven't gone past 0
					self.menu['current']['option'] = len(self.menu[self.menu['current']['mode']]) - 1
				tempvalue = self.menu['current']['option']
				tempmode = self.menu['current']['mode']
				index = 0
				selected = 'undefined'
				for item in self.menu[tempmode]:
					if (index == tempvalue):
						selected = item
						break
					index += 1
				print(
					f"Down pressed. Mode = {self.menu['current']['mode']} Value = {self.menu['current']['option']} Selected = {selected}")
			elif (action == 'up'):
				self.menu['current']['option'] += 1
				if (self.menu['current']['option'] == len(self.menu[self.menu['current'][
					'mode']])):  # Check to make sure we haven't gone past the end of the menu
					self.menu['current']['option'] = 0
				tempvalue = self.menu['current']['option']
				tempmode = self.menu['current']['mode']
				index = 0
				selected = 'undefined'
				for item in self.menu[tempmode]:
					if (index == tempvalue):
						selected = item
						break
					index += 1
				print(
					f"Up pressed. Mode = {self.menu['current']['mode']} Value = {self.menu['current']['option']} Selected = {selected}")
			elif (action == 'enter'):
				print(f"Enter pressed. Value = {self.menu['current']['option']}")
				index = 0
				selected = 'undefined'
				for item in self.menu[self.menu['current']['mode']]:
					if (index == self.menu['current']['option']):
						selected = item
						break
					index += 1
				# Inactive Mode Items
				if (selected == 'Startup'):
					print('Startup Selected')
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					self.menuactive = False
					self.menutime = 0
					control = ReadControl()
					control['updated'] = True
					control['mode'] = 'Startup'
					WriteControl(control)
				elif (selected == 'Monitor'):
					print('Monitor Selected')
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					self.menuactive = False
					self.menutime = 0
					control = ReadControl()
					control['updated'] = True
					control['mode'] = 'Monitor'
					WriteControl(control)
				elif (selected == 'Stop'):
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
				elif (selected == 'Shutdown'):
					print('Shutdown Selected')
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					self.menuactive = False
					self.menutime = 0
					# self.ClearDisplay()
					control = ReadControl()
					control['updated'] = True
					control['mode'] = 'Shutdown'
					WriteControl(control)
				elif (selected == 'Hold'):
					print('Hold Selected')
					self.menu['current']['mode'] = 'grill_hold_value'
					if (self.units == 'F'):
						self.menu['current']['option'] = 225  # start at 225 for F
					else:
						self.menu['current']['option'] = 100  # start at 100 for C
				elif (selected == 'Smoke'):
					print('Smoke Selected')
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					self.menuactive = False
					self.menutime = 0
					# self.ClearDisplay()
					control = ReadControl()
					control['updated'] = True
					control['mode'] = 'Smoke'
					WriteControl(control)
				elif (selected == 'SmokePlus'):
					print('Smoke Plus Selected')
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					self.menuactive = False
					self.menutime = 0
					# self.ClearDisplay()
					control = ReadControl()
					if (control['s_plus'] == True):
						control['s_plus'] = False
					else:
						control['s_plus'] = True
					WriteControl(control)
				elif (selected == 'Wifi'):
					print('Wifi Selected')
					self.DisplayNetwork()


		# Create canvas
		img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=(0, 0, 0))

		background = Image.open('background.jpg')

		# Resize the boot-splash
		background = background.resize((self.WIDTH, self.HEIGHT))

		# Set the position
		position = (0, 0)

		# Paste the splash screen onto the canvas
		img.paste(background, position)

		# Create drawing object
		draw = ImageDraw.Draw(img)

		if (self.menu['current']['mode'] == 'grill_hold_value'):
			print(f"Grill Set Point = {self.menu['current']['option']}")

			# Grill Temperature (Large Centered)
			font = ImageFont.truetype("trebuc.ttf", 120)
			text = str(self.menu['current']['option'])
			(font_width, font_height) = font.getsize(text)
			draw.text((self.WIDTH // 2 - font_width // 2, self.HEIGHT // 3 - font_height // 2), text, font=font,
					  fill=(255, 255, 255))

			# Current Mode (Bottom Center)
			font = ImageFont.truetype("trebuc.ttf", 36)
			text = "Grill Set Point"
			(font_width, font_height) = font.getsize(text)
			# Draw Black Rectangle
			draw.rectangle([(0, (self.HEIGHT // 8) * 6), (self.WIDTH, self.HEIGHT)], fill=(0, 0, 0))
			# Draw White Line/Rectangle
			draw.rectangle([(0, (self.HEIGHT // 8) * 6), (self.WIDTH, ((self.HEIGHT // 8) * 6) + 2)],
						   fill=(255, 255, 255))
			# Draw Text
			draw.text((self.WIDTH // 2 - font_width // 2, (self.HEIGHT // 8) * 6.25), text, font=font,
					  fill=(255, 255, 255))

			# Up / Down Arrows (Middle Right)
			font = ImageFont.truetype("FA-Free-Solid.otf", 80)
			text = '\uf0dc'  # FontAwesome Icon Sort (Up/Down Arrows)
			(font_width, font_height) = font.getsize(text)
			draw.text(((self.WIDTH - (font_width // 2) ** 1.3), (self.HEIGHT // 2.5 - font_height // 2)), text,
					  font=font, fill=(255, 255, 255))

		elif (self.menu['current']['mode'] != 'none'):
			# Menu Option (Large Top Center)
			index = 0
			selected = 'undefined'
			for item in self.menu[self.menu['current']['mode']]:
				if (index == self.menu['current']['option']):
					selected = item
					break
				index += 1
			font = ImageFont.truetype("FA-Free-Solid.otf", 120)
			text = self.menu[self.menu['current']['mode']][selected]['icon']
			(font_width, font_height) = font.getsize(text)
			draw.text((self.WIDTH // 2 - font_width // 2, self.HEIGHT // 2.5 - font_height // 2), text, font=font,
					  fill=(255, 255, 255))
			# Draw a Plus Icon over the top of the Smoke Icon
			if (selected == 'SmokePlus'):
				font = ImageFont.truetype("FA-Free-Solid.otf", 80)
				text = '\uf067'  # FontAwesome Icon for PLUS
				(font_width, font_height) = font.getsize(text)
				draw.text((self.WIDTH // 2 - font_width // 2, self.HEIGHT // 2.5 - font_height // 2), text, font=font,
						  fill=(0, 0, 0))

			# Current Mode (Bottom Center)
			font = ImageFont.truetype("trebuc.ttf", 36)
			text = self.menu[self.menu['current']['mode']][selected]['displaytext']
			(font_width, font_height) = font.getsize(text)
			# Draw Black Rectangle
			draw.rectangle([(0, (self.HEIGHT // 8) * 6), (self.WIDTH, self.HEIGHT)], fill=(0, 0, 0))
			# Draw White Line/Rectangle
			draw.rectangle([(0, (self.HEIGHT // 8) * 6), (self.WIDTH, ((self.HEIGHT // 8) * 6) + 2)],
						   fill=(255, 255, 255))
			# Draw Text
			draw.text((self.WIDTH // 2 - font_width // 2, (self.HEIGHT // 8) * 6.25), text, font=font,
					  fill=(255, 255, 255))

			# Up / Down Arrows (Middle Right)
			font = ImageFont.truetype("FA-Free-Solid.otf", 80)
			text = '\uf0dc'  # FontAwesome Icon Sort (Up/Down Arrows)
			(font_width, font_height) = font.getsize(text)
			draw.text(((self.WIDTH - (font_width // 2) ** 1.3), (self.HEIGHT // 2.5 - font_height // 2)), text,
					  font=font, fill=(255, 255, 255))

		# Display Image
		self.device.backlight(True)
		self.device.show()
		self.device.display(img)
