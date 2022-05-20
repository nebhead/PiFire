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
# Base Imported Libraries
# *****************************************
import importlib
import requests
from pushbullet import Pushbullet  # Pushbullet Import
import pid as PID  # Library for calculating PID setpoints
from common import *  # Common Library for WebUI and Control Program
from temp_queue import TempQueue

'''
Read and initialize Settings, Control, History, Metrics, and Error Data
'''
# Read Settings & Wizard Manifest to Get Modules Configuration 
settings = ReadSettings()
wizardData = ReadWizard()

# Flush Redis DB and create JSON structure
control = ReadControl(flush=True)
# Delete Redis DB for history / current
ReadHistory(0, flushhistory=True)
# Flush metrics DB for tracking certain metrics
WriteMetrics(flush=True)
# Create errors log 
errors = ReadErrors(flush=True)

event = 'Flushing Redis DB and creating new control structure'
WriteLog(event)

'''
Set up GrillPlatform Module
'''
try: 
	grillplatform = settings['modules']['grillplat']
	filename = 'grillplat_' + wizardData['modules']['grillplatform'][grillplatform]['filename']
	GrillPlatModule = importlib.import_module(filename)

except:
	GrillPlatModule = importlib.import_module('grillplat_prototype')
	error_event = f'An error occured loading the [{settings["modules"]["grillplat"]}] platform module.  The prototype module has been loaded instead.  This sometimes means that the hardware is not connected properly, or the module is not configured.  Please run the configuration wizard again from the admin panel to fix this issue.'
	errors.append(error_event)
	WriteErrors(errors)
	WriteLog(error_event)
	if settings['globals']['debug_mode']:
		raise

outpins = settings['outpins']
inpins = settings['inpins']
triggerlevel = settings['globals']['triggerlevel']
buttonslevel = settings['globals']['buttonslevel']
disp_rotation = settings['globals']['disp_rotation']
units = settings['globals']['units']

if triggerlevel == 'LOW':
	AUGERON = 0
	AUGEROFF = 1
	FANON = 0
	FANOFF = 1
	IGNITERON = 0
	IGNITEROFF = 1
	POWERON = 0
	POWEROFF = 1
else:
	AUGERON = 1
	AUGEROFF = 0
	FANON = 1
	FANOFF = 0
	IGNITERON = 1
	IGNITEROFF = 0
	POWERON = 1
	POWEROFF = 0

try:
	grill_platform = GrillPlatModule.GrillPlatform(outpins, inpins, triggerlevel)
except:
	from grillplat_prototype import GrillPlatform  # Simulated Library for controlling the grill platform
	grill_platform = GrillPlatform(outpins, inpins, triggerlevel)
	error_event = f'An error occured configuring the [{settings["modules"]["grillplat"]}] platform object.  The prototype module has been loaded instead.  This sometimes means that the hardware is not connected properly, or the module is not configured.  Please run the configuration wizard again from the admin panel to fix this issue.'
	errors.append(error_event)
	WriteErrors(errors)
	WriteLog(error_event)
	if settings['globals']['debug_mode']:
		raise

# If powering on, check the on/off switch and set grill power appropriately.
last = grill_platform.GetInputStatus()

if last == 0:
	grill_platform.PowerOn()
else:
	grill_platform.PowerOff()

'''
Set up Probes Input (ADC) Module
'''
try: 
	probesinput = settings['modules']['adc']
	filename = 'adc_' + wizardData['modules']['probes'][probesinput]['filename']
	ProbesModule = importlib.import_module(filename)

except:
	ProbesModule = importlib.import_module('adc_prototype')
	error_event = f'An error occured loading the [{settings["modules"]["adc"]}] probes module.  The prototype module has been loaded instead.  This sometimes means that the hardware is not connected properly, or the module is not configured.  Please run the configuration wizard again from the admin panel to fix this issue.'
	errors.append(error_event)
	WriteErrors(errors)
	WriteLog(error_event)
	if settings['globals']['debug_mode']:
		raise

# Start ADC object and set profiles
grill1type = settings['probe_types']['grill1type']
grill2type = settings['probe_types']['grill2type']
probe1type = settings['probe_types']['probe1type']
probe2type = settings['probe_types']['probe2type']

try:
	adc_device = ProbesModule.ReadADC(
					settings['probe_settings']['probe_profiles'][grill1type],
					settings['probe_settings']['probe_profiles'][grill2type],
					settings['probe_settings']['probe_profiles'][probe1type],
					settings['probe_settings']['probe_profiles'][probe2type], 
					units=settings['globals']['units'])
except:
	from adc_prototype import ReadADC  # Simulated Library for controlling the grill platform
	adc_device = ReadADC(
					settings['probe_settings']['probe_profiles'][grill1type],
					settings['probe_settings']['probe_profiles'][grill2type],
					settings['probe_settings']['probe_profiles'][probe1type],
					settings['probe_settings']['probe_profiles'][probe2type], 
					units=settings['globals']['units'])
	
	error_event = f'An error occured configuring the [{settings["modules"]["adc"]}] probes object.  The prototype module has been loaded instead.  This sometimes means that the hardware is not connected properly, or the module is not configured.  Please run the configuration wizard again from the admin panel to fix this issue.'
	errors.append(error_event)
	WriteErrors(errors)
	WriteLog(error_event)
	if settings['globals']['debug_mode']:
		raise

for probe_source in settings['probe_settings']['probe_sources']:
	# if any of the probes uses max31865 then load the library
	if 'max31865' in probe_source:
		from probe_max31865 import probe_max31865_read

		break

'''
Set up Display Module
'''
try: 
	displayname = settings['modules']['display']
	filename = 'display_' + wizardData['modules']['display'][displayname]['filename']
	DisplayModule = importlib.import_module(filename)

except:
	DisplayModule = importlib.import_module('display_none')
	error_event = f'An error occured loading the [{settings["modules"]["display"]}] display module.  The "display_none" module has been loaded instead.  This sometimes means that the hardware is not connected properly, or the module is not configured.  Please run the configuration wizard again from the admin panel to fix this issue.'
	errors.append(error_event)
	WriteErrors(errors)
	WriteLog(error_event)
	if settings['globals']['debug_mode']:
		raise

try:
	display_device = DisplayModule.Display(buttonslevel=buttonslevel, rotation=disp_rotation, units=units)
except:
	from display_none import Display  # Simulated Library for controlling the grill platform
	display_device = Display(buttonslevel=buttonslevel, rotation=disp_rotation, units=units)
	error_event = f'An error occured configuring the [{settings["modules"]["display"]}] display object.  The "display_none" module has been loaded instead.  This sometimes means that the hardware is not connected properly, or the module is not configured.  Please run the configuration wizard again from the admin panel to fix this issue.'
	errors.append(error_event)
	WriteErrors(errors)
	WriteLog(error_event)
	if settings['globals']['debug_mode']:
		raise

'''
Set up Distance (Hopper Level) Module
'''
try: 
	distname = settings['modules']['dist']
	filename = 'distance_' + wizardData['modules']['distance'][distname]['filename']
	DistanceModule = importlib.import_module(filename)

except:
	DistanceModule = importlib.import_module('distance_prototype')
	error_event = f'An error occured loading the [{settings["modules"]["dist"]}] distance module.  The prototype module has been loaded instead.  This sometimes means that the hardware is not connected properly, or the module is not configured.  Please run the configuration wizard again from the admin panel to fix this issue.'
	errors.append(error_event)
	WriteErrors(errors)
	WriteLog(error_event)
	if settings['globals']['debug_mode']:
		raise

try:
	if (settings['modules']['grillplat'] == 'prototype') and (settings['modules']['dist'] == 'prototype'):
		# If in prototype mode, enable test reading (i.e. random values from proto distance sensor)
		dist_device = DistanceModule.HopperLevel(settings['pelletlevel']['empty'], settings['pelletlevel']['full'], test=True)
	else:
		dist_device = DistanceModule.HopperLevel(settings['pelletlevel']['empty'], settings['pelletlevel']['full'])
except:
	from distance_prototype import HopperLevel  # Simulated Library for controlling the grill platform
	dist_device = HopperLevel(settings['pelletlevel']['empty'], settings['pelletlevel']['full'])
	error_event = f'An error occured configuring the [{settings["modules"]["dist"]}] distance object.  The prototype module has been loaded instead.  This sometimes means that the hardware is not connected properly, or the module is not configured.  Please run the configuration wizard again from the admin panel to fix this issue.'
	errors.append(error_event)
	WriteErrors(errors)
	WriteLog(error_event)
	if settings['globals']['debug_mode']:
		raise

# Get current hopper level and save it to the current pellet information
pelletdb = ReadPelletDB()
pelletdb['current']['hopper_level'] = dist_device.GetLevel()
WritePelletDB(pelletdb)
if settings['globals']['debug_mode']:
	event = "* Hopper Level Checked @ " + str(pelletdb['current']['hopper_level']) + "%"
	print(event)
	WriteLog(event)

