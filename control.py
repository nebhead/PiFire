#!/usr/bin/env python3

# *****************************************
# PiFire Main Control Program
# *****************************************
#
# Description: This script will start at boot, initialize the relays and
#  wait for further commands from the web user interface.
#
# This script runs as a separate process from the Flask / Gunicorn
# implementation which handles the web interface.
#
# *****************************************

# Prototype Mode is now selected through modifying the module selections in the settings.json file.
# Run 'bash modules.sh' from the command prompt to select prototype modules, for prototype mode

# *****************************************
# Imported Libraries
# *****************************************

import time
import os
import json
import datetime
from common import *  # Common Library for WebUI and Control Program
from pushbullet import Pushbullet # Pushbullet Import
import pid as PID # Library for calculating PID setpoints
import requests

# Read Settings to Get Modules Configuration 
settings = ReadSettings()

if(settings['modules']['grillplat'] == 'pifire'):
	from grillplat_pifire import GrillPlatform # Library for controlling the grill platform w/Raspberry Pi GPIOs
else:
	from grillplat_prototype import GrillPlatform # Simulated Library for controlling the grill platform

if(settings['modules']['adc'] == 'ads1115'):
	from adc_ads1115 import ReadADC # Library for reading the ADC device
else: 
	from adc_prototype import ReadADC # Simulated Library for reading the ADC device
	
if(settings['modules']['display'] == 'ssd1306'):
	from display_ssd1306 import Display # Library for controlling the display device
elif(settings['modules']['display'] == 'ssd1306b'):
	from display_ssd1306b import Display # Library for controlling the display device w/button input
elif(settings['modules']['display'] == 'st7789p'):
	from display_st7789p import Display # Library for controlling the display device
elif(settings['modules']['display'] == 'pygame'):
	from display_pygame import Display # Library for controlling the display device
elif(settings['modules']['display'] == 'pygame_240x320'):
	from display_pygame_240x320 import Display # Library for controlling the display device
elif(settings['modules']['display'] == 'pygame_240x320b'):
	from display_pygame_240x320b import Display # Library for controlling the display device
elif(settings['modules']['display'] == 'ili9341'):
	from display_ili9341 import Display # Library for controlling the display device
elif(settings['modules']['display'] == 'ili9341b'):
	from display_ili9341b import Display # Library for controlling the display device
else:
	from display_prototype import Display # Simulated Library for controlling the display device

if(settings['modules']['dist'] == 'vl53l0x'):
	from distance_vl53l0x import HopperLevel # Library for reading the HopperLevel from vl53l0x TOF Sensor
elif(settings['modules']['dist'] == 'hcsr04'):
	from distance_hcsr04 import HopperLevel # Library for reading HopperLevel HC-SR04 Ultrasonic Sensor
else: 
	from distance_prototype import HopperLevel # Simulated Library for reading the HopperLevel

# *****************************************
# Function Definitions
# *****************************************

def GetStatus(grill_platform, control, settings, pelletdb):
	# *****************************************
	# Get Status Details for Display Function
	# *****************************************
	status_data = {}
	status_data['outpins'] = {}

	current = grill_platform.GetOutputStatus()	# Get current pin settings
	
	if settings['globals']['triggerlevel'] == 'LOW':
		for item in settings['outpins']:
			status_data['outpins'][item] = current[item]
	else:
		for item in settings['outpins']:
			status_data['outpins'][item] = not current[item] # Reverse Logic
	
	status_data['mode'] = control['mode'] # Get current mode
	status_data['notify_req'] = control['notify_req'] # Get any flagged notificiations
	status_data['timer'] = control['timer'] # Get the timer information
	status_data['ipaddress'] = '192.168.10.43' # Future implementation (TODO)
	status_data['s_plus'] = control['s_plus']
	status_data['hopper_level'] = pelletdb['current']['hopper_level']

	return(status_data)

