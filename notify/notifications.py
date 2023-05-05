#!/usr/bin/env python3

'''
==============================================================================
 PiFire Notifications Module
==============================================================================

Description: This library provides notification functions for
   control.py

==============================================================================
'''

'''
==============================================================================
 Imported Modules
==============================================================================
'''
import datetime
import time
import requests
import json
import apprise
import logging
from common import write_settings, write_control, create_logger

'''
==============================================================================
 Functions
==============================================================================
'''

def check_notify(in_data, control, settings, pelletdb, grill_platform):
	"""
	Check for any pending notifications

	:param in_data: In Data (Probe Temps)
	:param control: Control
	:param settings: Settings
	:param pelletdb: Pellet DB
	:param grill_platform: Grill Platform
	"""
	if settings['notify_services']['influxdb']['url'] != '' and settings['notify_services']['influxdb']['enabled']:
		_send_influxdb_notification('GRILL_STATE', control, settings, pelletdb, in_data, grill_platform)

	''' Get simple list of temperatures key:value pairs '''
	probe_temp_list = {}
	for group in in_data['probe_history']:
		if group != 'tr':
			for probe in in_data['probe_history'][group]:
				probe_temp_list[probe] = in_data['probe_history'][group][probe]

	''' Process all registered notification items '''
	for index, item in enumerate(control['notify_data']):
		if item['req']: 
			if item['type'] == 'probe':
				if probe_temp_list[item['label']] >= in_data['notify_targets'][item['label']]:
					send_notifications("Probe_Temp_Achieved", control, settings, pelletdb, label=item['label'], target=in_data['notify_targets'][item['label']])
					if control['mode'] == 'Recipe':
						if control['recipe']['step_data']['trigger_temps'][item['label']] > 0:
							control['recipe']['step_data']['triggered'] = True
					control['notify_data'][index]['req'] = False
					control['notify_data'][index]['target'] = 0 

			elif item['type'] == 'timer':
				if time.time() >= control['timer']['end']:
					send_notifications("Timer_Expired", control, settings, pelletdb)
					if control['mode'] == 'Recipe':
						if control['recipe']['step_data']['timer'] > 0:
							control['recipe']['step_data']['triggered'] = True
					control['timer']['start'] = 0
					control['timer']['paused'] = 0
					control['timer']['end'] = 0
					control['notify_data'][index]['req'] = False 

			elif item['type'] == 'hopper':
				if (time.time() - item['last_check']) > (settings['pelletlevel']['warning_time'] * 60):
					if pelletdb['current']['hopper_level'] <= settings['pelletlevel']['warning_level']:
						send_notifications("Pellet_Level_Low", control, settings, pelletdb)
						control['notify_data'][index]['last_check'] = time.time()
			
			''' Do Shutdown or Keep Warm if Requested '''
			if item['shutdown'] and control['mode'] in ('Reignite', 'Startup', 'Smoke', 'Hold') and not control['notify_data'][index]['req']:
				control['mode'] = 'Shutdown'
				control['updated'] = True
				control['notify_data'][index]['shutdown'] = False 
			elif item['keep_warm'] and control['mode'] in ('Smoke', 'Hold') and not control['notify_data'][index]['req']:
				control['mode'] = 'Hold'
				control['primary_setpoint'] = settings['keep_warm']['temp']
				control['s_plus'] = settings['keep_warm']['s_plus']
				control['updated'] = True
				control['notify_data'][index]['keep_warm'] = False 

			write_control(control, direct_write=True, origin='notifications')

	return control