# *****************************************
# Function Definitions
# *****************************************
def ReadProbes(settings, adc_device, units):
	adc_data = adc_device.ReadAllPorts()

	prob_data = {}

	probe_ids = ['Grill1', 'Probe1', 'Probe2', 'Grill2']
	adc_properties = ['Temp', 'Tr']
	adc_probe_indices = ['Grill1', 'Probe1', 'Probe2', 'Grill2']
	for idx, probe_source in enumerate(settings['probe_settings']['probe_sources']):
		if 'ADC' in probe_source and len(probe_source) > 3:
			# map ADC proves to the output probes. i.e ADC0 is adc_probe_indices[0] => 'Grill' so if this is defined
			# for first source map Grill to Grill. If ADC1 in first source map it to Probe1
			source_index = int(probe_source[3:])
			for p in adc_properties:
				prob_data[probe_ids[idx] + p] = adc_data[adc_probe_indices[source_index] + p]
		elif 'max31865' in probe_source:
			temperature, resistance = probe_max31865_read(units=units)
			prob_data[probe_ids[idx] + adc_properties[0]] = temperature
			prob_data[probe_ids[idx] + adc_properties[1]] = resistance

	return prob_data


def GetStatus(grill_platform, control, settings, pelletdb):
	# *****************************************
	# Get Status Details for Display Function
	# *****************************************
	status_data = {}
	status_data['outpins'] = {}

	current = grill_platform.GetOutputStatus()  # Get current pin settings

	if settings['globals']['triggerlevel'] == 'LOW':
		for item in settings['outpins']:
			status_data['outpins'][item] = current[item]
	else:
		for item in settings['outpins']:
			status_data['outpins'][item] = not current[item]  # Reverse Logic

	status_data['mode'] = control['mode']  # Get current mode
	status_data['notify_req'] = control['notify_req']  # Get any flagged notificiations
	status_data['timer'] = control['timer']  # Get the timer information
	status_data['ipaddress'] = '192.168.10.43'  # Future implementation (TODO)
	status_data['s_plus'] = control['s_plus']
	status_data['hopper_level'] = pelletdb['current']['hopper_level']
	status_data['units'] = settings['globals']['units']

	return (status_data)


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

	WriteMetrics(new_metric=True)
	metrics = ReadMetrics()
	metrics['mode'] = str(control['mode'])
	metrics['smokeplus'] = control['s_plus'] 
	metrics['grill_settemp'] = control['setpoints']['grill']
	WriteMetrics(metrics)

	if settings['globals']['debug_mode']:
		event = '* Fan ON, Igniter OFF, Auger OFF'
		print(event)
		WriteLog(event)
	if (mode == 'Startup') or (mode == 'Reignite'):
		grill_platform.IgniterOn()
		if settings['globals']['debug_mode']:
			event = '* Igniter ON'
			print(event)
			WriteLog(event)
	if (mode == 'Smoke') or (mode == 'Hold') or (mode == 'Startup') or (mode == 'Reignite'):
		grill_platform.AugerOn()
		if settings['globals']['debug_mode']:
			event = '* Auger ON'
			print(event)
			WriteLog(event)

	if mode == 'Startup' or 'Smoke' or 'Reignite':
		OnTime = settings['cycle_data']['SmokeCycleTime']  # Auger On Time (Default 15s)
		OffTime = 45 + (settings['cycle_data']['PMode'] * 10)  # Auger Off Time
		CycleTime = OnTime + OffTime  # Total Cycle Time
		CycleRatio = OnTime / CycleTime  # Ratio of OnTime to CycleTime
		# Write Metrics (note these will be overwritten if smart start is enabled)
		metrics['p_mode'] = settings['cycle_data']['PMode']
		metrics['auger_cycle_time'] = settings['cycle_data']['SmokeCycleTime']
		WriteMetrics(metrics)

	if mode == 'Shutdown':
		OnTime = 0  # Auger On Time
		OffTime = 100  # Auger Off Time
		CycleTime = 100  # Total Cycle Time
		CycleRatio = 0  # Ratio of OnTime to CycleTime

	if mode == 'Hold':
		OnTime = settings['cycle_data']['HoldCycleTime'] * settings['cycle_data']['u_min']  # Auger On Time
		OffTime = settings['cycle_data']['HoldCycleTime'] * (1 - settings['cycle_data']['u_min'])  # Auger Off Time
		CycleTime = settings['cycle_data']['HoldCycleTime']  # Total Cycle Time
		CycleRatio = settings['cycle_data']['u_min']  # Ratio of OnTime to CycleTime
		PIDControl = PID.PID(settings['cycle_data']['PB'], settings['cycle_data']['Ti'], settings['cycle_data']['Td'])
		PIDControl.setTarget(control['setpoints']['grill'])  # Initialize with setpoint for grill
		if settings['globals']['debug_mode']:
			event = '* On Time = ' + str(OnTime) + ', OffTime = ' + str(OffTime) + ', CycleTime = ' + str(
				CycleTime) + ', CycleRatio = ' + str(CycleRatio)
			print(event)
			WriteLog(event)

	# Initialize all temperature variables
	AvgGT = TempQueue(units=settings['globals']['units'])
	AvgP1 = TempQueue(units=settings['globals']['units'])
	AvgP2 = TempQueue(units=settings['globals']['units'])

	# Check pellets level notification upon starting cycle
	CheckNotifyPellets(control, settings, pelletdb)

	# Collect Initial Temperature Information
	# Get Probe Types From Settings
	grill1type = settings['probe_types']['grill1type']
	grill2type = settings['probe_types']['grill2type']
	probe1type = settings['probe_types']['probe1type']
	probe2type = settings['probe_types']['probe2type']

	adc_device.SetProfiles(settings['probe_settings']['probe_profiles'][grill1type],
						   settings['probe_settings']['probe_profiles'][grill2type],
						   settings['probe_settings']['probe_profiles'][probe1type],
						   settings['probe_settings']['probe_profiles'][probe2type])

	adc_data = ReadProbes(settings, adc_device, units)

	if settings['globals']['four_probes']:
		if settings['grill_probe_settings']['grill_probe_enabled'][2] == 1:
			AvgGT.enqueue((adc_data['Grill1Temp'] + adc_data['Grill2Temp']) / 2)
		elif settings['grill_probe_settings']['grill_probe_enabled'][1] == 1:
			AvgGT.enqueue(adc_data['Grill2Temp'])
		else:
			AvgGT.enqueue(adc_data['Grill1Temp'])
	else:
		AvgGT.enqueue(adc_data['Grill1Temp'])

	AvgP1.enqueue(adc_data['Probe1Temp'])
	AvgP2.enqueue(adc_data['Probe2Temp'])

	status = 'Active'

	# Safety Controls
	if (mode == 'Startup') or (mode == 'Reignite'):
		# control = ReadControl()  # Read Modify Write
		control['safety']['startuptemp'] = int(max((AvgGT.average() * 0.9), settings['safety']['minstartuptemp']))
		control['safety']['startuptemp'] = int(
			min(control['safety']['startuptemp'], settings['safety']['maxstartuptemp']))
		control['safety']['afterstarttemp'] = AvgGT.average()
		WriteControl(control)
	# Check if the temperature of the grill dropped below the startuptemperature
	elif (mode == 'Hold') or (mode == 'Smoke'):
		if control['safety']['afterstarttemp'] < control['safety']['startuptemp']:
			if control['safety']['reigniteretries'] == 0:
				status = 'Inactive'
				event = 'ERROR: Grill temperature dropped below minimum startup temperature of ' + str(
					control['safety']['startuptemp']) + settings['globals'][
							'units'] + '! Shutting down to prevent firepot overload.'
				WriteLog(event)
				display_device.display_text('ERROR')
				# control = ReadControl()  # Read Modify Write
				control['mode'] = 'Error'
				control['updated'] = True
				WriteControl(control)
				SendNotifications("Grill_Error_02", control, settings, pelletdb)
			else:
				# control = ReadControl()  # Read Modify Write
				control['safety']['reigniteretries'] -= 1
				control['safety']['reignitelaststate'] = mode
				status = 'Inactive'
				event = 'ERROR: Grill temperature dropped below minimum startup temperature of ' + str(
					control['safety']['startuptemp']) + settings['globals'][
							'units'] + '. Starting a re-ignite attempt, per user settings.'
				WriteLog(event)
				display_device.display_text('Re-Ignite')
				control['mode'] = 'Reignite'
				control['updated'] = True
				WriteControl(control)

	# Apply Smart Start Settings if Enabled 
	if(settings['smartstart']['enabled']) and ((control['mode'] == 'Startup') or (control['mode'] == 'Smoke') or (control['mode'] == 'Reignite')):
		# If Startup, then save intial temperature & select the profile
		if (control['mode'] == 'Startup') or (control['mode'] == 'Reignite'):
			control['smartstart']['startuptemp'] = int(AvgGT.average())
			# Cycle through profiles, and set profile if startup temperature falls below the minimum temperature
			for profile_selected in range(0, len(settings['smartstart']['temp_range_list'])):
				if control['smartstart']['startuptemp'] < settings['smartstart']['temp_range_list'][profile_selected]:
					control['smartstart']['profile_selected'] = profile_selected
					WriteControl(control)
					break  # Break out of the loop
				if profile_selected == len(settings['smartstart']['temp_range_list'])-1:
					control['smartstart']['profile_selected'] = profile_selected + 1
					WriteControl(control)
		# Apply the profile 
		profile_selected = control['smartstart']['profile_selected']
		OnTime = settings['smartstart']['profiles'][profile_selected]['augerontime']  # Auger On Time (Default 15s)
		OffTime = 45 + (settings['smartstart']['profiles'][profile_selected]['p_mode'] * 10)  # Auger Off Time
		CycleTime = OnTime + OffTime  # Total Cycle Time
		CycleRatio = OnTime / CycleTime  # Ratio of OnTime to CycleTime
		# Write Metrics
		metrics['smart_start_profile'] = profile_selected
		metrics['startup_temp'] = control['smartstart']['startuptemp']
		metrics['p_mode'] = settings['smartstart']['profiles'][profile_selected]['p_mode']
		metrics['auger_cycle_time'] = settings['smartstart']['profiles'][profile_selected]['augerontime']
		WriteMetrics(metrics)

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

	# Set time since last pellet level check
	pelletschecktime = starttime

	# Initialize Current Auger State Structure
	current_output_status = {}

	# Set Hold Mode Target Temp Boolean
	target_temp_achieved = False

	# ============ Main Work Cycle ============
	while status == 'Active':
		now = time.time()

		# Check for button input event
		#display_device.EventDetect()

		# Check for update in control status every 0.1 seconds
		if now - controlchecktime > 0.1:
			control = ReadControl()
			controlchecktime = now

		# Check for pellet level notifications every 20 minutes
		if now - pelletschecktime > 1200:
			CheckNotifyPellets(control, settings, pelletdb)
			pelletschecktime = now

		# Check if new mode has been requested
		if control['updated']:
			status = 'Inactive'
			break

		# Check hopper level when requested or every 300 seconds
		if (control['hopper_check'] == True) or (now - hoppertoggletime > 300):
			pelletdb = ReadPelletDB()
			# Get current hopper level and save it to the current pellet information
			pelletdb['current']['hopper_level'] = dist_device.GetLevel()
			WritePelletDB(pelletdb)
			hoppertoggletime = now
			if control['hopper_check']:
				# control = ReadControl()  # Read Modify Write
				control['hopper_check'] = False
				WriteControl(control)
			if settings['globals']['debug_mode']:
				event = "* Hopper Level Checked @ " + str(pelletdb['current']['hopper_level']) + "%"
				print(event)
				WriteLog(event)

		# Check for update in ON/OFF Switch
		if last != grill_platform.GetInputStatus():
			last = grill_platform.GetInputStatus()
			if last == 1:
				status = 'Inactive'
				event = 'Switch set to off, going to monitor mode.'
				WriteLog(event)
				# control = ReadControl()  # Read Modify Write
				control['updated'] = True  # Change mode
				control['mode'] = 'Stop'
				control['status'] = 'active'
				WriteControl(control)
				break

		# Change Auger State based on Cycle Time
		current_output_status = grill_platform.GetOutputStatus()

		# If Auger is OFF and time since toggle is greater than Off Time
		if (current_output_status['auger'] == AUGEROFF) and (now - augertoggletime > CycleTime * (1 - CycleRatio)):
			grill_platform.AugerOn()
			augertoggletime = now
			# Reset Cycle Time for HOLD Mode
			if mode == 'Hold':
				CycleRatio = PIDControl.update(AvgGT.average())
				CycleRatio = max(CycleRatio, settings['cycle_data']['u_min'])
				CycleRatio = min(CycleRatio, settings['cycle_data']['u_max'])
				OnTime = settings['cycle_data']['HoldCycleTime'] * CycleRatio
				OffTime = settings['cycle_data']['HoldCycleTime'] * (1 - CycleRatio)
				CycleTime = OnTime + OffTime
				if settings['globals']['debug_mode']:
					event = '* On Time = ' + str(OnTime) + ', OffTime = ' + str(OffTime) + ', CycleTime = ' + str(
						CycleTime) + ', CycleRatio = ' + str(CycleRatio)
					print(event)
					WriteLog(event)
			if settings['globals']['debug_mode']:
				event = '* Cycle Event: Auger On'
				print(event)
				WriteLog(event)

		# If Auger is ON and time since toggle is greater than On Time
		if (current_output_status['auger'] == AUGERON) and (now - augertoggletime > CycleTime * CycleRatio):
			grill_platform.AugerOff()
			# Add auger ON time to the metrics
			metrics['augerontime'] += now - augertoggletime
			WriteMetrics(metrics)
			# Set current last toggle time to now
			augertoggletime = now
			if settings['globals']['debug_mode']:
				event = '* Cycle Event: Auger Off'
				print(event)
				WriteLog(event)

		# Grab current probe profiles if they have changed since the last loop.
		if control['probe_profile_update']:
			settings = ReadSettings()
			# control = ReadControl()  # Read Modify Write
			control['probe_profile_update'] = False
			WriteControl(control)
			# Get new probe profiles
			grill1type = settings['probe_types']['grill1type']
			grill2type = settings['probe_types']['grill2type']
			probe1type = settings['probe_types']['probe1type']
			probe2type = settings['probe_types']['probe2type']
			# Add new probe profiles to ADC Object
			adc_device.SetProfiles(settings['probe_settings']['probe_profiles'][grill1type],
								   settings['probe_settings']['probe_profiles'][grill2type],
								   settings['probe_settings']['probe_profiles'][probe1type],
								   settings['probe_settings']['probe_profiles'][probe2type])

		# Get temperatures from all probes
		adc_data = ReadProbes(settings, adc_device, units)

		# Test temperature data returned for errors (+/- 20% Temp Variance), and average the data since last reading
		if settings['globals']['four_probes']:
			if settings['grill_probe_settings']['grill_probe_enabled'][2] == 1:
				AvgGT.enqueue((adc_data['Grill1Temp'] + adc_data['Grill2Temp']) / 2 )
			elif settings['grill_probe_settings']['grill_probe_enabled'][1] == 1:
				AvgGT.enqueue(adc_data['Grill2Temp'])
			else:
				AvgGT.enqueue(adc_data['Grill1Temp'])
		else:
			AvgGT.enqueue(adc_data['Grill1Temp'])

		AvgP1.enqueue(adc_data['Probe1Temp'])
		AvgP2.enqueue(adc_data['Probe2Temp'])

		in_data = {}
		in_data['GrillTemp'] = AvgGT.average()
		in_data['GrillSetPoint'] = control['setpoints']['grill']
		in_data['Probe1Temp'] = AvgP1.average()
		in_data['Probe1SetPoint'] = control['setpoints']['probe1']
		in_data['Probe2Temp'] = AvgP2.average()
		in_data['Probe2SetPoint'] = control['setpoints']['probe2']

		if settings['globals']['four_probes']:
			if settings['grill_probe_settings']['grill_probe_enabled'][2] == 1:
				in_data['GrillTr'] = 0 # This is an average of two probes so it should be disabled for editing.
			elif settings['grill_probe_settings']['grill_probe_enabled'][1] == 1:
				in_data['GrillTr'] = adc_data['Grill2Tr']  # For Temp Resistance Tuning
			else:
				in_data['GrillTr'] = adc_data['Grill1Tr']  # For Temp Resistance Tuning
		else:
			in_data['GrillTr'] = adc_data['Grill1Tr']  # For Temp Resistance Tuning

		in_data['Probe1Tr'] = adc_data['Probe1Tr']  # For Temp Resistance Tuning
		in_data['Probe2Tr'] = adc_data['Probe2Tr']  # For Temp Resistance Tuning

		# Check to see if there are any pending notifications (i.e. Timer / Temperature Settings)
		control = CheckNotify(in_data, control, settings, pelletdb, grill_platform)

		# Check for button input event
		#display_device.EventDetect()

		# Send Current Status / Temperature Data to Display Device every 0.5 second (Display Refresh)
		if now - displaytoggletime > 0.5:
			status_data = GetStatus(grill_platform, control, settings, pelletdb)
			display_device.display_status(in_data, status_data)
			displaytoggletime = time.time()  # Reset the displaytoggletime to current time

		# Safety Controls
		if (mode == 'Startup') or (mode == 'Reignite'):
			control['safety']['afterstarttemp'] = AvgGT.average()
		elif (mode == 'Hold') or (mode == 'Smoke'):
			if AvgGT.average() < control['safety']['startuptemp']:
				if control['safety']['reigniteretries'] == 0:
					status = 'Inactive'
					event = 'ERROR: Grill temperature dropped below minimum startup temperature of ' + str(
						control['safety']['startuptemp']) + settings['globals'][
								'units'] + '! Shutting down to prevent firepot overload.'
					WriteLog(event)
					display_device.display_text('ERROR')
					# control = ReadControl()  # Read Modify Write
					control['mode'] = 'Error'
					control['updated'] = True
					WriteControl(control)
					SendNotifications("Grill_Error_02", control, settings, pelletdb)
				else:
					control['safety']['reigniteretries'] -= 1
					control['safety']['reignitelaststate'] = mode
					status = 'Inactive'
					event = 'ERROR: Grill temperature dropped below minimum startup temperature of ' + str(
						control['safety']['startuptemp']) + settings['globals'][
								'units'] + '. Starting a re-ignite attempt, per user settings.'
					WriteLog(event)
					display_device.display_text('Re-Ignite')
					# control = ReadControl()  # Read Modify Write
					control['mode'] = 'Reignite'
					control['updated'] = True
					WriteControl(control)

			if AvgGT.average() > settings['safety']['maxtemp']:
				status = 'Inactive'
				event = 'ERROR: Grill exceed maximum temperature limit of ' + str(
					settings['safety']['maxtemp']) + 'F! Shutting down.'
				WriteLog(event)
				display_device.display_text('ERROR')
				# control = ReadControl()  # Read Modify Write
				control['mode'] = 'Error'
				control['updated'] = True
				WriteControl(control)
				SendNotifications("Grill_Error_01", control, settings, pelletdb)

		# Check if target temperature has been achieved before utilizing Smoke Plus Mode
		if ((mode == 'Hold') and (AvgGT.average() >= control['setpoints']['grill']) and (
				target_temp_achieved == False)):
			target_temp_achieved = True

		# If in Smoke Plus Mode, Cycle the Fan
		if ((mode == 'Smoke') or ((mode == 'Hold') and (target_temp_achieved))) and (control['s_plus'] == True):
			# If Temperature is > settings['smoke_plus']['max_temp'] then turn on fan
			if AvgGT.average() > settings['smoke_plus']['max_temp']:
				grill_platform.FanOn()
			# elif Temperature is < settings['smoke_plus']['min_temp'] then turn on fan
			elif AvgGT.average() < settings['smoke_plus']['min_temp']:
				grill_platform.FanOn()
			# elif now - sp_cycletoggletime > settings['smoke_plus']['cycle'] / 2 then toggle fan, reset sp_cycletoggletime = now
			elif (now - sp_cycletoggletime) > (settings['smoke_plus']['cycle'] * 0.5):
				grill_platform.FanToggle()
				sp_cycletoggletime = now
				if settings['globals']['debug_mode']:
					event = '* Smoke Plus: Fan Toggled'
					print(event)
					WriteLog(event)

		elif (current_output_status['fan'] == FANOFF) and (control['s_plus'] == False):
			grill_platform.FanOn()

		# Write History after 3 seconds has passed
		if now - temptoggletime > 3:
			temptoggletime = time.time()
			WriteHistory(in_data, tuning_mode=control['tuning_mode'])

		# Check if startup time has elapsed since startup/reignite mode started
		if (mode == 'Startup') or (mode == 'Reignite'):
			if settings['smartstart']['enabled']:
				startup_timer = settings['smartstart']['profiles'][profile_selected]['startuptime']
			else: 
				startup_timer = settings['globals']['startup_timer']
			if (now - starttime) > startup_timer:
				status = 'Inactive'

		# Check if shutdown time has elapsed since shutdown mode started
		if (mode == 'Shutdown') and ((now - starttime) > settings['globals']['shutdown_timer']):
			status = 'Inactive'

		time.sleep(0.05)
	# *********
	# END Mode Loop
	# *********

	# Clean-up and Exit
	grill_platform.AugerOff()
	grill_platform.IgniterOff()

	if settings['globals']['debug_mode']:
		event = '* Auger OFF, Igniter OFF'
		print(event)
		WriteLog(event)
	if mode == 'Shutdown':
		grill_platform.FanOff()
		grill_platform.PowerOff()
		if settings['globals']['debug_mode']:
			event = '* Fan OFF, Power OFF'
			print(event)
			WriteLog(event)
	if (mode == 'Startup') or (mode == 'Reignite'):
		# control = ReadControl()  # Read Modify Write
		control['safety']['afterstarttemp'] = AvgGT.average()
		WriteControl(control)
	event = mode + ' mode ended.'
	WriteLog(event)

	# Log the end time
	metrics['endtime'] = time.time()
	WriteMetrics(metrics)

	return ()


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

	# Setup Cycle Parameters
	settings = ReadSettings()
	control = ReadControl()
	pelletdb = ReadPelletDB()

	# Initialize all temperature objects
	AvgGT = TempQueue(units=settings['globals']['units'])
	AvgP1 = TempQueue(units=settings['globals']['units'])
	AvgP2 = TempQueue(units=settings['globals']['units'])

	# Check pellets level notification upon starting cycle
	CheckNotifyPellets(control, settings, pelletdb)

	# Collect Initial Temperature Information
	# Get Probe Types From Settings
	grill1type = settings['probe_types']['grill1type']
	grill2type = settings['probe_types']['grill2type']
	probe1type = settings['probe_types']['probe1type']
	probe2type = settings['probe_types']['probe2type']

	adc_device.SetProfiles(settings['probe_settings']['probe_profiles'][grill1type],
						   settings['probe_settings']['probe_profiles'][grill2type],
						   settings['probe_settings']['probe_profiles'][probe1type],
						   settings['probe_settings']['probe_profiles'][probe2type])

	adc_data = ReadProbes(settings, adc_device, units)

	if settings['globals']['four_probes']:
		if settings['grill_probe_settings']['grill_probe_enabled'][2] == 1:
			AvgGT.enqueue((adc_data['Grill1Temp'] + adc_data['Grill2Temp']) / 2 )
		elif settings['grill_probe_settings']['grill_probe_enabled'][1] == 1:
			AvgGT.enqueue(adc_data['Grill2Temp'])
		else:
			AvgGT.enqueue(adc_data['Grill1Temp'])
	else:
		AvgGT.enqueue(adc_data['Grill1Temp'])

	AvgP1.enqueue(adc_data['Probe1Temp'])
	AvgP2.enqueue(adc_data['Probe2Temp'])

	now = time.time()

	# Set time since toggle for temperature
	temptoggletime = now

	# Set time since toggle for display
	displaytoggletime = now

	# Set time since toggle for hopper check
	hoppertoggletime = now

	# Set time since last control check
	controlchecktime = now

	# Set time since last pellet level check
	pelletschecktime = now

	status = 'Active'

	while status == 'Active':
		now = time.time()

		# Check for update in control status every 0.5 seconds
		if now - controlchecktime > 0.5:
			control = ReadControl()
			controlchecktime = now

		# Check for pellet level notifications every 20 minutes
		if now - pelletschecktime > 1200:
			CheckNotifyPellets(control, settings, pelletdb)
			pelletschecktime = now

		# Check for update in control status
		if control['updated'] == True:
			status = 'Inactive'
			break

		# Check for update in ON/OFF Switch
		if last != grill_platform.GetInputStatus():
			last = grill_platform.GetInputStatus()
			if last == 1:
				status = 'Inactive'
				event = 'Switch set to off, going to Stop mode.'
				WriteLog(event)
				# control = ReadControl()  # Read Modify Write
				control['updated'] = True  # Change mode
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
			if control['hopper_check']:
				# control = ReadControl()  # Read Modify Write
				control['hopper_check'] = False
				WriteControl(control)
			if settings['globals']['debug_mode']:
				event = "* Hopper Level Checked @ " + str(pelletdb['current']['hopper_level']) + "%"
				print(event)
				WriteLog(event)

		# Grab current probe profiles if they have changed since the last loop.
		if control['probe_profile_update']:
			settings = ReadSettings()
			# control = ReadControl()  # Read Modify Write
			control['probe_profile_update'] = False
			WriteControl(control)
			# Get new probe profiles
			grill1type = settings['probe_types']['grill1type']
			grill2type = settings['probe_types']['grill2type']
			probe1type = settings['probe_types']['probe1type']
			probe2type = settings['probe_types']['probe2type']
			# Add new probe profiles to ADC Object
			adc_device.SetProfiles(settings['probe_settings']['probe_profiles'][grill1type],
								   settings['probe_settings']['probe_profiles'][grill2type],
								   settings['probe_settings']['probe_profiles'][probe1type],
								   settings['probe_settings']['probe_profiles'][probe2type])

		adc_data = ReadProbes(settings, adc_device, units)

		# Test temperature data returned for errors (+/- 20% Temp Variance), and average the data since last reading
		if settings['globals']['four_probes']:
			if settings['grill_probe_settings']['grill_probe_enabled'][2] == 1:
				AvgGT.enqueue((adc_data['Grill1Temp'] + adc_data['Grill2Temp']) / 2 )
			elif settings['grill_probe_settings']['grill_probe_enabled'][1] == 1:
				AvgGT.enqueue(adc_data['Grill2Temp'])
			else:
				AvgGT.enqueue(adc_data['Grill1Temp'])
		else:
			AvgGT.enqueue(adc_data['Grill1Temp'])

		AvgP1.enqueue(adc_data['Probe1Temp'])
		AvgP2.enqueue(adc_data['Probe2Temp'])

		in_data = {}
		in_data['GrillTemp'] = AvgGT.average()
		in_data['GrillSetPoint'] = control['setpoints']['grill']
		in_data['Probe1Temp'] = AvgP1.average()
		in_data['Probe1SetPoint'] = control['setpoints']['probe1']
		in_data['Probe2Temp'] = AvgP2.average()
		in_data['Probe2SetPoint'] = control['setpoints']['probe2']

		if settings['globals']['four_probes']:
			if settings['grill_probe_settings']['grill_probe_enabled'][2] == 1:
				in_data['GrillTr'] = 0 # This is an average of two probes so it should be disabled for editing.
			elif settings['grill_probe_settings']['grill_probe_enabled'][1] == 1:
				in_data['GrillTr'] = adc_data['Grill2Tr']  # For Temp Resistance Tuning
			else:
				in_data['GrillTr'] = adc_data['Grill1Tr']  # For Temp Resistance Tuning
		else:
			in_data['GrillTr'] = adc_data['Grill1Tr']  # For Temp Resistance Tuning

		in_data['Probe1Tr'] = adc_data['Probe1Tr']  # For Temp Resistance Tuning
		in_data['Probe2Tr'] = adc_data['Probe2Tr']  # For Temp Resistance Tuning

		# Check to see if there are any pending notifications (i.e. Timer / Temperature Settings)
		control = CheckNotify(in_data, control, settings, pelletdb, grill_platform)

		# Check for button input event
		#display_device.EventDetect()

		# Update Display Device after 1 second has passed
		if now - displaytoggletime > 1:
			status_data = GetStatus(grill_platform, control, settings, pelletdb)
			display_device.display_status(in_data, status_data)
			displaytoggletime = now

		# Write History after 3 seconds has passed
		if now - temptoggletime > 3:
			temptoggletime = now
			WriteHistory(in_data, tuning_mode=control['tuning_mode'])

		# Safety Control Section
		if AvgGT.average() > settings['safety']['maxtemp']:
			status = 'Inactive'
			event = 'ERROR: Grill exceed maximum temperature limit of ' + str(settings['safety']['maxtemp']) + \
					settings['globals']['units'] + '! Shutting down.'
			WriteLog(event)
			display_device.display_text('ERROR')
			# control = ReadControl()  # Read Modify Write
			control['mode'] = 'Error'
			control['updated'] = True
			control['status'] = 'monitor'
			WriteControl(control)
			SendNotifications("Grill_Error_01", control, settings, pelletdb)

		time.sleep(0.05)

	event = 'Monitor mode ended.'
	WriteLog(event)

	return ()


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
	AvgGT = TempQueue(units=settings['globals']['units'])
	AvgP1 = TempQueue(units=settings['globals']['units'])
	AvgP2 = TempQueue(units=settings['globals']['units'])

	# Collect Initial Temperature Information
	# Get Probe Types From Settings
	grill1type = settings['probe_types']['grill1type']
	grill2type = settings['probe_types']['grill2type']
	probe1type = settings['probe_types']['probe1type']
	probe2type = settings['probe_types']['probe2type']

	adc_device.SetProfiles(settings['probe_settings']['probe_profiles'][grill1type],
						   settings['probe_settings']['probe_profiles'][grill2type],
						   settings['probe_settings']['probe_profiles'][probe1type],
						   settings['probe_settings']['probe_profiles'][probe2type])

	adc_data = ReadProbes(settings, adc_device, units)

	if settings['globals']['four_probes']:
		if settings['grill_probe_settings']['grill_probe_enabled'][2] == 1:
			AvgGT.enqueue((adc_data['Grill1Temp'] + adc_data['Grill2Temp']) / 2 )
		elif settings['grill_probe_settings']['grill_probe_enabled'][1] == 1:
			AvgGT.enqueue(adc_data['Grill2Temp'])
		else:
			AvgGT.enqueue(adc_data['Grill1Temp'])
	else:
		AvgGT.enqueue(adc_data['Grill1Temp'])

	AvgP1.enqueue(adc_data['Probe1Temp'])
	AvgP2.enqueue(adc_data['Probe2Temp'])

	now = time.time()

	# Set time since toggle for temperature
	temptoggletime = now

	# Set time since toggle for display
	displaytoggletime = now

	# Set time since last control check
	controlchecktime = now

	status = 'Active'

	while status == 'Active':
		now = time.time()
		# Check for update in control status every 0.5 seconds
		if now - controlchecktime > 0.5:
			control = ReadControl()
			controlchecktime = now

		# Check for update in control status
		if control['updated']:
			status = 'Inactive'
			break

		# Check for update in ON/OFF Switch
		if last != grill_platform.GetInputStatus():
			last = grill_platform.GetInputStatus()
			if last == 1:
				status = 'Inactive'
				event = 'Switch set to off, going to Stop mode.'
				WriteLog(event)
				# control = ReadControl()  # Read Modify Write
				control['updated'] = True  # Change mode
				control['mode'] == 'Stop'
				control['status'] == 'active'
				WriteControl(control)
				break

		# Get current grill output status
		current_output_status = grill_platform.GetOutputStatus()

		if control['manual']['change']:
			if (control['manual']['fan'] == True) and (current_output_status['fan'] == FANOFF):
				grill_platform.FanOn()
			elif (control['manual']['fan'] == False) and (current_output_status['fan'] == FANON):
				grill_platform.FanOff()

			if (control['manual']['auger'] == True) and (current_output_status['auger'] == AUGEROFF):
				grill_platform.AugerOn()
			elif (control['manual']['auger'] == False) and (current_output_status['auger'] == AUGERON):
				grill_platform.AugerOff()

			if (control['manual']['igniter'] == True) and (current_output_status['igniter'] == IGNITEROFF):
				grill_platform.IgniterOn()
			elif (control['manual']['igniter'] == False) and (current_output_status['igniter'] == IGNITERON):
				grill_platform.IgniterOff()

			if (control['manual']['power'] == True) and (current_output_status['power'] == POWEROFF):
				grill_platform.PowerOn()
			elif (control['manual']['power'] == False) and (current_output_status['power'] == POWERON):
				grill_platform.PowerOff()

			# control = ReadControl()  # Read Modify Write
			control['manual']['change'] = False
			WriteControl(control)

		# Grab current probe profiles if they have changed since the last loop.
		if control['probe_profile_update']:
			settings = ReadSettings()
			control['probe_profile_update'] = False
			WriteControl(control)
			# Get new probe profiles
			grill1type = settings['probe_types']['grill1type']
			grill2type = settings['probe_types']['grill2type']
			probe1type = settings['probe_types']['probe1type']
			probe2type = settings['probe_types']['probe2type']
			# Add new probe profiles to ADC Object
			adc_device.SetProfiles(settings['probe_settings']['probe_profiles'][grill1type],
								   settings['probe_settings']['probe_profiles'][grill2type],
								   settings['probe_settings']['probe_profiles'][probe1type],
								   settings['probe_settings']['probe_profiles'][probe2type])

		adc_data = {}
		adc_data = adc_device.ReadAllPorts()

		# Test temperature data returned for errors (+/- 20% Temp Variance), and average the data since last reading
		if settings['globals']['four_probes']:
			if settings['grill_probe_settings']['grill_probe_enabled'][2] == 1:
				AvgGT.enqueue((adc_data['Grill1Temp'] + adc_data['Grill2Temp']) / 2 )
			elif settings['grill_probe_settings']['grill_probe_enabled'][1] == 1:
				AvgGT.enqueue(adc_data['Grill2Temp'])
			else:
				AvgGT.enqueue(adc_data['Grill1Temp'])
		else:
			AvgGT.enqueue(adc_data['Grill1Temp'])

		AvgP1.enqueue(adc_data['Probe1Temp'])
		AvgP2.enqueue(adc_data['Probe2Temp'])

		in_data = {}
		in_data['GrillTemp'] = AvgGT.average()
		in_data['GrillSetPoint'] = control['setpoints']['grill']
		in_data['Probe1Temp'] = AvgP1.average()
		in_data['Probe1SetPoint'] = control['setpoints']['probe1']
		in_data['Probe2Temp'] = AvgP2.average()
		in_data['Probe2SetPoint'] = control['setpoints']['probe2']

		if settings['globals']['four_probes']:
			if settings['grill_probe_settings']['grill_probe_enabled'][2] == 1:
				in_data['GrillTr'] = 0 # This is an average of two probes so it should be disabled for editing.
			elif settings['grill_probe_settings']['grill_probe_enabled'][1] == 1:
				in_data['GrillTr'] = adc_data['Grill2Tr']  # For Temp Resistance Tuning
			else:
				in_data['GrillTr'] = adc_data['Grill1Tr']  # For Temp Resistance Tuning
		else:
			in_data['GrillTr'] = adc_data['Grill1Tr']  # For Temp Resistance Tuning

		in_data['Probe1Tr'] = adc_data['Probe1Tr']  # For Temp Resistance Tuning
		in_data['Probe2Tr'] = adc_data['Probe2Tr']  # For Temp Resistance Tuning

		# Update Display Device after 1 second has passed
		if now - displaytoggletime > 1:
			status_data = GetStatus(grill_platform, control, settings, pelletdb)
			display_device.display_status(in_data, status_data)
			displaytoggletime = now

		control = CheckNotify(in_data, control, settings, pelletdb, grill_platform)

		# Write History after 3 seconds has passed
		if now - temptoggletime > 3:
			temptoggletime = time.time()
			WriteHistory(in_data, tuning_mode=control['tuning_mode'])

		time.sleep(0.2)

	# Clean-up and Exit
	grill_platform.AugerOff()
	grill_platform.IgniterOff()
	grill_platform.FanOff()
	grill_platform.PowerOff()

	event = 'Manual mode ended.'
	WriteLog(event)

	return ()


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

	if recipename in cookbook:
		recipe = cookbook[recipename]
		if settings['globals']['debug_mode']:
			event = '* Found recipe: ' + recipename
			print(event)
			WriteLog(event)

	# Execute Recipe Steps
	# for(item in recipe['steps'].sort()):
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

	return ()


