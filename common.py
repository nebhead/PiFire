#!/usr/bin/env python3

# *****************************************
# PiFire Common Library
# *****************************************
#
# Description: This library provides functions that are common to 
#  both app.py and control.py
#
# *****************************************

# *****************************************
# Imported Libraries
# *****************************************
import time
import datetime
import os
import io
import json
import math
import redis
import uuid
import random

# *****************************************
# Functions
# *****************************************

# Setup Command / Status database connection
cmdsts = redis.StrictRedis('localhost', 6379, charset="utf-8", decode_responses=True)

def default_settings():
	settings = {}

	settings['versions'] = {
		'server' : "1.3.6",
		'cookfile' : "1.0.1",  # Current cookfile format version
		'recipe' : "1.0.0"  # Current recipe file format version
	}

	settings['history_page'] = {
		'minutes' : 15, 				# Sets default number of minutes to show in history
		'clearhistoryonstart' : True, 	# Clear history when StartUp Mode selected
		'autorefresh' : 'on', 			# Sets history graph to auto refresh ('live' graph)
		'datapoints' : 60 				# Number of data points to show on the history chart
	}

	settings['probe_settings'] = {
		'probe_profiles' :  _default_probe_profiles(),
		'probes_enabled' : [1,1,1],
		'probe_sources' : ['ADC0', 'ADC1', 'ADC2', 'ADC3'], # Probe sources can be ADC0-3 or max31865
		'probe_options' : ['ADC0', 'ADC1', 'ADC2', 'ADC3'] 	# Probe source options (max31865 can be added but requires spi-dev to be installed and control.py to be restarted to load the module)
	}

	settings['globals'] = {
		'grill_name' : '',
		'debug_mode' : False,
		'page_theme' : 'light',
		'triggerlevel' : 'LOW',
		'buttonslevel' : 'HIGH',
		'disp_rotation' : 0,
		'shutdown_timer' : 60,
		'startup_timer' : 240,
		'auto_power_off' : False,
		'four_probes' : False,
		'dc_fan': False,
		'standalone': True,
		'units' : 'F',
		'augerrate' : 0.3,  		# (grams per second) default auger load rate is 10 grams / 30 seconds
		'first_time_setup' : True,  # Set to True on first setup, to run wizard on load 
		'ext_data' : False,  # Set to True to allow tracking of extended data.  More data will be stored in the history database and can be reviewed in the CSV.
	}

	settings['apprise'] = {
		'enabled': False,
		'locations': {} 		# list of locations
	}

	settings['ifttt'] = {
		'enabled': False,
		'APIKey': '' 		# API Key for WebMaker IFTTT App notification
	}

	settings['pushbullet'] = {
		'enabled': False,
		'APIKey': '', 		# API Key for PushBullet notifications
		'PublicURL': '' 	# Used in PushBullet notifications
	}

	settings['pushover'] = {
		'enabled': False,
		'APIKey': '', 		# API Key for Pushover notifications
		'UserKeys': '', 	# Comma-separated list of user keys
		'PublicURL': '' 	# Used in Pushover notifications
	}

	settings['onesignal'] = {
		'enabled': False,
		'uuid' : generate_uuid(),
		'app_id' : '',
		'devices' : {}
	}

	settings['influxdb'] = {
		'enabled': False,
		'url': '',
		'token': '',
		'org': '',
		'bucket': ''
	}

	settings['probe_types'] = {
		'grill1type' : 'PT-1000-OEM',
		'grill2type' : 'TWPS00',
		'probe1type' : 'TWPS00',
		'probe2type' : 'TWPS00'
	}

	settings['grill_probe_settings'] = {
		'grill_probes': _default_grill_probes(),
		'grill_probe' : 'grill_probe1',
		'grill_probe_enabled' : [1,0,0]
	}

	settings['outpins'] = {
		'power' : 4,
		'auger' : 14,
		'fan' : 15,
		'igniter' : 18,
		'dc_fan' : 26,
		'pwm' : 13
	}

	settings['inpins'] = { 'selector' : 17 }

	settings['dev_pins'] = {	# Device Pin Assignment
		'input': {
			'up_clk': 16,		# Up Button or CLK for encoder
			'enter_sw' : 21,	# Enter Button or SW for encoder
			'down_dt' : 20		# Down Button or DT for encoder
		},
		'display': {
			'led' : 5,			# ILI9341: LED	- ST7789: BL
			'dc' : 24,			# ILI9341: DC	- ST7789: DC
			'rst' : 25			# ILI9341: RST	- ST7789: RST
		},
		'distance': {
			'trig': 23,			# For hcsr04
			'echo' : 27			# For hcsr04
		},
	}

	# PID controller based on proportional band in standard PID form
	# https://en.wikipedia.org/wiki/PID_controller#Ideal_versus_standard_PID_form
	# u = Kp (e(t)+ 1/Ti INT + Td de/dt)
	# PB = Proportional Band
	# Ti = Goal of eliminating in Ti seconds
	# Td = Predicts error value at Td in seconds

	settings['cycle_data'] = {
		'PB' : 60.0,
		'Ti' : 180.0,
		'Td' : 45.0,
		'HoldCycleTime' : 20,
		'SmokeCycleTime' : 15,
		'PMode' : 2,  			# http://tipsforbbq.com/Definition/Traeger-P-Setting
		'u_min' : 0.15,
		'u_max' : 1.0,
		'center' : 0.5, 
		'LidOpenDetectEnabled' : False,  #  Enable Lid Open Detection
		'LidOpenThreshold' : 15,	 #  Percentage drop in temperature from the hold temp, to trigger lid open event
		'LidOpenPauseTime' : 60  #  Number of seconds to pause when a lid open event is detected 
	}

	settings['keep_warm'] = {
		'temp' : 165,
		's_plus' : False
	}

	settings['smoke_plus'] = {
		'enabled' : False, 		# Sets default Enable/Disable (True = Enabled, False = Disabled)
		'min_temp' : 160, 		# Minimum temperature to cycle fan on/off
		'max_temp' : 220, 		# Maximum temperature to cycle fan on/off
		'on_time' : 5, 			# Number of seconds the fan will remain ON
		'off_time' : 5, 		# Number of seconds the fan will remain OFF
		'duty_cycle' : 75, 		# Duty cycle that will be used during fan ramping. 20-100%
		'fan_ramp' : False 		# If enabled fan will ramp up to speed instead of just turning on
	}

	settings['pwm'] = {
		'pwm_control': False,
		'update_time' : 10,
		'frequency' : 30, 		# PWM Fan Frequency. This may vary with different fans
		'min_duty_cycle' : 20, 	# This is the minimum duty cycle that can be set. Some fans stall below a certain speed
		'max_duty_cycle' : 100, # This is the maximum duty cycle that can be set. Can limit fans that are overpowered
		'temp_range_list' : [3, 7, 10, 15],  # Temp Bands for Each Profile
		'profiles' : [
			{
				'duty_cycle' : 20 		# Duty Cycle to set fan
			},
			{
				'duty_cycle' : 35
			},
			{
				'duty_cycle' : 50
			},
			{
				'duty_cycle' : 75
			},
			{
				'duty_cycle' : 100
			}
		]
	}

	settings['safety'] = {
		'minstartuptemp' : 75, 	# User Defined. Minimum temperature allowed for startup.
		'maxstartuptemp' : 100, # User Defined. Take this value if the startup temp is higher than maxstartuptemp
		'maxtemp' : 550, 		# User Defined. If temp exceeds value in any mode, shut off. (including monitor mode)
		'reigniteretries' : 1 	# Number of tries to reignite grill if it has gone below the safe temp (0 to disable)
	}

	settings['pelletlevel'] = {
		'warning_enabled' : True,
		'warning_level' : 25,	# Percent to begin low pellet warning notifications
		'warning_time' : 20,	# Number of minutes to check for low pellets and send notification
		'empty' : 22, 			# Number of centimeters from the sensor that indicates empty
		'full' : 4  			# Number of centimeters from the sensor that indicates full
	}

	settings['modules'] = {
		'grillplat' : 'prototype',
		'adc' : 'prototype',
		'display' : 'prototype',
		'dist' : 'prototype'
	}

	settings['lastupdated'] = {
		'time' : math.trunc(time.time())
	}

	settings['smartstart'] = {
		'enabled' : True, 
		'temp_range_list' : [60, 80, 90],  # Min Temps for Each Profile
		'profiles' : [
			{
				'startuptime' : 360,  
				'augerontime' : 15,
				'p_mode' : 0
			},
			{
				'startuptime' : 360,  
				'augerontime' : 15,
				'p_mode' : 1
			},
			{
				'startuptime' : 240,  
				'augerontime' : 15,
				'p_mode' : 3
			},
			{
				'startuptime' : 240,  
				'augerontime' : 15,
				'p_mode' : 5
			}
		]
	}

	settings['start_to_mode'] = {
		'after_startup_mode' : 'Smoke',
		'grill1_setpoint' : 165  # If Hold, set the setpoint
	}

	settings['dashboard'] = {
		'current' : 'Default', 
		'dashboards' : [
			{	'name' : 'Default',
				'friendly_name' : 'Default/Classic Dashboard', 
				'html_name' : 'dash_default.html'
			},
			{	'name' : 'Modern',
				'friendly_name' : 'Modern Dashboard', 
				'html_name' : 'dash_default.html'
			},
		]
	}

	return settings

