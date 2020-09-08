import time
import datetime
import os
import json

debugMode = True

def DefaultSettings():
	settings = {}

	settings['debug_mode'] = False

	settings['ifttt'] = {
		'APIKey': '', # API Key for WebMaker IFTTT App notification
	}

	settings['pushover'] = {
		'APIKey': '', # API Key for Pushover notifications
		'UserKeys': '', # Comma-separated list of user keys
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

	settings['probe_profiles'] = DefaultProbeProfiles()

	settings['probes_enabled'] = [1,1,1]

	#PID controller based on proportional band in standard PID form https://en.wikipedia.org/wiki/PID_controller#Ideal_versus_standard_PID_form
	# u = Kp (e(t)+ 1/Ti INT + Td de/dt)
	# PB = Proportional Band
	# Ti = Goal of eliminating in Ti seconds
	# Td = Predicts error value at Td in seconds

	settings['cycle_data'] = {
		'PB' : 60.0,
		'Ti' : 180.0,
		'Td' : 45.0,
		'CycleTime' : 20,
		'PMode' : 2,  # http://tipsforbbq.com/Definition/Traeger-P-Setting
		'u_min' : 0.15,
		'u_max' : 1.0
	}

	settings['minutes'] = 60 # Sets default number of items to show in history

	settings['clearhistoryonstart'] = True # Clear history when StartUp Mode selected

	settings['autorefresh'] = 'on' # Sets history graph to autorefresh ('live' graph)

	settings['datapoints'] = 60 # Number of datapoints to show on the history chart

	settings['safety'] = {
		'minstartuptemp' : 75, # User Defined. Minimum temperature allowed for startup.
		'maxstartuptemp' : 100, # User Defined. Take this value if the startup temp is higher than maxstartuptemp
		'maxtemp' : 500 # User Defined. If temp exceeds this value in any mode, shut off.  (including monitor mode)
	}

	settings['page_theme'] = 'light'

	return settings

def DefaultControl():
	control = {}

	control['updated'] = True

	control['mode'] = 'Stop'

	control['recipe'] = ''

	control['status'] = ''

	control['setpoints'] = {
		'grill' : 150,
		'probe1' : 0,
		'probe2' : 0
	}

	control['notify_req'] = {
		'grill' : False,
		'probe1' : False,
		'probe2' : False,
		'timer' : False
	}

	control['timer'] = {
		'start' : 0,
		'paused' : 0,
		'end' : 0
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

def DefaultTempStuct():
	tempstruct = {}

	tempstruct['GrillTemp'] = 0
	tempstruct['GrillSetPoint'] = 0
	tempstruct['Probe1Temp'] = 0
	tempstruct['Probe1SetPoint'] = 0
	tempstruct['Probe2Temp'] = 0
	tempstruct['Probe2SetPoint'] = 0

	return tempstruct

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
			"name": "PT-1000-Traeger-RTD"
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

def ReadSettings():
	# *****************************************
	# Read Settings from file
	# *****************************************

	# Read all lines of settings.json into an list(array)
	try:
		json_data_file = open("settings.json", "r")
		json_data_string = json_data_file.read()
		settings = json.loads(json_data_string)
		json_data_file.close()

	except(IOError, OSError):
		# Default settings
		settings = DefaultSettings()
		# Issue with reading states JSON, so create one/write new one
		WriteSettings(settings)

	return(settings)

def WriteSettings(settings):
	# *****************************************
	# Write all control states to JSON file
	# *****************************************
	json_data_string = json.dumps(settings)
	with open("settings.json", 'w') as settings_file:
	    settings_file.write(json_data_string)

def ReadRecipes():
	# *****************************************
	# Read Switch States from File
	# *****************************************

	# Read all lines of states.json into an list(array)
	try:
		json_data_file = open("recipes.json", "r")
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
	# Write all control states to JSON file
	# *****************************************
	json_data_string = json.dumps(recipes)
	with open("recipes.json", 'w') as recipes_file:
		recipes_file.write(json_data_string)

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
		DebugWrite('Issue reading /tmp/history.log')

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
		DebugWrite('Issue reading /tmp/current.log')

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

	command = 'wc -l /tmp/history.log' # Use the Word Count CLI tool to get number of lines
	history_file = os.popen(command)
	history_lines = history_file.readlines()
	history_file.close()
	temp_array = history_lines[0].split(' ') # Split result line into parts

	if(int(temp_array[0]) >= maxsizelines):
		WriteLog('File: history.log at maximum set size, removing an hour of data from beginning.')
		os.system('tail -n ' + str(maxsizelines - 1200) + ' /tmp/history.log > /tmp/history.bak')
		os.system('rm /tmp/history.log && mv /tmp/history.bak /tmp/history.log')

def DebugWrite(event):
	# Is Debug Mode enabled
	settings = ReadSettings()

	if(settings['debug_mode'] == True):
		now = str(datetime.datetime.now())
		now = now[0:19] # Truncate the microseconds
		event = now + ' ' + event + '\n'
		print(event) # Print event to console
		logfile = open("/tmp/debug.log", "a")
		logfile.write(event) # Write event to debug.log
		logfile.close()

def DebugRead():
	# *****************************************
	# Function: DebugRead
	# Input: none
	# Output:
	# Description: Read debug.log and populate
	#  an array of events.
	# *****************************************

	# Read all lines of events.log into an list(array)
	try:
		with open('/tmp/debug.log') as event_file:
			event_lines = event_file.readlines()
			event_file.close()
	# If file not found error, then create events.log file
	except(IOError, OSError):
		event_file = open('/tmp/debug.log', "w")
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

def ReadControl():
	# *****************************************
	# Read Control From JSON File
	# *****************************************

	try:
		json_data_file = open("/tmp/control.json", "r")
		json_data_string = json_data_file.read()
		control = json.loads(json_data_string)
		json_data_file.close()
	except(IOError, OSError):
		# Issue with reading file, so create one/write new one
		control = DefaultControl()
		WriteControl(control)

	return(control)

def WriteControl(control):
	# *****************************************
	# Write all control states to JSON file
	# *****************************************
	json_data_string = json.dumps(control)
	with open("/tmp/control.json", 'w') as control_file:
		control_file.write(json_data_string)