def WorkCycle(mode, grill_platform, adc_device, display_device, dist_device):
	# *****************************************
	# Work Cycle Function
	# *****************************************
	event = mode + ' Mode started.'
	WriteLog(event)

	# Setup Cycle Parameters
	settings = ReadSettings()
	control = ReadControl()
	pelletdb = ReadPelletDB()

	# Get ON/OFF Switch state and set as last state
	last = grill_platform.GetInputStatus()

	# Set Starting Configuration for Igniter, Fan , Auger
	grill_platform.FanOn()
	grill_platform.IgniterOff()
	grill_platform.AugerOff()
	grill_platform.PowerOn()
	
	if(settings['globals']['debug_mode'] == True):
		event = '* Fan ON, Igniter OFF, Auger OFF'
		print(event)
		WriteLog(event)
	if ((mode == 'Startup') or (mode == 'Reignite')):
		grill_platform.IgniterOn()
		if(settings['globals']['debug_mode'] == True):
			event = '* Igniter ON'
			print(event)
			WriteLog(event)
	if ((mode == 'Smoke') or (mode == 'Hold') or (mode == 'Startup') or (mode == 'Reignite')):
		grill_platform.AugerOn()
		if(settings['globals']['debug_mode'] == True):
			event = '* Auger ON'
			print(event)
			WriteLog(event)

	if (mode == 'Startup' or 'Smoke' or 'Reignite'):
		OnTime = settings['cycle_data']['SmokeCycleTime'] #  Auger On Time (Default 15s)
		OffTime = 45 + (settings['cycle_data']['PMode'] * 10) 	#  Auger Off Time
		CycleTime = OnTime + OffTime 	#  Total Cycle Time
		CycleRatio = OnTime / CycleTime #  Ratio of OnTime to CycleTime

	if (mode == 'Shutdown'):
		OnTime = 0		#  Auger On Time
		OffTime = 100	#  Auger Off Time
		CycleTime = 100 #  Total Cycle Time
		CycleRatio = 0 	#  Ratio of OnTime to CycleTime

	if (mode == 'Hold'):
		OnTime = settings['cycle_data']['HoldCycleTime'] * settings['cycle_data']['u_min']		#  Auger On Time
		OffTime = settings['cycle_data']['HoldCycleTime'] * (1 - settings['cycle_data']['u_min'])	#  Auger Off Time
		CycleTime = settings['cycle_data']['HoldCycleTime'] #  Total Cycle Time
		CycleRatio = settings['cycle_data']['u_min'] 	#  Ratio of OnTime to CycleTime
		PIDControl = PID.PID(settings['cycle_data']['PB'],settings['cycle_data']['Ti'],settings['cycle_data']['Td'])
		PIDControl.setTarget(control['setpoints']['grill'])	# Initialize with setpoint for grill
		if(settings['globals']['debug_mode'] == True):
			event = '* On Time = ' + str(OnTime) + ', OffTime = ' + str(OffTime) + ', CycleTime = ' + str(CycleTime) + ', CycleRatio = ' + str(CycleRatio)
			print(event)
			WriteLog(event)

	# Initialize all temperature variables
	GrillTemp = 0
	Probe1Temp = 0
	Probe2Temp = 0

	# Collect Initial Temperature Information
	# Get Probe Types From Settings
	grill0type = settings['probe_types']['grill0type']
	probe1type = settings['probe_types']['probe1type']
	probe2type = settings['probe_types']['probe2type']

	adc_device.SetProfiles(settings['probe_settings']['probe_profiles'][grill0type], settings['probe_settings']['probe_profiles'][probe1type], settings['probe_settings']['probe_profiles'][probe2type])
	
	adc_data = {}
	adc_data = adc_device.ReadAllPorts()

	AvgGT = adc_data['GrillTemp']
	AvgP1 = adc_data['Probe1Temp']
	AvgP2 = adc_data['Probe2Temp']

	status = 'Active'

	# Safety Controls
	if ((mode == 'Startup') or (mode == 'Reignite')):
		#control = ReadControl()  # Read Modify Write
		control['safety']['startuptemp'] = max((GrillTemp*0.9), settings['safety']['minstartuptemp'])
		control['safety']['startuptemp'] = min(control['safety']['startuptemp'], settings['safety']['maxstartuptemp'])
		control['safety']['afterstarttemp'] = GrillTemp
		WriteControl(control)
	# Check if the temperature of the grill dropped below the startuptemperature 
	elif ((mode == 'Hold') or (mode == 'Smoke')):
		if (control['safety']['afterstarttemp'] < control['safety']['startuptemp']):
			if(control['safety']['reigniteretries'] == 0):
				status = 'Inactive'
				event = 'ERROR: Grill temperature dropped below minimum startup temperature of ' + str(control['safety']['startuptemp']) + 'F! Shutting down to prevent firepot overload.'
				WriteLog(event)
				display_device.DisplayText('ERROR')
				#control = ReadControl()  # Read Modify Write
				control['mode'] = 'Error'
				control['updated'] = True
				WriteControl(control)
				if(settings['ifttt']['APIKey'] != ''):
					SendIFTTTNotification("Grill_Error_02", control, settings)
				if(settings['pushbullet']['APIKey'] != ''):
					SendPushBulletNotification("Grill_Error_02", control, settings)
				if(settings['pushover']['APIKey'] != '' and settings['pushover']['UserKeys'] != ''):
					SendPushoverNotification("Grill_Error_02", control, settings)
			else:
				#control = ReadControl()  # Read Modify Write
				control['safety']['reigniteretries'] -= 1
				control['safety']['reignitelaststate'] = mode 
				status = 'Inactive'
				event = 'ERROR: Grill temperature dropped below minimum startup temperature of ' + str(control['safety']['startuptemp']) + 'F. Starting a re-ignite attempt, per user settings.'
				WriteLog(event)
				display_device.DisplayText('Re-Ignite')
				control['mode'] = 'Reignite'
				control['updated'] = True
				WriteControl(control)

	# Set the start time
	starttime = time.time()

	# Set time since toggle for temperature
	temptoggletime = starttime

	# Set time since toggle for auger
	augertoggletime = starttime

	# Set time since toggle for display
	displaytoggletime = starttime 

	# Initializing Start Time for Smoke Plus Mode
	sp_cycletoggletime = starttime 

	# Set time since toggle for hopper check
	hoppertoggletime = starttime 

	# Set time since last control check
	controlchecktime = starttime 

	# Initialize Current Auger State Structure
	current_output_status = {}

	# ============ Main Work Cycle ============
	while(status == 'Active'):
		now = time.time()

		# Check for button input event
		display_device.EventDetect()

		# Check for update in control status every 0.5 seconds 
		if (now - controlchecktime > 0.5):
			control = ReadControl()
			controlchecktime = now 

		# Check if new mode has been requested 
		if (control['updated'] == True):
			status = 'Inactive'
			break

		# Check hopper level when requested or every 300 seconds 
		if (control['hopper_check'] == True) or (now - hoppertoggletime > 300):
			pelletdb = ReadPelletDB()
			# Get current hopper level and save it to the current pellet information
			pelletdb['current']['hopper_level'] = dist_device.GetLevel()
			WritePelletDB(pelletdb)
			hoppertoggletime = now
			if(control['hopper_check'] == True):
				#control = ReadControl()  # Read Modify Write
				control['hopper_check'] = False
				WriteControl(control)
			if(settings['globals']['debug_mode'] == True):
				event = "* Hopper Level Checked @ " + str(pelletdb['current']['hopper_level']) + "%"
				print(event)
				WriteLog(event)

		# Check for update in ON/OFF Switch
		if (last != grill_platform.GetInputStatus()):
			last = grill_platform.GetInputStatus()
			if(last == 1):
				status = 'Inactive'
				event = 'Switch set to off, going to monitor mode.'
				WriteLog(event)
				#control = ReadControl()  # Read Modify Write
				control['updated'] = True # Change mode
				control['mode'] = 'Stop'
				control['status'] = 'active'
				WriteControl(control)
				break
		
		# Change Auger State based on Cycle Time
		current_output_status = grill_platform.GetOutputStatus()

		# If Auger is OFF and time since toggle is greater than Off Time
		if (current_output_status['auger'] == AUGEROFF) and (now - augertoggletime > CycleTime * (1-CycleRatio)):
			grill_platform.AugerOn()
			augertoggletime = now
			# Reset Cycle Time for HOLD Mode
			if (mode == 'Hold'):
				CycleRatio = PIDControl.update(AvgGT)
				CycleRatio = max(CycleRatio, settings['cycle_data']['u_min'])
				CycleRatio = min(CycleRatio, settings['cycle_data']['u_max'])
				OnTime = settings['cycle_data']['HoldCycleTime'] * CycleRatio
				OffTime = settings['cycle_data']['HoldCycleTime'] * (1 - CycleRatio)
				CycleTime = OnTime + OffTime
				if(settings['globals']['debug_mode'] == True):
					event = '* On Time = ' + str(OnTime) + ', OffTime = ' + str(OffTime) + ', CycleTime = ' + str(CycleTime) + ', CycleRatio = ' + str(CycleRatio)
					print(event)
					WriteLog(event)
			if(settings['globals']['debug_mode'] == True):
				event = '* Cycle Event: Auger On'
				print(event)
				WriteLog(event)

		# If Auger is ON and time since toggle is greater than On Time
		if (current_output_status['auger'] == AUGERON) and (now - augertoggletime > CycleTime * CycleRatio):
			grill_platform.AugerOff()
			augertoggletime = now
			if(settings['globals']['debug_mode'] == True):
				event = '* Cycle Event: Auger Off'
				print(event)
				WriteLog(event)

		# Grab current probe profiles if they have changed since the last loop. 
		if (control['probe_profile_update'] == True):
			settings = ReadSettings()
			#control = ReadControl()  # Read Modify Write
			control['probe_profile_update'] = False
			WriteControl(control)
			# Get new probe profiles
			grill0type = settings['probe_types']['grill0type']
			probe1type = settings['probe_types']['probe1type']
			probe2type = settings['probe_types']['probe2type']
			# Add new probe profiles to ADC Object
			adc_device.SetProfiles(settings['probe_settings']['probe_profiles'][grill0type], settings['probe_settings']['probe_profiles'][probe1type], settings['probe_settings']['probe_profiles'][probe2type])

		# Get temperatures from all probes
		adc_data = {}
		adc_data = adc_device.ReadAllPorts()

		# Test temperature data returned for errors (+/- 20% Temp Variance), and average the data since last reading
		if((adc_data['GrillTemp'] != 0) and (adc_data['GrillTemp'] >= AvgGT * 0.8) and (adc_data['GrillTemp'] <= AvgGT * 1.2)):
			AvgGT = (adc_data['GrillTemp'] + AvgGT) / 2

		if((adc_data['Probe1Temp'] != 0) and (adc_data['Probe1Temp'] >= AvgP1 * 0.8) and (adc_data['Probe1Temp'] <= AvgP1 * 1.2)):
			AvgP1 = (adc_data['Probe1Temp'] + AvgP1) / 2
		elif(AvgP1 == 0):
			AvgP1 = adc_data['Probe1Temp']
		elif(adc_data['Probe1Temp'] == 0):
			AvgP1 = 0

		if((adc_data['Probe2Temp'] != 0) and (adc_data['Probe2Temp'] >= AvgP2 * 0.8) and (adc_data['Probe2Temp'] <= AvgP2 * 1.2)):
			AvgP2 = (adc_data['Probe2Temp'] + AvgP2) / 2
		elif(AvgP2 == 0):
			AvgP2 = adc_data['Probe2Temp']
		elif(adc_data['Probe2Temp'] == 0):
			AvgP2 = 0

		in_data = {}
		in_data['GrillTemp'] = int(AvgGT)
		in_data['GrillSetPoint'] = control['setpoints']['grill']
		in_data['Probe1Temp'] = int(AvgP1)
		in_data['Probe1SetPoint'] = control['setpoints']['probe1']
		in_data['Probe2Temp'] = int(AvgP2)
		in_data['Probe2SetPoint'] = control['setpoints']['probe2']
		in_data['GrillTr'] = adc_data['GrillTr']  # For Temp Resistance Tuning
		in_data['Probe1Tr'] = adc_data['Probe1Tr']  # For Temp Resistance Tuning
		in_data['Probe2Tr'] = adc_data['Probe2Tr']  # For Temp Resistance Tuning

		# Check to see if there are any pending notifications (i.e. Timer / Temperature Settings)
		control = CheckNotify(in_data, control, settings)

		# Check for button input event
		display_device.EventDetect()
		
		# Send Current Status / Temperature Data to Display Device every 1 second
		if(now - displaytoggletime > 1):
			status_data = GetStatus(grill_platform, control, settings, pelletdb)
			display_device.DisplayStatus(in_data, status_data)
			displaytoggletime = time.time() # Reset the displaytoggletime to current time

		# Safety Controls
		if ((mode == 'Startup') or (mode == 'Reignite')):
			control['safety']['afterstarttemp'] = AvgGT
		elif ((mode == 'Hold') or (mode == 'Smoke')):
			if (AvgGT < control['safety']['startuptemp']):
				if(control['safety']['reigniteretries'] == 0):
					status = 'Inactive'
					event = 'ERROR: Grill temperature dropped below minimum startup temperature of ' + str(control['safety']['startuptemp']) + 'F! Shutting down to prevent firepot overload.'
					WriteLog(event)
					display_device.DisplayText('ERROR')
					#control = ReadControl()  # Read Modify Write
					control['mode'] = 'Error'
					control['updated'] = True
					WriteControl(control)
					if(settings['ifttt']['APIKey'] != ''):
						SendIFTTTNotification("Grill_Error_02", control, settings)
					if(settings['pushbullet']['APIKey'] != ''):
						SendPushBulletNotification("Grill_Error_02", control, settings)
					if(settings['pushover']['APIKey'] != '' and settings['pushover']['UserKeys'] != ''):
						SendPushoverNotification("Grill_Error_02", control, settings)
				else:
					control['safety']['reigniteretries'] -= 1
					control['safety']['reignitelaststate'] = mode 
					status = 'Inactive'
					event = 'ERROR: Grill temperature dropped below minimum startup temperature of ' + str(control['safety']['startuptemp']) + 'F. Starting a re-ignite attempt, per user settings.'
					WriteLog(event)
					display_device.DisplayText('Re-Ignite')
					#control = ReadControl()  # Read Modify Write
					control['mode'] = 'Reignite'
					control['updated'] = True
					WriteControl(control)

			if (AvgGT > settings['safety']['maxtemp']):
				status = 'Inactive'
				event = 'ERROR: Grill exceed maximum temperature limit of ' + str(settings['safety']['maxtemp']) + 'F! Shutting down.'
				WriteLog(event)
				display_device.DisplayText('ERROR')
				#control = ReadControl()  # Read Modify Write
				control['mode'] = 'Error'
				control['updated'] = True
				WriteControl(control)
				if(settings['ifttt']['APIKey'] != ''):
					SendIFTTTNotification("Grill_Error_01", control, settings)
				if(settings['pushbullet']['APIKey'] != ''):
					SendPushBulletNotification("Grill_Error_01", control, settings)
				if(settings['pushover']['APIKey'] != '' and settings['pushover']['UserKeys'] != ''):
					SendPushoverNotification("Grill_Error_01", control, settings)

		# If in Smoke Plus Mode, Cycle the Fan
		if(((mode == 'Smoke') or (mode == 'Hold')) and (control['s_plus'] == True)):
			# If Temperature is > settings['smoke_plus']['max_temp'] then turn on fan
			if(AvgGT > settings['smoke_plus']['max_temp']):
				grill_platform.FanOn()
			# elif Temperature is < settings['smoke_plus']['min_temp'] then turn on fan
			elif(AvgGT < settings['smoke_plus']['min_temp']):
				grill_platform.FanOn()
			# elif now - sp_cycletoggletime > settings['smoke_plus']['cycle'] / 2 then toggle fan, reset sp_cycletoggletime = now
			elif((now - sp_cycletoggletime) > (settings['smoke_plus']['cycle']*0.5)):
				grill_platform.FanToggle()
				sp_cycletoggletime = now
				if(settings['globals']['debug_mode'] == True):
					event = '* Smoke Plus: Fan Toggled'
					print(event)
					WriteLog(event)

		# Write History after 3 seconds has passed
		if (now - temptoggletime > 3):
			temptoggletime = time.time()
			WriteHistory(in_data)
			#status_data = GetStatus(grill_platform, control, settings, pelletdb) # Does this need to be here? 

		# Check if 240s have elapsed since startup/reignite mode started
		if ((mode == 'Startup') or (mode == 'Reignite')):
			if((now - starttime) > 240):
				status = 'Inactive'

		# Check if shutdown time has elapsed since shutdown mode started
		if ((mode == 'Shutdown') and ((now - starttime) > settings['globals']['shutdown_timer'])):
			status = 'Inactive'

		time.sleep(0.05)
		# *********
		# END Mode Loop
		# *********

	# Clean-up and Exit
	grill_platform.AugerOff()
	grill_platform.IgniterOff()
	
	if(settings['globals']['debug_mode'] == True):
		event = '* Auger OFF, Igniter OFF'
		print(event)
		WriteLog(event)
	if(mode == 'Shutdown'):
		grill_platform.FanOff()
		grill_platform.PowerOff()
		if(settings['globals']['debug_mode'] == True):
			event = '* Fan OFF, Power OFF'
			print(event)
			WriteLog(event)
	if ((mode == 'Startup') or (mode == 'Reignite')):
		#control = ReadControl()  # Read Modify Write
		control['safety']['afterstarttemp'] = AvgGT
		WriteControl(control)
	event = mode + ' mode ended.'
	WriteLog(event)

	return()

