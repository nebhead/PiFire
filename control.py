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

# Set this to False on Raspberry Pi Host ()
prototype_mode = False # Set this to True to enable TEST / Prototype mode

# *****************************************
# Imported Libraries
# *****************************************

import time
import os
import json
import datetime
from common import *  # Common Library for WebUI and Control Program
import pid as PID # Library for calculating PID setpoints
import requests

if(prototype_mode == True):
	# Prototype Modules for Test Host (i.e. PC based testing)
	from adc_prototype import ReadADC # Library for reading the ADC device
	from grillplat_prototype import GrillPlatform # Library for controlling the grill platform
	from display_prototype import Display # Library for controlling the display device
else:
	# Actual Modules for RasPi
	from adc_ads1115 import ReadADC # Library for reading the ADC device
	from grillplat_traeger import GrillPlatform # Library for controlling the grill platform
	from display_ssd1306 import Display # Library for controlling the display device

# *****************************************
# Function Definitions
# *****************************************

def WorkCycle(mode, grill_platform, adc_device, display_device):
	# *****************************************
	# Work Cycle Function
	# *****************************************
	event = mode + ' Mode started.'
	WriteLog(event)
	DebugWrite(event)

	# Get ON/OFF Switch state and set as last state
	last = grill_platform.GetInputStatus()

	# Set Starting Configuration for Igniter, Fan , Auger
	grill_platform.FanOn()
	grill_platform.IgniterOff()
	grill_platform.AugerOff()
	grill_platform.PowerOn()
	event = 'Fan ON, Igniter OFF, Auger OFF'
	DebugWrite(event)
	if (mode == 'Startup'):
		grill_platform.IgniterOn()
		event = 'Igniter ON'
		DebugWrite(event)
	if ((mode == 'Smoke') or (mode == 'Hold') or (mode == 'Startup')):
		grill_platform.AugerOn()
		event = 'Auger ON'
		DebugWrite(event)

	# Setup Cycle Parameters
	settings = ReadSettings()
	control = ReadControl()

	if (mode == 'Startup' or 'Smoke'):
		OnTime = 15		#  Auger On Time
		OffTime = 45 + (settings['cycle_data']['PMode'] * 10) 	#  Auger Off Time
		CycleTime = OnTime + OffTime 	#  Total Cycle Time
		CycleRatio = OnTime / CycleTime #  Ratio of OnTime to CycleTime

	if (mode == 'Shutdown'):
		OnTime = 0		#  Auger On Time
		OffTime = 100	#  Auger Off Time
		CycleTime = 100 #  Total Cycle Time
		CycleRatio = 0 	#  Ratio of OnTime to CycleTime

	if (mode == 'Hold'):
		OnTime = settings['cycle_data']['CycleTime'] * settings['cycle_data']['u_min']		#  Auger On Time
		OffTime = settings['cycle_data']['CycleTime'] * (1 - settings['cycle_data']['u_min'])	#  Auger Off Time
		CycleTime = settings['cycle_data']['CycleTime'] #  Total Cycle Time
		CycleRatio = settings['cycle_data']['u_min'] 	#  Ratio of OnTime to CycleTime
		PIDControl = PID.PID(settings['cycle_data']['PB'],settings['cycle_data']['Ti'],settings['cycle_data']['Td'])
		PIDControl.setTarget(control['setpoints']['grill'])	# Initialize with setpoint for grill
		event = 'On Time = ' + str(OnTime) + ', OffTime = ' + str(OffTime) + ', CycleTime = ' + str(CycleTime) + ', CycleRatio = ' + str(CycleRatio)
		DebugWrite(event)

	# Initialize all temperature variables
	GrillTemp = 0
	Probe1Temp = 0
	Probe2Temp = 0

	# Collect Initial Temperature Information
	# Get Probe Types From Settings
	grill0type = settings['probe_types']['grill0type']
	probe1type = settings['probe_types']['probe1type']
	probe2type = settings['probe_types']['probe2type']

	adc_device.SetProfiles(settings['probe_profiles'][grill0type], settings['probe_profiles'][probe1type], settings['probe_profiles'][probe2type])

	GrillTemp, Probe1Temp, Probe2Temp = adc_device.ReadAllPorts()

	AvgGT = GrillTemp
	AvgP1 = Probe1Temp
	AvgP2 = Probe2Temp

	status = 'Active'

	# Safety Controls
	if (mode == 'Startup'):
		control['safety']['startuptemp'] = max((GrillTemp*0.9), settings['safety']['minstartuptemp'])
		control['safety']['startuptemp'] = min(control['safety']['startuptemp'], settings['safety']['maxstartuptemp'])
		control['safety']['afterstarttemp'] = GrillTemp
		WriteControl(control)
	# Commented out this safety control until I can fix it.
	elif ((mode == 'Hold') or (mode == 'Smoke')):
		if (control['safety']['afterstarttemp'] < control['safety']['startuptemp']):
			status = 'Inactive'
			event = 'Grill temperature dropped below minimum startup temperature of ' + str(control['safety']['startuptemp']) + 'F! Shutting down to prevent firepot overload.'
			DebugWrite(event)
			WriteLog(event)
			display_device.DisplayText('ERROR')
			control['mode'] = 'Stop'
			control['updated'] = True
			WriteControl(control)
			if(settings['ifttt']['APIKey'] != ''):
				SendIFTTTNotification("Grill_Error_02")
			if(settings['pushover']['APIKey'] != '' and settings['pushover']['UserKeys'] != ''):
				SendPushoverNotification("Grill_Error_02")

	# Set the start time
	starttime = time.time()

	# Set time since toggle for temperature
	temptoggletime = starttime

	# Set time since toggle for auger
	augertoggletime = starttime

	# Initialize Current Auger State Structure
	current_output_status = {}

	while(status == 'Active'):
		now = time.time()

		# Reset time since toggle for cycle
		cycletoggletime = now

		while((now - cycletoggletime) < CycleTime):	# Run a Cycle

			# Check for update in control status
			control = ReadControl()
			if (control['updated'] == True):
				status = 'Inactive'
				break

			# Check for update in ON/OFF Switch
			if (last != grill_platform.GetInputStatus()):
				last = grill_platform.GetInputStatus()
				if(last == 1):
					status = 'Inactive'
					event = 'Switch set to off, going to monitor mode.'
					WriteLog(event)
					control['updated'] = True # Change mode
					control['mode'] = 'Stop'
					control['statu'] = 'active'
					WriteControl(control)

					break

			# Change Auger State based on Cycle Time
			current_output_status = grill_platform.GetOutputStatus()

			# If Auger is OFF and time since toggle is greater than Off Time
			if (current_output_status['auger'] == 1) and (now - augertoggletime > CycleTime * (1-CycleRatio)):
				grill_platform.AugerOn()
				augertoggletime = time.time()
				event = 'Cycle Event: Auger On'
				DebugWrite(event)

			# If Auger is ON and time since toggle is greater than On Time
			if (current_output_status['auger'] == 0) and (now - augertoggletime > CycleTime * CycleRatio):
				grill_platform.AugerOff()
				augertoggletime = time.time()
				event = 'Cycle Event: Auger Off'
				DebugWrite(event)

			# Grab current settings
			settings = ReadSettings()

			# Collect Temperature Information and Write History
			grill0type = settings['probe_types']['grill0type']
			probe1type = settings['probe_types']['probe1type']
			probe2type = settings['probe_types']['probe2type']

			adc_device.SetProfiles(settings['probe_profiles'][grill0type], settings['probe_profiles'][probe1type], settings['probe_profiles'][probe2type])

			GrillTemp, Probe1Temp, Probe2Temp = adc_device.ReadAllPorts()

			if(GrillTemp != 0):
				AvgGT = (GrillTemp + AvgGT) / 2

			AvgP1 = (Probe1Temp + AvgP1) / 2
			AvgP2 = (Probe2Temp + AvgP2) / 2

			# Write History after 3 seconds has passed
			if (now - temptoggletime > 3):
				temptoggletime = time.time()
				in_data = DefaultTempStuct()
				in_data['GrillTemp'] = int(AvgGT)
				in_data['GrillSetPoint'] = control['setpoints']['grill']
				in_data['Probe1Temp'] = int(AvgP1)
				in_data['Probe1SetPoint'] = control['setpoints']['probe1']
				in_data['Probe2Temp'] = int(AvgP2)
				in_data['Probe2SetPoint'] = control['setpoints']['probe2']
				WriteHistory(in_data)
				display_device.DisplayTemp(in_data['GrillTemp'])
				RefreshControlData = CheckNotify(in_data)

				# Safety Controls
				if (mode == 'Startup'):
					if(RefreshControlData == True):
						control = ReadControl()
					control['safety']['afterstarttemp'] = AvgGT
					WriteControl(control)
				elif ((mode == 'Hold') or (mode == 'Smoke')):
					if (AvgGT < control['safety']['startuptemp']):
						status = 'Inactive'
						event = 'Grill temperature dropped below minimum startup temperature of ' + str(control['safety']['startuptemp']) + 'F! Shutting down to prevent firepot overload.'
						DebugWrite(event)
						WriteLog(event)
						display_device.DisplayText('ERROR')
						control['mode'] = 'Error'
						control['updated'] = True
						WriteControl(control)
						if(settings['ifttt']['APIKey'] != ''):
							SendIFTTTNotification("Grill_Error_02")
						if(settings['pushover']['APIKey'] != '' and settings['pushover']['UserKeys'] != ''):
							SendPushoverNotification("Grill_Error_02")

				if (AvgGT > settings['safety']['maxtemp']):
					status = 'Inactive'
					event = 'Grill exceed maximum temperature limit of ' + str(settings['safety']['maxtemp']) + 'F! Shutting down.'
					DebugWrite(event)
					WriteLog(event)
					display_device.DisplayText('ERROR')
					control['mode'] = 'Error'
					control['updated'] = True
					WriteControl(control)
					if(settings['ifttt']['APIKey'] != ''):
						SendIFTTTNotification("Grill_Error_01")
					if(settings['pushover']['APIKey'] != '' and settings['pushover']['UserKeys'] != ''):
						SendPushoverNotification("Grill_Error_01")

			time.sleep(0.5)
			now = time.time()

			# *********
			# END Cycle Loop
			# *********
		event = 'Cycle Completed.'
		DebugWrite(event)

		# Reset Cycle Time for HOLD Mode
		if (mode == 'Hold'):
			CycleRatio = PIDControl.update(AvgGT)
			CycleRatio = max(CycleRatio, settings['cycle_data']['u_min'])
			CycleRatio = min(CycleRatio, settings['cycle_data']['u_max'])
			OnTime = settings['cycle_data']['CycleTime'] * CycleRatio
			OffTime = settings['cycle_data']['CycleTime'] * (1 - CycleRatio)
			CycleTime = OnTime + OffTime
			event = 'On Time = ' + str(OnTime) + ', OffTime = ' + str(OffTime) + ', CycleTime = ' + str(CycleTime) + ', CycleRatio = ' + str(CycleRatio)
			DebugWrite(event)

		# Check for update in control status
		control = ReadControl()
		if (control['updated'] == True):
			status = 'Inactive'

		if (last != grill_platform.GetInputStatus()):
			last = grill_platform.GetInputStatus()
			if(last == 1):
				status = 'Inactive'
				event = 'Switch set to off, going to stop mode.'
				WriteLog(event)
				control['updated'] = True # Change mode
				control['mode'] == 'Stop'
				WriteControl(control)

		if ((mode == 'Startup') and ((now - starttime) > 240)):
			status = 'Inactive'

		if ((mode == 'Shutdown') and ((now - starttime) > 60)):
			status = 'Inactive'

		# *********
		# END Mode Loop
		# *********

	# Clean-up and Exit
	grill_platform.AugerOff()
	grill_platform.IgniterOff()
	event = 'Auger OFF, Igniter OFF'
	DebugWrite(event)
	if(mode == 'Shutdown'):
		grill_platform.FanOff()
		grill_platform.PowerOff()
		event = 'Fan OFF, Power OFF'
		DebugWrite(event)

	event = mode + ' mode ended.'
	WriteLog(event)
	DebugWrite(event)

	return()

