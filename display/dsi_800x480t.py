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
import time
import multiprocessing
import pygame
from PIL import Image, ImageFilter
from display.base_flex import DisplayBase
from display.flexobject_pygame import FlexObjectPygame as FlexObjPygame

'''
Dummy backlight class for prototyping 
'''
class DummyBacklight():
	def __init__(self):
		self.brightness = 100
		self.power = True
		self.fade_duration = 1

'''
Display class definition
'''
class Display(DisplayBase):

	def __init__(self, dev_pins, buttonslevel='HIGH', rotation=0, units='F', config={}):
		config['display_data_filename'] = "./display/dsi_800x480t.json"
		super().__init__(dev_pins, buttonslevel, rotation, units, config)

	def _init_display_device(self):
		''' Init backlight '''
		if self.real_hardware:
			# Use the rpi-backlight module if running on the RasPi
			from rpi_backlight import Backlight
			self.backlight = Backlight()
		else: 
			# Else use a fake module class for backlight
			self.backlight = DummyBacklight()

		self._wake_display()

		# Setup & Start Display Loop Worker
		display_worker = multiprocessing.Process(target=self._display_loop)
		display_worker.start()

	def _init_input(self):
		self.input_enabled = True
		self.input_event = None
		self.touch_pos = (0,0)

	def _display_loop(self):
		"""
		Main display loop worker
		"""
		# Init Device
		pygame.init()
		# Set the pygame window name (for debug)
		pygame.display.set_caption('PiFire Device Display')
		# Create Display Surface

		if self.real_hardware:
			flags = pygame.FULLSCREEN | pygame.DOUBLEBUF
			self.display_surface = pygame.display.set_mode((0, 0), flags)
			pygame.mouse.set_visible(False)  # make mouse pointer invisible 
		else: 
			self.display_surface = pygame.display.set_mode(size=(self.WIDTH, self.HEIGHT), flags=pygame.SHOWN)

		self.clock = pygame.time.Clock()

		self.display_loop_active = True

		''' Display the Splash Screen on Startup '''
		self._display_splash()
		pygame.time.delay(self.SPLASH_DELAY) # Hold splash screen for designated time
		self._display_clear()
		
		self.command = None 
		self.display_active = None
		self.display_timeout = None
		self.display_init = True 
		self.display_updated = False

		self.dash_object_list = []

		refresh_data = 0 

		''' Display Loop '''
		while self.display_loop_active:
			''' Fetch display data every 200ms '''
			now = time.time()
			if now - refresh_data > 0.2:
				self._fetch_data()
				refresh_data = now

			''' Poll for PyGame Events '''
			for event in pygame.event.get():
				if event.type == pygame.QUIT:
					self.display_loop_active = False
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
			
			''' Check for pressed keys '''
			keys = pygame.key.get_pressed()
			if keys[pygame.K_UP]:
				self.input_event = 'UP'
			elif keys[pygame.K_DOWN]:
				self.input_event = 'DOWN'
			elif keys[pygame.K_RETURN]:
				self.input_event = 'ENTER'
			elif keys[pygame.K_x] or keys[pygame.K_q]:
				self.display_loop_active = False
				break
			elif self.touch_pos != (0,0):
				self.input_event = 'TOUCH'

			''' Normal display loop'''
			self._event_detect()

			if self.display_active != None: 

				if self.display_timeout:
					if time.time() > self.display_timeout:
						self.display_timeout = None
						self.display_active = None
						self.display_init = True

				if self.display_active == 'home':
					if self.display_init:
						''' Initialize Home Screen '''
						self._display_background()
						self._build_objects(self.background)
						self.display_init = False
						self.display_updated = True

				elif self.display_active == 'dash':
					if self.display_init:
						''' Initialize Dash Screen '''
						self._display_background()
						if self.dash_object_list == []:
							self._init_dash()
						self._restore_dash_objects()
						self._update_dash_objects()
						self.display_init = False
						self.display_updated = True
					else:
						self._update_dash_objects()

				elif self.display_active is not None:
					if (('menu_' in self.display_active) or ('input_' in self.display_active)) and self.display_init:
						''' Initialize Menu / Input Dialog '''
						self._display_menu_background()
						self._build_objects(self.menu_background)
						self.display_init = False
						self.display_updated = True
					
				''' Perform any animations that need to be displayed. '''
				self._animate_objects()

				if self.display_updated:
					self._display_canvas()
					self.display_update = False 

			else:
				if self.display_init:
					self._display_clear()
					self.display_init = False
					if not self.HOME_ENABLED:
						self.display_active = 'dash'
						self._init_dash()
						self.display_active = None

			self.clock.tick(self.FRAMERATE)

		pygame.quit()

	'''
	============== Graphics / Display / Draw Methods ============= 
	'''

	def _init_background(self):
		super()._init_background()
		''' Convert image to PyGame surface ''' 
		strFormat = self.background.mode
		size = self.background.size
		raw_str = self.background.tobytes("raw", strFormat)
		self.background_surface = pygame.image.fromstring(raw_str, size, strFormat)

	def _init_splash(self):
		super()._init_splash()
		''' Convert image to PyGame surface ''' 
		strFormat = self.splash.mode
		size = self.splash.size
		raw_str = self.splash.tobytes("raw", strFormat)
		self.splash = pygame.image.fromstring(raw_str, size, strFormat)

	def _wake_display(self):
		self.backlight.power = True 
		self.backlight.brightness = 100 
		self.backlight.fade_duration = 1
	
	def _sleep_display(self):
		self.backlight.fade_duration = 1
		self.backlight.brightness = 0
		pygame.time.delay(1000)  # give time for the screen to fade
		self.backlight.power = False

	def _display_clear(self):
		self.eventLogger.info('Screen Cleared.')
		self._sleep_display()
		self.display_surface.fill((0,0,0,255))
		pygame.display.update() 

	def _display_canvas(self):
		pygame.display.update() 

	def _display_splash(self):
		self.display_surface.blit(self.splash, (0,0))
		self._display_canvas() 

	def _display_background(self):
		self.display_surface.blit(self.background_surface, (0,0))
		self._display_canvas()

	def _capture_background(self):
		pil_string_image = pygame.image.tostring(self.display_surface, 'RGBA', False)
		pil_image = Image.frombytes('RGBA', (self.WIDTH, self.HEIGHT), pil_string_image)
		self.menu_background = pil_image.filter(ImageFilter.GaussianBlur(radius = 5))

	def _display_menu_background(self):
		strFormat = self.menu_background.mode
		size = self.menu_background.size
		raw_str = self.menu_background.tobytes("raw", strFormat)
		background_surface = pygame.image.fromstring(raw_str, size, strFormat)
		self.display_surface.blit(background_surface, (0,0))
		self._display_canvas()

	def _build_objects(self, background):
		self.display_object_list = []

		if self.display_active in ['home', 'dash']:
			section_data = self.display_data[self.display_active] 
		elif 'menu_' in self.display_active:
			section_data = [self.display_data['menus'][self.display_active.replace('menu_', '')]]
		elif 'input_' in self.display_active:
			section_data = [self.display_data['input'][self.display_active.replace('input_', '')]]
			section_data[0]['data']['origin'] = self.input_origin
		else:
			return 
			
		for object_data in section_data:
			self.display_object_list.append(FlexObjPygame(object_data['type'], object_data, background))
	
	def _init_dash(self):
		self._init_framework()
		self._configure_dash()
		self._build_objects(self.background)
		self._build_dash_map()
		self._store_dash_objects()
	
	'''
	 ====================== Input & Menu Code ========================
	'''
	def _event_detect(self):
		"""
		Called to detect input events from buttons, encoder, touch, etc.
		"""
		user_input = self.input_event  # Save to variable to prevent spurious changes 
		self.command = None
		if user_input:
			if self.display_timeout is not None:
				self.display_timeout = time.time() + self.TIMEOUT
			if user_input not in ['UP', 'DOWN', 'ENTER', 'TOUCH']:
				self.input_event = None 
				self.touch_pos = (0,0)
				return
			elif user_input == 'TOUCH':
				self._process_touch()
			elif user_input in ['UP', 'DOWN', 'ENTER']:
				''' TODO '''
				pass

			# Clear the input event and touch_pos
			self.input_event = None
			self.touch_pos = (0,0)

	def _process_touch(self):
		if self.display_active:
			'''
			Loop through current displayed objects and check for touch collisions
			'''
			for pointer, object in enumerate(self.display_object_list):
				objectData = object.get_object_data()
				for index, touch_area in enumerate(objectData['touch_areas']):
					if touch_area.collidepoint(self.touch_pos):
						#print(f'You touched {objectData["button_list"][index]}.')
						if 'cmd_' in objectData['button_list'][index]:
							self.command = objectData['button_list'][index]
							if objectData.get('button_value', False):
								self.command_data = objectData['button_value'][index]
							else:
								self.command_data = None 
							self._command_handler()
						elif objectData['button_list'][index] == 'menu_close':
							self.display_active = 'dash'
							self.display_init = True
						elif ('menu_' in objectData['button_list'][index]) or ('input_' in objectData['button_list'][index]):
							if self.display_active == 'dash':
								self._capture_background()
								self._store_dash_objects()
							if ('input_' in objectData['button_list'][index]) and ('button_value' in list(objectData.keys())):
								self.input_origin = objectData['button_value'][index]
							self.display_active = objectData['button_list'][index]
							self.display_init = True
						elif 'button_' in objectData['button_list'][index]:
							objectData['data']['input'] = objectData['button_list'][index].replace('button_', '')
							self.display_object_list[pointer].update_object_data(updated_objectData=objectData)

		else:
			'''
			Wake the display & go to home/dash
			'''					
			self._wake_display()
			self.display_active = 'home' if self.HOME_ENABLED else 'dash'
			self.display_init = True
			self.display_timeout = time.time() + self.TIMEOUT
	