def default_control():
	settings = read_settings()

	control = {}

	control['updated'] = True

	control['mode'] = 'Stop'

	control['next_mode'] = 'Stop'

	control['s_plus'] = settings['smoke_plus']['enabled'] 		# Smoke-Plus Feature Enable/Disable

	control['pwm_control'] = settings['pwm']['pwm_control'] 	# Temp Fan Control Enable/Disable

	control['duty_cycle'] = settings['pwm']['max_duty_cycle'] 	# Set PWM Fan Duty Cycle

	control['hopper_check'] = False 	# Trigger a synchronous hopper level check

	control['recipe'] = {
		'filename' : '',
		'start_step' : 0,
		'step' : 0,
		'step_data' : {}
	}

	control['status'] = ''

	control['probe_profile_update'] = False

	control['settings_update'] = False

	control['distance_update'] = False

	control['units_change'] = False  	# Used to indicate that a units change has been requested

	control['tuning_mode'] = False  	# Used to set tuning mode enabled so Tr values will be recorded (False by default)

	control['safety'] = {
		'startuptemp' : 0, 		# Set by control function at startup
		'afterstarttemp' : 0, 	# Set by control function during startup
		'reigniteretries' : settings['safety']['reigniteretries'], # Set by user to attempt a re-ignite when the grill drops below a certain temp
		'reignitelaststate' : 'Smoke' # Set by control function to remember the last state we were in when the temp dropped below safety levels
	}

	control['setpoints'] = {
		'grill' : 0,
		'probe1' : 0,
		'probe2' : 0,
		'grill_notify' : 0
	}

	control['notify_req'] = {
		'grill' : False,
		'probe1' : False,
		'probe2' : False,
		'timer' : False
	}

	control['notify_data'] = {
		'hopper_low' : False,
		'p1_shutdown' : False,
		'p2_shutdown' : False,
		'timer_shutdown' : False,
		'p1_keep_warm' : False,
		'p2_keep_warm' : False,
		'timer_keep_warm' : False
	}

	control['timer'] = {
		'start' : 0,
		'paused' : 0,
		'end' : 0,
		'shutdown' : False 
	}

	control['manual'] = {
		'change' : False,
		'fan' : False,
		'auger' : False,
		'igniter' : False,
		'power' : False,
		'pwm' : 100
	}

	control['errors'] = []

	control['probe_titles'] = {
		'grill_title' : 'Grill',
		'probe1_title' : 'Probe 1',
		'probe2_title' : 'Probe 2',
	}

	control['smartstart'] = {
		'startuptemp' : 0,
		'profile_selected' : 0
	}

	control['prime_amount'] = 10  # Default Prime Amount in Grams

	return(control)

