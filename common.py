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
import json

# *****************************************
# Functions
# *****************************************

def DefaultSettings():
	settings = {}

	settings['history_page'] = {
		'minutes' : 60, # Sets default number of items to show in history
		'clearhistoryonstart' : True, # Clear history when StartUp Mode selected
		'autorefresh' : 'on', # Sets history graph to autorefresh ('live' graph)
		'datapoints' : 60 # Number of datapoints to show on the history chart
	}

	settings['probe_settings'] = {
		'probe_profiles' :  DefaultProbeProfiles(), 
		'probes_enabled' : [1,1,1]
	}

	settings['globals'] = {
		'grill_name' : '',
		'debug_mode' : False,
		'page_theme' : 'light',
		'triggerlevel' : 'LOW',
		'buttonslevel' : 'HIGH',
		'shutdown_timer' : 60,
		'units' : 'F'
	}

	settings['ifttt'] = {
		'APIKey': '', # API Key for WebMaker IFTTT App notification
	}

	settings['pushbullet'] = {
		'APIKey': '', # API Key for Pushbullet notifications
		'PublicURL': '', # Used in Pushbullet notifications
	}

	settings['pushover'] = {
		'APIKey': '', # API Key for Pushover notifications
		'UserKeys': '', # Comma-separated list of user keys
		'PublicURL': '', # Used in Pushover notifications
	}

	settings['probe_types'] = {
		'grill0type' : 'PT1000-00',
		'probe1type' : 'TWPS00',
		'probe2type' : 'TWPS00',
	}

	settings['outpins'] = {
		'power' : 4,
		'auger' : 14,
		'fan' : 15,
		'igniter' : 18
	}

	settings['inpins'] = { 'selector' : 17 }

	#PID controller based on proportional band in standard PID form https://en.wikipedia.org/wiki/PID_controller#Ideal_versus_standard_PID_form
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
		'PMode' : 2,  # http://tipsforbbq.com/Definition/Traeger-P-Setting
		'u_min' : 0.15,
		'u_max' : 1.0
	}

	settings['smoke_plus'] = {
		'enabled' : False, # Sets default Enable/Disable (True = Enabled, False = Disabled)
		'min_temp' : 160, # Minimum temperature to cycle fan on/off
		'max_temp' : 220, # Maximum temperature to cycle fan on/off
		'cycle' : 10,  # Number of seconds to cycle the fan on/off
		'frequency' : 1, # For PWM, if implemented (Currently not used)
		'duty_cycle' : 50 # For PWM, if implemented (Currently not used)
	}

	settings['safety'] = {
		'minstartuptemp' : 75, # User Defined. Minimum temperature allowed for startup.
		'maxstartuptemp' : 100, # User Defined. Take this value if the startup temp is higher than maxstartuptemp
		'maxtemp' : 550, # User Defined. If temp exceeds this value in any mode, shut off.  (including monitor mode)
		'reigniteretries' : 1, # Number of tries to reignite the grill if it has gone below the safe temperature (set to 0 to disable)
	}

	settings['modules'] = {
		'grillplat' : 'pifire',	 	# Grill Platform (PiFire - Raspberry Pi GPIOs)
		'adc' : 'ads1115',			# Analog to Digital Converter Default is the ADS1115
		'display' : 'ssd1306',		# Default display is the SSD1306
		'dist' : 'prototype'		# Default distance sensor is none
	}

	return settings