# ******************************
# Send Pushover Notifications
# ******************************

def SendPushoverNotification(notifyevent, control, settings, pelletdb):
	now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

	unit = settings['globals']['units']

	if "Grill_Temp_Achieved" in notifyevent:
		notifymessage = "The Grill setpoint of " + str(
			control['setpoints']['grill']) + unit + " was achieved at " + str(now)
		subjectmessage = "Grill at " + str(control['setpoints']['grill']) + unit + " at " + str(now)
	elif "Probe1_Temp_Achieved" in notifyevent:
		notifymessage = "The Probe 1 setpoint of " + str(
			control['setpoints']['probe1']) + unit + " was achieved at " + str(now)
		subjectmessage = "Probe 1 at " + str(control['setpoints']['probe1']) + unit + " at " + str(now)
	elif "Probe2_Temp_Achieved" in notifyevent:
		notifymessage = "The Probe 2 setpoint of " + str(
			control['setpoints']['probe2']) + unit + " was achieved at " + str(now)
		subjectmessage = "Probe 2 at " + str(control['setpoints']['probe2']) + unit + " at " + str(now)
	elif "Timer_Expired" in notifyevent:
		notifymessage = "Your grill timer has expired, time to check your cook!"
		subjectmessage = "Grill Timer Complete: " + str(now)
	elif "Pellet_Level_Low" in notifyevent:
		notifymessage = "Your pellet level is currently at " + str(pelletdb['current']['hopper_level']) + "%"
		subjectmessage = "Low Pellet Level"
	elif "Grill_Error_00" in notifyevent:
		notifymessage = "Your grill has experienced an error and will shutdown now. " + str(now)
		subjectmessage = "Grill Error!"
	elif "Grill_Error_01" in notifyevent:
		notifymessage = "Grill exceed maximum temperature limit of " + str(
			settings['safety']['maxtemp']) + unit + "! Shutting down. " + str(now)
		subjectmessage = "Grill Error!"
	elif "Grill_Error_02" in notifyevent:
		notifymessage = "Grill temperature dropped below minimum startup temperature of " + str(
			control['safety']['startuptemp']) + unit + "! Shutting down to prevent firepot overload. " + str(now)
		subjectmessage = "Grill Error!"
	elif "Grill_Warning" in notifyevent:
		notifymessage = "Your grill has experienced a warning condition.  Please check the logs. " + str(now)
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
			if settings['globals']['debug_mode']:
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