"""
List of Tuples ('metric_key', default_value)
 - This structure will be used to build the default metrics structure, and to export the data easily
 - To add a metric, simply add a tuple to this list.  
"""
metrics_items = [ 
	('id', 0),
	('starttime', 0),
	('starttime_c', 0),  		# Converted Start Time
	('endtime', 0),
	('endtime_c', 0),  			# Converted End Time
	('timeinmode', 0),  		# Calculated Time in Mode
	('mode', ''),  
	('augerontime', 0), 
	('augerontime_c', 0), 		# Converted Auger On Time
	('estusage_m', ''),  		# Estimated pellet usage in metric (grams)
	('estusage_i', ''),  		# Estimated pellet usage in pounds (and ounces)
	('fanontime', 0),
	('fanontime_c', 0),  		# Converted Fan On Time
	('smokeplus', True), 
	('grill_settemp', 0),
	('smart_start_profile', 0), # Smart Start Profile Selected
	('startup_temp', 0), # Smart Start Start Up Temp
	('p_mode', 0), # P_mode selected
	('auger_cycle_time', 0),  # Auger Cycle Time
	('pellet_level_start', 0),  # Pellet Level at the begining of this mode
	('pellet_level_end', 0),  # Pellet Level at the end of this mode
	('pellet_brand_type', '')  # Pellet Brand and Wood Type 
]

def default_metrics():
	metrics = {}

	for index in range(0, len(metrics_items)):
		metrics[metrics_items[index][0]] = metrics_items[index][1]

	return(metrics)

def default_pellets():
	pelletdb = {}

	now = str(datetime.datetime.now())
	now = now[0:19] # Truncate the microseconds

	ID = ''.join(filter(str.isalnum, str(datetime.datetime.now())))

	pelletdb['current'] = {
		'pelletid' : ID,		# Pellet ID for the profile currently loaded
		'hopper_level' : 100,	# Percentage of pellets remaining
		'date_loaded' : now, 	# Date that current pellets loaded
		'est_usage' : 0			# Estimated usage since loading (use auger load rate, and auger on time)
	}

	pelletdb['woods'] = [
		'Alder',
		'Almond',
		'Apple',
		'Apricot',
		'Blend',
		'Competition',
		'Cherry',
		'Chestnut',
		'Hickory',
		'Lemon',
		'Maple',
		'Mesquite',
		'Mulberry',
		'Nectarine',
		'Oak',
		'Orange',
		'Peach',
		'Pear',
		'Plum',
		'Walnut'
	]

	pelletdb['brands'] = ['Generic', 'Custom']

	pelletdb['archive'] = {
		ID : {
			'id' : ID,
			'brand' : 'Generic', 
			'wood' : 'Alder', 
			'rating' : 4, 
			'comments' : 'This is a placeholder profile.  Alder is generic and used in almost all pellets, '
						'regardless of the wood type indicated on the packaging.  It tends to burn '
						'consistently and produces a mild smoke.',
		}
	}

	pelletdb['log'] = {
		now : ID
	}

	pelletdb['lastupdated'] = {
		'time' : math.trunc(time.time())
	}

	return pelletdb 

