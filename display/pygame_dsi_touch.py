#!/usr/bin/env python3
'''
*****************************************
PiFire Display Interface Library
*****************************************

 Description: This library supports using pygame 
 with a DSI attached touch display like the official 
 Raspberry Pi 7 inch DSI attached display.    

 This version supports mouse for development.

*****************************************
'''

'''
 Imported Libraries
'''
import logging
import time
import threading
import socket
import pygame 
from display.base_flex import DisplayBase

'''
Display class definition
'''
class Display(DisplayBase):

	def __init__(self, dev_pins, buttonslevel='HIGH', rotation=0, units='F'):
		super().__init__(dev_pins, buttonslevel, rotation, units)
		self.eventLogger = logging.getLogger('events')

	def _init_display_device(self):
		# Setup & Start Display Loop Thread 
		display_thread = threading.Thread(target=self._display_loop)
		display_thread.start()

	def _init_input(self):
		self.input_enabled = True
		self.input_event = None
		# Init Menu Structures
		self._init_menu()

	def _display_loop(self):
		"""
		Main display loop
		"""
		# Init Device
		pygame.init()
		# set the pygame window name 
		pygame.display.set_caption('PiFire Device Display')
		# Create Display Surface

		if self.raspberry_pi:
			self.display_surface = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
			pygame.mouse.set_visible(False)  # make mouse pointer invisible 
		else: 
			self.display_surface = pygame.display.set_mode(size=(self.WIDTH, self.HEIGHT), flags=pygame.SHOWN)

		self.display_command = 'splash'

		self.touch_pos = (0,0)

		self.clock = pygame.time.Clock()

		# Create Touch Zones 
		self.touch_enter = pygame.Rect(0, 0, self.WIDTH * 0.75, self.HEIGHT)
		self.touch_up = pygame.Rect(self.WIDTH * 0.75, 0, self.WIDTH - (self.WIDTH * 0.25), self.HEIGHT / 2)
		self.touch_down = pygame.Rect(self.WIDTH * 0.75, self.HEIGHT / 2, self.WIDTH - (self.WIDTH * 0.25), self.HEIGHT / 2)

		while True:
			''' Add pygame key test here. '''
			pygame.time.delay(250)
			for event in pygame.event.get():
				if event.type == pygame.QUIT:
					break
				# Check for mouse inputs
				elif event.type == pygame.MOUSEBUTTONDOWN:
					mouse_x, mouse_y = pygame.mouse.get_pos()
					#print(f'{mouse_x}, {mouse_y}')
					self.touch_pos = (mouse_x, mouse_y)
					self.touch_held = True 
				elif event.type == pygame.MOUSEBUTTONUP:
					self.touch_held = False 
				
				# Check for touch inputs
				elif event.type == pygame.FINGERDOWN:
					touch_x = int(event.x * self.display_surface.get_width())
					touch_y = int(event.y * self.display_surface.get_height())
					#print(f'{touch_x}, {touch_y}')
					self.touch_pos = (touch_x, touch_y) 
					self.touch_held = True 
				elif event.type == pygame.FINGERUP:
					self.touch_held = False

			keys = pygame.key.get_pressed()
			if keys[pygame.K_UP]:
				self.input_event = 'UP'
			elif keys[pygame.K_DOWN]:
				self.input_event = 'DOWN'
			elif keys[pygame.K_RETURN]:
				self.input_event = 'ENTER'
			elif keys[pygame.K_x]:
				break
			elif self.touch_pos != (0,0):
				self.input_event = 'TOUCH'

			''' Normal display loop'''
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
				pygame.time.delay(3000) # Hold splash screen for 3 seconds

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

			self.clock.tick(30)

		pygame.quit()

	'''
	============== Graphics / Display / Draw Methods ============= 
	'''
	def _display_clear(self):
		self.eventLogger.info('Screen Cleared.')
		self.display_surface.fill((0,0,0))
		pygame.display.update() 

	def _display_canvas(self, canvas):
		# Convert to PyGame and Display
		strFormat = canvas.mode
		size = canvas.size
		raw_str = canvas.tobytes("raw", strFormat)
		
		self.display_image = pygame.image.fromstring(raw_str, size, strFormat)

		self.display_surface.fill((255,255,255))
		self.display_surface.blit(self.display_image, (0, 0))

		pygame.display.update() 

	'''
	 ====================== Input & Menu Code ========================
	'''
	def _event_detect(self):
		"""
		Called to detect input events from buttons, encoder, touch, etc.
		"""
		command = self.input_event  # Save to variable to prevent spurious changes 
		if command:
			self.display_timeout = None  # If something is being displayed i.e. text, network, splash then override this

			if command not in ['UP', 'DOWN', 'ENTER', 'TOUCH']:
				self.touch_pos = (0,0)
				return
			elif command == 'TOUCH':
				if self.touch_enter.collidepoint(self.touch_pos):
					command = 'ENTER'
					self.touch_pos = (0,0)
				elif self.touch_up.collidepoint(self.touch_pos):
					command = 'UP'
					if not self.touch_held:
						self.touch_pos = (0,0)
				elif self.touch_down.collidepoint(self.touch_pos):
					command = 'DOWN'
					if not self.touch_held:
						self.touch_pos = (0,0)

			self.display_command = None
			self.display_data = None
			self.input_event=None
			self.menu_active = True
			self.menu_time = time.time()
			self._menu_display(command)