# ******************************
# Monitor Grill Temperatures while alternative OEM controller is running
# ******************************

def Monitor(grill_platform, adc_device, display_device, dist_device):

	event = 'Monitor Mode started.'
	WriteLog(event)

	# Get ON/OFF Switch state and set as last state
	last = grill_platform.GetInputStatus()

	grill_platform.AugerOff()
	grill_platform.IgniterOff()
	grill_platform.FanOff()
	grill_platform.PowerOff()

	# Initialize all temperature variables
	GrillTemp = 0
	Probe1Temp = 0
	Probe2Temp = 0

	# Setup Cycle Parameters
	settings = ReadSettings()
	control = ReadControl()
	pelletdb = ReadPelletDB()

	# Collect Initial Temperature Information
	# Get Probe Types From Settings
	grill0type = settings['probe_types']['grill0type']
	probe1type = settings['probe_types']['probe1type']
	probe2type = settings['probe_types']['probe2type']

	adc_device.SetProfiles(settings['probe_settings']['probe_profiles'][grill0type], settings['probe_settings']['probe_profiles'][probe1type], settings['probe_settings']['probe_profiles'][probe2type])

	adc_data = {}
	adc_data = adc_device.ReadAllPorts()

	AvgGT = adc_data['GrillTemp']
	AvgP1 = adc_data['Probe1Temp']
	AvgP2 = adc_data['Probe2Temp']

	now = time.time()

	# Set time since toggle for temperature
	temptoggletime = now

	# Set time since toggle for display
	displaytoggletime = now 

	# Set time since toggle for hopper check
	hoppertoggletime = now 

	# Set time since last control check
	controlchecktime = now 

	status = 'Active'

	while(status == 'Active'):
		now = time.time()

		# Check for update in control status every 0.5 seconds 
		if (now - controlchecktime > 0.5):
			control = ReadControl()
			controlchecktime = now 

		# Check for update in control status
		if (control['updated'] == True):
			status = 'Inactive'
			break

		# Check for update in ON/OFF Switch
		if (last != grill_platform.GetInputStatus()):
			last = grill_platform.GetInputStatus()
			if(last == 1):
				status = 'Inactive'
				event = 'Switch set to off, going to Stop mode.'
				WriteLog(event)
				#control = ReadControl()  # Read Modify Write
				control['updated'] = True # Change mode
				control['mode'] == 'Stop'
				control['status'] == 'active'
				WriteControl(control)
				break

		# Check hopper level when requested or every 300 seconds 
		if (control['hopper_check'] == True) or (now - hoppertoggletime > 300):
			pelletdb = ReadPelletDB()
			# Get current hopper level and save it to the current pellet information
			pelletdb['current']['hopper_level'] = dist_device.GetLevel()
			WritePelletDB(pelletdb)
			hoppertoggletime = now
			if(control['hopper_check'] == True):
				#control = ReadControl()  # Read Modify Write
				control['hopper_check'] = False
				WriteControl(control)
			if(settings['globals']['debug_mode'] == True):
				event = "* Hopper Level Checked @ " + str(pelletdb['current']['hopper_level']) + "%"
				print(event)
				WriteLog(event)

		# Grab current probe profiles if they have changed since the last loop. 
		if (control['probe_profile_update'] == True):
			settings = ReadSettings()
			#control = ReadControl()  # Read Modify Write
			control['probe_profile_update'] = False
			WriteControl(control)
			# Get new probe profiles
			grill0type = settings['probe_types']['grill0type']
			probe1type = settings['probe_types']['probe1type']
			probe2type = settings['probe_types']['probe2type']
			# Add new probe profiles to ADC Object
			adc_device.SetProfiles(settings['probe_settings']['probe_profiles'][grill0type], settings['probe_settings']['probe_profiles'][probe1type], settings['probe_settings']['probe_profiles'][probe2type])

		adc_data = {}
		adc_data = adc_device.ReadAllPorts()

		AvgGT = (adc_data['GrillTemp'] + AvgGT) / 2
		AvgP1 = (adc_data['Probe1Temp'] + AvgP1) / 2
		AvgP2 = (adc_data['Probe2Temp'] + AvgP2) / 2

		in_data = {}
		in_data['GrillTemp'] = int(AvgGT)
		in_data['GrillSetPoint'] = control['setpoints']['grill']
		in_data['Probe1Temp'] = int(AvgP1)
		in_data['Probe1SetPoint'] = control['setpoints']['probe1']
		in_data['Probe2Temp'] = int(AvgP2)
		in_data['Probe2SetPoint'] = control['setpoints']['probe2']
		in_data['GrillTr'] = adc_data['GrillTr']
		in_data['Probe1Tr'] = adc_data['Probe1Tr']
		in_data['Probe2Tr'] = adc_data['Probe2Tr']
		
		control = CheckNotify(in_data, control, settings)

		# Check for button input event
		display_device.EventDetect()

		# Update Display Device after 1 second has passed 
		if(now - displaytoggletime > 1):
			status_data = GetStatus(grill_platform, control, settings, pelletdb)
			display_device.DisplayStatus(in_data, status_data)
			displaytoggletime = now 

		# Write History after 3 seconds has passed
		if (now - temptoggletime > 3):
			temptoggletime = now 
			WriteHistory(in_data)

		# Safety Control Section
		if (AvgGT > settings['safety']['maxtemp']):
			status = 'Inactive'
			event = 'ERROR: Grill exceed maximum temperature limit of ' + str(settings['safety']['maxtemp']) + 'F! Shutting down.'
			WriteLog(event)
			display_device.DisplayText('ERROR')
			#control = ReadControl()  # Read Modify Write
			control['mode'] = 'Error'
			control['updated'] = True
			control['status'] = 'monitor'
			WriteControl(control)
			if(settings['ifttt']['APIKey'] != ''):
				SendIFTTTNotification("Grill_Error_01", control, settings)
			if(settings['pushbullet']['APIKey'] != ''):
				SendPushBulletNotification("Grill_Error_01", control, settings)
			if(settings['pushover']['APIKey'] != '' and settings['pushover']['UserKeys'] != ''):
				SendPushoverNotification("Grill_Error_01", control, settings)

		time.sleep(0.05)

	event = 'Monitor mode ended.'
	WriteLog(event)

	return()