# ******************************
# Monitor Grill Temperatures while Traeger controller is running
# ******************************

def Monitor(grill_platform, adc_device, display_device):

	event = 'Monitor Mode started.'
	WriteLog(event)
	DebugWrite(event)

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

	# Collect Initial Temperature Information
	# Get Probe Types From Settings
	grill0type = settings['probe_types']['grill0type']
	probe1type = settings['probe_types']['probe1type']
	probe2type = settings['probe_types']['probe2type']

	adc_device.SetProfiles(settings['probe_profiles'][grill0type], settings['probe_profiles'][probe1type], settings['probe_profiles'][probe2type])

	GrillTemp, Probe1Temp, Probe2Temp = adc_device.ReadAllPorts()

	AvgGT = GrillTemp
	AvgP1 = Probe1Temp
	AvgP2 = Probe2Temp

	# Set time since toggle for temperature
	temptoggletime = time.time()

	status = 'Active'

	while(status == 'Active'):

		# Check for update in control status
		control = ReadControl()
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
				control['updated'] = True # Change mode
				control['mode'] == 'Stop'
				control['status'] == 'active'
				WriteControl(control)
				break


		now = time.time()

		# Grab current settings
		settings = ReadSettings()

		# Collect Temperature Information and Write History
		grill0type = settings['probe_types']['grill0type']
		probe1type = settings['probe_types']['probe1type']
		probe2type = settings['probe_types']['probe2type']

		adc_device.SetProfiles(settings['probe_profiles'][grill0type], settings['probe_profiles'][probe1type], settings['probe_profiles'][probe2type])

		GrillTemp, Probe1Temp, Probe2Temp = adc_device.ReadAllPorts()

		AvgGT = (GrillTemp + AvgGT) / 2
		AvgP1 = (Probe1Temp + AvgP1) / 2
		AvgP2 = (Probe2Temp + AvgP2) / 2

		# Write History after 3 seconds has passed
		if (now - temptoggletime > 3):
			temptoggletime = time.time()
			in_data = DefaultTempStuct()
			in_data['GrillTemp'] = int(AvgGT)
			in_data['GrillSetPoint'] = control['setpoints']['grill']
			in_data['Probe1Temp'] = int(AvgP1)
			in_data['Probe1SetPoint'] = control['setpoints']['probe1']
			in_data['Probe2Temp'] = int(AvgP2)
			in_data['Probe2SetPoint'] = control['setpoints']['probe2']
			WriteHistory(in_data)
			display_device.DisplayTemp(in_data['GrillTemp'])
			CheckNotify(in_data)

			# Safety Control Section
			if (AvgGT > settings['safety']['maxtemp']):
				status = 'Inactive'
				event = 'Grill exceed maximum temperature limit of ' + str(settings['safety']['maxtemp']) + 'F! Shutting down.'
				DebugWrite(event)
				WriteLog(event)
				display_device.DisplayText('ERROR')
				control['mode'] = 'Error'
				control['updated'] = True
				control['status'] = 'monitor'
				WriteControl(control)
				if(settings['ifttt']['APIKey'] != ''):
					SendIFTTTNotification("Grill_Error_01")
				if(settings['pushover']['APIKey'] != '' and settings['pushover']['UserKeys'] != ''):
					SendPushoverNotification("Grill_Error_01")


		time.sleep(0.5)

	event = 'Monitor mode ended.'
	WriteLog(event)
	DebugWrite(event)
	return()