def SendPushBulletNotification(notifyevent, control, settings, pelletdb):
	now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')

	unit = settings['globals']['units']
	if "Grill_Temp_Achieved" in notifyevent:
		notifymessage = "The Grill setpoint of " + str(
			control['setpoints']['grill']) + unit + " was achieved at " + str(now)
		subjectmessage = "Grill at " + str(control['setpoints']['grill']) + unit + " at " + str(now)
	elif "Probe1_Temp_Achieved" in notifyevent:
		notifymessage = "The Probe 1 setpoint of " + str(
			control['setpoints']['probe1']) + unit + " was achieved at " + str(now)
		subjectmessage = "Probe 1 at " + str(control['setpoints']['probe1']) + unit + " at " + str(now)
	elif "Probe2_Temp_Achieved" in notifyevent:
		notifymessage = "The Probe 2 setpoint of " + str(
			control['setpoints']['probe2']) + unit + " was achieved at " + str(now)
		subjectmessage = "Probe 2 at " + str(control['setpoints']['probe2']) + unit + " at " + str(now)
	elif "Timer_Expired" in notifyevent:
		notifymessage = "Your grill timer has expired, time to check your cook!"
		subjectmessage = "Grill Timer Complete: " + str(now)
	elif "Pellet_Level_Low" in notifyevent:
		notifymessage = "Your pellet level is currently at " + str(pelletdb['current']['hopper_level']) + "%"
		subjectmessage = "Low Pellet Level"
	elif "Grill_Error_00" in notifyevent:
		notifymessage = "Your grill has experienced an error and will shutdown now. " + str(now)
		subjectmessage = "Grill Error!"
	elif "Grill_Error_01" in notifyevent:
		notifymessage = "Grill exceed maximum temperature limit of " + str(
			settings['safety']['maxtemp']) + unit + "! Shutting down. " + str(now)
		subjectmessage = "Grill Error!"
	elif "Grill_Error_02" in notifyevent:
		notifymessage = "Grill temperature dropped below minimum startup temperature of " + str(
			control['safety']['startuptemp']) + unit + "! Shutting down to prevent firepot overload. " + str(now)
		subjectmessage = "Grill Error!"
	elif "Grill_Warning" in notifyevent:
		notifymessage = "Your grill has experienced a warning condition.  Please check the logs. " + str(now)
		subjectmessage = "Grill Warning!"
	else:
		notifymessage = "Whoops! PiFire had the following unhandled notify event: " + notifyevent + " at " + now
		subjectmessage = "PiFire: Unknown Notification at " + str(now)

	api_key = settings['pushbullet']['APIKey']
	pushbullet_link = settings['pushbullet']['PublicURL']

	try:
		pb = Pushbullet(api_key)
		pb.push_link(subjectmessage, pushbullet_link, notifymessage)
		WriteLog("Pushbullet Notification Success: " + subjectmessage)
	except:
		WriteLog("Pushbullet Notification Failed: " + subjectmessage)