def DefaultControl():

	settings = ReadSettings()

	control = {}

	control['updated'] = True

	control['mode'] = 'Stop'

	if(settings['smoke_plus']['enabled'] == True):
		control['s_plus'] = True # Smoke-Plus Feature Enable/Disable
	else: 
		control['s_plus'] = False # Smoke-Plus Feature Enable/Disable

	control['hopper_check'] = False # Trigger an synchronous hopper level check 

	control['recipe'] = ''

	control['status'] = ''

	control['probe_profile_update'] = False 

	control['setpoints'] = {
		'grill' : 0,
		'probe1' : 0,
		'probe2' : 0
	}

	control['notify_req'] = {
		'grill' : False,
		'probe1' : False,
		'probe2' : False,
		'timer' : False,
	}

	control['notify_data'] = {
		'hopper_low' : False,
		'p1_shutdown' : False,
		'p2_shutdown' : False,
		'timer_shutdown' : False,
	}

	control['timer'] = {
		'start' : 0,
		'paused' : 0,
		'end' : 0,
		'shutdown' : False 
	}

	control['manual'] = {
		'change' : False,
		'output' : '',
		'state' : '',
		'current' : {
			'fan' : 1,
			'auger' : 1,
			'igniter' : 1,
			'power' : 1
		}
	}

	control['safety'] = {
		'startuptemp' : 0, # Set by control function at startup
		'afterstarttemp' : 0, # Set by control function during startup
		'reigniteretries' : settings['safety']['reigniteretries'], # Set by user to attempt a re-ignite when the grill drops below a certain temp
		'reignitelaststate' : 'Smoke' # Set by control function to remember the last state we were in when the temp dropped below safety levels 
	}

	return(control)

def DefaultRecipes():
	recipes = {}

	recipes['321ribs'] = {
		'metadata': {
			'display_name': '3-2-1 Baby Back Ribs',
			'image': ''
		},
		'steps' : {
			'step_00': {
				'smoke' : True, # Start with smoke temp for grill
				'timer' : 180, # Go for three hours (180 mins)
				'notify' : True,
				'desciption' : 'Set grill to smoke at 165F.'
			},
			'step_01': {
				'grill_temp' : 275,
				'notify' : True,
				'timer' : 120, # Go for two hours (120 mins)
				'desciption' : 'Wrap ribs and increase grill temp to 275F'
			},
			'step_02': {
				'grill_temp' : 300,
				'timer' : 60,
				'notify' : True,
				'desciption' : 'Un-wrap ribs and increase grill temp to 300F'
			}
		}
	}

	return recipes

def DefaultPellets():
	pelletdb = {}

	now = str(datetime.datetime.now())
	now = now[0:19] # Truncate the microseconds

	ID = ''.join(filter(str.isalnum, str(datetime.datetime.now())))

	pelletdb['current'] = {
		'pelletid' : ID,			# Pellet ID for the profile currently loaded
		'hopper_level' : 100,	# Percentage of pellets remaining
		'date_loaded' : now, 		# Date that current pellets loaded
	}

	pelletdb['empty'] = 30 # Number of centimeters from the sensor that indicates empty

	pelletdb['woods'] = ['Alder', 'Almond', 'Apple', 'Apricot', 'Blend', 'Competition', 'Cherry', 'Chestnut', 'Hickory', 'Lemon', 'Maple', 'Mesquite', 'Mulberry', 'Nectarine', 'Oak', 'Orange', 'Peach', 'Pear', 'Plum', 'Walnut' ]

	pelletdb['brands'] = ['Generic', 'Custom']

	pelletdb['archive'] = {
		ID : {
			'id' : ID,
			'brand' : 'Generic', 
			'wood' : 'Alder', 
			'rating' : 4, 
			'comments' : 'This is a placeholder profile.  Alder is generic and used in almost all pellets, regardless of the wood type indicated on the packaging.  It tends to burn consistantly and produces a mild smoke.'
		}
	}

	pelletdb['log'] = {
		now : ID
	}

	return pelletdb 