# ******************************
# Manual Mode Control
# ******************************

def Manual_Mode(grill_platform, adc_device, display_device):

	event = 'Manual Mode started.'
	WriteLog(event)
	DebugWrite(event)

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

	# Collect Initial Temperature Information
	# Get Probe Types From Settings
	grill0type = settings['probe_types']['grill0type']
	probe1type = settings['probe_types']['probe1type']
	probe2type = settings['probe_types']['probe2type']

	adc_device.SetProfiles(settings['probe_profiles'][grill0type], settings['probe_profiles'][probe1type], settings['probe_profiles'][probe2type])

	GrillTemp, Probe1Temp, Probe2Temp = adc_device.ReadAllPorts()

	AvgGT = GrillTemp
	AvgP1 = Probe1Temp
	AvgP2 = Probe2Temp

	# Set time since toggle for temperature
	temptoggletime = time.time()

	status = 'Active'

	while(status == 'Active'):

		# Check for update in control status
		control = ReadControl()
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
			control['manual']['change'] = False
			WriteControl(control)

		control['manual']['current'] = grill_platform.GetOutputStatus()

		WriteControl(control)

		now = time.time()

		# Grab current settings
		settings = ReadSettings()

		# Collect Temperature Information and Write History
		grill0type = settings['probe_types']['grill0type']
		probe1type = settings['probe_types']['probe1type']
		probe2type = settings['probe_types']['probe2type']

		adc_device.SetProfiles(settings['probe_profiles'][grill0type], settings['probe_profiles'][probe1type], settings['probe_profiles'][probe2type])

		GrillTemp, Probe1Temp, Probe2Temp = adc_device.ReadAllPorts()

		AvgGT = (GrillTemp + AvgGT) / 2
		AvgP1 = (Probe1Temp + AvgP1) / 2
		AvgP2 = (Probe2Temp + AvgP2) / 2

		# Write History after 3 seconds has passed
		if (now - temptoggletime > 3):
			temptoggletime = time.time()
			in_data = DefaultTempStuct()
			in_data['GrillTemp'] = int(AvgGT)
			in_data['GrillSetPoint'] = control['setpoints']['grill']
			in_data['Probe1Temp'] = int(AvgP1)
			in_data['Probe1SetPoint'] = control['setpoints']['probe1']
			in_data['Probe2Temp'] = int(AvgP2)
			in_data['Probe2SetPoint'] = control['setpoints']['probe2']
			WriteHistory(in_data)
			display_device.DisplayTemp(in_data['GrillTemp'])
			CheckNotify(in_data)

		time.sleep(0.5)

	event = 'Manual mode ended.'
	WriteLog(event)
	DebugWrite(event)
	return()