# *********************************
# Send OneSignal Push Notification
# *********************************

def SendOneSignalNotification(notifyevent, control, settings, pelletdb):
	date = datetime.datetime.now()
	now = date.strftime('%m-%d %H:%M')
	time = date.strftime('%H:%M')
	day = date.strftime('%m/%d')

	unit = settings['globals']['units']

	if "Grill_Temp_Achieved" in notifyevent:
		titlemessage = "Grill Setpoint Achieved"
		bodymessage = "Grill setpoint of " + str(control['setpoints']['grill']) + unit + " achieved at " + str(
			time) + " on " + str(day)
		channel = 'pifire_temp_alerts'
	elif "Probe1_Temp_Achieved" in notifyevent:
		titlemessage = "Probe 1 Setpoint Achieved"
		bodymessage = "Probe 1 setpoint of " + str(control['setpoints']['probe1']) + unit + " achieved at " + str(
			time) + " on " + str(day)
		channel = 'pifire_temp_alerts'
	elif "Probe2_Temp_Achieved" in notifyevent:
		titlemessage = "Probe 2 Setpoint Achieved"
		bodymessage = "Probe 2 setpoint of " + str(control['setpoints']['probe2']) + unit + " achieved at " + str(
			time) + " on " + str(day)
		channel = 'pifire_temp_alerts'
	elif "Timer_Expired" in notifyevent:
		titlemessage = "Grill Timer Complete"
		bodymessage = "Your grill timer has expired, time to check your cook!"
		channel = 'pifire_timer_alerts'
	elif "Pellet_Level_Low" in notifyevent:
		titlemessage = "Low Pellet Level"
		bodymessage = "Your pellet level is currently at " + str(pelletdb['current']['hopper_level']) + "%"
		channel = 'pifire_pellet_alerts'
	elif "Grill_Error_00" in notifyevent:
		titlemessage = "Grill Error!"
		bodymessage = "Your grill has experienced an error and will shutdown now. " + str(now)
		channel = 'pifire_error_alerts'
	elif "Grill_Error_01" in notifyevent:
		titlemessage = "Grill Error!"
		bodymessage = "Grill exceded maximum temperature limit of " + str(
			settings['safety']['maxtemp']) + unit + "! Shutting down. " + str(now)
		channel = 'pifire_error_alerts'
	elif "Grill_Error_02" in notifyevent:
		titlemessage = "Grill Error!"
		bodymessage = "Grill temperature dropped below minimum startup temperature of " + str(
			control['safety']['startuptemp']) + unit + "! Shutting down to prevent firepot overload. " + str(now)
		channel = 'pifire_error_alerts'
	elif "Grill_Warning" in notifyevent:
		titlemessage = "Grill Warning!"
		bodymessage = "Your grill has experienced a warning condition. Please check the logs. "  + str(now)
		channel = 'pifire_error_alerts'
	else:
		titlemessage = "PiFire: Unknown Notification issue"
		bodymessage = "Whoops! PiFire had the following unhandled notify event: " + notifyevent + " at " + str(now)
		channel = 'default'

	app_id = settings['onesignal']['app_id']
	devices = settings['onesignal']['devices']
	player_ids = []

	for key in devices.keys():
		player_ids.append(key)

	if player_ids:
		headers = {"Content-Type": "application/json; charset=utf-8"}
		payload = {"app_id": app_id,
				   "include_player_ids": player_ids,
				   "headings": {"en": titlemessage},
				   "contents": {"en": bodymessage},
				   "priority": 10,
				   "existing_android_channel_id": channel,
				   "ttl" : 3600 }

		response = requests.post("https://onesignal.com/api/v1/notifications", headers=headers, data=json.dumps(payload))

		if response.status_code == 200:
			WriteLog("OneSignal Notification Success: " + titlemessage)
		else:
			WriteLog("OneSignal Notification Failed: " + titlemessage)

		json_response = response.json()
		if 'errors' in json_response:
			if 'invalid_player_ids' in json_response['errors']:
				for device in json_response['errors']['invalid_player_ids']:
					if device in settings['onesignal']['devices']:
						WriteLog("OneSignal: " + settings['onesignal']['devices'][device]['device_name'] +
								 " has an invalid id and has been removed")
						settings['onesignal']['devices'].pop(device)
						WriteSettings(settings)
	else:
		WriteLog("OneSignal Notification Failed No Devices Registered")