# ******************************
# Manual Mode Control
# ******************************

def Manual_Mode(grill_platform, adc_device, display_device, dist_device):
	# Setup Cycle Parameters
	settings = ReadSettings()
	control = ReadControl()
	pelletdb = ReadPelletDB()

	event = 'Manual Mode started.'
	WriteLog(event)

	# Get ON/OFF Switch state and set as last state
	last = grill_platform.GetInputStatus()

	grill_platform.AugerOff()
	grill_platform.IgniterOff()
	grill_platform.FanOff()
	grill_platform.PowerOff()

	# Initialize all temperature variables
	GrillTemp = 0
	Probe1Temp = 0
	Probe2Temp = 0

	# Collect Initial Temperature Information
	# Get Probe Types From Settings
	grill0type = settings['probe_types']['grill0type']
	probe1type = settings['probe_types']['probe1type']
	probe2type = settings['probe_types']['probe2type']

	adc_device.SetProfiles(settings['probe_settings']['probe_profiles'][grill0type], settings['probe_settings']['probe_profiles'][probe1type], settings['probe_settings']['probe_profiles'][probe2type])

	adc_data = {}
	adc_data = adc_device.ReadAllPorts()

	AvgGT = adc_data['GrillTemp']
	AvgP1 = adc_data['Probe1Temp']
	AvgP2 = adc_data['Probe2Temp']

	now = time.time()

	# Set time since toggle for temperature
	temptoggletime = now

	# Set time since toggle for display
	displaytoggletime = now 

	# Set time since last control check
	controlchecktime = now 

	status = 'Active'

	while(status == 'Active'):
		now = time.time()
		# Check for update in control status every 0.5 seconds 
		if (now - controlchecktime > 0.5):
			control = ReadControl()
			controlchecktime = now 

		# Check for update in control status
		if (control['updated'] == True):
			status = 'Inactive'
			break

		# Check for update in ON/OFF Switch
		if (last != grill_platform.GetInputStatus()):
			last = grill_platform.GetInputStatus()
			if(last == 1):
				status = 'Inactive'
				event = 'Switch set to off, going to Stop mode.'
				WriteLog(event)
				#control = ReadControl()  # Read Modify Write
				control['updated'] = True # Change mode
				control['mode'] == 'Stop'
				control['status'] == 'active'
				WriteControl(control)
				break

		if (control['manual']['change'] == True):
			if (control['manual']['output'] == 'fan'):
				if (control['manual']['state'] == 'on'):
					grill_platform.FanOn()
				else:
					grill_platform.FanOff()
			if (control['manual']['output'] == 'auger'):
				if (control['manual']['state'] == 'on'):
					grill_platform.AugerOn()
				else:
					grill_platform.AugerOff()
			if (control['manual']['output'] == 'igniter'):
				if (control['manual']['state'] == 'on'):
					grill_platform.IgniterOn()
				else:
					grill_platform.IgniterOff()
			if (control['manual']['output'] == 'power'):
				if (control['manual']['state'] == 'on'):
					grill_platform.PowerOn()
				else:
					grill_platform.PowerOff()
			#control = ReadControl()  # Read Modify Write
			control['manual']['change'] = False
			WriteControl(control)

		#control = ReadControl()  # Read Modify Write
		control['manual']['current'] = not grill_platform.GetOutputStatus()

		WriteControl(control)

		# Grab current probe profiles if they have changed since the last loop. 
		if (control['probe_profile_update'] == True):
			settings = ReadSettings()
			control['probe_profile_update'] = False
			WriteControl(control)
			# Get new probe profiles
			grill0type = settings['probe_types']['grill0type']
			probe1type = settings['probe_types']['probe1type']
			probe2type = settings['probe_types']['probe2type']
			# Add new probe profiles to ADC Object
			adc_device.SetProfiles(settings['probe_settings']['probe_profiles'][grill0type], settings['probe_settings']['probe_profiles'][probe1type], settings['probe_settings']['probe_profiles'][probe2type])

		adc_data = {}
		adc_data = adc_device.ReadAllPorts()

		AvgGT = (adc_data['GrillTemp'] + AvgGT) / 2
		AvgP1 = (adc_data['Probe1Temp'] + AvgP1) / 2
		AvgP2 = (adc_data['Probe2Temp'] + AvgP2) / 2

		in_data = {}
		in_data['GrillTemp'] = int(AvgGT)
		in_data['GrillSetPoint'] = control['setpoints']['grill']
		in_data['Probe1Temp'] = int(AvgP1)
		in_data['Probe1SetPoint'] = control['setpoints']['probe1']
		in_data['Probe2Temp'] = int(AvgP2)
		in_data['Probe2SetPoint'] = control['setpoints']['probe2']
		in_data['GrillTr'] = adc_data['GrillTr']
		in_data['Probe1Tr'] = adc_data['Probe1Tr']
		in_data['Probe2Tr'] = adc_data['Probe2Tr']

		# Update Display Device after 1 second has passed 
		if(now - displaytoggletime > 1):
			status_data = GetStatus(grill_platform, control, settings, pelletdb)
			display_device.DisplayStatus(in_data, status_data)
			displaytoggletime = now 

		control = CheckNotify(in_data, control, settings) 

		# Write History after 3 seconds has passed
		if (now - temptoggletime > 3):
			temptoggletime = time.time()
			WriteHistory(in_data)

		time.sleep(0.1)

	event = 'Manual mode ended.'
	WriteLog(event)

	return()