# ******************************
# Recipe Mode Control
# ******************************

def Recipe_Mode(grill_platform, adc_device, display_device):

	event = 'Recipe Mode started.'
	WriteLog(event)
	DebugWrite(event)

	# Find Recipe
	control = ReadControl()
	recipename = control['recipe']
	cookbook = ReadRecipes()

	if(recipename in cookbook):
		recipe = cookbook[recipename]
		event = 'Found recipe: ' + recipename
		DebugWrite(event)

		# Execute Recipe Steps
		#for(item in recipe['steps'].sort()):
		#	if('grill_temp' in recipe['steps'][item]):
		#		temp = recipe['steps'][item]['grill_temp']
		#		notify = recipe['steps'][item]['notify']
		#		desc = recipe['steps'][item]['description']
		#		event = item + ': Setting Grill Temp: ' + str(temp) + 'F, Notify: ' + str(notify) + ', Desc: ' + desc
		#		DebugWrite(event)

			# Read Control, Check for updates, break
			# Read Switch, Check if changed to off, break
	else:
		# Error Recipe Not Found
		event = 'Recipe not found'



	event = 'Recipe mode ended.'
	WriteLog(event)
	DebugWrite(event)
	return()

# ******************************
# Send Pushover Notifications
# ******************************

def SendPushoverNotification(notifyevent):
	now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
	settings = ReadSettings()
	control = ReadControl()

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
		notifymessage = "Your grill has experienced an warning condition.  Please check the logs."  + str(now)
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
				"title": subjectmessage
				#"url": settings['misc']['PublicURL']
			})
			DebugWrite('Pushover Response: ' + r.text)
			WriteLog(subjectmessage + ". Pushover notification sent to: " + user.strip())

		except Exception as e:
			WriteLog("Pushover Notification to %s failed: %s" % (user, e))
		except:
			WriteLog("Pushover Notification to %s failed for unknown reason." % (user))