# ******************************
# Send IFTTT Notifications
# ******************************

def SendIFTTTNotification(notifyevent, control, settings, pelletdb):
	if "Grill_Temp_Achieved" in notifyevent:
		query_args = {"value1": str(control['setpoints']['grill'])}
	elif "Probe1_Temp_Achieved" in notifyevent:
		query_args = {"value1": str(control['setpoints']['probe1'])}
	elif "Probe2_Temp_Achieved" in notifyevent:
		query_args = {"value1": str(control['setpoints']['probe2'])}
	elif "Timer_Expired" in notifyevent:
		query_args = {"value1": 'Your grill timer has expired.'}
	elif "Pellet_Level_Low" in notifyevent:
		query_args = {"value1": 'Pellet level currently at ' + str(pelletdb['current']['hopper_level']) + '%'}
	elif "Grill_Error_00" in notifyevent:
		query_args = {"value1": 'Your grill has experienced an error and will shutdown now. '}
	elif "Grill_Error_01" in notifyevent:
		query_args = {"value1": str(settings['safety']['maxtemp'])}
	elif "Grill_Error_02" in notifyevent:
		query_args = {"value1": str(control['safety']['startuptemp'])}
	elif "Grill_Warning" in notifyevent:
		query_args = {"value1": 'General Warning.'}
	else:
		WriteLog("IFTTT Notification Failed: Unhandled notify event.")
		return ()

	key = settings['ifttt']['APIKey']
	url = 'https://maker.ifttt.com/trigger/' + notifyevent + '/with/key/' + key

	try:
		r = requests.post(url, data=query_args)
		WriteLog("IFTTT Notification Success: " + r.text)
	except:
		WriteLog("IFTTT Notification Failed: " + url)


