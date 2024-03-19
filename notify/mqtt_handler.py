#!/usr/bin/env python3

# *****************************************
# PiFire Mqtt Interface Library
# *****************************************
#
# Description: This library supports publishing data to an mqtt
#				broker, including metadata for homeassistant
#				sensor autodiscovery.
#
# Install Dependencies:
#
#    sudo pip3 install paho-mqtt
#
# *****************************************

import paho.mqtt.client as mqtt
import json
import logging
import time
from socket import gethostname
from common import create_logger
import psutil
#from common import write_control


class MqttNotificationHandler:

	def __init__(self, settings) -> None:
		""" Initialize an mqtt client
		Home Assistant mqtt sensor metadata: https://www.home-assistant.io/integrations/sensor.mqtt/
		Home Assistant auto-discovery description: https://www.home-assistant.io/integrations/mqtt/

		Arguments:
		settings: PiFire settings dict
		"""

		try:	
			self.client = None				# Initialize to none so we can check its existance later
			self.initialized_topics = []	# Topics that have already sent auto-discover data
			self.last = {}					# Last published values so we can send by exception
			self.last_mode = None			# Last mode we were in
			self.last_conn_time = 0			# Last time we tried to connect to the mqtt broker
			self.subscriptions = []			# Topics we have subscribed to so we can be remotely controlled
			self.control = None				# Link to the control structure so we can send controls to the Control app

			# Create shortcuts to settings we will use frequently
			self._global_settings = settings['globals']
			self._probe_settings  = settings['probe_settings']['probe_map']['probe_info']
			self._mqtt_settings   = settings['notify_services']['mqtt']

			# This lists contexts that will be published to mqtt
			self.CONTEXTS = ['control','devices',
			 	'probe_data_primary','probe_data_food','probe_data_aux','probe_data_tr',
			 	'pid', 'pid_config','pid_cycle_data','pellet','notify_event','system']
			
			# These list the devices aka attributes that will be published to mqtt
			self.DEVICE_SENSORS = ['auger','igniter','power','fan','notify_event']
			self.CONTROL_SENSORS = ['mode','next_mode','s_plus','pwm_control','duty_cycle','status','primary_setpoint']
			self.PID_CONFIG_SENSORS = ['PB','Td','Ti','center']
			self.PID_CYCLE_TIME_SENSORS = ['HoldCycleTime','LidOpenPauseTime','LidOpenThreshold','PMode','SmokeCycleTime','u_max','u_min']
			self.PID_SENSORS = ['kp','ki','kd','p','i','d','u','error','derv','inter','inter_max']
			self.HOPPER_SENSORS = ['hopper_level']
			self.CONTROL_NOTIFY_SENSORS = ['target']
			#self.LAST_NOTIFICATION = ['msg']
			self.SYSTEM_SENSORS = ['cpu','available_memory','free_memory','cpu_temp']

			# Setup logging
			log_level = logging.DEBUG if settings['globals']['debug_mode'] else logging.INFO
			self._mqttLogger = create_logger('mqtt', filename='./logs/mqtt.log', level=log_level, 
									messageformat='%(asctime)s | %(levelname)s | %(thread)s | %(message)s')

			# Default payload for setting up home assistant auto discovery messagage.  
			self.discovery_topic = self._mqtt_settings['homeassistant_autodiscovery_topic']
			self.pifire_id = self._mqtt_settings['id']
			grill_name = "PiFire" if len(self._global_settings['grill_name']) == 0 else self._global_settings['grill_name']
			self.default_payload = {
				'availability': [{
				 	'topic': f"{self.pifire_id}/availability",
				 	}],
				'availability_mode': 'all',
				'device': {
					'identifiers': [ self.pifire_id	],
					'manufacturer': "PiFire",
					'model': settings['modules']['grillplat'],
					'name': grill_name,
					'configuration_url': f"http://{gethostname()}:5000/settings"
					},
				'enabled_by_default': True,
				}
			
			# Connect to the broker
			self._check_connection()
						
		except:
			self._mqttLogger.exception(f'Error initializing the mqtt class object: ')

	def __del__(self):
		try:
			self._publish_data(topic=f"{self._mqtt_settings['id']}/availability",payload="offline")
			self.client.loop_stop()
			self.client.disconnect()
		except:
			self._mqttLogger.exception(f'Error occurred closing mqtt client: ')	
	
	def _connect(self):	
			try:
				settings = self._mqtt_settings

				# Initialize our client if not already intialized
				if self.client == None:
					
					# Future: may want to make these configurable
					self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, transport='tcp', protocol=mqtt.MQTTv5)
					self.client.on_connect = self._on_connect
					self.client.on_disconnect = self._on_disconnect
					self.client.on_connect_fail = self._on_connect_fail
					self.client.on_message = self._on_message
					self.client.will_set(topic=f"{settings['id']}/availability",payload="offline")

					if len(settings['username']) > 0:
						self.client.username_pw_set(settings['username'], settings['password']) 

					# Future: may want to support tls
					#self.client.tls_set( certfile=None, keyfile=None, cert_reqs=None)				
				
				ret = self.client.connect(host=settings['broker'], port=int(settings['port']),
							  			  keepalive=10)
				
				if ret == mqtt.MQTT_ERR_SUCCESS:
					self.client.loop_start()	#Will run async forever, monitoring mqtt and sending keepalives
				else:
					self._mqttLogger.error(f"Error {mqtt.connack_string(ret)} connecting to {settings['broker']}.")
					self.client = None
			except:
				self._mqttLogger.exception(f'Error occurred connecting to the mqtt broker: ')

	def _on_connect(self, client, userdata, flags, rc, properties):
		self._mqttLogger.info(f"Connection to '{self._mqtt_settings['broker']}' returned result: '{mqtt.connack_string(rc)}'")
		self.last_conn_time = 0
		self._publish_data(topic=f"{self._mqtt_settings['id']}/availability",payload="online", qos=1)

		# Restore any subscriptions that we have
		for sub in self.subscriptions:
			self._subscribe(sub)

	def _on_message(self, client, userdata, msg):
		
		# Ignore if we haven't finished intializing or haven't enabled control
		#if self.control == None: return
		#if self._mqtt_settings['control'] == False: return
		
		# element = msg.topic.split('/')[-1]
		# payload = msg.payload.decode('utf-8')

		# self._mqttLogger.debug(f"Recieved message {payload} for {element}")

		# if element == "mode":
		# 		# If going into Hold mode we need to set the setpoint as well.  Default to 150 if not set.
		# 		if payload == 'Hold':
		# 			self.control['primary_setpoint'] = max(self.control['primary_setpoint'], 150)

		# 		self.control[element] = payload
		# 		self.control['updated'] = 'yes'
		# 		write_control(self.control, direct_write=False, origin='mqtt')

		# 		#TODO when switching to HOLD mode we also need to send a setpoint

		# elif element == "primary_setpoint":
		# 		#Only adjust the setpoint if we are in Hold mode
		# 		if (self.control['mode']) == 'Hold':
		# 			self.control[element] = int(payload)
		# 			self.control['updated'] = 'yes'
		# 			write_control(self.control, direct_write=False, origin='mqtt')

		# 	else:
		# 		pass
		pass

	def _on_disconnect(self, client, userdata, rc, properties):
		if rc != 0:
			self._mqttLogger.error(f"Disconnect returned result: {mqtt.connack_string(rc)}")
		else:
			self._mqttLogger.info(f"Disconnect returned result: {mqtt.connack_string(rc)}")

	def _on_connect_fail(self, client, userdata, rc):
		self._mqttLogger.error(f"Connection failure: {mqtt.connack_string(rc)}")

	def _check_connection(self):

		# Connection process is async, so give it some time
		if time.time() < self.last_conn_time + 5: return False
		
		# Connect if not already connected
		if self.client is None or not self.client.is_connected():
			self._mqttLogger.error(f"Need to connect to the broker")
			self._connect()
			self.last_conn_time = time.time()
		
		return self.client.is_connected()

	def _check_homeassistant(self):
		return len(self._mqtt_settings['homeassistant_autodiscovery_topic']) > 0

	def _publish_data(self, topic, payload, qos=0, retain=False, properties=None):

		if not self._check_connection(): 
			return False

		ret= self.client.publish(topic, payload, qos, retain, properties)

		# Check the return
		if ret.rc == mqtt.MQTT_ERR_SUCCESS:
			return True
		elif ret.rc == mqtt.MQTT_ERR_CONN_LOST:
			self._mqttLogger.error(f"Cannot publish data for {topic} because the mqtt connection is lost.")
			return False
		elif ret.rc == mqtt.MQTT_ERR_AUTH:
			self._mqttLogger.error(f"Cannot publish data for {topic} because of error {mqtt.connack_string(ret.rc)}")
			self.client = None
		else:
			self._mqttLogger.error(f"Cannot publish data for {topic} because of error {mqtt.connack_string(ret.rc)}")
			return False
			
	def _publish_autodiscover(self, category, topic, payload, qos=2, retain=True, properties=None):

		ret= self.client.publish(topic, payload, qos, retain, properties)

		# Check the return
		if ret.rc == mqtt.MQTT_ERR_SUCCESS:
			if not category in self.initialized_topics:
				self.initialized_topics.append(category)
		elif ret.rc == mqtt.MQTT_ERR_CONN_LOST:
			self._mqttLogger.error(f"Cannot publish autodiscover data for {topic} because the mqtt connection is lost.")
		else:
			self._mqttLogger.error(f"Cannot publish autodiscover data for {topic} because of error {mqtt.connack_string(ret.rc)}")
	
	def _publish(self, context, data):

		# Extract the supported attributes and verify there is a change
		change_detected = False
		payload = {}
		for device in data:		
			if (context == 'devices' and device in self.DEVICE_SENSORS) or \
			   (context == 'control' and device in self.CONTROL_SENSORS) or \
			   (context == 'pid_config' and device in self.PID_CONFIG_SENSORS) or \
			   (context == 'pid_cycle_data' and device in self.PID_CYCLE_TIME_SENSORS) or \
			   (context == 'pellet') and device in self.HOPPER_SENSORS or \
			   (context == 'pid' and device in self.PID_SENSORS) or \
			   (context == 'notify_event') or \
			   (context == 'system') or \
			   (context.startswith('control_notify_data') and device in self.CONTROL_NOTIFY_SENSORS) or \
			   (context.startswith("probe_data")):

				device_name = context + '_' + device
				last_val = self.last.get(device_name)
				payload[device] = data[device]
				new_val = data[device]
				if new_val != last_val:
					change_detected = True
					self.last[device_name] = new_val

		if not change_detected: return
		
		if self._publish_data(topic=f"{self._mqtt_settings['id']}/{context}", payload=json.dumps(payload)):

			# Publish home assitant auto-discovery info
			if self._check_homeassistant:
				self._create_autodiscover(context, data)
	
	def _subscribe(self,topic):
		self.client.subscribe(topic)
		if topic not in self.subscriptions: 
			self.subscriptions.append(topic)

	def _create_autodiscover(self, context, data):
		for device in data:
			device_name = context + '_' + device
			topic_name = device_name
			if device_name in self.last:
				if not device_name in set(self.initialized_topics):

					discovery = self.default_payload.copy()
					discovery['state_topic'] = f"{self.pifire_id}/{context}"
					discovery['object_id'] = f"{self.pifire_id}_{device_name}".lower()
					discovery['unique_id'] = f"{self.pifire_id}_{device_name}".lower()
					discovery['value_template'] = f"{{{{ value_json.{device} }}}}"
					discovery['name'] = device.title().replace('_',' ')	

					datatype = type(data[device])			

					if datatype == bool:
						component = "binary_sensor"
						discovery['payload_on'] = True
						discovery['payload_off'] = False
						
						if device not in {'auger','igniter','power','fan'}:
							discovery['enabled_by_default'] = False

					elif datatype == str:
						component = "sensor"

					elif datatype == int or datatype == float:
						component = "sensor"
						discovery['state_class'] = "measurement"

						if context in ['probe_data_primary', 'probe_data_food','probe_data_aux']:
							discovery['device_class'] = "temperature"
							discovery['unit_of_measurement'] = f"°{self._global_settings['units']}"
							suffix = 'Temp'

						if context == 'probe_data_tr':
							discovery['unit_of_measurement'] = "ohms"
							discovery['enabled_by_default'] = False
							discovery['entity_category'] = "diagnostic"
							suffix = 'RTD Ohms'

						if context.startswith('probe_data'):
							# Find this probes name in the settings
							for probe in self._probe_settings:
								if probe['label'] == device:
									discovery['name'] = f"{discovery['name']} {suffix}"
									topic_name = context + '_' + probe['port']
									break

						if context.startswith('control_notify'):
							discovery['device_class'] = "temperature"
							discovery['unit_of_measurement'] = f"°{self._global_settings['units']}"
							suffix = 'Target'
							for probe in self._probe_settings:
								if probe['label'] == data['label']:
									discovery['name'] = f"{data['name']} {suffix}"
									topic_name = context
									break

						if context.startswith('pid'):
							discovery['entity_category'] = "diagnostic"
							if device in ['p','i','d','u']:
								discovery['unit_of_measurement'] = "%"
								discovery['value_template'] = f"{{{{ value_json.{device} | round(2)}}}}"
							discovery['enabled_by_default'] = False
							
						if device in ['u_min', 'u_max', 'center']:
							discovery['value_template'] = f"{{{{ value_json.{device} * 100 }}}}"
							discovery['unit_of_measurement'] = "%"
							discovery['enabled_by_default'] = False

						if device in ['available_memory', 'free_memory']:
								discovery['unit_of_measurement'] = "b"

						if device in ['duty_cycle', 'hopper_level','cpu']:
							discovery['unit_of_measurement'] = "%"

						if device in ['PB', 'Td', 'Ti', 'HoldCycleTime', 'LidOpenPauseTime']:
							discovery['unit_of_measurement'] = "s"
							discovery['enabled_by_default'] = False

						if device == 'cpu_temp':
							discovery['device_class'] = "temperature"
							discovery['unit_of_measurement'] = "°C"

						if device in ['primary_setpoint']:
							discovery['device_class'] = "temperature"
							discovery['unit_of_measurement'] = f"°{self._global_settings['units']}"

							#if self._mqtt_settings['control']:
								#component = "number"

								# Make setpoint subscribeable and subscribe to it
								#discovery['command_topic'] = f"{discovery['state_topic']}/set/{device}"
								#discovery['min'] = 100
								#discovery['max'] = 700
								#discovery['mode'] = 'auto'
								#discovery['optimistic'] = 'false'
								#discovery['step'] = 1
								#self._subscribe(discovery['command_topic'])
							
					self._publish_autodiscover(
									device, 
									f"{self.discovery_topic}/{component}/{self.pifire_id}/{topic_name}/config", 
									json.dumps(discovery))
					
					self.initialized_topics.append(device_name)

	def notify(self, context: str, data: dict):
		""" Publish changed data to the mqtt broker

		Parameters: 
			context (str): Description of the data (devices, probes, control, cycle)
			data (dict): Key-value pairs of data to publish
		"""
		try:		
			# Split out nested dictionaries 
			for key in data:
				if key == 'notify_data':
					for device in data[key]:
						#new_context = context + '_' + key + '_' + device['label']
						for probe in self._probe_settings:
							if probe['label'] == device['label']:
								new_context = context + '_' + key + '_' + probe['port']
								break
						self.notify(new_context, device )
				elif isinstance(data[key], dict):
					new_context = context + '_' + key
					self.notify(new_context, data[key])

			# Save the latest control info
			if context == 'control' and self.control == None:
				self.control = data

			# Get system info if requested
			if context == 'system':
				data = {}
				data['cpu'] = psutil.cpu_percent(interval=None)
				data['available_memory'] = psutil.virtual_memory().available
				data['free_memory'] = psutil.virtual_memory().free
				if 'sensors_temperatures' in dir(psutil):
					# This is for raspberry PI.  Other hardware may be different
					temps = psutil.sensors_temperatures()
					if 'cpu_thermal' in temps:
						cpu_temps = temps['cpu_thermal']
						data['cpu_temp'] = cpu_temps[0].current

			# Publish the data we are interested in
			if context in self.CONTEXTS or context.startswith('control_notify_data'): 
				self._publish(context, data)

			# Check to see if we have changed operating mode
			if context != 'control' or data['mode'] == self.last_mode: return

			new_mode = data['mode']

			# Update the message state if we moved to a more advanced state (ignore Stop and Error)
			# all modes ['Stop','Recipe','Error','Reignite','Monitor','Prime','Startup','Smoke','Hold','Shutdown','Manual']
			#if new_mode in ['Recipe', 'Reignite','Monitor','Prime','Startup','Smoke','Hold','Shutdown','Manual']:
			payload = {'msg': f"Entered {new_mode} mode" }
			self.notify("notify_event", payload)
			
			self.last_mode = data['mode']

			# Zero the PID data if not controlling
			if data['mode'] not in ['Hold']:
				payload = {}
				for key in self.PID_SENSORS:
					payload[key] = 0
				self._publish('pid', payload)

			# Zero the temps if stopped
			if data['mode'] == "Stop":
				primary_data = {}
				food_data = {}
				aux_data = {}
				tr_data = {}
				for probe in self._probe_settings:
					if probe['type'] == 'Food':
						food_data[probe['label']] = 0
					elif probe['type'] ==  'Primary':
						primary_data[probe['label']] = 0
					elif probe['type'] ==  'aux':
						aux_data[probe['label']] = 0
					else:
						pass

					tr_data[probe['label']] = 0
				self._publish('probe_data_primary', primary_data)
				self._publish('probe_data_food', food_data)
				self._publish('probe_data_aux', aux_data)
				self._publish('probe_data_tr', tr_data)
				
		except:
			self._mqttLogger.exception(f'Error occurred publishing device data: ')