# ******************************
# Send IFTTT Notifications
# ******************************

def SendIFTTTNotification(notifyevent):

	now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
	settings = ReadSettings()
	control = ReadControl()

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

def CheckNotify(in_data):

	settings = ReadSettings()
	control = ReadControl()
	RefreshControlData = False

	if (control['notify_req']['grill'] == True):
		if (in_data['GrillTemp'] >= in_data['GrillSetPoint']):
			control['notify_req']['grill'] = False
			WriteControl(control)
			if(settings['ifttt']['APIKey'] != ''):
				SendIFTTTNotification("Grill_Temp_Achieved")
			if(settings['pushover']['APIKey'] != '' and settings['pushover']['UserKeys'] != ''):
				SendPushoverNotification("Grill_Temp_Achieved")
			RefreshControlData = True
	if (control['notify_req']['probe1']):
		if (in_data['Probe1Temp'] >= in_data['Probe1SetPoint']):
			control['notify_req']['probe1'] = False
			WriteControl(control)
			if(settings['ifttt']['APIKey'] != ''):
				SendIFTTTNotification("Probe1_Temp_Achieved")
			if(settings['pushover']['APIKey'] != '' and settings['pushover']['UserKeys'] != ''):
				SendPushoverNotification("Probe1_Temp_Achieved")
			RefreshControlData = True
	if (control['notify_req']['probe2']):
		if (in_data['Probe2Temp'] >= in_data['Probe2SetPoint']):
			control['notify_req']['probe2'] = False
			WriteControl(control)
			if(settings['ifttt']['APIKey'] != ''):
				SendIFTTTNotification("Probe2_Temp_Achieved")
			if(settings['pushover']['APIKey'] != '' and settings['pushover']['UserKeys'] != ''):
				SendPushoverNotification("Probe2_Temp_Achieved")
			RefreshControlData = True
	if (control['notify_req']['timer']):
		if (time.time() >= control['timer']['end']):
			control['notify_req']['timer'] = False
			control['timer']['start'] = 0
			control['timer']['paused'] = 0
			control['timer']['end'] = 0
			WriteControl(control)
			if(settings['ifttt']['APIKey'] != ''):
				SendIFTTTNotification("Timer_Expired")
			if(settings['pushover']['APIKey'] != '' and settings['pushover']['UserKeys'] != ''):
				SendPushoverNotification("Timer_Expired")
			RefreshControlData = True

	return(RefreshControlData)