# ******************************
# Send influxdb Notifications
# ******************************


influx_handler = None


def SendInfluxDbNotification(notifyevent, control, settings, pelletdb, in_data, grill_platform):
	global influx_handler
	if not influx_handler:
		from notification_handlers import InfluxNotificationHandler
		influx_handler = InfluxNotificationHandler(settings)
	influx_handler.notify(notifyevent, control, settings, pelletdb, in_data, grill_platform)


# ******************************
# Send Notifications
# ******************************

def SendNotifications(notifyevent, control, settings, pelletdb, in_data=None, grill_platform=None):
	if notifyevent != 'GRILL_STATE':
		if settings['ifttt']['APIKey'] != '' and settings['ifttt']['enabled'] == True:
			SendIFTTTNotification(notifyevent, control, settings, pelletdb)
		if settings['pushbullet']['APIKey'] != '' and settings['pushbullet']['enabled'] == True:
			SendPushBulletNotification(notifyevent, control, settings, pelletdb)
		if (settings['pushover']['APIKey'] != '' and settings['pushover']['UserKeys'] != '' and settings['pushover'][
			'enabled'] == True):
			SendPushoverNotification(notifyevent, control, settings, pelletdb)
		if settings['onesignal']['app_id'] != '' and settings['onesignal']['enabled'] == True:
			SendOneSignalNotification(notifyevent, control, settings, pelletdb)
	else:
		if settings['influxdb']['url'] != '' and settings['influxdb']['enabled']:
			SendInfluxDbNotification(notifyevent, control, settings, pelletdb, in_data, grill_platform)

# ******************************
# Check for any pending notifications
# ******************************

def CheckNotify(in_data, control, settings, pelletdb, grill_platform):
	if settings['influxdb']['url'] != '' and settings['influxdb']['enabled']:
		SendNotifications('GRILL_STATE', control, settings, pelletdb, in_data, grill_platform)

	if control['notify_req']['grill']:
		if in_data['GrillTemp'] >= control['setpoints']['grill']:
			# control = ReadControl()  # Read Modify Write
			control['notify_req']['grill'] = False
			WriteControl(control)
			SendNotifications("Grill_Temp_Achieved", control, settings, pelletdb)
			notify_event = "Grill Temp of " + str(control['setpoints']['grill']) + settings['globals'][
				'units'] + " Achieved"
			WriteLog(notify_event)

	if control['notify_req']['probe1']:
		if in_data['Probe1Temp'] >= control['setpoints']['probe1']:
			SendNotifications("Probe1_Temp_Achieved", control, settings, pelletdb)
			# control = ReadControl()  # Read Modify Write
			control['notify_req']['probe1'] = False
			if (control['notify_data']['p1_shutdown'] == True) and (
					(control['mode'] == 'Smoke') or (control['mode'] == 'Hold') or (control['mode'] == 'Startup') or (
					control['mode'] == 'Reignite')):
				control['mode'] = 'Shutdown'
				control['updated'] = True
			if (control['notify_data']['p1_keep_warm'] == True) and (
					(control['mode'] == 'Smoke') or (control['mode'] == 'Hold')):
				control['mode'] = 'Hold'
				control['setpoints']['grill'] = settings['keep_warm']['temp']
				control['s_plus'] = settings['keep_warm']['s_plus']
				control['updated'] = True
			control['notify_data']['p1_shutdown'] = False
			control['notify_data']['p1_keep_warm'] = False
			WriteControl(control)
			notify_event = "Probe 1 Temp of " + str(control['setpoints']['probe1']) + settings['globals'][
				'units'] + " Achieved"
			WriteLog(notify_event)

	if control['notify_req']['probe2']:
		if in_data['Probe2Temp'] >= control['setpoints']['probe2']:
			SendNotifications("Probe2_Temp_Achieved", control, settings, pelletdb)
			# control = ReadControl()  # Read Modify Write
			control['notify_req']['probe2'] = False
			if (control['notify_data']['p2_shutdown'] == True) and (
					(control['mode'] == 'Smoke') or (control['mode'] == 'Hold') or (control['mode'] == 'Startup') or (
					control['mode'] == 'Reignite')):
				control['mode'] = 'Shutdown'
				control['updated'] = True
			if (control['notify_data']['p2_keep_warm'] == True) and (
					(control['mode'] == 'Smoke') or (control['mode'] == 'Hold')):
				control['mode'] = 'Hold'
				control['setpoints']['grill'] = settings['keep_warm']['temp']
				control['s_plus'] = settings['keep_warm']['s_plus']
				control['updated'] = True
			control['notify_data']['p2_shutdown'] = False
			control['notify_data']['p2_keep_warm'] = False
			WriteControl(control)
			notify_event = "Probe 2 Temp of " + str(control['setpoints']['probe2']) + settings['globals'][
				'units'] + " Achieved"
			WriteLog(notify_event)

	if control['notify_req']['timer']:
		if time.time() >= control['timer']['end']:
			SendNotifications("Timer_Expired", control, settings, pelletdb)
			# control = ReadControl()  # Read Modify Write
			if (control['notify_data']['timer_shutdown'] == True) and (
					(control['mode'] == 'Smoke') or (control['mode'] == 'Hold') or (control['mode'] == 'Startup') or (
					control['mode'] == 'Reignite')):
				control['mode'] = 'Shutdown'
				control['updated'] = True
			if (control['notify_data']['timer_keep_warm'] == True) and (
					(control['mode'] == 'Smoke') or (control['mode'] == 'Hold')):
				control['mode'] = 'Hold'
				control['setpoints']['grill'] = settings['keep_warm']['temp']
				control['s_plus'] = settings['keep_warm']['s_plus']
				control['updated'] = True
			control['notify_req']['timer'] = False
			control['timer']['start'] = 0
			control['timer']['paused'] = 0
			control['timer']['end'] = 0
			control['notify_data']['timer_shutdown'] = False
			control['notify_data']['timer_keep_warm'] = False
			WriteControl(control)

	return control