# ******************************
# Recipe Mode Control
# ******************************

def Recipe_Mode(grill_platform, adc_device, display_device, dist_device):
	settings = ReadSettings()
	event = 'Recipe Mode started.'
	WriteLog(event)

	# Find Recipe
	control = ReadControl()
	recipename = control['recipe']
	cookbook = ReadRecipes()

	if(recipename in cookbook):
		recipe = cookbook[recipename]
		if(settings['globals']['debug_mode'] == True):
			event = '* Found recipe: ' + recipename
			print(event)
			WriteLog(event)

		# Execute Recipe Steps
		#for(item in recipe['steps'].sort()):
		#	if('grill_temp' in recipe['steps'][item]):
		#		temp = recipe['steps'][item]['grill_temp']
		#		notify = recipe['steps'][item]['notify']
		#		desc = recipe['steps'][item]['description']
		#		event = item + ': Setting Grill Temp: ' + str(temp) + 'F, Notify: ' + str(notify) + ', Desc: ' + desc
		#		WriteLog(event)

			# Read Control, Check for updates, break
			# Read Switch, Check if changed to off, break
	else:
		# Error Recipe Not Found
		event = 'Recipe not found'



	event = 'Recipe mode ended.'
	WriteLog(event)

	return()

# ******************************
# Send Pushover Notifications
# ******************************

