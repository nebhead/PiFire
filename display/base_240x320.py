#!/usr/bin/env python3
'''
*****************************************
PiFire Display Interface Library
*****************************************

 Description: 
   This is a base class for displays using 
 a 240Hx320W resolution.  Other display 
 libraries will inherit this base class 
 and add device specific features.

*****************************************
'''

'''
 Imported Libraries
'''
import time
import socket
import qrcode
import logging
from PIL import Image, ImageDraw, ImageFont
from common import read_control, write_control

'''
Display base class definition
'''
class DisplayBase:

	def __init__(self, dev_pins, buttonslevel='HIGH', rotation=0, units='F'):
		# Init Global Variables and Constants
		self.dev_pins = dev_pins
		self.buttonslevel = buttonslevel
		self.rotation = rotation
		self.units = units
		self.display_active = False
		self.in_data = None
		self.status_data = None
		self.display_timeout = None
		self.display_command = 'splash'
		self.input_counter = 0
		self.input_enabled = False
		# Attempt to set the log level of PIL so that it does not pollute the logs
		logging.getLogger('PIL').setLevel(logging.CRITICAL + 1)
		# Init Display Device, Input Device, Assets
		self._init_globals()
		self._init_assets() 
		self._init_input()
		self._init_display_device()

	def _init_globals(self):
		# Init constants and variables
		'''
		0 = Zero Degrees Rotation
		90, 1 = 90 Degrees Rotation (Pimoroni Libraries, Luma.LCD Libraries)
		180, 2 = 180 Degrees Rotation (Pimoroni Libraries, Luma.LCD Libraries)
		270, 3 = 270 Degrees Rotation (Pimoroni Libraries, Luma.LCD Libraries)
		'''
		if self.rotation in [90, 270, 1, 3]:
			self.WIDTH = 240
			self.HEIGHT = 320
		else:
			self.WIDTH = 320
			self.HEIGHT = 240

		self.inc_pulse_color = True 
		self.icon_color = 100
		self.fan_rotation = 0
		self.auger_step = 0

	def _init_display_device(self):
		'''
        Inheriting classes will override this function to init the display device and start the display thread.
        '''
		pass

	def _init_input(self):
		'''
		Inheriting classes will override this function to setup the inputs.
		'''
		self.input_enabled = False  # If the inheriting class does not implement input, then clear this flag
		self.input_counter = 0

	def _init_menu(self):
		self.menu_active = False
		self.menu_time = 0
		self.menu_item = ''

		self.menu = {}

		self.menu['inactive'] = {
			# List of options for the 'inactive' menu.  This is the initial menu when smoker is not running.
			'Startup': {
				'displaytext': 'Startup',
				'icon': '\uf04b'  # FontAwesome Play Icon
			},
			'Prime': {
				'displaytext': 'Prime',
				'icon': '\uf101'  # FontAwesome Double Arrow Right Icon
			},
			'Monitor': {
				'displaytext': 'Monitor',
				'icon': '\uf530'  # FontAwesome Glasses Icon
			},
			'Stop': {
				'displaytext': 'Stop',
				'icon': '\uf04d'  # FontAwesome Stop Icon
			},
			'Network': {
				'displaytext': 'IP QR Code',
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
			'Network': {
				'displaytext': 'IP QR Code',
				'icon': '\uf1eb'  # FontAwesome Wifi Icon
			}
		}

		self.menu['active_recipe'] = {
			# List of options for the 'active' menu.  This is the second level menu of options while running.
			'NextStep': {
				'displaytext': 'Next Recipe Step',
				'icon': '\uf051'  # FontAwesome Step Forward Icon
			},
			'Shutdown': {
				'displaytext': 'Shutdown',
				'icon': '\uf11e'  # FontAwesome Finish Icon
			},
			'Stop': {
				'displaytext': 'Stop',
				'icon': '\uf04d'  # FontAwesome Stop Icon
			},
			'SmokePlus': {
				'displaytext': 'Toggle Smoke+',
				'icon': '\uf0c2'  # FontAwesome Cloud Icon
			},
			'Network': {
				'displaytext': 'IP QR Code',
				'icon': '\uf1eb'  # FontAwesome Wifi Icon
			}
		}

		self.menu['prime_selection'] = {
			'Prime_10' : {
				'displaytext': '\u00BB10g',
				'icon': '10'
			},
			'Prime_25' : {
				'displaytext': '\u00BB25g',
				'icon': '25'
			},
			'Prime_50' : {
				'displaytext': '\u00BB50g',
				'icon': '50'
			},
			'Prime_10_Start' : {
				'displaytext': '\u00BB10g & Start',
				'icon': '10'
			},
			'Prime_25_Start' : {
				'displaytext': '\u00BB25g & Start',
				'icon': '25'
			},
			'Prime_50_Start' : {
				'displaytext': '\u00BB50g & Start',
				'icon': '50'
			}
		}
		self.menu['current'] = {}
		self.menu['current']['mode'] = 'none'  # Current Menu Mode (inactive, active)
		self.menu['current']['option'] = 0  # Current option in current mode

	def _display_loop(self):
		"""
		Main display loop
		"""
		while True:
			if self.input_enabled:
				self._event_detect()

			if self.display_timeout:
				if time.time() > self.display_timeout:
					self.display_timeout = None
					if not self.display_active:
						self.display_command = 'clear'

			if self.display_command == 'clear':
				self.display_active = False
				self.display_timeout = None
				self.display_command = None
				self._display_clear()

			if self.display_command == 'splash':
				self._display_splash()
				self.display_timeout = time.time() + 3
				self.display_command = 'clear'
				time.sleep(3) # Hold splash screen for 3 seconds

			if self.display_command == 'text':
				self._display_text()
				self.display_command = None
				self.display_timeout = time.time() + 10

			if self.display_command == 'network':
				s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
				s.connect(("8.8.8.8", 80))
				network_ip = s.getsockname()[0]
				if network_ip != '':
					self._display_network(network_ip)
					self.display_timeout = time.time() + 30
					self.display_command = None
				else:
					self.display_text("No IP Found")
			
			if self.input_enabled:
				if self.menu_active and not self.display_timeout:
					if time.time() - self.menu_time > 5:
						self.menu_active = False
						self.menu['current']['mode'] = 'none'
						self.menu['current']['option'] = 0
						if not self.display_active:
							self.display_command = 'clear'
				elif not self.display_timeout and self.display_active:
					if self.in_data is not None and self.status_data is not None:
						self._display_current(self.in_data, self.status_data)

			elif not self.display_timeout and self.display_active:
				if self.in_data is not None and self.status_data is not None:
					self._display_current(self.in_data, self.status_data)


			time.sleep(0.1)

	'''
	============== Input Callbacks ============= 
	
	Inheriting classes will override these functions for all inputs.
	'''
	def _enter_callback(self):
		'''
		Inheriting classes will override this function.
		'''
		pass

	def _up_callback(self, held=False):
		'''
		Inheriting classes will override this function to clear the display device.
		'''
		pass
	
	def _down_callback(self, held=False):
		'''
		Inheriting classes will override this function to clear the display device.
		'''
		pass

	'''
	============== Graphics / Display / Draw Methods ============= 
	'''
	def _init_assets(self): 
		self._init_background()
		self._init_splash()

	def _init_background(self):
		self.background = Image.open('static/img/display/background.jpg')
		self.background = self.background.resize((self.WIDTH, self.HEIGHT))
	
	def _init_splash(self):
		self.splash = Image.open('static/img/display/color-boot-splash.png')
		(self.splash_width, self.splash_height) = self.splash.size
		self.splash_width *= 2
		self.splash_height *= 2
		self.splash = self.splash.resize((self.splash_width, self.splash_height))

	def _rounded_rectangle(self, draw, xy, rad, fill=None):
		x0, y0, x1, y1 = xy
		draw.rectangle([(x0, y0 + rad), (x1, y1 - rad)], fill=fill)
		draw.rectangle([(x0 + rad, y0), (x1 - rad, y1)], fill=fill)
		draw.pieslice([(x0, y0), (x0 + rad * 2, y0 + rad * 2)], 180, 270, fill=fill)
		draw.pieslice([(x1 - rad * 2, y1 - rad * 2), (x1, y1)], 0, 90, fill=fill)
		draw.pieslice([(x0, y1 - rad * 2), (x0 + rad * 2, y1)], 90, 180, fill=fill)
		draw.pieslice([(x1 - rad * 2, y0), (x1, y0 + rad * 2)], 270, 360, fill=fill)

	def _text_circle(self, draw, position, size, text, fg_color=(255,255,255), bg_color=(0,0,0)):
		# Draw outline with fg_color
		coords = (position[0], position[1], position[0] + size[0], position[1] + size[1])
		draw.ellipse(coords, fill=fg_color)
		# Fill circle with Center with bg_color
		fill_coords = (coords[0]+2, coords[1]+2, coords[2]-2, coords[3]-2)
		draw.ellipse(fill_coords, fill=bg_color)
		# Place Text
		font_point_size = round(size[1] * 0.6)  # Convert size to height of circle * font point ratio 0.6
		font = ImageFont.truetype("trebuc.ttf", font_point_size)
		(font_width, font_height) = font.getsize(text)  # Grab the width of the text
		label_x = position[0] + (size[0] // 2) - (font_width // 2)
		label_y = position[1] + round((size[1] // 2) - (font_point_size // 2))  
		label_origin = (label_x, label_y)
		draw.text(label_origin, text, font=font, fill=fg_color)

	def _text_rectangle(self, draw, center_point, text, font_point_size, text_color, fill_color, outline_color):
		# Create drawing object
		vertical_margin = 5
		horizontal_margin = 10
		border = 2
		rad = 5

		font = ImageFont.truetype("trebuc.ttf", font_point_size)
		(font_width, font_height) = font.getsize(text)  # Grab the width of the text

		size = (font_width + horizontal_margin + border, font_height + vertical_margin + border)
		outside_coords = (center_point[0] - (size[0] // 2), center_point[1] - (size[1] // 2), center_point[0] + (size[0] // 2), center_point[1] + (size[1] // 2))
		inside_coords = (outside_coords[0] + border, outside_coords[1] + border, outside_coords[2] - border, outside_coords[3] - border)
		self._rounded_rectangle(draw, outside_coords, rad, outline_color)
		self._rounded_rectangle(draw, inside_coords, rad, fill_color)
		draw.text((center_point[0] - (font_width // 2), center_point[1] - (font_height // 1.75)), text, font=font, fill=text_color)

		#return draw

	def _create_icon(self, charid, size, color):
		# Get font and character size 
		font = ImageFont.truetype("static/font/FA-Free-Solid.otf", size)
		# Create canvas
		icon_canvas = Image.new('RGBa', font.getsize(charid))
		# Create drawing object
		draw = ImageDraw.Draw(icon_canvas)
		draw.text((0, 0), charid, font=font, fill=color)
		icon_canvas = icon_canvas.crop(icon_canvas.getbbox())
		return(icon_canvas)

	def _paste_icon(self, icon, canvas, position, rotation):
		# Rotate the icon
		icon = icon.rotate(rotation)
		# Set the position & paste the icon onto the canvas
		canvas.paste(icon, position, icon)
		return(canvas)

	def _draw_fan_icon(self, canvas, position):
		draw = ImageDraw.Draw(canvas)
		# F = Fan (Upper Left)
		icon_char = '\uf863'
		icon_color = (0, self.icon_color, 255)

		# Draw Rounded Rectangle Border
		self._rounded_rectangle(draw, 
			(position[0], position[1], 
			position[0] + 42, position[1] + 42), 
			5, icon_color)

		# Fill Rectangle with Black
		self._rounded_rectangle(draw, 
			(position[0] + 2, position[1] + 2, 
			position[0] + 40, position[1] + 40), 
			5, (0,0,0))

		# Create Icon Image
		icon = self._create_icon(icon_char, 36, icon_color)
		icon_position = (position[0] + 4, position[1] + 4)
		canvas = self._paste_icon(icon, canvas, icon_position, self.fan_rotation)

		# Increment Fan Rotation 
		self.fan_rotation += 30 
		if self.fan_rotation >= 360: 
			self.fan_rotation = 0

		return canvas

	def _draw_auger_icon(self, canvas, position):
		# Create a drawing object
		draw = ImageDraw.Draw(canvas)

		# A = Auger (Center Left)
		icon_char = '\uf101'
		icon_color = (0, self.icon_color, 0)

		# Draw Rounded Rectangle Border
		self._rounded_rectangle(draw, 
			(position[0], position[1], 
			position[0] + 42, position[1] + 42), 
			5, icon_color)

		# Fill Rectangle with Black
		self._rounded_rectangle(draw, 
			(position[0] + 2, position[1] + 2, 
			position[0] + 40, position[1] + 40), 
			5, (0,0,0))

		# Create Icon Image
		icon = self._create_icon(icon_char, 36, icon_color)
		icon_position = (position[0] + 7 + self.auger_step, position[1] + 10)
		canvas = self._paste_icon(icon, canvas, icon_position, 0)

		self.auger_step += 1 
		if self.auger_step >= 3: 
			self.auger_step = 0

		return canvas

	def _draw_ignitor_icon(self, canvas, position):
		# Create a drawing object
		draw = ImageDraw.Draw(canvas)

		# I = Ignitor  (Center Right)
		icon_char = '\uf46a'
		icon_color = (255, self.icon_color, 0)

		# Draw Rounded Rectangle Border
		self._rounded_rectangle(draw, 
			(position[0], position[1], 
			position[0] + 42, position[1] + 42), 
			5, icon_color)

		# Fill Rectangle with Black
		self._rounded_rectangle(draw, 
			(position[0] + 2, position[1] + 2, 
			position[0] + 40, position[1] + 40), 
			5, (0,0,0))

		# Create Icon Image
		icon = self._create_icon(icon_char, 36, icon_color)
		icon_position = (position[0] + 8, position[1] + 4)
		canvas = self._paste_icon(icon, canvas, icon_position, 0)

		return canvas

	def _draw_notify_icon(self, canvas, position):
		# Create a drawing object
		draw = ImageDraw.Draw(canvas)

		# Notification Bell
		icon_char = '\uf0f3'
		icon_color = (255,255, 0)

		# Draw Rounded Rectangle Border
		self._rounded_rectangle(draw, 
			(position[0], position[1], 
			position[0] + 42, position[1] + 42), 
			5, icon_color)

		# Fill Rectangle with Black
		self._rounded_rectangle(draw, 
			(position[0] + 2, position[1] + 2, 
			position[0] + 40, position[1] + 40), 
			5, (0,0,0))

		# Create Icon Image
		icon = self._create_icon(icon_char, 36, icon_color)
		icon_position = (position[0] + 6, position[1] + 3)
		canvas = self._paste_icon(icon, canvas, icon_position, 0)

		return canvas

	def _draw_recipe_icon(self, canvas, position):
		# Create a drawing object
		draw = ImageDraw.Draw(canvas)

		# Recipe Icon
		icon_char = '\uf46d'
		icon_color = (255,255, 0)

		# Draw Rounded Rectangle Border
		self._rounded_rectangle(draw, 
			(position[0], position[1], 
			position[0] + 42, position[1] + 42), 
			5, icon_color)

		# Fill Rectangle with Black
		self._rounded_rectangle(draw, 
			(position[0] + 2, position[1] + 2, 
			position[0] + 40, position[1] + 40), 
			5, (0,0,0))

		# Create Icon Image
		icon = self._create_icon(icon_char, 32, icon_color)
		icon_position = (position[0] + 9, position[1] + 5)
		canvas = self._paste_icon(icon, canvas, icon_position, 0)

		return canvas

	def _draw_pause_icon(self, canvas, position):
		# Create a drawing object
		draw = ImageDraw.Draw(canvas)

		# Recipe Pause Icon
		icon_char = '\uf04c'
		icon_color = (255,self.icon_color, 0)

		# Draw Rounded Rectangle Border
		self._rounded_rectangle(draw, 
			(position[0], position[1], 
			position[0] + 42, position[1] + 42), 
			5, icon_color)

		# Fill Rectangle with Black
		self._rounded_rectangle(draw, 
			(position[0] + 2, position[1] + 2, 
			position[0] + 40, position[1] + 40), 
			5, (0,0,0))

		# Create Icon Image
		icon = self._create_icon(icon_char, 28, icon_color)
		icon_position = (position[0] + 9, position[1] + 9)
		canvas = self._paste_icon(icon, canvas, icon_position, 0)

		return canvas

	def _draw_splus_icon(self, canvas, position):
		# Create a drawing object
		draw = ImageDraw.Draw(canvas)

		# S = Smoke Plus  (Center Right)
		icon_color = (150, 0, 255)

		# Draw Rounded Rectangle Border
		self._rounded_rectangle(draw, 
			(position[0], position[1], 
			position[0] + 42, position[1] + 42), 
			5, icon_color)

		# Fill Rectangle with Black
		self._rounded_rectangle(draw, 
			(position[0] + 2, position[1] + 2, 
			position[0] + 40, position[1] + 40), 
			5, (0,0,0))

		# Create Smoke Plus Icon Image (cloud + plus)
		font = ImageFont.truetype("static/font/FA-Free-Solid.otf", 32)
		text = '\uf0c2'  # FontAwesome Icon for Cloud (Smoke)
		draw.text((position[0] + 2, position[1] + 6), text,
					font=font, fill=(100, 0, 255))
		font = ImageFont.truetype("static/font/FA-Free-Solid.otf", 24)
		text = '\uf067'  # FontAwesome Icon for PLUS
		draw.text((position[0] + 10, position[1] + 10), text,
					font=font, fill=(0, 0, 0))

		return canvas

	def _draw_gauge(self, canvas, position, size, fg_color, bg_color, percents, temps, label, sp1_color=(0, 200, 255), sp2_color=(255, 255, 0)):
		# Create drawing object
		draw = ImageDraw.Draw(canvas)
		# bgcolor = (50, 50, 50)  # Grey
		# fgcolor = (200, 0, 0)  # Red
		# percents = [temperature, setpoint1, setpoint2]
		# temps = [current, setpoint1, setpoint2]
		# sp1_color = (0, 200, 255)  # Cyan 
		# sp2_color = (255, 255, 0)  # Yellow
		fill_color = (0, 0, 0)  # Black 

		# Draw Background Line
		coords = (position[0], position[1], position[0] + size[0], position[1] + size[1])
		draw.ellipse(coords, fill=bg_color)

		# Draw Arc for Temperature (Percent)
		if (percents[0] > 0) and (percents[0] < 100):
			endpoint = (360 * (percents[0] / 100)) + 90 
		elif percents[0] > 100:
			endpoint = 360 + 90
		else:
			endpoint = 90 
		draw.pieslice(coords, start=90, end=endpoint, fill=fg_color)

		# Draw Tic for Setpoint[1] 
		if percents[1] > 0:
			if percents[1] < 100:
				setpoint = (360 * (percents[1] / 100)) + 90 
			else: 
				setpoint = 360 + 90 
			draw.pieslice(coords, start=setpoint - 2, end=setpoint + 2, fill=sp1_color)

		# Draw Tic for Setpoint[2] 
		if percents[2] > 0:
			if percents[2] < 100:
				setpoint = (360 * (percents[2] / 100)) + 90 
			else: 
				setpoint = 360 + 90 
			draw.pieslice(coords, start=setpoint - 2, end=setpoint + 2, fill=sp2_color)

		# Fill Circle with Center with black
		fill_coords = (coords[0]+10, coords[1]+10, coords[2]-10, coords[3]-10)
		draw.ellipse(fill_coords, fill=fill_color)

		# Gauge Label
		if len(label) <= 5:
			font_point_size = round((size[1] * 0.75) / 4) + 1 # Convert size to height of circle * font point ratio / 8
		elif len(label) <= 6: 
			font_point_size = round((size[1] * 0.60) / 4) + 1 # Convert size to height of circle * font point ratio / 8
		else:
			font_point_size = round((size[1] * 0.40) / 4) + 1 # Convert size to height of circle * font point ratio / 8
		font = ImageFont.truetype("trebuc.ttf", font_point_size)
		(font_width, font_height) = font.getsize(label)  # Grab the width of the text
		label_x = position[0] + (size[0] // 2) - (font_width // 2)
		label_y = position[1] + (round(((size[1] * 0.75) / 8) * 6.6))
		label_origin = (label_x, label_y)
		draw.text(label_origin, label, font=font, fill=(255, 255, 255))

		# SetPoint1 Label 
		if percents[1] > 0:
			sp1_label = f'>{temps[1]}<'
			font_point_size = round((size[1] * 0.75) / 4) - 1  # Convert size to height of circle * font point ratio
			font = ImageFont.truetype("trebuc.ttf", font_point_size)
			(font_width, font_height) = font.getsize(sp1_label)  # Grab the width of the text
			label_x = position[0] + (size[0] // 2) - (font_width // 2)
			label_y = position[1] + round((size[1] * 0.75) / 8)  
			label_origin = (label_x, label_y)
			draw.text(label_origin, sp1_label, font=font, fill=sp1_color)

		# Current Temperature (Large Centered)
		cur_temp = str(temps[0])[:5]
		if self.units == 'F':
			font_point_size = round(size[1] * 0.45)  # Convert size to height of circle * font point ratio / 8
		else:
			font_point_size = round(size[1] * 0.3)  # Convert size to height of circle * font point ratio / 8
		font = ImageFont.truetype("trebuc.ttf", font_point_size)
		(font_width, font_height) = font.getsize(cur_temp)  # Grab the width of the text
		label_x = position[0] + (size[0] // 2) - (font_width // 2)
		label_y = position[1] + ((size[1] // 2) - (font_point_size // 1.5))  
		label_origin = (label_x, label_y)
		draw.text(label_origin, cur_temp, font=font, fill=(255,255,255))

		return(canvas)

	def _display_clear(self):
		'''
		Inheriting classes will override this function to clear the display device.
		'''
		pass


	def _display_canvas(self, canvas):
		'''
		Inheriting classes will override this function to show the canvas on the display device.
		'''
		pass

	def _display_splash(self):
		# Create canvas
		img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=(0, 0, 0))

		# Set the position & paste the splash image onto the canvas
		position = ((self.WIDTH - self.splash_width) // 2, (self.HEIGHT - self.splash_height) // 2)
		img.paste(self.splash, position)

		self._display_canvas(img)

	def _display_text(self):
		# Create canvas
		img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=(0, 0, 0))

		# Create drawing object
		draw = ImageDraw.Draw(img)

		font = ImageFont.truetype("impact.ttf", 42)
		(font_width, font_height) = font.getsize(self.display_data)
		draw.text((self.WIDTH // 2 - font_width // 2, self.HEIGHT // 2 - font_height // 2), self.display_data,
				  font=font, fill=255)

		self._display_canvas(img)

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

		self._display_canvas(img)

	def _display_current(self, in_data, status_data):
		# Create canvas
		img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=(0, 0, 0))

		# Set the position and paste the background image onto the canvas
		position = (0, 0)
		img.paste(self.background, position)

		# Create drawing object
		draw = ImageDraw.Draw(img)

		# ======== Primary Temp Circle Gauge ========
		position = (self.WIDTH // 2 - 80, self.HEIGHT // 2 - 110)
		size = (160, 160)
		bg_color = (50, 50, 50)  # Grey
		fg_color = (200, 0, 0)  # Red

		label = list(in_data['probe_history']['primary'].keys())[0]
		
		# percents = [temperature, setpoint1, setpoint2]
		temps = [0,0,0]
		percents = [0,0,0]

		temps[0] = in_data['probe_history']['primary'][label]
		if temps[0] <= 0:
			percents[0] = 0
		elif self.units == 'F':
			percents[0] = round((temps[0] / 600) * 100)  # F Temp Range [0 - 600F] for Grill
		else:
			percents[0] = round((temps[0] / 300) * 100)  # C Temp Range [0 - 300C] for Grill 

		temps[1] = in_data['primary_setpoint']
		if temps[1] <= 0:
			percents[1] = 0
		elif self.units == 'F' and status_data['mode'] == 'Hold':
			percents[1] = round((temps[1] / 600) * 100)  # F Temp Range [0 - 600F] for Grill
		elif self.units == 'C' and status_data['mode'] == 'Hold':
			percents[1] = round((temps[1] / 300) * 100)  # C Temp Range [0 - 300C] for Grill 

		temps[2] = in_data['notify_targets'][label]
		if temps[2] <= 0:
			percents[2] = 0
		elif self.units == 'F':
			percents[2] = round((temps[2] / 600) * 100)  # F Temp Range [0 - 600F] for Grill
		else:
			percents[2] = round((temps[2] / 300) * 100)  # C Temp Range [0 - 300C] for Grill 

		# Draw the Grill Gauge w/Labels
		img = self._draw_gauge(img, position, size, fg_color, bg_color, 
			percents, temps, label)

		# ======== Probe1 Temp Circle Gauge ========
		position = (10, self.HEIGHT - 110)
		size = (100, 100)
		bg_color = (50, 50, 50)  # Grey
		fg_color = (3, 161, 252)  # Blue

		label = list(in_data['probe_history']['food'].keys())[0]
		
		# temp, percents = [current temperature, setpoint1, setpoint2]
		temps = [0,0,0]
		percents = [0,0,0]

		temps[0] = in_data['probe_history']['food'][label]
		if temps[0] <= 0:
			percents[0] = 0
		elif self.units == 'F':
			percents[0] = round((temps[0] / 300) * 100)  # F Temp Range [0 - 300F] for probe
		else:
			percents[0] = round((temps[0] / 150) * 100)  # C Temp Range [0 - 150C] for probe

		temps[1] = in_data['notify_targets'][label]
		if temps[1] <= 0:
			percents[1] = 0
		elif self.units == 'F':
			percents[1] = round((temps[1] / 300) * 100)  # F Temp Range [0 - 300F] for probe
		elif self.units == 'C':
			percents[1] = round((temps[1] / 150) * 100)  # C Temp Range [0 - 150C] for probe 

		# No SetPoint2 on Probes
		temps[2] = 0
		percents[2] = 0

		# Draw the Probe1 Gauge w/Labels - Use Yellow as the SetPoint Color
		img = self._draw_gauge(img, position, size, fg_color, bg_color, 
			percents, temps, label, sp1_color=(255, 255, 0))

		# ======== Probe2 Temp Circle Gauge ========
		position = (self.WIDTH - 110, self.HEIGHT - 110)
		size = (100, 100)
		bg_color = (50, 50, 50)  # Grey
		fg_color = (3, 161, 252)  # Blue

		label = list(in_data['probe_history']['food'].keys())[1]
		
		# temp, percents = [current temperature, setpoint1, setpoint2]
		temps = [0,0,0]
		percents = [0,0,0]

		temps[0] = in_data['probe_history']['food'][label]
		if temps[0] <= 0:
			percents[0] = 0
		elif self.units == 'F':
			percents[0] = round((temps[0] / 300) * 100)  # F Temp Range [0 - 300F] for probe
		else:
			percents[0] = round((temps[0] / 150) * 100)  # C Temp Range [0 - 150C] for probe

		temps[1] = in_data['notify_targets'][label]
		if temps[1] <= 0:
			percents[1] = 0
		elif self.units == 'F':
			percents[1] = round((temps[1] / 300) * 100)  # F Temp Range [0 - 300F] for probe
		elif self.units == 'C':
			percents[1] = round((temps[1] / 150) * 100)  # C Temp Range [0 - 150C] for probe 

		# No SetPoint2 on Probes
		temps[2] = 0
		percents[2] = 0

		# Draw the Probe1 Gauge w/Labels - Use Yellow as the SetPoint Color
		img = self._draw_gauge(img, position, size, fg_color, bg_color, 
			percents, temps, label, sp1_color=(255, 255, 0))

		# Display Icons for Active Outputs

		# Pulse Color for some Icons
		if self.inc_pulse_color:
			if self.icon_color < 200:
				self.icon_color += 20
			else: 
				self.inc_pulse_color = False 
				self.icon_color -= 20 
		else:
			if self.icon_color < 100:
				self.inc_pulse_color = True
				self.icon_color += 20 
			else: 
				self.icon_color -= 20 

		if status_data['outpins']['fan']:
			# F = Fan (Upper Left), position (10,10)
			if self.WIDTH == 240:
				self._draw_fan_icon(img, (10, 50))
			else:
				self._draw_fan_icon(img, (10, 10))

		if status_data['outpins']['igniter']:
			# I = Igniter(Center Right)
			if self.WIDTH == 240:
				self._draw_ignitor_icon(img, (self.WIDTH - 52, 170))
			else:
				self._draw_ignitor_icon(img, (self.WIDTH - 52, 60))
		
		if status_data['outpins']['auger']:
			# A = Auger (Center Left)
			if self.WIDTH == 240:
				self._draw_auger_icon(img, (10, 170))
			else:
				self._draw_auger_icon(img, (10, 60))

		# Notification Indicator (Right)
		show_notify_indicator = False
		notify_count = 0
		for index, item in enumerate(status_data['notify_data']):
			if item['req'] and item['type'] != 'hopper':
				show_notify_indicator = True
				notify_count += 1

		if status_data['recipe_paused']:
			if self.WIDTH == 240:
				self._draw_pause_icon(img, (self.WIDTH - 52, 50))
			else: 
				self._draw_pause_icon(img, (self.WIDTH - 52, 10))

		elif status_data['recipe']:
			if self.WIDTH == 240:
				self._draw_recipe_icon(img, (self.WIDTH - 52, 50))
			else: 
				self._draw_recipe_icon(img, (self.WIDTH - 52, 10))

		elif show_notify_indicator:
			if self.WIDTH == 240:
				self._draw_notify_icon(img, (self.WIDTH - 52, 50))
			else: 
				self._draw_notify_icon(img, (self.WIDTH - 52, 10))

			if notify_count > 1:
				self._text_circle(draw, (self.WIDTH - 24, 40), (22, 22), str(notify_count), fg_color=(255, 255, 255), bg_color=(200, 0, 0))

		# Smoke Plus Indicator
		if status_data['s_plus'] and (status_data['mode'] == 'Smoke' or status_data['mode'] == 'Hold'):
			if self.WIDTH == 240:
				self._draw_splus_icon(img, (self.WIDTH - 52, 170))
			else:
				self._draw_splus_icon(img, (self.WIDTH - 52, 60))

		# Grill Hopper Level (Lower Center)
		text = "Hopper:" + str(status_data['hopper_level']) + "%"
		if status_data['hopper_level'] > 70:
			hopper_color = (0, 255, 0)
		elif status_data['hopper_level'] > 30:
			hopper_color = (255, 150, 0)
		else:
			hopper_color = (255, 0, 0)
		if self.WIDTH == 240:
			center_point = self.WIDTH // 2, self.HEIGHT - 14
		else:
			center_point = self.WIDTH // 2, (self.HEIGHT // 2) + 64
		self._text_rectangle(draw, center_point, text, 16, hopper_color, (0,0,0), hopper_color)

		# Current Mode (Bottom Center)
		text = status_data['mode']  # + ' Mode'
		if self.WIDTH == 240:
			center_point = (self.WIDTH // 2, 22)
		else:
			center_point = (self.WIDTH // 2, self.HEIGHT - 22)
		self._text_rectangle(draw, center_point, text, 32, text_color=(0,0,0), fill_color=(255,255,255), outline_color=(3, 161, 252))

		# Draw Units Circle
		text = f'°{self.units}'
		position = ((self.WIDTH // 2) - 13, (self.HEIGHT // 2) + 24)
		size = (26, 26)
		self._text_circle(draw, position, size, text)

		# Display Countdown for Startup / Reignite / Shutdown / Prime
		if status_data['mode'] in ['Startup', 'Reignite', 'Shutdown', 'Prime']:
			if status_data['mode'] in ['Startup', 'Reignite']: 
				duration = status_data['start_duration'] 
			elif status_data['mode'] in ['Prime']: 
				duration = status_data['prime_duration']
			else: 
				duration = status_data['shutdown_duration']
			
			countdown = int(duration - (time.time() - status_data['start_time'])) if int(duration - (time.time() - status_data['start_time'])) > 0 else 0
			text = f'{countdown}s'
			center_point = (self.WIDTH // 2, self.HEIGHT // 2 - 100)
			self._text_rectangle(draw, center_point, text, 26, text_color=(0,200,0), fill_color=(0,0,0), outline_color=(0, 200, 0))

		# Lid open detection timer display
		if status_data['mode'] in ['Hold']:
			if status_data['lid_open_detected']:
				duration = int(status_data['lid_open_endtime'] - time.time()) if int(status_data['lid_open_endtime'] - time.time()) > 0 else 0
				text = f'Lid Pause {duration}s'
				center_point = (self.WIDTH // 2, self.HEIGHT // 2 - 100)
				self._text_rectangle(draw, center_point, text, 18, text_color=(0,200,0), fill_color=(0,0,0), outline_color=(0, 200, 0))

		# Display Final Screen
		self._display_canvas(img)

	'''
	 ====================== Input & Menu Code ========================
	'''
	def _event_detect(self):
		"""
		Called to detect input events from buttons, encoder, touch, etc.
		This function should be overriden by the inheriting class. 
		"""
		pass

	def _menu_display(self, action):
		# If menu is not currently being displayed, check mode and draw menu
		if self.menu['current']['mode'] == 'none':
			control = read_control()
			# If in an inactive mode
			if control['mode'] in ['Stop', 'Error', 'Monitor', 'Prime']:
				self.menu['current']['mode'] = 'inactive'
			elif control['mode'] in ['Recipe']:
				self.menu['current']['mode'] = 'active_recipe'
			else:  # Use the active menu
				self.menu['current']['mode'] = 'active'

			self.menu['current']['option'] = 0  # Set the menu option to the very first item in the list
		# If selecting the 'grill_hold_value', take action based on button press was
		elif self.menu['current']['mode'] == 'grill_hold_value':
			if self.units == 'F':
				stepValue = 5  # change in temp each time button pressed
				minTemp = 120  # minimum temperature set for hold
				maxTemp = 500  # maximum temperature set for hold
			else:
				stepValue = 2  # change in temp each time button pressed
				minTemp = 50  # minimum temperature set for hold
				maxTemp = 260  # maximum temperature set for hold
			
			# Speed up step count if input is faster
			if self.input_counter < 3:
				pass
			elif self.input_counter < 7: 
				stepValue *= 4
			else:
				stepValue *= 6 

			if action == 'DOWN':
				self.menu['current']['option'] -= stepValue  # Step down by stepValue degrees
				if self.menu['current']['option'] <= minTemp:
					self.menu['current']['option'] = maxTemp  # Roll over to maxTemp if you go less than 120.
			elif action == 'UP':
				self.menu['current']['option'] += stepValue  # Step up by stepValue degrees
				if self.menu['current']['option'] > maxTemp:
					self.menu['current']['option'] = minTemp  # Roll over to minTemp if you go greater than 500.
			elif action == 'ENTER':
				control = read_control()
				control['primary_setpoint'] = self.menu['current']['option']
				control['updated'] = True
				control['mode'] = 'Hold'
				write_control(control, origin='display')
				self.menu['current']['mode'] = 'none'
				self.menu['current']['option'] = 0
				self.menu_active = False
				self.menu_time = 0
		# If selecting either active menu items or inactive menu items, take action based on what the button press was
		else:
			if action == 'DOWN':
				self.menu['current']['option'] -= 1
				if self.menu['current']['option'] < 0:  # Check to make sure we haven't gone past 0
					self.menu['current']['option'] = len(self.menu[self.menu['current']['mode']]) - 1
				temp_value = self.menu['current']['option']
				temp_mode = self.menu['current']['mode']
				index = 0
				selected = 'undefined'
				for item in self.menu[temp_mode]:
					if index == temp_value:
						selected = item
						break
					index += 1
			elif action == 'UP':
				self.menu['current']['option'] += 1
				# Check to make sure we haven't gone past the end of the menu
				if self.menu['current']['option'] == len(self.menu[self.menu['current']['mode']]):
					self.menu['current']['option'] = 0
				temp_value = self.menu['current']['option']
				temp_mode = self.menu['current']['mode']
				index = 0
				selected = 'undefined'
				for item in self.menu[temp_mode]:
					if index == temp_value:
						selected = item
						break
					index += 1
			elif action == 'ENTER':
				index = 0
				selected = 'undefined'
				for item in self.menu[self.menu['current']['mode']]:
					if (index == self.menu['current']['option']):
						selected = item
						break
					index += 1
				# Inactive Mode Items
				if selected == 'Startup':
					self.display_active = True
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					self.menu_active = False
					self.menu_time = 0
					control = read_control()
					control['updated'] = True
					control['mode'] = 'Startup'
					write_control(control, origin='display')
				elif selected == 'Monitor':
					self.display_active = True
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					self.menu_active = False
					self.menu_time = 0
					control = read_control()
					control['updated'] = True
					control['mode'] = 'Monitor'
					write_control(control, origin='display')
				elif selected == 'Stop':
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					self.menu_active = False
					self.menu_time = 0
					self.clear_display()
					control = read_control()
					control['updated'] = True
					control['mode'] = 'Stop'
					write_control(control, origin='display')
				# Active Mode
				elif selected == 'Shutdown':
					self.display_active = True
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					self.menu_active = False
					self.menu_time = 0
					control = read_control()
					control['updated'] = True
					control['mode'] = 'Shutdown'
					write_control(control, origin='display')
				elif selected == 'Hold':
					self.display_active = True
					self.menu['current']['mode'] = 'grill_hold_value'
					if self.in_data['primary_setpoint'] == 0:
						if self.units == 'F':
							self.menu['current']['option'] = 200  # start at 200 for F
						else:
							self.menu['current']['option'] = 100  # start at 100 for C
					else:
						self.menu['current']['option'] = self.in_data['primary_setpoint']
				elif selected == 'Smoke':
					self.display_active = True
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					self.menu_active = False
					self.menu_time = 0
					control = read_control()
					control['updated'] = True
					control['mode'] = 'Smoke'
					write_control(control, origin='display')
				elif selected == 'SmokePlus':
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					self.menu_active = False
					self.menu_time = 0
					control = read_control()
					if control['s_plus']:
						control['s_plus'] = False
					else:
						control['s_plus'] = True
					write_control(control, origin='display')
				elif selected == 'Network':
					self.display_network()
				elif selected == 'Prime':
					self.menu['current']['mode'] = 'prime_selection'
					self.menu['current']['option'] = 0
				elif 'Prime_' in selected:
					control = read_control()
					if '50' in selected:
						control['prime_amount'] = 25
					elif '25' in selected:
						control['prime_amount'] = 25
					else:
						control['prime_amount'] = 10

					if 'Start' in selected:
						control['next_mode'] = 'Startup'
					else:
						control['next_mode'] = 'Stop'
					self.display_active = True
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					self.menu_active = False
					self.menu_time = 0
					control['updated'] = True
					control['mode'] = 'Prime'
					write_control(control, origin='display')
				elif 'NextStep' in selected:
					self.display_active = True
					self.menu['current']['mode'] = 'none'
					self.menu['current']['option'] = 0
					self.menu_active = False
					self.menu_time = 0
					control = read_control()
					# Check if currently in 'Paused' Status
					if 'triggered' in control['recipe']['step_data'] and 'pause' in control['recipe']['step_data']:
						if control['recipe']['step_data']['triggered'] and control['recipe']['step_data']['pause']:
							# 'Unpause' Recipe 
							control['recipe']['step_data']['pause'] = False
							write_control(control, origin='display')
						else:
							# User is forcing next step
							control['updated'] = True
							write_control(control, origin='display')
					else:
						# User is forcing next step
						control['updated'] = True
						write_control(control, origin='display')

		# Create canvas
		img = Image.new('RGB', (self.WIDTH, self.HEIGHT), color=(0, 0, 0))
		# Set the position & paste background image onto canvas 
		position = (0, 0)
		img.paste(self.background, position)
		# Create drawing object
		draw = ImageDraw.Draw(img)

		if self.menu['current']['mode'] == 'grill_hold_value':
			# Grill Temperature (Large Centered)
			font_point_size = 80 if self.WIDTH == 240 else 120 
			font = ImageFont.truetype("trebuc.ttf", font_point_size)
			text = str(self.menu['current']['option'])
			(font_width, font_height) = font.getsize(text)
			if self.WIDTH == 240:
				draw.text((self.WIDTH // 2 - font_width // 2 - 20, self.HEIGHT // 2.5 - font_height // 2), text, font=font,
					  fill=(255, 255, 255))
			else:
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

		elif self.menu['current']['mode'] != 'none':
			# Menu Option (Large Top Center)
			index = 0
			selected = 'undefined'
			for item in self.menu[self.menu['current']['mode']]:
				if index == self.menu['current']['option']:
					selected = item
					break
				index += 1
			font_point_size = 80 if self.WIDTH == 240 else 120 
			font = ImageFont.truetype("static/font/FA-Free-Solid.otf", font_point_size)
			text = self.menu[self.menu['current']['mode']][selected]['icon']
			(font_width, font_height) = font.getsize(text)
			draw.text((self.WIDTH // 2 - font_width // 2, self.HEIGHT // 2.5 - font_height // 2), text, font=font,
					  fill=(255, 255, 255))
			# Draw a Plus Icon over the top of the Smoke Icon
			if selected == 'SmokePlus':
				font_point_size = 60 if self.WIDTH == 240 else 80
				font = ImageFont.truetype("static/font/FA-Free-Solid.otf", font_point_size)
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

		# Change color of Arrow for Up / Down when adjusting temperature
		up_color = (255, 255, 255)
		down_color = (255, 255, 255)

		if action == 'UP': 
			up_color = (255, 255, 0)
		elif action == 'DOWN':
			down_color = (255, 255, 0)

		# Up / Down Arrows (Middle Right)
		font_point_size = 80 if self.WIDTH == 240 else 60 
		font = ImageFont.truetype("static/font/FA-Free-Solid.otf", font_point_size)
		text = '\uf0de'  # FontAwesome Icon Sort (Up Arrow)
		(font_width, font_height) = font.getsize(text)
		draw.text(((self.WIDTH - (font_width // 2) ** 1.3), (self.HEIGHT // 2.5 - font_height // 2)), text,
					font=font, fill=up_color)

		text = '\uf0dd'  # FontAwesome Icon Sort (Down Arrow)
		(font_width, font_height) = font.getsize(text)
		draw.text(((self.WIDTH - (font_width // 2) ** 1.3), (self.HEIGHT // 2.4 - font_height // 2)), text,
					font=font, fill=down_color)
		
		self._display_canvas(img)
		time.sleep(0.05)

		# Up / Down Arrows (Middle Right)
		font_point_size = 80 if self.WIDTH == 240 else 60 
		font = ImageFont.truetype("static/font/FA-Free-Solid.otf", font_point_size)
		text = '\uf0de'  # FontAwesome Icon Sort (Up Arrow)
		(font_width, font_height) = font.getsize(text)
		draw.text(((self.WIDTH - (font_width // 2) ** 1.3), (self.HEIGHT // 2.5 - font_height // 2)), text,
					font=font, fill=(255, 255, 255))

		text = '\uf0dd'  # FontAwesome Icon Sort (Down Arrow)
		(font_width, font_height) = font.getsize(text)
		draw.text(((self.WIDTH - (font_width // 2) ** 1.3), (self.HEIGHT // 2.4 - font_height // 2)), text,
		font=font, fill=(255, 255, 255))

		self._display_canvas(img)


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