def _default_probe_profiles():

	probe_profiles = {}

	probe_profiles['TWPS00'] = {
		'Vs' : 3.28,		# Vs = Voltage Source input to resistor divider
		'Rd' : 10000,		# Divider Resistance Ohms (Default 10k Ohm)
		'A' : 7.3431401e-4,	# Coefficient A for SHH # from HeaterMeter?
		'B' : 2.1574370e-4,	# Coefficient B for SHH
		'C' : 9.5156860e-8,	# Coefficient C for SHH
		'name' : 'Thermoworks-Pro-Series-HeaterMeter'
	}

	probe_profiles['ET73-HM'] = {
			'Vs' : 3.28,			# Vs = Voltage Source input to resistor divider
			'Rd' : 10000,			# Divider Resistance Ohms (Default 10k Ohm)
			'A' : 2.4723753e-04,	# Coefficient A for SHH # from HeaterMeter?
			'B' : 2.3402251e-04,	# Coefficient B for SHH
			'C' : 1.3879768e-07,	# Coefficient C for SHH
			'name' : 'ET-73-Heatermeter'
	}

	probe_profiles['iGrill-HM'] = {
			'Vs' : 3.28,			# Vs = Voltage Source input to resistor divider
			'Rd' : 10000,			# Divider Resistance Ohms (Default 10k Ohm)
			'A' : 0.7739251279e-3,	# Coefficient A for SHH # from HeaterMeter?
			'B' : 2.088025997e-4,	# Coefficient B for SHH
			'C' : 1.154400438e-7,	# Coefficient C for SHH
			'name' : 'iGrill-Heatermeter'
	}

	probe_profiles["PT-1000-OEM"] = {
			"Vs": 3.28,
			"Rd": 10000,
			"A": 0.04136906456,
			"B": -0.00677987613,
			"C": 2.760294589e-05,
			"name": "PT-1000-Grill-Probe-OEM" # This profile was for the original probe on my Traeger
	}

	probe_profiles["PT-1000-PiFire"] = {
			"Vs": 3.28,
			"Rd": 10000,
			"A": 0.05469905897345206,
			"B": -0.009473055040089443,
			"C": 4.3768560703857386e-5,
			"name": "PT-1000-Grill-Probe-PiFire" # This profile is for a replacement PT-1000 grill probe
	}

	probe_profiles['ET73-SP'] = {
			'Vs' : 3.28,  # Vs = Voltage Source input to resistor divider
			'Rd' : 10000,  # Divider Resistance Ohms (Default 10k Ohm)
			# from: https://github.com/skyeperry1/Maverick-ET-73-Meat-Probe-Arduino-Library/blob/master/ET73.h
			'A' : 2.3067434E-4,
			'B' : 2.3696596E-4,
			'C' : 1.2636414E-7,
			'name' : 'ET-73-skyeperry1'
	}
	return probe_profiles

def _default_grill_probes():

	grill_probes = {}

	grill_probes['grill_probe1'] = {
		'name' : 'Grill Probe 1'
	}

	grill_probes['grill_probe2'] = {
		'name' : 'Grill Probe 2'
	}

	grill_probes['grill_probe3'] = {
		'name' : 'Avg Grill Probes'
	}

	return grill_probes

def generate_uuid():
	"""
	Generate a uuid based on mac address and random int

	:return: A string uuid
	"""
	node = uuid.getnode()
	rand_int = random.randint(100, 200)
	generated_uuid = uuid.uuid1(node + rand_int)

	return str(generated_uuid)

def read_control(flush=False):
	"""
	Read Control from Redis DB

	:param flush: True to clean control. False otherwise
	:return: control
	"""
	global cmdsts

	try:
		if flush:
			# Remove all control structures in Redis DB (not history or current)
			cmdsts.delete('control:general')

			# The following set's no persistence so that we don't get writes to the disk / SDCard 
			cmdsts.config_set('appendonly', 'no')
			cmdsts.config_set('save', '')

			control = default_control()
			write_control(control)
		else: 
			control = json.loads(cmdsts.get('control:general'))
	except:
		control = default_control()

	return(control)

def write_control(control):
	"""
	Read Control from Redis DB

	:param control: Control
	"""
	global cmdsts

	cmdsts.set('control:general', json.dumps(control))

def read_errors(flush=False):
	"""
	Read Errors from Redis DB

	:param flush: True to clear errors. False otherwise
	:return: errors
	"""
	global cmdsts

	try:
		if flush:
			# Remove all error structures in Redis DB
			cmdsts.delete('errors')

			errors = []
			write_errors(errors)
		else: 
			errors = json.loads(cmdsts.get('errors'))
	except:
		errors = ['Unable to reach Redis database.  You may need to reinstall PiFire or enable redis-server.']

	return(errors)

def write_errors(errors):
	"""
	Write Errors to Redis DB

	:param errors: Errors
	"""
	global cmdsts

	cmdsts.set('errors', json.dumps(errors))

def read_metrics(all=False):
	"""
	Read Metrics from Redis DB

	:param all: True to read entire list. False for top of list.
	"""
	global cmdsts

	if not(cmdsts.exists('metrics:general')):
		write_metrics(flush=True)
		return([])
	
	if all: 
		# Read entire list of Metrics
		llength = cmdsts.llen('metrics:general')
		metrics = cmdsts.lrange('metrics:general', 0, -1)
		metrics_list = []
		for index in range(0, llength):
			metrics_list.append(json.loads(metrics[index]))
		return(metrics_list)
	
	# Read current Metrics Record (i.e. top of the list)
	return(json.loads(cmdsts.lindex('metrics:general', -1)))