def SendPushoverNotification(notifyevent, control, settings):
	now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

	if "Grill_Temp_Achieved" in notifyevent:
		notifymessage = "The Grill setpoint of " + str(control['setpoints']['grill']) + "F was achieved at " + str(now)
		subjectmessage = "Grill at " + str(control['setpoints']['grill']) + "F at " + str(now)
	elif "Probe1_Temp_Achieved" in notifyevent:
		notifymessage = "The Probe 1 setpoint of " + str(control['setpoints']['probe1']) + "F was achieved at " + str(now)
		subjectmessage = "Probe 1 at " + str(control['setpoints']['probe1']) + "F at " + str(now)
	elif "Probe2_Temp_Achieved" in notifyevent:
		notifymessage = "The Probe 2 setpoint of " + str(control['setpoints']['probe2']) + "F was achieved at " + str(now)
		subjectmessage = "Probe 2 at " + str(control['setpoints']['probe2']) + "F at " + str(now)
	elif "Timer_Expired" in notifyevent:
		notifymessage = "Your grill timer has expired, time to check your cook!"
		subjectmessage = "Grill Timer Complete: " + str(now)
	elif "Grill_Error_00" in notifyevent:
		notifymessage = "Your grill has experienced an error and will shutdown now. " + str(now)
		subjectmessage = "Grill Error!"
	elif "Grill_Error_01" in notifyevent:
		notifymessage = "Grill exceed maximum temperature limit of " + str(settings['safety']['maxtemp']) + "F! Shutting down." + str(now)
		subjectmessage = "Grill Error!"
	elif "Grill_Error_02" in notifyevent:
		notifymessage = "Grill temperature dropped below minimum startup temperature of " + str(control['safety']['startuptemp']) + "F! Shutting down to prevent firepot overload." + str(now)
		subjectmessage = "Grill Error!"
	elif "Grill_Warning" in notifyevent:
		notifymessage = "Your grill has experienced a warning condition.  Please check the logs."  + str(now)
		subjectmessage = "Grill Warning!"
	else:
		notifymessage = "Whoops! PiFire had the following unhandled notify event: " + notifyevent + " at " + now
		subjectmessage = "PiFire: Unknown Notification at " + str(now)

	url = 'https://api.pushover.net/1/messages.json'
	for user in settings['pushover']['UserKeys'].split(','):
		try:
			r = requests.post(url, data={
				"token": settings['pushover']['APIKey'],
				"user": user.strip(),
				"message": notifymessage,
				"title": subjectmessage,
				"url": settings['pushover']['PublicURL']
			})
			if(settings['globals']['debug_mode'] == True):
				event = '* Pushover Response: ' + r.text
				print(event)
				WriteLog(event)
			WriteLog(subjectmessage + ". Pushover notification sent to: " + user.strip())

		except Exception as e:
			WriteLog("WARNING: Pushover Notification to %s failed: %s" % (user, e))
		except:
			WriteLog("WARNING: Pushover Notification to %s failed for unknown reason." % (user))

# ******************************
# Send Pushbullet Notifications
# ******************************

def SendPushBulletNotification(notifyevent, control, settings):
	now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

	if "Grill_Temp_Achieved" in notifyevent:
		notifymessage = "The Grill setpoint of " + str(control['setpoints']['grill']) + "F was achieved at " + str(now)
		subjectmessage = "Grill at " + str(control['setpoints']['grill']) + "F at " + str(now)
	elif "Probe1_Temp_Achieved" in notifyevent:
		notifymessage = "The Probe 1 setpoint of " + str(control['setpoints']['probe1']) + "F was achieved at " + str(now)
		subjectmessage = "Probe 1 at " + str(control['setpoints']['probe1']) + "F at " + str(now)
	elif "Probe2_Temp_Achieved" in notifyevent:
		notifymessage = "The Probe 2 setpoint of " + str(control['setpoints']['probe2']) + "F was achieved at " + str(now)
		subjectmessage = "Probe 2 at " + str(control['setpoints']['probe2']) + "F at " + str(now)
	elif "Timer_Expired" in notifyevent:
		notifymessage = "Your grill timer has expired, time to check your cook!"
		subjectmessage = "Grill Timer Complete: " + str(now)
	elif "Grill_Error_00" in notifyevent:
		notifymessage = "Your grill has experienced an error and will shutdown now. " + str(now)
		subjectmessage = "Grill Error!"
	elif "Grill_Error_01" in notifyevent:
		notifymessage = "Grill exceed maximum temperature limit of " + str(settings['safety']['maxtemp']) + "F! Shutting down." + str(now)
		subjectmessage = "Grill Error!"
	elif "Grill_Error_02" in notifyevent:
		notifymessage = "Grill temperature dropped below minimum startup temperature of " + str(control['safety']['startuptemp']) + "F! Shutting down to prevent firepot overload." + str(now)
		subjectmessage = "Grill Error!"
	elif "Grill_Warning" in notifyevent:
		notifymessage = "Your grill has experienced a warning condition.  Please check the logs."  + str(now)
		subjectmessage = "Grill Warning!"
	else:
		notifymessage = "Whoops! PiFire had the following unhandled notify event: " + notifyevent + " at " + now
		subjectmessage = "PiFire: Unknown Notification at " + str(now)

	api_key = settings['pushbullet']['APIKey']
	pushbullet_link = settings['pushbullet']['PublicURL']

	try:
		pb = Pushbullet(api_key)
		push = pb.push_link(subjectmessage, pushbullet_link, notifymessage)
		WriteLog("Pushbullet Notification Success: " + subjectmessage)
	except:
		WriteLog("Pushbullet Notification Failed: " + subjectmessage)