# ******************************
# Check for any pending pellet notifications
# ******************************

def CheckNotifyPellets(control, settings, pelletdb):
	if settings['pelletlevel']['warning_enabled']:
		if pelletdb['current']['hopper_level'] <= settings['pelletlevel']['warning_level']:
			SendNotifications("Pellet_Level_Low", control, settings, pelletdb)


# *****************************************
# Main Program Start / Init
# *****************************************
event = 'Control Script Starting Up.'
WriteLog(event)

# *****************************************
# Main Program Loop
# *****************************************

while True:

	# Check the On/Off switch for changes
	if last != grill_platform.GetInputStatus():
		last = grill_platform.GetInputStatus()
		if last == 1:
			event = 'Switch set to off, going to stop mode.'
			WriteLog(event)
			# control = ReadControl()  # Read Modify Write
			control['updated'] = True  # Change mode
			control['mode'] == 'Stop'
			WriteControl(control)

	#display_device.EventDetect()

	# 1. Check control.json for commands
	control = ReadControl()

	# Check if there is a timer running, see if it has expired, send notification and reset
	if control['notify_req']['timer']:
		if time.time() >= control['timer']['end']:
			SendNotifications("Timer_Expired", control, settings, pelletdb)
			control['notify_req']['timer'] = False
			control['timer']['start'] = 0
			control['timer']['paused'] = 0
			control['timer']['end'] = 0
			control['notify_data']['timer_shutdown'] = False
			control['notify_data']['timer_keep_warm'] = False
			WriteControl(control)

	if control['hopper_check']:
		pelletdb = ReadPelletDB()
		# Get current hopper level and save it to the current pellet information
		pelletdb['current']['hopper_level'] = dist_device.GetLevel()
		WritePelletDB(pelletdb)
		if settings['globals']['debug_mode']:
			event = "* Hopper Level Checked @ " + str(pelletdb['current']['hopper_level']) + "%"
			print(event)
			WriteLog(event)
		# control = ReadControl()  # Read Modify Write
		control['hopper_check'] = False
		WriteControl(control)

	if control['updated']:
		if settings['globals']['debug_mode']:
			event = "* Updated Flag Captured."
			print(event)
			WriteLog(event)
		# Clear control flag
		control['updated'] = False  # Reset Control Updated to False to acknowledge
		WriteControl(control)  # Commit change in 'updated' status to the file

		if control['units_change']:
			if settings['globals']['debug_mode']:
				event = "Changing Base Units."
				print(event)
				WriteLog(event)
			settings = ReadSettings()
			# Update ADC object and set profiles
			adc_device.update_units(settings['globals']['units'])
			control['mode'] = 'Stop'  # Stop any activity
			control['units_change'] = False
			ReadHistory(0, flushhistory=True)  # Clear history data

		# Check if there was an Error flagged in Monitor Mode - If no, then change status to active
		if (control['status'] != 'monitor') and (control['mode'] != 'Error'):
			control['status'] = 'active'  # Set status to active
			WriteControl(control)

		if (control['mode'] == 'Stop') or (control['mode'] == 'Error'):
			grill_platform.AugerOff()
			grill_platform.IgniterOff()
			grill_platform.FanOff()
			# Register Stop Mode in Metrics DB if this is not initial stop-mode on startup (i.e. DB is empty)
			metrics_list = ReadMetrics(all=True)
			if(len(metrics_list) != 0):
				WriteMetrics(new_metric=True)
				metrics = ReadMetrics()
				metrics['mode'] = 'Stop'
				WriteMetrics(metrics)

			if (control['status'] == 'monitor') and (control['mode'] == 'Error'):
				grill_platform.PowerOn()
			else:
				grill_platform.PowerOff()
			if control['mode'] == 'Stop':
				display_device.clear_display()  # When in error mode, leave the display showing ERROR
				control['status'] = 'inactive'
				event = "Stop Mode Started."
				# Reset Control to Defaults
				control = ReadControl(flush=True)
				control['updated'] = False
				control['tuning_mode'] = False  # Turn off Tuning Mode on Stop just in case it is on
				WriteControl(control)
			else:
				event = "ERROR: An error has occured, Stop Mode enabled."
				# Reset Control to Defaults but preserve 'Error' mode condition
				control = DefaultControl()
				control['mode'] = 'Error'
				control['status'] = 'inactive'
				control['tuning_mode'] = False  # Turn off Tuning Mode on Stop just in case it is on
				control['updated'] = False
				WriteControl(control)

			ReadCurrent(zero_out=True)  # Zero out the current values

			WriteLog(event)

		# Startup (startup sequence)
		elif control['mode'] == 'Startup':
			if grill_platform.GetInputStatus() == 1:
				event = "Warning: PiFire is set to OFF. This doesn't prevent startup, but this means the switch won't behave as normal."
				WriteLog(event)
			settings = ReadSettings()
			if settings['history_page']['clearhistoryonstart']:
				if settings['globals']['debug_mode']:
					event = '* Clearing History and Current Log on Startup Mode.'
					print(event)
					WriteLog(event)
				ReadHistory(0, flushhistory=True)  # Clear all history
			WorkCycle('Startup', grill_platform, adc_device, display_device, dist_device)
			control = ReadControl()
			# If mode is Startup, then assume you can transition into smoke mode
			if control['mode'] == 'Startup':
				control['mode'] = 'Smoke'  # Set status to active
				WriteControl(control)
				WorkCycle('Smoke', grill_platform, adc_device, display_device, dist_device)
		# Smoke (smoke cycle)
		elif control['mode'] == 'Smoke':
			WorkCycle('Smoke', grill_platform, adc_device, display_device, dist_device)
		# Hold (hold at setpoint)
		elif control['mode'] == 'Hold':
			WorkCycle('Hold', grill_platform, adc_device, display_device, dist_device)
		# Shutdown (shutdown sequence)
		elif control['mode'] == 'Shutdown':
			WorkCycle('Shutdown', grill_platform, adc_device, display_device, dist_device)
			control = ReadControl()
			if control['mode'] == 'Shutdown':
				control['mode'] = 'Stop'  # Set mode to Stop
				control['updated'] = True
				WriteControl(control)
				if settings['globals']['auto_power_off']:
					WriteLog('Shutdown mode ended powering off grill')
					os.system("sleep 3 && sudo shutdown -h now &")
		# e. Monitor (monitor the OEM controller)
		elif control['mode'] == 'Monitor':
			control['status'] = 'monitor'  # Set status to monitor
			WriteControl(control)
			Monitor(grill_platform, adc_device, display_device, dist_device)
		elif control['mode'] == 'Manual':
			Manual_Mode(grill_platform, adc_device, display_device, dist_device)
		elif control['mode'] == 'Recipe':
			Recipe_Mode(grill_platform, adc_device, display_device, dist_device)
		# Reignite (reignite sequence)
		elif control['mode'] == 'Reignite':
			if grill_platform.GetInputStatus() == 1:
				event = "Warning: PiFire is set to OFF. This doesn't prevent reignite, but this means the switch won't behave as normal."
				WriteLog(event)
			WorkCycle('Reignite', grill_platform, adc_device, display_device, dist_device)
			control = ReadControl()
			lastmode = control['safety']['reignitelaststate']
			if lastmode == 'Hold':
				control['mode'] = 'Hold'  # Set status to active
			else:
				control['mode'] = 'Smoke'  # Set status to active
			WriteControl(control)
			WorkCycle(control['mode'], grill_platform, adc_device, display_device, dist_device)

	time.sleep(0.1)
# ===================
# End of Main Loop
# ===================