def write_metrics(metrics=default_metrics(), flush=False, new_metric=False):
	"""
	Write metrics to Redis DB

	:param metrics: Metrics Data
	:param flush: True to clear metrics. False otherwise
	:param new_metric:
	"""
	global cmdsts

	if(flush or not(cmdsts.exists('metrics:general'))):
		# Remove all metrics structures in Redis DB
		cmdsts.delete('metrics:general')

		# The following set's no persistence so that we don't get writes to the disk / SDCard 
		cmdsts.config_set('appendonly', 'no')
		cmdsts.config_set('save', '')
		if not flush:
			new_metric=True
		else:
			return

	if new_metric:
		metrics['starttime'] = time.time() * 1000
		metrics['id'] = generate_uuid()
		cmdsts.rpush('metrics:general', json.dumps(metrics))
	else: 
		cmdsts.rpop('metrics:general')
		cmdsts.rpush('metrics:general', json.dumps(metrics))

def read_settings(filename='settings.json'):
	"""
	Read Settings from file

	:param filename: Filename to use (default settings.json)
	"""

	# Get latest settings format
	settings = default_settings()

	try:
		json_data_file = os.fdopen(os.open(filename, os.O_RDONLY))
		json_data_string = json_data_file.read()
		settings_struct = json.loads(json_data_string)
		json_data_file.close()

	except(IOError, OSError):
		# Default settings
		settings = default_settings()
		# Issue with reading states JSON, so create one/write new one
		write_settings(settings)
		return(settings)
	except(ValueError):
		# A ValueError Exception occurs when multiple accesses collide, this code attempts a retry.
		event = 'ERROR: Value Error Exception - JSONDecodeError reading settings.json'
		write_log(event)
		json_data_file.close()
		# Retry Reading Settings
		settings_struct = read_settings(filename=filename)

	# Overlay the read values over the top of the default settings
	#  This ensures that any NEW fields are captured.  
	update_settings = False # set flag in case an update needs to be written back

	# If default version is different from what is currently saved, update version in saved settings
	if 'versions' not in settings_struct.keys():
		settings_struct['versions'] = {
			'server' : settings['versions']['server']
		}
		update_settings = True
	elif settings_struct['versions']['server'] != settings['versions']['server']:
		settings_struct['versions']['server'] = settings['versions']['server']
		update_settings = True

	# Prevent the wizard from popping up on existing installations
	if 'first_time_setup' not in settings_struct['globals'].keys():
		settings_struct['globals']['first_time_setup'] = False
		update_settings = True
		print(' ===  DEBUG: Setting First Time Setup to False!! ')

	for key in settings.keys():
		if key in settings_struct.keys():
			for subkey in settings[key].keys():
				if subkey not in settings_struct[key].keys():
					update_settings = True
			settings[key].update(settings_struct.get(key, {}))
		else:
			update_settings = True

	if update_settings or filename != 'settings.json': # If any of the keys were added, then write back the changes
		write_settings(settings)
	#print('key mismatch - update flag set')

	return(settings)

def write_settings(settings):
	"""
	Write all settings to JSON file

	:param settings: Settings

	"""
	settings['lastupdated']['time'] = math.trunc(time.time())

	json_data_string = json.dumps(settings, indent=2, sort_keys=True)
	with open("settings.json", 'w') as settings_file:
		settings_file.write(json_data_string)

def read_pellet_db(filename='pelletdb.json'):
	"""
	Read Pellet DataBase from file

	:param filename: Filename to use (default pelletdb.json)
	"""

	pelletdb = default_pellets()

	# Read all lines of pelletdb.json into a list(array)
	try:
		json_data_file = os.fdopen(os.open(filename, os.O_RDONLY))
		json_data_string = json_data_file.read()
		pelletdb_struct = json.loads(json_data_string)
		json_data_file.close()
	except(IOError, OSError):
		# Issue with reading JSON, so create one/write new one
		pelletdb = default_pellets()
		write_pellet_db(pelletdb)
		return(pelletdb)

	# Overlay the read values over the top of the default values
	#  This ensures that any NEW fields are captured.  
	update_db = False # set flag in case an update needs to be written back

	for key in pelletdb.keys():
		if key in pelletdb_struct.keys():
			pelletdb[key] = pelletdb_struct[key].copy()
		else: 
			update_db = True 

	# If any of the keys were added or if restoring from file, then write back the changes 
	if update_db or filename != 'pelletdb.json':
		write_pellet_db(pelletdb)

	return(pelletdb)

def write_pellet_db(pelletdb):
	"""
	Write Pellet DataBase to JSON file

	:param pelletdb: Pellet Database
	"""
	json_data_string = json.dumps(pelletdb, indent=2, sort_keys=True)
	with open("pelletdb.json", 'w') as json_file:
		json_file.write(json_data_string)

def read_log(legacy=True):
	"""
	Read event.log and populate an array of events.

	if legacy=true:
	:return: (event_list, num_events)

	if legacy=false:
	:return: (event_list, num_events)
	"""
	# Read all lines of events.log into a list(array)
	try:
		with open('/tmp/events.log') as event_file:
			event_lines = event_file.readlines()
			event_file.close()
	# If file not found error, then create events.log file
	except(IOError, OSError):
		event_file = open('/tmp/events.log', "w")
		event_file.close()
		event_lines = []

	# Initialize event_list list
	event_list = []

	# Get number of events
	num_events = len(event_lines)

	if legacy:
		for x in range(num_events):
			event_list.insert(0, event_lines[x].split(" ",2))

		# Error handling if number of events is less than 10, fill array with empty
		if num_events < 10:
			for line in range((10-num_events)):
				event_list.append(["--------","--:--:--","---"])
			num_events = 10
	else:
		for x in range(num_events):
			event_list.append(event_lines[x].split(" ",2))
		return event_list

	return(event_list, num_events)