def send_notifications(notify_event, control, settings, pelletdb, label='Probe', target=0):
	"""
	Build and send notification based on notify_event and write to log.

	:param notify_event: String Event
	:param control: Control
	:param settings: Settings
	:param pelletdb: Pellet DB
	"""
	log_level = logging.DEBUG if settings['globals']['debug_mode'] else logging.INFO
	eventLogger = create_logger('events', filename='/tmp/events.log', messageformat='%(asctime)s [%(levelname)s] %(message)s', level=log_level)
	date = datetime.datetime.now()
	now = date.strftime('%m-%d %H:%M')
	time = date.strftime('%H:%M')
	day = date.strftime('%m/%d')

	unit = settings['globals']['units']

	if "Probe_Temp_Achieved" in notify_event:
		title_message = f"{label} Target Achieved"
		body_message = f"{label} target of {target} {unit} achieved at {time} on {day}"
		channel = 'pifire_temp_alerts'
		query_args = {"value1": True}
		eventLogger.info(body_message)
	elif "Timer_Expired" in notify_event:
		title_message = "Timer Complete"
		body_message = "Your timer has expired, time to check your cook!"
		channel = 'pifire_timer_alerts'
		query_args = {"value1": 'Your timer has expired.'}
		eventLogger.info(body_message)
	elif "Pellet_Level_Low" in notify_event:
		title_message = "Low Pellet Level"
		body_message = f"Your pellet level is currently at {pelletdb['current']['hopper_level']}%"
		channel = 'pifire_pellet_alerts'
		query_args = {"value1": body_message}
		eventLogger.info(body_message)
	elif "Grill_Error_00" in notify_event:
		title_message = "Grill Error!"
		body_message = "Your grill has experienced an error and will shutdown now. " + str(now)
		channel = 'pifire_error_alerts'
		query_args = {"value1": 'Your grill has experienced an error and will shutdown now. '}
		eventLogger.info(body_message)
	elif "Grill_Error_01" in notify_event:
		title_message = "Grill Error!"
		body_message = "Grill exceded maximum temperature limit of " + str(
			settings['safety']['maxtemp']) + unit + "! Shutting down. " + str(now)
		channel = 'pifire_error_alerts'
		query_args = {"value1": str(settings['safety']['maxtemp'])}
		eventLogger.info(body_message)
	elif "Grill_Error_02" in notify_event:
		title_message = "Grill Error!"
		body_message = "Grill temperature dropped below minimum startup temperature of " + str(
			control['safety']['startuptemp']) + unit + "! Shutting down to prevent firepot overload. " + str(now)
		channel = 'pifire_error_alerts'
		query_args = {"value1": str(control['safety']['startuptemp'])}
		eventLogger.info(body_message)
	elif "Grill_Error_03" in notify_event:
		title_message = "Grill Error!"
		body_message = "Grill temperature dropped below minimum startup temperature of " + str(
			control['safety']['startuptemp']) + unit + "! Starting a re-ignite attempt, per user settings."
		channel = 'pifire_error_alerts'
		query_args = {"value1": str(control['safety']['startuptemp'])}
		eventLogger.info(body_message)
	elif "Grill_Warning" in notify_event:
		title_message = "Grill Warning!"
		body_message = "Your grill has experienced a warning condition. Please check the logs. " + str(now)
		channel = 'pifire_error_alerts'
		query_args = {"value1": 'General Warning.'}
		eventLogger.info(body_message)
	elif "Recipe_Step_Message" in notify_event:
		title_message = "Recipe Message"
		body_message = control['recipe']['step_data']['message'] + str(now)
		channel = 'pifire_recipe_message'
		query_args = {"value1": control['recipe']['step_data']['message']}
		eventLogger.info(body_message)
	else:
		title_message = "PiFire: Unknown Notification issue"
		body_message = "Whoops! PiFire had the following unhandled notify event: " + notify_event + " at " + str(now)
		channel = 'default'
		query_args = {"value1": 'Unknown Notification issue'}
		eventLogger.error(body_message)

	if settings['notify_services']['apprise']['locations'] != '' and settings['notify_services']['apprise']['enabled']:
		_send_apprise_notifications(settings, title_message, body_message)
	if settings['notify_services']['ifttt']['APIKey'] != '' and settings['notify_services']['ifttt']['enabled']:
		_send_ifttt_notification(settings, notify_event, query_args)
	if settings['notify_services']['pushbullet']['APIKey'] != '' and settings['notify_services']['pushbullet']['enabled']:
		_send_pushbullet_notification(settings, title_message, body_message)
	if settings['notify_services']['pushover']['APIKey'] != '' and settings['notify_services']['pushover']['UserKeys'] != '' \
		and settings['notify_services']['pushover']['enabled']:
		_send_pushover_notification(settings, title_message, body_message)
	if settings['notify_services']['onesignal']['app_id'] != '' and settings['notify_services']['onesignal']['enabled']:
		_send_onesignal_notification(settings, title_message, body_message, channel)


def _send_apprise_notifications(settings, title_message, body_message):
	"""
	Send Apprise Notifications

	:param settings: Settings
	:param title_message: Message Title
	:param body_message: Message Body
	"""
	log_level = logging.DEBUG if settings['globals']['debug_mode'] else logging.INFO
	eventLogger = create_logger('events', filename='/tmp/events.log', messageformat='%(asctime)s [%(levelname)s] %(message)s', level=log_level)
	if(len(settings['notify_services']['apprise']['locations'])):
		eventLogger.info("Sending Apprise Notifications: " + ", ".join(settings['notify_services']['apprise']['locations']))
		appriseHandler = apprise.Apprise()

		for location in settings['notify_services']['apprise']['locations']:
			appriseHandler.add(location)

		result = appriseHandler.notify(
			title=title_message,
			body=body_message,
		)
	else:
		eventLogger.warning("No Apprise Locations Configured")

def _send_pushover_notification(settings, title_message, body_message):
	"""
	Send Pushover Notifications

	:param settings: Settings
	:param title_message: Message Title
	:param body_message: Message Body
	"""
	log_level = logging.DEBUG if settings['globals']['debug_mode'] else logging.INFO
	eventLogger = create_logger('events', filename='/tmp/events.log', messageformat='%(asctime)s [%(levelname)s] %(message)s', level=log_level)
	url = 'https://api.pushover.net/1/messages.json'
	for user in settings['notify_services']['pushover']['UserKeys'].split(','):
		try:
			response = requests.post(url, data={
				"token": settings['notify_services']['pushover']['APIKey'],
				"user": user.strip(),
				"message": body_message,
				"title": title_message,
				"url": settings['notify_services']['pushover']['PublicURL']
			})

			if not response.status_code == 200:
				eventLogger.warning("Pushover Notification Failed: " + title_message)

			eventLogger.debug("Pushover Response: " + response.text)

		except Exception as e:
			eventLogger.warning("Pushover Notification to %s failed: %s" % (user, e))
		except:
			eventLogger.warning("Pushover Notification to %s failed for unknown reason." % (user))