def DefaultProbeProfiles():

	probe_profiles = {}

	probe_profiles['TWPS00'] = {
		'Vs' : 3.28,		# Vs = Voltage Source input to resistor divider
		'Rd' : 10000,	# Divider Resistance Ohms (Default 10k Ohm)
		'A' : 7.3431401e-4,	# Coefficient A for SHH # from HeaterMeter?
		'B' : 2.1574370e-4,	# Coefficient B for SHH
		'C' : 9.5156860e-8,	# Coefficient C for SHH
		'name' : 'Thermoworks-Pro-Series-HeaterMeter'
	}

	probe_profiles['ET73-HM'] = {
			'Vs' : 3.28,		# Vs = Voltage Source input to resistor divider
			'Rd' : 10000,	# Divider Resistance Ohms (Default 10k Ohm)
			'A' : 2.4723753e-04,	# Coefficient A for SHH # from HeaterMeter?
			'B' : 2.3402251e-04,	# Coefficient B for SHH
			'C' : 1.3879768e-07,	# Coefficient C for SHH
			'name' : 'ET-73-Heatermeter'
	}

	probe_profiles['iGrill-HM'] = {
			'Vs' : 3.28,		# Vs = Voltage Source input to resistor divider
			'Rd' : 10000,	# Divider Resistance Ohms (Default 10k Ohm)
			'A' : 0.7739251279e-3,	# Coefficient A for SHH # from HeaterMeter?
			'B' : 2.088025997e-4,	# Coefficient B for SHH
			'C' : 1.154400438e-7,	# Coefficient C for SHH
			'name' : 'iGrill-Heatermeter'
	}

	probe_profiles["PT1000-00"] = {
			"Vs": 3.28,
			"Rd": 10000,
			"A": 0.04136906456,
			"B": -0.00677987613,
			"C": 2.760294589e-05,
			"name": "PT-1000-OEM-RTD"
	}

	probe_profiles['ET73-SP'] = {
			'Vs' : 3.28,		# Vs = Voltage Source input to resistor divider
			'Rd' : 10000,	# Divider Resistance Ohms (Default 10k Ohm)
			'A' : 2.3067434E-4,		# from: https://github.com/skyeperry1/Maverick-ET-73-Meat-Probe-Arduino-Library/blob/master/ET73.h
			'B' : 2.3696596E-4,
			'C' : 1.2636414E-7,
			'name' : 'ET-73-skyeperry1'
	}
	return probe_profiles

def ReadControl():
	# *****************************************
	# Read Control From JSON File
	# *****************************************

	try:
		json_data_file = os.fdopen(os.open('/tmp/control.json', os.O_RDONLY))
		#json_data_file = open("/tmp/control.json", "r")
		json_data_string = json_data_file.read()
		control = json.loads(json_data_string)
		json_data_file.close()
	except(IOError, OSError):
		# Issue with reading file, so create one/write new one
		control = DefaultControl()
		WriteControl(control)
		return(control)
	except(ValueError):
		# A ValueError Exception occurs when multiple accesses collide, this code attempts a retry.
		event = 'ERROR: Value Error Exception - JSONDecodeError reading control.json'
		WriteLog(event)
		json_data_file.close()
		# Retry Reading Control 
		control = ReadControl() 

	return(control)

def WriteControl(control):
	# *****************************************
	# Write all control states to JSON file
	# *****************************************
	json_data_string = json.dumps(control)
	with open("/tmp/control.json", 'w') as control_file:
		control_file.write(json_data_string)

def ReadSettings():
	# *****************************************
	# Read Settings from file
	# *****************************************

	# Get latest settings format
	settings = DefaultSettings()

	try:
		json_data_file = os.fdopen(os.open('settings.json', os.O_RDONLY))
		#json_data_file = open("settings.json", "r")
		json_data_string = json_data_file.read()
		settings_struct = json.loads(json_data_string)
		json_data_file.close()

	except(IOError, OSError):
		# Default settings
		settings = DefaultSettings()
		# Issue with reading states JSON, so create one/write new one
		WriteSettings(settings)
		return(settings)
	except(ValueError):
		# A ValueError Exception occurs when multiple accesses collide, this code attempts a retry.
		event = 'ERROR: Value Error Exception - JSONDecodeError reading control.json'
		WriteLog(event)
		json_data_file.close()
		# Retry Reading Settings
		settings_struct = ReadSettings() 

	# Overlay the read values over the top of the default settings
	#  This ensures that any NEW fields are captured.  
	update_settings = False # set flag in case an update needs to be written back

	for key in settings.keys():
		if key in settings_struct.keys():
			for subkey in settings[key].keys():
				if subkey not in settings_struct[key].keys():
					update_settings = True
			settings[key].update(settings_struct.get(key, {}))
		else: 
			update_settings = True 

	if update_settings: # If any of the keys were added, then write back the changes 
		WriteSettings(settings)
		#print('key mismatch - update flag set')
	
	return(settings)