def write_log(event):
	"""
	Write event to event.log

	:param event: String event
	"""
	now = str(datetime.datetime.now())
	now = now[0:19] # Truncate the microseconds

	logfile = open("/tmp/events.log", "a")
	logfile.write(now + ' ' + event + '\n')
	logfile.close()

def write_event(settings, event):
	"""
	Send event to log and console if debug mode enabled or only to log if
	string does not begin with *

	:param settings: Settings
	:param event: String event
	"""
	if settings['globals']['debug_mode']:
		print(event)
		write_log(event)
	elif not event.startswith('*'):
		write_log(event)

def read_history(num_items=0, flushhistory=False):
	"""
	Read history from Redis DB and populate a list of data

	:param num_items: Items from end of the history
	:param flushhistory: True to clean history / current. False otherwise
	:return: List of history items
	"""
	global cmdsts
	
	temp_dict = {}  # Initialize data list

	# If a flushhistory is requested, then flush the control:history key (and data)
	if flushhistory:
		if cmdsts.exists('control:history'):
			cmdsts.delete('control:history')  # deletes the history
			# These lines set the current temps to zero
			cmdsts.hset('control:current', 'GrillTemp', 0)
			cmdsts.hset('control:current', 'Probe1Temp', 0)
			cmdsts.hset('control:current', 'Probe2Temp', 0)
			event = 'WARNING: History data flushed.'
			write_log(event)
			write_metrics(flush=True)
	else:
		if cmdsts.exists('control:history'):
			list_length = cmdsts.llen('control:history') 

			if((num_items > 0) and (list_length < num_items)) or (num_items == 0):
				list_start = 0
			else: 
				list_start = list_length - num_items

			data = cmdsts.lrange('control:history', list_start, -1)
			
			''' Unpack data from json to dictionary '''

			temp_dict = {}  # Create temporary dictionary to store all of the history data lists
			temp_struct = json.loads(data[0])  # Load the initial history data into a temporary dictionary  
			for key in temp_struct.keys():  # Iterate each of the keys
				temp_dict[key] = []  # Create an empty list for each of the keys

			for index in range(len(data)):
				datastruct = json.loads(data[index])
				for key, value in datastruct.items():
					temp_dict[key].append(value)
		else:
			# Return empty data
			temp_dict = {
				'T' : [int(time.time() * 1000)], 
				'GT1': [0], 
				'GSP1': [0],
				'PT1': [0], 
				'PSP1': [0], 
				'PT2': [0], 
				'PSP2': [0],
			}
			tr_values = '0 0 0'
			cmdsts.set('control:tuning', tr_values)

	return(temp_dict)

def write_history(temp_struct, maxsizelines=28800, tuning_mode=False, ext_data=False):
	"""
	Write History to Redis DB

	:param temp_struct: TempStruct
	:param maxsizelines: Maximum Line Size (Default 28800)
	:param tuning_mode: True to populate tuning data otherwise False
	"""
	
	global cmdsts

	#time_now = datetime.datetime.now()
	#time_str = str(int(time_now.timestamp() * 1000))
	#datastring = time_str + ' ' + str(temp_struct['GrillTemp']) + ' ' + str(temp_struct['GrillSetPoint']) + ' ' + str(temp_struct['Probe1Temp']) + ' ' + str(temp_struct['Probe1SetPoint']) + ' ' + str(temp_struct['Probe2Temp']) + ' ' + str(temp_struct['Probe2SetPoint'])

	# Create data structure for current temperature data and timestamp
	datastruct = {}
	datastruct['T'] = int(time.time() * 1000)
	datastruct['GT1'] = temp_struct['GrillTemp']
	datastruct['GSP1'] = temp_struct['GrillSetPoint']
	datastruct['PT1'] = temp_struct['Probe1Temp']
	datastruct['PSP1'] = temp_struct['Probe1SetPoint']
	datastruct['PT2'] = temp_struct['Probe2Temp']
	datastruct['PSP2'] = temp_struct['Probe2SetPoint']

	if ext_data:
		# For any key/value pairs that were passed in, and not in the above standard values, add them to the database
		for key in temp_struct.keys():
			if key not in ['GrillTemp', 'GrillSetPoint', 'Probe1Temp', 'Probe1SetPoint', 'Probe2Temp', 'Probe2SetPoint']:
				datastruct[key] = temp_struct[key]

	# Push data string to the list in the last position
	cmdsts.rpush('control:history', json.dumps(datastruct))

	# Check if the list has exceeded maxsizelines, and pop the first item from the list if it has
	if cmdsts.llen('control:history') > maxsizelines:
		cmdsts.lpop('control:history')

	# Set current values in the control:current hash
	cmdsts.hset('control:current', 'GrillTemp', temp_struct['GrillTemp'])
	cmdsts.hset('control:current', 'Probe1Temp', temp_struct['Probe1Temp'])
	cmdsts.hset('control:current', 'Probe2Temp', temp_struct['Probe2Temp'])

	# If in tuning mode, populate the Tr data in the database 
	if tuning_mode:
		tr_values = str(int(temp_struct['GrillTr'])) + ' ' + str(int(temp_struct['Probe1Tr'])) + ' ' + str(int(
			temp_struct['Probe2Tr']))
		cmdsts.set('control:tuning', tr_values)