def _send_pushbullet_notification(settings, title_message, body_message):
	"""
	Send PushBullet Notifications

	:param settings: Settings
	:param title_message: Message Title
	:param body_message: Message Body
	:return:
	"""
	log_level = logging.DEBUG if settings['globals']['debug_mode'] else logging.INFO
	eventLogger = create_logger('events', filename='/tmp/events.log', messageformat='%(asctime)s [%(levelname)s] %(message)s', level=log_level)
	api_key = settings['notify_services']['pushbullet']['APIKey']
	pushbullet_link = settings['notify_services']['pushbullet']['PublicURL']
	url = "https://api.pushbullet.com/v2/pushes"

	headers = {"content-type": "application/json", "Authorization": 'Bearer ' + api_key}
	payload = {"type": "link", "title": title_message, "url": pushbullet_link, "body": body_message}

	try:
		response = requests.post(url, headers=headers, data=json.dumps(payload))

		if not response.status_code == 200:
			eventLogger.warning("PushBullet Notification Failed: " + title_message)

		eventLogger.debug("PushBullet Response: " + response.text)

	except Exception as e:
		eventLogger.warning("PushBullet Notification failed: %s" % (e))
	except:
		eventLogger.warning("PushBullet Notification failed for unknown reason.")


def _send_onesignal_notification(settings, title_message, body_message, channel):
	"""
	Send OneSignal Push Notification

	:param settings: Settings
	:param title_message: Message Title
	:param body_message: Message Body
	:param channel: Android Notifications Channel
	"""
	log_level = logging.DEBUG if settings['globals']['debug_mode'] else logging.INFO
	eventLogger = create_logger('events', filename='/tmp/events.log', messageformat='%(asctime)s [%(levelname)s] %(message)s', level=log_level)
	app_id = settings['notify_services']['onesignal']['app_id']
	devices = settings['notify_services']['onesignal']['devices']
	url = "https://onesignal.com/api/v1/notifications"
	player_ids = []

	for key in devices.keys():
		player_ids.append(key)

	if player_ids:
		headers = {"Content-Type": "application/json; charset=utf-8"}
		payload = {"app_id": app_id,
				   "include_player_ids": player_ids,
				   "headings": {"en": title_message},
				   "contents": {"en": body_message},
				   "priority": 10,
				   "existing_android_channel_id": channel,
				   "ttl" : 3600 }

		try:
			response = requests.post(url, headers=headers, data=json.dumps(payload))

			if not response.status_code == 200:
				eventLogger.warning("OneSignal Notification Failed: " + title_message)

			eventLogger.debug("OneSignal Response: " + response.text)

			json_response = response.json()
			if 'errors' in json_response:
				if 'invalid_player_ids' in json_response['errors']:
					for device in json_response['errors']['invalid_player_ids']:
						if device in settings['onesignal']['devices']:
							eventLogger.info("OneSignal: " + settings['onesignal']['devices'][device]
							['device_name'] + " has an invalid id and has been removed")
							settings['onesignal']['devices'].pop(device)
							write_settings(settings)

		except Exception as e:
			eventLogger.warning("OneSignal Notification failed: %s" % (e))
		except:
			eventLogger.warning("OneSignal Notification failed for unknown reason.")
	else:
		eventLogger.warning("OneSignal Notification Failed No Devices Registered")


def _send_ifttt_notification(settings, notify_event, query_args):
	"""
	Send IFTTT Notifications

	:param settings: Settings
	:param notify_event: String Event
	:param query_args: Query Args
	"""
	log_level = logging.DEBUG if settings['globals']['debug_mode'] else logging.INFO
	eventLogger = create_logger('events', filename='/tmp/events.log', messageformat='%(asctime)s [%(levelname)s] %(message)s', level=log_level)
	key = settings['notify_services']['ifttt']['APIKey']
	url = 'https://maker.ifttt.com/trigger/' + notify_event + '/with/key/' + key

	try:
		r = requests.post(url, data=query_args)
		eventLogger.info("IFTTT Notification Success: " + r.text)
	except:
		eventLogger.warning("IFTTT Notification Failed: " + url)


influx_handler = None

def _send_influxdb_notification(notify_event, control, settings, pelletdb, in_data, grill_platform):
	"""
	Send influxdb Notifications

	:param notify_event: String Event
	:param control: Control
	:param settings: Settings
	:param pelletdb: Pellet DB
	:param in_data: In Data (Probe Temps)
	:param grill_platform: Grill Platform
	"""
	global influx_handler
	if not influx_handler:
		from notify.influxdb_handler import InfluxNotificationHandler
		influx_handler = InfluxNotificationHandler(settings)
	influx_handler.notify(notify_event, control, settings, pelletdb, in_data, grill_platform)