def WriteSettings(settings):
	# *****************************************
	# Write all settings to JSON file
	# *****************************************
	json_data_string = json.dumps(settings)
	with open("settings.json", 'w') as settings_file:
	    settings_file.write(json_data_string)

def ReadRecipes():
	# *****************************************
	# Read RecipeDB from File
	# *****************************************

	# Read all lines of states.json into an list(array)
	try:
		json_data_file = os.fdopen(os.open('recipes.json', os.O_RDONLY))
		#json_data_file = open("recipes.json", "r")
		json_data_string = json_data_file.read()
		recipes = json.loads(json_data_string)
		json_data_file.close()
	except(IOError, OSError):
		# Issue with reading JSON, so create one/write new one
		recipes = DefaultRecipes()
		WriteRecipes(recipes)

	return(recipes)

def WriteRecipes(recipes):
	# *****************************************
	# Write RecipeDB to JSON file
	# *****************************************
	json_data_string = json.dumps(recipes)
	with open("recipes.json", 'w') as recipes_file:
		recipes_file.write(json_data_string)

def ReadPelletDB():
	# *****************************************
	# Read Pellet DataBase from file
	# *****************************************

	# Read all lines of states.json into an list(array)
	try:
		json_data_file = os.fdopen(os.open('pelletdb.json', os.O_RDONLY))
		#json_data_file = open("pelletdb.json", "r")
		json_data_string = json_data_file.read()
		pelletdb = json.loads(json_data_string)
		json_data_file.close()
	except(IOError, OSError):
		# Issue with reading JSON, so create one/write new one
		pelletdb = DefaultPellets()
		WritePelletDB(pelletdb)

	return(pelletdb)

def WritePelletDB(pelletdb):
	# *****************************************
	# Write Pellet DataBase to JSON file
	# *****************************************
	json_data_string = json.dumps(pelletdb)
	with open("pelletdb.json", 'w') as json_file:
		json_file.write(json_data_string)

def ReadLog():
	# *****************************************
	# Function: ReadLog
	# Input: none
	# Output:
	# Description: Read event.log and populate
	#  an array of events.
	# *****************************************

	# Read all lines of events.log into an list(array)
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

	for x in range(num_events):
		event_list.append(event_lines[x].split(" ",2))

	# Error handling if number of events is less than 10, fill array with empty
	if (num_events < 10):
		for line in range((10-num_events)):
			event_list.append(["--------","--:--:--","---"])
		num_events = 10

	return(event_list, num_events)

def WriteLog(event):
	# *****************************************
	# Function: WriteLog
	# Input: str event
	# Description: Write event to event.log
	#  Event should be a string.
	# *****************************************
	now = str(datetime.datetime.now())
	now = now[0:19] # Truncate the microseconds

	logfile = open("/tmp/events.log", "a")
	logfile.write(now + ' ' + event + '\n')
	logfile.close()

def ReadHistory(num_items=0):
	# *****************************************
	# Function: ReadHistory
	# Input: num_items (items from end of the history)
	# Output: data_list
	# Description: Read history.log and populate
	#  a list of data
	# *****************************************

	# Read all lines of history.log into a list(array)
	try:
		if(num_items == 0):
			with open('/tmp/history.log') as history_file:
				history_lines = history_file.readlines()
				history_file.close()
		else:
			command = 'tail -n ' + str(num_items) + ' /tmp/history.log'
			history_file = os.popen(command)
			history_lines = history_file.readlines()
			history_file.close()

	# If file not found error, then create history.log file
	except(IOError, OSError):
		data_list = []
		WriteLog('WARNING: Issue reading /tmp/history.log')
		return(data_list)

	# Initialize data list
	data_list = []

	for index in range(len(history_lines)):
		data_line = history_lines[index].rsplit(' ', 1)[0] # Strips off the '\n' from the line
		data_list.append(data_line.split(' ',6)) # Splits out each of the values into seperate list items

	return(data_list)

