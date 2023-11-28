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
import threading
import pygame
from PIL import Image, ImageFilter
from display.base_flex import DisplayBase, DisplayObjects

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

		self.WIDTH = 800
		self.HEIGHT = 480
		self.FRAMERATE = 20
		self.SPLASH_DELAY = 500  # 1000 = 1s 
		super().__init__(dev_pins, buttonslevel, rotation, units, config)

	def _init_display_device(self):
		''' Init backlight '''
		if self.raspberry_pi:
			# Use the rpi-backlight module if running on the RasPi
			from rpi_backlight import Backlight
			self.backlight = Backlight()
		else: 
			# Else use a fake module class for backlight
			self.backlight = DummyBacklight()

		self._wake_display()

		# Setup & Start Display Loop Thread 
		display_thread = threading.Thread(target=self._display_loop)
		display_thread.start()

	def _init_input(self):
		self.input_enabled = True
		self.input_event = None
		self.touch_pos = (0,0)

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

		''' Display Loop '''
		while self.display_loop_active:
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

			'''
			TODO
			'''
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
						self._init_framework()
						self._configure_dash()
						self._build_objects(self.background)
						self._build_dash_map()
						self._store_dash_objects()
						self.display_active = None

			self.clock.tick(self.FRAMERATE)

		pygame.quit()

	'''
	============== Graphics / Display / Draw Methods ============= 
	'''
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
			self.display_object_list.append(DisplayObjects(object_data['type'], object_data, background))

	def _configure_dash(self):
		''' Build Food Probe Map '''
		num_food_probes = min(len(self.config['probe_info']['food']), self.display_data['metadata']['max_food_probes'])
		self.food_probe_label_map = {}
		self.food_probe_name_map = {}
		for index in range(num_food_probes):
			self.food_probe_label_map[f'food_probe_gauge_{index}'] = self.config['probe_info']['food'][index]['label']
			self.food_probe_name_map[f'food_probe_gauge_{index}'] = self.config['probe_info']['food'][index]['name']

		''' Remove Unused Food Probes & Rename Used Food Probes'''
		display_data_dash_list = []
		for object in self.display_data['dash']:
			if 'food_probe_gauge_' in object['name'] and object['name'] not in list(self.food_probe_label_map.keys()):
				pass
			else: 
				if 'food_probe_gauge_' in object['name']:
					''' Rename Displayed Food Probes '''
					object['label'] = self.food_probe_name_map[object['name']]
					object['units'] = self.units
					object['button_value'] = [object['label']]
				elif object['name'] == 'primary_gauge':
					object['label'] = self.config['probe_info']['primary']['name']
					object['button_value'] = [object['label']]
				
				display_data_dash_list.append(object)

		self.display_data['dash'] = display_data_dash_list 

	def _build_dash_map(self):
		''' Setup dash object mapping '''
		self.dash_map = {}

		#print('Setting up Dash Map:')
		for index, object in enumerate(self.display_object_list):
			objectData = object.get_object_data()
			self.dash_map[objectData['name']] = index 
			#print(f' - Index: {index}, Maps to: {objectData["name"]}')

	def _update_dash_objects(self):
				
		if self.in_data is not None and self.status_data is not None:
			''' Update Mode Bar and Control Panel '''
			if (self.status_data['mode'] != self.last_status_data.get('mode', 'None')) or (self.status_data['recipe_paused'] != self.last_status_data.get('recipe_paused', 'None')):
				object_data = self.display_object_list[self.dash_map['mode_bar']].get_object_data()
				if self.status_data['recipe'] and self.status_data['mode'] != 'Shutdown':
					object_data['text'] = 'Recipe: ' + self.status_data['mode']
				else: 
					object_data['text'] = self.status_data['mode']
				self.display_object_list[self.dash_map['mode_bar']].update_object_data(object_data)

				object_data = self.display_object_list[self.dash_map['control_panel']].get_object_data()
				object_data['button_active'] = self.status_data['mode']
				if self.status_data['recipe']:
					''' Recipe Mode '''
					list_item = 'cmd_none'
					type_item = 'Error'
					if self.status_data['mode'] in ['Startup', 'Reignite']:
						type_item = 'Startup'
					elif self.status_data['mode'] == 'Smoke':
						type_item = 'Smoke'
					elif self.status_data['mode'] == 'Hold':
						type_item = 'Hold'
					elif self.status_data['mode'] == 'Shutdown':
						type_item = 'None'
					object_data['button_list'] = ['cmd_next_step', list_item, 'cmd_stop', 'cmd_shutdown']
					object_data['button_type'] = ['Next', type_item, 'Stop', 'Shutdown']
					if self.status_data['recipe_paused']:
						object_data['button_active'] = 'Next'
				elif self.status_data['mode'] in ['Startup', 'Reignite']:
					''' Startup Mode '''
					object_data['button_list'] = ['cmd_startup', 'cmd_smoke', 'input_hold', 'cmd_stop']
					object_data['button_type'] = ['Startup', 'Smoke', 'Hold', 'Stop']
				elif self.status_data['mode'] in ['Smoke', 'Hold', 'Shutdown']:
					''' Smoke, Hold or Shutdown Modes '''
					object_data['button_list'] = ['cmd_smoke', 'input_hold', 'cmd_stop', 'cmd_shutdown']
					object_data['button_type'] = ['Smoke', 'Hold', 'Stop', 'Shutdown']
				else:
					''' Stopped, Prime, Monitor Modes '''
					object_data['button_list'] = ['menu_prime', 'menu_startup', 'cmd_monitor', 'cmd_stop']
					object_data['button_type'] = ['Prime', 'Startup', 'Monitor', 'Stop']
				
				self.display_object_list[self.dash_map['control_panel']].update_object_data(object_data)

			''' Update Primary Gauge Values '''
			if self.last_in_data != {}:
				primary_key = list(self.in_data['probe_history']['primary'].keys())[0]  # Get the key for the primary gauge 
				if (self.in_data['probe_history']['primary'] != self.last_in_data['probe_history']['primary']) or \
					(self.in_data['primary_setpoint'] != self.last_in_data['primary_setpoint']) or \
					(self.in_data['notify_targets'][primary_key] != self.last_in_data['notify_targets'].get(primary_key)):
					
					''' Update the Primary Gauge '''
					object_data = self.display_object_list[self.dash_map['primary_gauge']].get_object_data()
					object_data['temps'][0] = self.in_data['probe_history']['primary'][primary_key]
					object_data['temps'][1] = self.in_data['notify_targets'][primary_key]
					object_data['temps'][2] = self.in_data['primary_setpoint']
					object_data['units'] = self.units 
					#object_data['label'] = primary_key
					self.display_object_list[self.dash_map['primary_gauge']].update_object_data(object_data)
			
			''' Update Food Probe Gauges and Values '''
			if self.last_in_data != {}:
				food_gauge_keys = list(self.food_probe_label_map.keys())
				for gauge in food_gauge_keys:
					key = self.food_probe_label_map[gauge]
					if self.last_in_data['probe_history']['food'][key] != \
						self.in_data['probe_history']['food'][key] or \
						self.last_in_data['notify_targets'][key] != \
						self.in_data['notify_targets'][key]:
						
						''' Update this food gauge '''
						object_data = self.display_object_list[self.dash_map[gauge]].get_object_data()
						object_data['temps'][0] = self.in_data['probe_history']['food'][key]
						object_data['temps'][1] = self.in_data['notify_targets'][key]
						object_data['temps'][2] = 0  # There is no set temp for food probes 
						object_data['units'] = self.units
						self.display_object_list[self.dash_map[gauge]].update_object_data(object_data)

			''' Update Output Status Icons '''
			if self.last_status_data.get('outpins') is None:
				self.last_status_data['outpins'] = self.status_data['outpins'].copy()
				for output in self.last_status_data['outpins']:
					self.last_status_data['outpins'][output] = True if self.status_data['outpins'][output] == False else False
			for output in self.status_data['outpins']:
				if self.status_data['outpins'][output] != self.last_status_data['outpins'].get(output):
					if output == 'auger':
						object_data = self.display_object_list[self.dash_map['auger_status']].get_object_data()
						object_data['animation_enabled'] = True if self.status_data['outpins'][output] else False
						object_data['active'] = True if self.status_data['outpins'][output] else False
						self.display_object_list[self.dash_map['auger_status']].update_object_data(object_data)
					if output == 'fan':
						object_data = self.display_object_list[self.dash_map['fan_status']].get_object_data()
						object_data['animation_enabled'] = True if self.status_data['outpins'][output] else False
						object_data['active'] = True if self.status_data['outpins'][output] else False
						self.display_object_list[self.dash_map['fan_status']].update_object_data(object_data)
					if output == 'igniter':
						object_data = self.display_object_list[self.dash_map['igniter_status']].get_object_data()
						object_data['animation_enabled'] = True if self.status_data['outpins'][output] else False
						object_data['active'] = True if self.status_data['outpins'][output] else False
						self.display_object_list[self.dash_map['igniter_status']].update_object_data(object_data)

			''' Update Timer Output '''
			if self.status_data['mode'] in ['Prime', 'Startup', 'Reignite', 'Shutdown']:
				if self.status_data['mode'] in ['Startup', 'Reignite']: 
					duration = self.status_data['start_duration']
				elif self.status_data['mode'] in ['Prime']: 
					duration = self.status_data['prime_duration']
				else: 
					duration = self.status_data['shutdown_duration']
			
				countdown = int(duration - (time.time() - self.status_data['start_time'])) if int(duration - (time.time() - self.status_data['start_time'])) > 0 else 0
				object_data = self.display_object_list[self.dash_map['timer']].get_object_data()

				if countdown != object_data['data']['seconds']:
					object_data['data']['seconds'] = countdown
					object_data['label'] = 'Timer'
					self.display_object_list[self.dash_map['timer']].update_object_data(object_data)
			
			elif self.status_data['mode'] in ['Hold'] and self.status_data['lid_open_detected']:
				''' In Hold Mode, use timer for lid open detection '''
				countdown = int(self.status_data['lid_open_endtime'] - time.time()) if int(self.status_data['lid_open_endtime'] - time.time()) > 0 else 0
				object_data = self.display_object_list[self.dash_map['timer']].get_object_data()
				if countdown != object_data['data']['seconds']:
					object_data['data']['seconds'] = countdown
					object_data['label'] = 'Lid Pause'
					self.display_object_list[self.dash_map['timer']].update_object_data(object_data)

			else:
				''' Clear the timer in other modes. '''
				object_data = self.display_object_list[self.dash_map['timer']].get_object_data()
				if object_data['data']['seconds'] != 0:
					object_data['data']['seconds'] = 0
					self.display_object_list[self.dash_map['timer']].update_object_data(object_data)

			''' In Hold Mode, Check Lid Indicator '''
			if self.status_data['mode'] in ['Hold'] and self.last_status_data['lid_open_detected'] != self.status_data['lid_open_detected']:
				object_data = self.display_object_list[self.dash_map['lid_indicator']].get_object_data()
				if self.status_data['lid_open_detected']:
					object_data['active'] = True 
				else:
					object_data['active'] = False
				self.display_object_list[self.dash_map['lid_indicator']].update_object_data(object_data)

			''' Update PMode '''
			if self.status_data['mode'] in ['Startup', 'Reignite', 'Smoke'] and	\
				((self.status_data['mode'] != self.last_status_data.get('mode', 'None')) or \
	  			(self.status_data['p_mode'] != self.last_status_data.get('p_mode', 'None'))):
				
				object_data = self.display_object_list[self.dash_map['p_mode']].get_object_data()
				object_data['active'] = True
				object_data['data']['pmode'] = self.status_data['p_mode']
				self.display_object_list[self.dash_map['p_mode']].update_object_data(object_data)
			
			elif self.status_data['mode'] != self.last_status_data.get('mode', 'None'): 
				object_data = self.display_object_list[self.dash_map['p_mode']].get_object_data()
				object_data['active'] = False 
				self.display_object_list[self.dash_map['p_mode']].update_object_data(object_data)

			''' Update Smoke Plus '''
			if self.status_data['s_plus'] != self.last_status_data.get('s_plus', None):
				object_data = self.display_object_list[self.dash_map['smoke_plus']].get_object_data()

				object_data['active'] = self.status_data['s_plus'] 
				object_data['button_value'][0] = "off" if self.status_data['s_plus'] else "on" 
				
				self.display_object_list[self.dash_map['smoke_plus']].update_object_data(object_data)

			''' Update Hopper Info '''
			if self.status_data['hopper_level'] != self.last_status_data.get('hopper_level', None):
				object_data = self.display_object_list[self.dash_map['hopper']].get_object_data()
				object_data['data']['level'] = max(self.status_data['hopper_level'], 0)
				object_data['data']['level'] = min(object_data['data']['level'], 100)

				self.display_object_list[self.dash_map['hopper']].update_object_data(object_data)

			''' After all the updates, update the last states/data '''
			self.last_in_data = self.in_data.copy() 
			self.last_status_data = self.status_data.copy()

	def _update_input_objects(self):
		'''
		for index, object in enumerate(self.display_object_list):
			objectData = object.get_object_data()
			if objectData['data']['input'] != '':
				self.display_object_list[index].update_object_data(objectData)
		'''
		pass 
	
	def _animate_objects(self):
		for object in self.display_object_list: 
			objectData = object.get_object_data()
			objectState = object.get_object_state()

			if objectData['animation_enabled'] and objectState['animation_active']:
				object_image = object.update_object_data()
				self.display_updated = True 
				self.display_surface.blit(object_image, objectData['position'])
			else:
				object_image = object.get_object_surface()
				self.display_surface.blit(object_image, objectData['position'])

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
						print(f'You touched {objectData["button_list"][index]}.')
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
	