# ******************************
# Send IFTTT Notifications
# ******************************

def SendIFTTTNotification(notifyevent, control, settings):

	now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

	if "Grill_Temp_Achieved" in notifyevent:
		query_args = { "value1" : str(control['setpoints']['grill']) }
	elif "Probe1_Temp_Achieved" in notifyevent:
		query_args = { "value1" : str(control['setpoints']['probe1']) }
	elif "Probe2_Temp_Achieved" in notifyevent:
		query_args = { "value1" : str(control['setpoints']['probe2']) }
	elif "Timer_Expired" in notifyevent:
		query_args = { "value1" : 'Your grill timer has expired.' }
	elif "Grill_Error_00" in notifyevent:
		query_args = { "value1" : 'Your grill has experienced an error and will shutdown now. ' }
	elif "Grill_Error_01" in notifyevent:
		query_args = { "value1" : str(settings['safety']['maxtemp']) }
	elif "Grill_Error_02" in notifyevent:
		query_args = { "value1" : str(control['safety']['startuptemp']) }
	elif "Grill_Warning" in notifyevent:
		query_args = { "value1" : 'General Warning.' }
	else:
		WriteLog("IFTTT Notification Failed: Unhandled notify event.")
		return()

	key = settings['ifttt']['APIKey']
	url = 'https://maker.ifttt.com/trigger/' + notifyevent + '/with/key/' + key

	try:
		r = requests.post(url, data=query_args)
		WriteLog("IFTTT Notification Success: " + r.text)
	except:
		WriteLog("IFTTT Notification Failed: " + r.text)

# ******************************
# Check for any pending notifications
# ******************************

def CheckNotify(in_data, control, settings):

	if (control['notify_req']['grill'] == True):
		if (in_data['GrillTemp'] >= control['setpoints']['grill']):
			#control = ReadControl()  # Read Modify Write
			control['notify_req']['grill'] = False
			WriteControl(control)
			if(settings['ifttt']['APIKey'] != ''):
				SendIFTTTNotification("Grill_Temp_Achieved", control, settings)
			if(settings['pushbullet']['APIKey'] != ''):
				SendPushBulletNotification("Grill_Temp_Achieved", control, settings)
			if(settings['pushover']['APIKey'] != '' and settings['pushover']['UserKeys'] != ''):
				SendPushoverNotification("Grill_Temp_Achieved", control, settings)

	if (control['notify_req']['probe1']):
		if (in_data['Probe1Temp'] >= control['setpoints']['probe1']):
			if(settings['ifttt']['APIKey'] != ''):
				SendIFTTTNotification("Probe1_Temp_Achieved", control, settings)
			if(settings['pushbullet']['APIKey'] != ''):
				SendPushBulletNotification("Probe1_Temp_Achieved", control, settings)
			if(settings['pushover']['APIKey'] != '' and settings['pushover']['UserKeys'] != ''):
				SendPushoverNotification("Probe1_Temp_Achieved", control, settings)
			#control = ReadControl()  # Read Modify Write
			control['notify_req']['probe1'] = False
			if(control['notify_data']['p1_shutdown'] == True)and((control['mode'] == 'Smoke')or(control['mode'] == 'Hold')or(control['mode'] == 'Startup')or(control['mode'] == 'Reignite')):
				control['mode'] = 'Shutdown'
				control['updated'] = True
			WriteControl(control)

	if (control['notify_req']['probe2']):
		if (in_data['Probe2Temp'] >= control['setpoints']['probe2']):
			if(settings['ifttt']['APIKey'] != ''):
				SendIFTTTNotification("Probe2_Temp_Achieved", control, settings)
			if(settings['pushbullet']['APIKey'] != ''):
				SendPushBulletNotification("Probe2_Temp_Achieved", control, settings)
			if(settings['pushover']['APIKey'] != '' and settings['pushover']['UserKeys'] != ''):
				SendPushoverNotification("Probe2_Temp_Achieved", control, settings)
			#control = ReadControl()  # Read Modify Write
			control['notify_req']['probe2'] = False
			if(control['notify_data']['p2_shutdown'] == True)and((control['mode'] == 'Smoke')or(control['mode'] == 'Hold')or(control['mode'] == 'Startup')or(control['mode'] == 'Reignite')):
				control['mode'] = 'Shutdown'
				control['updated'] = True
			WriteControl(control)

	if (control['notify_req']['timer']):
		if (time.time() >= control['timer']['end']):
			if(settings['ifttt']['APIKey'] != ''):
				SendIFTTTNotification("Timer_Expired", control, settings)
			if(settings['pushbullet']['APIKey'] != ''):
				SendPushBulletNotification("Timer_Expired", control, settings)
			if(settings['pushover']['APIKey'] != '' and settings['pushover']['UserKeys'] != ''):
				SendPushoverNotification("Timer_Expired", control, settings)
			#control = ReadControl()  # Read Modify Write
			if(control['notify_data']['timer_shutdown'] == True)and((control['mode'] == 'Smoke')or(control['mode'] == 'Hold')or(control['mode'] == 'Startup')or(control['mode'] == 'Reignite')):
				control['mode'] = 'Shutdown'
				control['updated'] = True
			control['notify_req']['timer'] = False
			control['timer']['start'] = 0
			control['timer']['paused'] = 0
			control['timer']['end'] = 0
			control['notify_data']['timer_shutdown'] = False 
			WriteControl(control)

	return(control)

# *****************************************
# Main Program Start / Init
# *****************************************

# Init Global Variables / Classes

settings = ReadSettings()

outpins = settings['outpins']
inpins = settings['inpins']
triggerlevel = settings['globals']['triggerlevel']
buttonslevel = settings['globals']['buttonslevel']

if triggerlevel == 'LOW':
	AUGERON = 0
	AUGEROFF = 1
else:
	AUGERON = 1
	AUGEROFF = 0

# Initialize Grill Platform Object
grill_platform = GrillPlatform(outpins, inpins, triggerlevel)

# If powering on, check the on/off switch and set grill power appropriately.
last = grill_platform.GetInputStatus()

if(last == 0):
	grill_platform.PowerOn()
else:
	grill_platform.PowerOff()

# Start display device object and display splash
if(str(settings['modules']['display']).endswith('b')):	
	display_device = Display(buttonslevel)
else:
	display_device = Display()

grill0type = settings['probe_types']['grill0type']
probe1type = settings['probe_types']['probe1type']
probe2type = settings['probe_types']['probe2type']

# Start ADC object and set profiles
adc_device = ReadADC(settings['probe_settings']['probe_profiles'][grill0type], settings['probe_settings']['probe_profiles'][probe1type], settings['probe_settings']['probe_profiles'][probe2type])