def read_raw_history():
	global cmdsts
	return cmdsts.lrange('control:history', 1, -1)

def read_current(zero_out=False):
	"""
	Read current.log and populate a list of data

	:param zero_out: True to zero out current. False otherwise
	:return: Current Probe Temps [0, 0, 0]
	"""
	global cmdsts
	
	cur_probe_temps = [0, 0, 0]

	if not cmdsts.exists('control:current') or zero_out:
		cmdsts.hset('control:current', 'GrillTemp', 0)
		cmdsts.hset('control:current', 'Probe1Temp', 0)
		cmdsts.hset('control:current', 'Probe2Temp', 0)
	else:
		cur_probe_temps[0] = cmdsts.hget('control:current', 'GrillTemp')
		cur_probe_temps[1] = cmdsts.hget('control:current', 'Probe1Temp')
		cur_probe_temps[2] = cmdsts.hget('control:current', 'Probe2Temp')
	
	return(cur_probe_temps)

def read_tr():
	"""
	Read tr from Redis DB and populate a list of data

	:return: cur_probe_tr
	"""
	global cmdsts
	try:
		tr_data = cmdsts.get('control:tuning')
	except:
		cur_probe_tr = [0,0,0]
		write_log('WARNING: Issue reading tr data from database.')
		return(cur_probe_tr)

	if tr_data is not None:
		cur_probe_tr = tr_data.split(' ',2) # Splits out each of the values into separate list items
	else: 
		cur_probe_tr = [0,0,0]  # If data isn't available from database yet, output 0's

	return(cur_probe_tr)

def convert_temp(units, temp):
	"""
	Convert Temp Based on Units

	:param units: Units C or F
	:param temp: Temp to Convert
	:return: Converted Temp
	"""
	if units == 'F':
		temp_out = int(temp * (9/5) + 32) # Celsius to Fahrenheit
	else:
		temp_out = int((temp - 32) * (5/9)) # Fahrenheit to Celsius
	return(temp_out)

def convert_settings_units(units, settings):
	"""
	Convert Settings Units

	:param units: Units C or F
	:param settings: Settings
	:return: Updated Settings
	"""
	settings['globals']['units'] = units
	settings['safety']['maxstartuptemp'] = convert_temp(units, settings['safety']['maxstartuptemp'])
	settings['safety']['maxtemp'] = convert_temp(units, settings['safety']['maxtemp'])
	settings['safety']['minstartuptemp'] = convert_temp(units, settings['safety']['minstartuptemp'])
	settings['smoke_plus']['max_temp'] = convert_temp(units, settings['smoke_plus']['max_temp'])
	settings['smoke_plus']['min_temp'] = convert_temp(units, settings['smoke_plus']['min_temp'])
	settings['keep_warm']['temp'] = convert_temp(units, settings['keep_warm']['temp'])
	for temp in range(0, len(settings['smartstart']['temp_range_list'])):
		settings['smartstart']['temp_range_list'][temp] = convert_temp(
			units, settings['smartstart']['temp_range_list'][temp])
	return(settings)

# **************************************
# is_raspberrypi() function borrowed from user https://raspberrypi.stackexchange.com/users/126953/chris
# in post: https://raspberrypi.stackexchange.com/questions/5100/detect-that-a-python-program-is-running-on-the-pi
# **************************************
def is_raspberry_pi():
	"""
	Check if device is a Raspberry Pi

	:return: True if Raspberry Pi. False otherwise
	"""
	try:
		with io.open('/sys/firmware/devicetree/base/model', 'r') as m:
			if 'raspberry pi' in m.read().lower(): return True
	except Exception:
		pass
	return False

def restart_scripts():
	"""
	Restart the Control and WebApp Scripts
	"""
	print('[DEBUG MSG] Restarting Scripts... ')
	command = "sleep 3 && sudo service supervisor restart &"
	if is_raspberry_pi():
		os.system(command)

def read_wizard(filename='wizard/wizard_manifest.json'):
	"""
	Read Wizard Manifest Data from file

	:param filename: Filename to use (default wizard/wizard_manifest.json)
	:return: Wizard Data
	"""
	try:
		json_data_file = os.fdopen(os.open(filename, os.O_RDONLY))
		json_data_string = json_data_file.read()
		wizard = json.loads(json_data_string)
		json_data_file.close()
	except(IOError, OSError):
		event = 'ERROR: Could not read from wizard manifest.'
		write_log(event)
		wizard = {
			"modules" : {}
		}
		return(wizard)
	except(ValueError):
		# A ValueError Exception occurs when multiple accesses collide, this code attempts a retry.
		event = 'ERROR: Value Error Exception - JSONDecodeError reading wizard_manifest.json'
		write_log(event)
		json_data_file.close()
		# Retry Reading Settings
		wizard = read_wizard(filename=filename)

	return(wizard)