def ReadCurrent():
	# *****************************************
	# Function: ReadCurrent
	# Input: none
	# Output: cur_probe_temps []
	# Description: Read current.log and populate
	#  a list of data
	# *****************************************

	try:
		with open('/tmp/current.log') as current_file:
			current_line = current_file.readline()
			current_file.close()
	# If file not found error, then return 0'd data
	except(IOError, OSError):
		cur_probe_temps = [0,0,0]
		WriteLog('WARNING: Issue reading /tmp/current.log')
		
		timenow = datetime.datetime.now()
		timestr = timenow.strftime('%H:%M:%S') # Truncate the microseconds
		curfile = open("/tmp/current.log", "w") # Write current data to current.log file
		curfile.write(timestr + ' 0 0 0 0 0 0' )
		curfile.close()

		return(cur_probe_temps)

	# Initialize data list
	data_list = []

	data_list = current_line.split(' ',6) # Splits out each of the values into seperate list items

	cur_probe_temps = [0, 0, 0]

	cur_probe_temps[0] = int(data_list[1])
	cur_probe_temps[1] = int(data_list[3])
	cur_probe_temps[2] = int(data_list[5])

	return(cur_probe_temps)

def WriteHistory(TempStruct, maxsizelines=28800):
	# *****************************************
	# Function: WriteHistory
	# Input: TempStruct
	# Description: Write event to history.log AND current.log
	#  Event should be a string.
	# *****************************************

	timenow = datetime.datetime.now()
	timestr = timenow.strftime('%H:%M:%S') # Truncate the microseconds
	event = str(int(TempStruct['GrillTemp'])) + ' ' + str(TempStruct['GrillSetPoint']) + ' ' + str(int(TempStruct['Probe1Temp'])) + ' ' + str(TempStruct['Probe1SetPoint']) + ' ' + str(int(TempStruct['Probe2Temp'])) + ' ' + str(TempStruct['Probe2SetPoint'])

	logfile = open("/tmp/history.log", "a")	# Append current data to history.log file
	logfile.write(timestr + ' ' + event + ' \n')
	logfile.close()

	curfile = open("/tmp/current.log", "w") # Write current data to current.log file
	curfile.write(timestr + ' ' + event)
	curfile.close()

	tr_values = str(int(TempStruct['GrillTr'])) + ' ' + str(int(TempStruct['Probe1Tr'])) + ' ' + str(int(TempStruct['Probe2Tr']))
	trfile = open("/tmp/tr.log", "w") # Write current data to current.log file
	trfile.write(tr_values)
	trfile.close()

	command = 'wc -l /tmp/history.log' # Use the Word Count CLI tool to get number of lines
	history_file = os.popen(command)
	history_lines = history_file.readlines()
	history_file.close()
	temp_array = history_lines[0].split(' ') # Split result line into parts

	if(int(temp_array[0]) >= maxsizelines):
		WriteLog('File: history.log at maximum set size, removing an hour of data from beginning.')
		os.system('tail -n ' + str(maxsizelines - 1200) + ' /tmp/history.log > /tmp/history.bak')
		os.system('rm /tmp/history.log && mv /tmp/history.bak /tmp/history.log')

def ReadTr():
	# *****************************************
	# Function: ReadTr
	# Input: none
	# Output: cur_probe_tr []
	# Description: Read tr.log and populate
	#  a list of data
	# *****************************************

	try:
		with open('/tmp/tr.log') as tr_file:
			tr_line = tr_file.readline()
			tr_file.close()
	# If file not found error, then return 0'd data
	except(IOError, OSError):
		cur_probe_tr = [0,0,0]
		WriteLog('WARNING: Issue reading /tmp/tr.log')

		return(cur_probe_tr)

	cur_probe_tr = tr_line.split(' ',2) # Splits out each of the values into seperate list items

	return(cur_probe_tr)