pelletdb = ReadPelletDB()

# Start Distance Sensor Object for Hopper
dist_device = HopperLevel(pelletdb['empty'])

# Get current hopper level and save it to the current pellet information
pelletdb['current']['hopper_level'] = dist_device.GetLevel()
WritePelletDB(pelletdb)
if(settings['globals']['debug_mode'] == True):
	event = "* Hopper Level Checked @ " + str(pelletdb['current']['hopper_level']) + "%"
	print(event)
	WriteLog(event)

# Initialize Temp files
#  Remove existing control file
if(settings['globals']['debug_mode'] == True):
	event = '* Removing /tmp/control.json.'
	print(event)
	WriteLog(event)
os.system('rm /tmp/control.json')

#  Create /tmp/control.json file
control = ReadControl()

#  Create /logs/event.log file
event = 'Control Script Starting Up.'
WriteLog(event)


# *****************************************
# Main Program Loop
# *****************************************

while True:

	# Check the On/Off switch for changes
	if (last != grill_platform.GetInputStatus()):
		last = grill_platform.GetInputStatus()
		if(last == 1):
			event = 'Switch set to off, going to stop mode.'
			WriteLog(event)
			#control = ReadControl()  # Read Modify Write
			control['updated'] = True # Change mode
			control['mode'] == 'Stop'
			WriteControl(control)

	display_device.EventDetect()

	# 1. Check control.json for commands
	control = ReadControl()

	if (control['hopper_check'] == True):
		pelletdb = ReadPelletDB()
		# Get current hopper level and save it to the current pellet information
		pelletdb['current']['hopper_level'] = dist_device.GetLevel()
		WritePelletDB(pelletdb)
		if(settings['globals']['debug_mode'] == True):
			event = "* Hopper Level Checked @ " + str(pelletdb['current']['hopper_level']) + "%"
			print(event)
			WriteLog(event)
		#control = ReadControl()  # Read Modify Write
		control['hopper_check'] = False
		WriteControl(control)

	if (control['updated'] == True):
		if(settings['globals']['debug_mode'] == True):
			event = "* Updated Flag Captured."
			print(event)
			WriteLog(event)
		# Clear control flag
		control['updated'] = False # Reset Control Updated to False to acknowledge
		WriteControl(control) # Commit change in 'updated' status to the file 

		# Check if there was an Error flagged in Monitor Mode - If no, then change status to active
		if(control['status'] != 'monitor') and (control['mode'] != 'Error'):
			control['status'] = 'active' # Set status to active
			WriteControl(control)

		if (control['mode'] == 'Stop') or (control['mode'] == 'Error'):
			grill_platform.AugerOff()
			grill_platform.IgniterOff()
			grill_platform.FanOff()
			if(control['status'] == 'monitor') and (control['mode'] == 'Error'):
				grill_platform.PowerOn()
			else:
				grill_platform.PowerOff()
			if(control['mode'] == 'Stop'):
				display_device.ClearDisplay() # When in error mode, leave the display showing ERROR
				control['status'] = 'inactive'
				event = "Stop Mode Started."
				# Reset Control to Defaults
				control = DefaultControl()
				control['updated'] = False
				WriteControl(control)
			else:
				event = "ERROR: An error has occured, Stop Mode enabled."
				# Reset Control to Defaults but preserve 'Error' mode condition
				control = DefaultControl()
				control['mode'] = 'Error'
				control['status'] = 'inactive'
				control['updated'] = False
				WriteControl(control)

			curfile = open("/tmp/current.log", "w") # Write current data to current.log file
			curfile.write('00:00:0 0 0 0 0 0 0')
			curfile.close()
			WriteLog(event)

		#	Startup (startup sequence)
		elif (control['mode'] == 'Startup'):
			if(grill_platform.GetInputStatus() == 1):
				event = "Warning: PiFire is set to OFF. This doesn't prevent startup, but this means the switch won't behave as normal."
				WriteLog(event)
			#settings = ReadSettings()
			if(settings['history_page']['clearhistoryonstart'] == True):
				if(settings['globals']['debug_mode'] == True):
					event = '* Clearing History and Current Log on Startup Mode.'
					print(event)
					WriteLog(event)
				os.system('rm /tmp/history.log')
				os.system('rm /tmp/current.log')
			WorkCycle('Startup', grill_platform, adc_device, display_device, dist_device)
			control = ReadControl()
			# If mode is Startup, then assume you can transition into smoke mode
			if(control['mode'] == 'Startup'):
				control['mode'] = 'Smoke' # Set status to active
				WriteControl(control)
				WorkCycle('Smoke', grill_platform, adc_device, display_device, dist_device)
		#	Smoke (smoke cycle)
		elif (control['mode'] == 'Smoke'):
			WorkCycle('Smoke', grill_platform, adc_device, display_device, dist_device)
		#	Hold (hold at setpoint)
		elif (control['mode'] == 'Hold'):
			WorkCycle('Hold', grill_platform, adc_device, display_device, dist_device)
		#	Shutdown (shutdown sequence)
		elif (control['mode'] == 'Shutdown'):
			WorkCycle('Shutdown', grill_platform, adc_device, display_device, dist_device)
			control = ReadControl()
			if(control['mode'] == 'Shutdown'):
				control['mode'] = 'Stop' # Set mode to Stop
				control['updated'] = True
				WriteControl(control)
		#	e. Monitor (monitor the OEM controller)
		elif (control['mode'] == 'Monitor'):
			control['status'] = 'monitor' # Set status to monitor
			WriteControl(control)
			Monitor(grill_platform, adc_device, display_device, dist_device)
		elif (control['mode'] == 'Manual'):
			Manual_Mode(grill_platform, adc_device, display_device, dist_device)
		elif (control['mode'] == 'Recipe'):
			Recipe_Mode(grill_platform, adc_device, display_device, dist_device)
		#	Reignite (reignite sequence)
		elif (control['mode'] == 'Reignite'):
			if(grill_platform.GetInputStatus() == 1):
				event = "Warning: PiFire is set to OFF. This doesn't prevent reignite, but this means the switch won't behave as normal."
				WriteLog(event)
			WorkCycle('Reignite', grill_platform, adc_device, display_device, dist_device)
			control = ReadControl()
			lastmode = control['safety']['reignitelaststate']
			if(lastmode == 'Hold'):
				control['mode'] = 'Hold' # Set status to active
			else:
				control['mode'] = 'Smoke' # Set status to active
			WriteControl(control)
			WorkCycle(control['mode'], grill_platform, adc_device, display_device, dist_device)

	time.sleep(0.1)
	# ===================
	# End of Main Loop
	# ===================

exit()