def load_wizard_install_info():
	"""
	Load Wizard Install Info from Redis DB

	:return: wizard_install_info
	"""
	global cmdsts
	wizard_install_info = json.loads(cmdsts.get('wizard:install'))
	return(wizard_install_info)

def store_wizard_install_info(wizard_install_info):
	"""
	Write Wizard Install Info to Redis DB

	:param wizard_install_info: Wizard Install Info
	:return:
	"""
	global cmdsts
	cmdsts.set('wizard:install', json.dumps(wizard_install_info))

def get_wizard_install_status():
	"""
	Read Wizard Install Status from Redis DB

	:return: Wizard Install (Percent, Status, Output)
	"""
	global cmdsts 
	percent = cmdsts.get('wizard:percent')
	status = cmdsts.get('wizard:status')
	output = cmdsts.get('wizard:output')
	return(percent, status, output)

def set_wizard_install_status(percent, status, output):
	"""
	Write Wizard Install Status to Redis DB

	:param percent: Percent Complete
	:param status: Current Status
	:param output: Output
	"""
	global cmdsts 
	cmdsts.set('wizard:percent', percent)
	cmdsts.set('wizard:status', status)
	cmdsts.set('wizard:output', output)

def read_dependencies(filename='updater/updater_manifest.json'):
	"""
	Read Updater Manifest Data from file

	:param filename: updater_manifest.json filename
	:return: Dependencies
	"""
	try:
		json_data_file = os.fdopen(os.open(filename, os.O_RDONLY))
		json_data_string = json_data_file.read()
		dependencies = json.loads(json_data_string)
		json_data_file.close()
	except(IOError, OSError):
		event = 'ERROR: Could not read from updater manifest.'
		write_log(event)
		dependencies = {
			"dependencies" : {}
		}
		return(dependencies)
	except(ValueError):
		# A ValueError Exception occurs when multiple accesses collide, this code attempts a retry.
		event = 'ERROR: Value Error Exception - JSONDecodeError reading updater_manifest.json'
		write_log(event)
		json_data_file.close()
		# Retry Reading Settings
		dependencies = read_dependencies(filename=filename)

	return(dependencies)

def get_updater_install_status():
	"""
	Read Updater Install Status from Redis DB

	:return: Wizard Updater (Percent, Status, Output)
	"""
	global cmdsts
	percent = cmdsts.get('updater:percent')
	status = cmdsts.get('updater:status')
	output = cmdsts.get('updater:output')
	return(percent, status, output)

def set_updater_install_status(percent, status, output):
	"""
	Write Updater Install Status to Redis DB

	:param percent: Percent Complete
	:param status: Current Status
	:param output: Output
	"""
	global cmdsts
	cmdsts.set('updater:percent', percent)
	cmdsts.set('updater:status', status)
	cmdsts.set('updater:output', output)

def process_metrics(metrics_data, augerrate=0.3):
	# Process Additional Metrics Information for Display
	for index in range(0, len(metrics_data)):
		# Convert Start Time
		starttime = metrics_data[index]['starttime']
		metrics_data[index]['starttime_c'] = _epoch_to_time(starttime/1000)
		# Convert End Time
		if(metrics_data[index]['endtime'] == 0):
			endtime = 0
		else: 
			endtime = _epoch_to_time(metrics_data[index]['endtime']/1000)
		metrics_data[index]['endtime_c'] = endtime
		# Time in Mode
		if(metrics_data[index]['mode'] == 'Stop'):
			timeinmode = 'NA'
		elif(metrics_data[index]['endtime'] == 0):
			timeinmode = 'Active'
		else:
			seconds = int((metrics_data[index]['endtime']/1000) - (metrics_data[index]['starttime']/1000))
			if seconds > 60:
				timeinmode = f'{int(seconds/60)} m {seconds % 60} s'
			else:
				timeinmode = f'{seconds} s'
		metrics_data[index]['timeinmode'] = timeinmode 
		# Convert Auger On Time
		metrics_data[index]['augerontime_c'] = str(int(metrics_data[index]['augerontime'])) + ' s'
		# Estimated Pellet Usage
		grams = int(metrics_data[index]['augerontime'] * augerrate)
		pounds = round(grams * 0.00220462, 2)
		ounces = round(grams * 0.03527392, 2)
		metrics_data[index]['estusage_m'] = f'{grams} grams'
		metrics_data[index]['estusage_i'] = f'{pounds} pounds ({ounces} ounces)'

	return(metrics_data)

def _epoch_to_time(epoch):
	end_time =  datetime.datetime.fromtimestamp(epoch)
	return end_time.strftime("%H:%M:%S")

def semantic_ver_to_list(version_string):
	# Count number of '.' in string
	decimal_count = version_string.count('.')
	ver_list = version_string.split('.')

	if decimal_count == 0:
		ver_list = [0, 0, 0]
	elif decimal_count < 2:
		ver_list.append('0')

	ver_list = list(map(int, ver_list))

	return(ver_list)

def seconds_to_string(seconds):
	m, s = divmod(seconds, 60)
	h, m = divmod(m, 60)

	if h > 0:
		time_string = f'{h}h {m}m {s}s'
	elif m > 0:
		time_string = f'{m}m {s}s'
	else: 
		time_string = f'{s}s'

	return time_string 