# *****************************************
# Main Program Start / Init
# *****************************************

# Init Global Variables / Classes

settings = ReadSettings()

outpins = settings['outpins']
inpins = settings['inpins']

# Initialize Grill Platform Object
grill_platform = GrillPlatform(outpins, inpins)

# If powering on, check the on/off switch and set grill power appropriately.
last = grill_platform.GetInputStatus()

if(last == 0):
	grill_platform.PowerOn()
else:
	grill_platform.PowerOff()

# Start display device object and display splash
display_device = Display()

grill0type = settings['probe_types']['grill0type']
probe1type = settings['probe_types']['probe1type']
probe2type = settings['probe_types']['probe2type']

# Start ADC object and set profiles
adc_device = ReadADC(settings['probe_profiles'][grill0type], settings['probe_profiles'][probe1type], settings['probe_profiles'][probe2type])

# Initialize Temp files
#  Remove existing control file
DebugWrite('Removing /tmp/control.json.')
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
			control['updated'] = True # Change mode
			control['mode'] == 'Stop'
			WriteControl(control)

	# 1. Check control.json for commands
	control = ReadControl()

	if (control['updated'] == True):
		event = "Updated Flag Captured."
		DebugWrite(event)

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
			else:
				control['status'] = 'error'
				event = "An error has occured, Stop Mode enabled."

			curfile = open("/tmp/current.log", "w") # Write current data to current.log file
			curfile.write('00:00:0 0 0 0 0 0 0')
			curfile.close()
			WriteLog(event)
			DebugWrite(event)
			WriteControl(control)
		#	a. Startup (startup sequence)
		elif (control['mode'] == 'Startup'):
			if(grill_platform.GetInputStatus() == 1):
				event = "Warning: PiFire is set to OFF. This doesn't prevent startup, but this means the switch won't behave as normal."
				WriteLog(event)
				DebugWrite(event)
			settings = ReadSettings()
			if(settings['clearhistoryonstart'] == True):
				DebugWrite('Clearing History and Current Log on Startup Mode.')
				os.system('rm /tmp/history.log')
				os.system('rm /tmp/current.log')
			WorkCycle('Startup', grill_platform, adc_device, display_device)
			control = ReadControl()
			if(control['mode'] == 'Startup'):
				control['mode'] = 'Smoke' # Set status to active
				WriteControl(control)
				WorkCycle('Smoke', grill_platform, adc_device, display_device)
		#	b. Smoke (smoke cycle)
		elif (control['mode'] == 'Smoke'):
			WorkCycle('Smoke', grill_platform, adc_device, display_device)
		#	c. Hold (hold at setpoint)
		elif (control['mode'] == 'Hold'):
			WorkCycle('Hold', grill_platform, adc_device, display_device)
		#	d. Shutdown (shutdown sequence)
		elif (control['mode'] == 'Shutdown'):
			WorkCycle('Shutdown', grill_platform, adc_device, display_device)
			control = ReadControl()
			if(control['mode'] == 'Shutdown'):
				control['mode'] = 'Stop' # Set mode to Stop
				control['updated'] = True
				WriteControl(control)
		#	e. Monitor (monitor the Traeger controller)
		elif (control['mode'] == 'Monitor'):
			control['status'] = 'monitor' # Set status to monitor
			WriteControl(control)
			Monitor(grill_platform, adc_device, display_device)
		elif (control['mode'] == 'Manual'):
			Manual_Mode(grill_platform, adc_device, display_device)
		elif (control['mode'] == 'Recipe'):
			Recipe_Mode(grill_platform, adc_device, display_device)

	time.sleep(0.5)
	# ===================
	# End of Main Loop
	# ===================

exit()
