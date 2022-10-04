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

# Prototype Mode is now selected through the setup wizard or by running 'bash modules.sh' from the command prompt

# *****************************************
# Base Imported Libraries
# *****************************************
import importlib
import pid  # Library for calculating PID setpoints
from common import *  # Common Library for WebUI and Control Program
from notifications import *
from temp_queue import TempQueue

'''
Read and initialize Settings, Control, History, Metrics, and Error Data
'''
# Read Settings & Wizard Manifest to Get Modules Configuration 
settings = read_settings()
wizard_data = read_wizard()

# Flush Redis DB and create JSON structure
control = read_control(flush=True)
# Delete Redis DB for history / current
read_history(0, flushhistory=True)
# Flush metrics DB for tracking certain metrics
write_metrics(flush=True)
# Create errors log 
errors = read_errors(flush=True)

write_event(settings, 'Flushing Redis DB and creating new control structure')

'''
Set up GrillPlatform Module
'''
try: 
	grill_platform = settings['modules']['grillplat']
	filename = 'grillplat_' + wizard_data['modules']['grillplatform'][grill_platform]['filename']
	GrillPlatModule = importlib.import_module(filename)

except:
	GrillPlatModule = importlib.import_module('grillplat_prototype')
	error_event = f'An error occurred loading the [{settings["modules"]["grillplat"]}] platform module.  The ' \
		f'prototype module has been loaded instead.  This sometimes means that the hardware is not connected ' \
		f'properly, or the module is not configured.  Please run the configuration wizard again from the admin ' \
		f'panel to fix this issue.'
	errors.append(error_event)
	write_errors(errors)
	write_event(settings, error_event)
	if settings['globals']['debug_mode']:
		raise

out_pins = settings['outpins']
in_pins = settings['inpins']
trigger_level = settings['globals']['triggerlevel']
buttons_level = settings['globals']['buttonslevel']
dc_fan = settings['globals']['dc_fan']
frequency = settings['pwm']['frequency']
standalone = settings['globals']['standalone']
disp_rotation = settings['globals']['disp_rotation']
units = settings['globals']['units']
dev_pins = settings['dev_pins']

try:
	if dc_fan:
		grill_platform = GrillPlatModule.GrillPlatform(out_pins, in_pins, trigger_level, dc_fan, frequency)
	else:
		grill_platform = GrillPlatModule.GrillPlatform(out_pins, in_pins, trigger_level)
except:
	from grillplat_prototype import GrillPlatform  # Simulated Library for controlling the grill platform
	grill_platform = GrillPlatform(out_pins, in_pins, trigger_level)
	error_event = f'An error occurred configuring the [{settings["modules"]["grillplat"]}] platform object.  The ' \
		f'prototype module has been loaded instead.  This sometimes means that the hardware is not ' \
		f'connected properly, or the module is not configured.  Please run the configuration wizard ' \
		f'again from the admin panel to fix this issue.'
	errors.append(error_event)
	write_errors(errors)
	write_event(settings, error_event)
	if settings['globals']['debug_mode']:
		raise

'''
Set up Probes Input (ADC) Module
'''
try: 
	probes_input = settings['modules']['adc']
	filename = 'adc_' + wizard_data['modules']['probes'][probes_input]['filename']
	ProbesModule = importlib.import_module(filename)

except:
	ProbesModule = importlib.import_module('adc_prototype')
	error_event = f'An error occurred loading the [{settings["modules"]["adc"]}] probes module.  The prototype ' \
		f'module has been loaded instead.  This sometimes means that the hardware is not connected ' \
		f'properly, or the module is not configured.  Please run the configuration wizard again from ' \
		f'the admin panel to fix this issue.'
	errors.append(error_event)
	write_errors(errors)
	write_event(settings, error_event)
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
	
	error_event = f'An error occurred configuring the [{settings["modules"]["adc"]}] probes object.  The prototype' \
		f' module has been loaded instead.  This sometimes means that the hardware is not connected ' \
		f'properly, or the module is not configured.  Please run the configuration wizard again from ' \
		f'the admin panel to fix this issue.'
	errors.append(error_event)
	write_errors(errors)
	write_event(settings, error_event)
	if settings['globals']['debug_mode']:
		raise

for probe_source in settings['probe_settings']['probe_sources']:
	# if any of the probes uses max31865 then load the library
	if 'max31865' in probe_source:
		from adc_max31865 import probe_max31865_read
		break

'''
Set up Display Module
'''
try: 
	display_name = settings['modules']['display']
	filename = 'display_' + wizard_data['modules']['display'][display_name]['filename']
	DisplayModule = importlib.import_module(filename)

except:
	DisplayModule = importlib.import_module('display_none')
	error_event = f'An error occurred loading the [{settings["modules"]["display"]}] display module.  The ' \
		f'"display_none" module has been loaded instead.  This sometimes means that the hardware is ' \
		f'not connected properly, or the module is not configured.  Please run the configuration wizard ' \
		f'again from the admin panel to fix this issue.'
	errors.append(error_event)
	write_errors(errors)
	write_event(settings, error_event)
	if settings['globals']['debug_mode']:
		raise

try:
	display_device = DisplayModule.Display(dev_pins=dev_pins, buttonslevel=buttons_level,
										   rotation=disp_rotation, units=units)
except:
	from display_none import Display  # Simulated Library for controlling the grill platform
	display_device = Display(dev_pins=dev_pins, buttonslevel=buttons_level, rotation=disp_rotation, units=units)
	error_event = f'An error occurred configuring the [{settings["modules"]["display"]}] display object.  The ' \
		f'"display_none" module has been loaded instead.  This sometimes means that the hardware is ' \
		f'not connected properly, or the module is not configured.  Please run the configuration wizard ' \
		f'again from the admin panel to fix this issue.'
	errors.append(error_event)
	write_errors(errors)
	write_event(settings, error_event)
	if settings['globals']['debug_mode']:
		raise

'''
Set up Distance (Hopper Level) Module
'''
try: 
	dist_name = settings['modules']['dist']
	filename = 'distance_' + wizard_data['modules']['distance'][dist_name]['filename']
	DistanceModule = importlib.import_module(filename)

except:
	DistanceModule = importlib.import_module('distance_prototype')
	error_event = f'An error occurred loading the [{settings["modules"]["dist"]}] distance module.  The prototype ' \
		f'module has been loaded instead.  This sometimes means that the hardware is not connected ' \
		f'properly, or the module is not configured.  Please run the configuration wizard again from the ' \
		f'admin panel to fix this issue.'
	errors.append(error_event)
	write_errors(errors)
	write_event(settings, error_event)
	if settings['globals']['debug_mode']:
		raise

try:
	if settings['modules']['grillplat'] == 'prototype' and settings['modules']['dist'] == 'prototype':
		# If in prototype mode, enable test reading (i.e. random values from proto distance sensor)
		dist_device = DistanceModule.HopperLevel(
			dev_pins=dev_pins, empty=settings['pelletlevel']['empty'], full=settings['pelletlevel']['full'],
			debug=settings['globals']['debug_mode'], random=True)
	else:
		dist_device = DistanceModule.HopperLevel(
			dev_pins=dev_pins, empty=settings['pelletlevel']['empty'], full=settings['pelletlevel']['full'],
			debug=settings['globals']['debug_mode'])
except:
	from distance_prototype import HopperLevel  # Simulated Library for controlling the grill platform
	dist_device = HopperLevel(
		dev_pins=dev_pins, empty=settings['pelletlevel']['empty'], full=settings['pelletlevel']['full'],
		debug=settings['globals']['debug_mode'])
	error_event = f'An error occurred configuring the [{settings["modules"]["dist"]}] distance object.  The ' \
		f'prototype module has been loaded instead.  This sometimes means that the hardware is not ' \
		f'connected properly, or the module is not configured.  Please run the configuration wizard again ' \
		f'from the admin panel to fix this issue.'
	errors.append(error_event)
	write_errors(errors)
	write_event(settings, error_event)
	if settings['globals']['debug_mode']:
		raise

# Get current hopper level and save it to the current pellet information
pelletdb = read_pellet_db()
pelletdb['current']['hopper_level'] = dist_device.get_level()
write_pellet_db(pelletdb)
write_event(settings, "* Hopper Level Checked @ " + str(pelletdb['current']['hopper_level']) + "%")

# *****************************************
# Function Definitions
# *****************************************
def _read_probes(settings, adc_device, units):
	"""
	Read Probes from ADC and/or max31865

	:param settings: Settings
	:param adc_device: ADC Device
	:param units: Units C or F
	:return: probe_data
	"""
	adc_data = adc_device.read_all_ports()

	probe_data = {}

	probe_ids = ['Grill1', 'Probe1', 'Probe2', 'Grill2']
	adc_properties = ['Temp', 'Tr']
	adc_probe_indices = ['Grill1', 'Probe1', 'Probe2', 'Grill2']
	for idx, probe_source in enumerate(settings['probe_settings']['probe_sources']):
		if 'ADC' in probe_source and len(probe_source) > 3:
			# Map ADC probes to the output probes. i.e. ADC0 is adc_probe_indices[0] => 'Grill' so if this is
			# defined for first source map Grill to Grill. If ADC1 in first source map it to Probe1
			source_index = int(probe_source[3:])
			for p in adc_properties:
				probe_data[probe_ids[idx] + p] = adc_data[adc_probe_indices[source_index] + p]
		elif 'max31865' in probe_source:
			temperature, resistance = probe_max31865_read(units=units)
			probe_data[probe_ids[idx] + adc_properties[0]] = temperature
			probe_data[probe_ids[idx] + adc_properties[1]] = resistance

	return probe_data


def _get_status(grill_platform, control, settings, pelletdb):
	"""
	Get Status Details for Display Function

	:param grill_platform: Grill Platform
	:param control: Control
	:param settings: Settings
	:param pelletdb: Pellet DB
	:return: status_data
	"""
	status_data = {}
	status_data['outpins'] = {}

	current = grill_platform.get_output_status()  # Get current pin settings

	for item in settings['outpins']:
		try:
			status_data['outpins'][item] = current[item]
		except KeyError:
			continue

	status_data['mode'] = control['mode']  # Get current mode
	status_data['notify_req'] = control['notify_req']  # Get any flagged notifications
	status_data['timer'] = control['timer']  # Get the timer information
	status_data['ipaddress'] = '192.168.10.43'  # Future implementation (TODO)
	status_data['s_plus'] = control['s_plus']
	status_data['hopper_level'] = pelletdb['current']['hopper_level']
	status_data['units'] = settings['globals']['units']

	return (status_data)

def _start_fan(settings, duty_cycle=None):
	"""
	Check for DC Fan and set duty cycle when turning ON otherwise turn AC fan ON normally.

	:param settings: Settings
	:param duty_cycle: Duty Cycle to set. If not provided will be set to max_duty_cycle (dc_fan only)
	"""
	if dc_fan:
		if duty_cycle is not None:
			adjusted_dc = max(duty_cycle, settings['pwm']['min_duty_cycle'])
			adjusted_dc = min(adjusted_dc, settings['pwm']['max_duty_cycle'])
		else:
			adjusted_dc = settings['pwm']['max_duty_cycle']
		grill_platform.fan_on(adjusted_dc)
	else:
		grill_platform.fan_on()


def _work_cycle(mode, grill_platform, adc_device, display_device, dist_device):
	"""
	Work Cycle Function

	:param mode: Requested Mode
	:param grill_platform: Grill Platform
	:param adc_device: ADC Device
	:param display_device: Display Device
	:param dist_device: Distance Device
	"""

	# Setup Cycle Parameters
	settings = read_settings()
	control = read_control()
	pelletdb = read_pellet_db()

	write_event(settings, mode + ' Mode started.')

	# Get ON/OFF Switch state and set as last state
	last = grill_platform.get_input_status()

	# Set DC fan frequency if it has changed since init
	if dc_fan:
		pwm_frequency = settings['pwm']['frequency']
		status_data = grill_platform.get_output_status()
		if not pwm_frequency == status_data['frequency']:
			grill_platform.set_pwm_frequency(pwm_frequency)

	# Set Starting Configuration for Igniter, Fan , Auger
	grill_platform.igniter_off()
	grill_platform.auger_off()

	if mode in ('Startup', 'Reignite', 'Smoke', 'Hold', 'Shutdown'):
		_start_fan(settings)
		grill_platform.power_on()
		write_event(settings, '* Power ON, Fan ON, Igniter OFF, Auger OFF')
	else: # (Monitor, Manual)
		grill_platform.fan_off()
		grill_platform.power_off()
		write_event(settings, '* Power OFF, Fan OFF, Igniter OFF, Auger OFF')

	write_metrics(new_metric=True)
	metrics = read_metrics()
	metrics['mode'] = str(control['mode'])
	metrics['smokeplus'] = control['s_plus'] 
	metrics['grill_settemp'] = control['setpoints']['grill']
	metrics['pellet_level_start'] = pelletdb['current']['hopper_level']
	current_pellet_id = pelletdb['current']['pelletid']
	pellet_brand = pelletdb['archive'][current_pellet_id]['brand']
	pellet_type = pelletdb['archive'][current_pellet_id]['wood']
	metrics['pellet_brand_type'] = f'{pellet_brand} {pellet_type}'
	write_metrics(metrics)

	if mode in ('Startup', 'Reignite'):
		grill_platform.igniter_on()
		write_event(settings, '* Igniter ON')
	if mode in ('Startup', 'Reignite', 'Smoke', 'Hold'):
		grill_platform.auger_on()
		write_event(settings, '* Auger ON')

	if mode in ('Startup', 'Reignite', 'Smoke'):
		OnTime = settings['cycle_data']['SmokeCycleTime']  # Auger On Time (Default 15s)
		OffTime = 45 + (settings['cycle_data']['PMode'] * 10)  # Auger Off Time
		CycleTime = OnTime + OffTime  # Total Cycle Time
		CycleRatio = OnTime / CycleTime  # Ratio of OnTime to CycleTime
		# Write Metrics (note these will be overwritten if smart start is enabled)
		metrics['p_mode'] = settings['cycle_data']['PMode']
		metrics['auger_cycle_time'] = settings['cycle_data']['SmokeCycleTime']
		write_metrics(metrics)

	if mode == 'Hold':
		OnTime = settings['cycle_data']['HoldCycleTime'] * settings['cycle_data']['u_min']  # Auger On Time
		OffTime = settings['cycle_data']['HoldCycleTime'] * (1 - settings['cycle_data']['u_min'])  # Auger Off Time
		CycleTime = settings['cycle_data']['HoldCycleTime']  # Total Cycle Time
		CycleRatio = settings['cycle_data']['u_min']  # Ratio of OnTime to CycleTime
		PIDControl = pid.PID(settings['cycle_data']['PB'], settings['cycle_data']['Ti'], settings['cycle_data']['Td'],
							 settings['cycle_data']['center'])
		PIDControl.set_target(control['setpoints']['grill'])  # Initialize with setpoint for grill
		write_event(settings, '* On Time = ' + str(OnTime) + ', OffTime = ' + str(OffTime) + ', CycleTime = ' + str(
			CycleTime) + ', CycleRatio = ' + str(CycleRatio))


	# Initialize all temperature variables
	AvgGT = TempQueue(units=settings['globals']['units'])
	AvgP1 = TempQueue(units=settings['globals']['units'])
	AvgP2 = TempQueue(units=settings['globals']['units'])

	# Check pellets level notification upon starting cycle
	check_notify_pellets(control, settings, pelletdb)

	# Collect Initial Temperature Information
	# Get Probe Types From Settings
	grill1type = settings['probe_types']['grill1type']
	grill2type = settings['probe_types']['grill2type']
	probe1type = settings['probe_types']['probe1type']
	probe2type = settings['probe_types']['probe2type']

	adc_device.set_profiles(settings['probe_settings']['probe_profiles'][grill1type],
						   settings['probe_settings']['probe_profiles'][grill2type],
						   settings['probe_settings']['probe_profiles'][probe1type],
						   settings['probe_settings']['probe_profiles'][probe2type])

	adc_data = _read_probes(settings, adc_device, units)

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
	if mode in ('Startup', 'Reignite'):
		control['safety']['startuptemp'] = int(max((AvgGT.average() * 0.9), settings['safety']['minstartuptemp']))
		control['safety']['startuptemp'] = int(
			min(control['safety']['startuptemp'], settings['safety']['maxstartuptemp']))
		control['safety']['afterstarttemp'] = AvgGT.average()
		write_control(control)
	# Check if the temperature of the grill dropped below the startuptemp
	elif mode in ('Smoke', 'Hold'):
		if control['safety']['afterstarttemp'] < control['safety']['startuptemp']:
			if control['safety']['reigniteretries'] == 0:
				status = 'Inactive'
				display_device.display_text('ERROR')
				control['mode'] = 'Error'
				control['updated'] = True
				write_control(control)
				send_notifications("Grill_Error_02", control, settings, pelletdb)
			else:
				control['safety']['reigniteretries'] -= 1
				control['safety']['reignitelaststate'] = mode
				status = 'Inactive'
				display_device.display_text('Re-Ignite')
				control['mode'] = 'Reignite'
				control['updated'] = True
				write_control(control)
				send_notifications("Grill_Error_03", control, settings, pelletdb)

	# Apply Smart Start Settings if Enabled 
	startup_timer = settings['globals']['startup_timer']
	if settings['smartstart']['enabled'] and mode in ('Startup', 'Reignite', 'Smoke'):
		# If Startup, then save initial temperature & select the profile
		if mode in ('Startup', 'Reignite'):
			control['smartstart']['startuptemp'] = int(AvgGT.average())
			# Cycle through profiles, and set profile if startup temperature falls below the minimum temperature
			for profile_selected in range(0, len(settings['smartstart']['temp_range_list'])):
				if control['smartstart']['startuptemp'] < settings['smartstart']['temp_range_list'][profile_selected]:
					control['smartstart']['profile_selected'] = profile_selected
					write_control(control)
					break  # Break out of the loop
				if profile_selected == len(settings['smartstart']['temp_range_list']) - 1:
					control['smartstart']['profile_selected'] = profile_selected + 1
					write_control(control)
		# Apply the profile 
		profile_selected = control['smartstart']['profile_selected']
		OnTime = settings['smartstart']['profiles'][profile_selected]['augerontime']  # Auger On Time (Default 15s)
		OffTime = 45 + (settings['smartstart']['profiles'][profile_selected]['p_mode'] * 10)  # Auger Off Time
		CycleTime = OnTime + OffTime  # Total Cycle Time
		CycleRatio = OnTime / CycleTime  # Ratio of OnTime to CycleTime
		startup_timer = settings['smartstart']['profiles'][profile_selected]['startuptime']
		# Write Metrics
		metrics['smart_start_profile'] = profile_selected
		metrics['startup_temp'] = control['smartstart']['startuptemp']
		metrics['p_mode'] = settings['smartstart']['profiles'][profile_selected]['p_mode']
		metrics['auger_cycle_time'] = settings['smartstart']['profiles'][profile_selected]['augerontime']
		write_metrics(metrics)

	# Set the start time
	start_time = time.time()

	# Set time since toggle for temperature
	temp_toggle_time = start_time

	# Set time since toggle for auger
	auger_toggle_time = start_time

	# Set time since toggle for display
	display_toggle_time = start_time

	# Initializing Start Time for Smoke Plus Mode
	sp_cycle_toggle_time = start_time

	# Set time since toggle for hopper check
	hopper_toggle_time = start_time

	# Set time since last control check
	control_check_time = start_time

	# Set time since last pellet level check
	pellets_check_time = start_time

	# Set time since fan speed update
	fan_update_time = start_time

	# Set Hold Mode Target Temp Boolean
	target_temp_achieved = False

	# Set Fan Ramping Boolean
	pwm_fan_ramping = False

	# ============ Main Work Cycle ============
	while status == 'Active':
		now = time.time()

		# Check if user changed settings and reload
		if control['settings_update']:
			control['settings_update'] = False
			write_control(control)
			settings = read_settings()

		# Check if user changed hopper levels and update if required
		if control['distance_update']:
			empty = settings['pelletlevel']['empty']
			full = settings['pelletlevel']['full']
			dist_device.update_distances(empty, full)
			control['distance_update'] = False
			write_control(control)

		# Check for update in control status every 0.1 seconds
		if (now - control_check_time) > 0.1:
			control = read_control()
			control_check_time = now

		# Check for pellet level notifications
		if (now - pellets_check_time) > (settings['pelletlevel']['warning_time'] * 60):
			check_notify_pellets(control, settings, pelletdb)
			pellets_check_time = now

		# Check if new mode has been requested
		if control['updated']:
			break

		# Check hopper level when requested or every 300 seconds
		if control['hopper_check'] or (now - hopper_toggle_time) > 300:
			pelletdb = read_pellet_db()
			# Get current hopper level and save it to the current pellet information
			pelletdb['current']['hopper_level'] = dist_device.get_level()			
			write_pellet_db(pelletdb)
			hopper_toggle_time = now
			write_event(settings, "* Hopper Level Checked @ " + str(pelletdb['current']['hopper_level']) + "%")
			if control['hopper_check']:
				control['hopper_check'] = False
				write_control(control)

		# Check for update in ON/OFF Switch
		if not standalone and last != grill_platform.get_input_status():
			last = grill_platform.get_input_status()
			if not last:
				write_event(settings, 'Switch set to off, going to monitor mode.')
				control['updated'] = True  # Change mode
				control['mode'] = 'Stop'
				control['status'] = 'active'
				write_control(control)
				break

		current_output_status = grill_platform.get_output_status()

		if mode == 'Manual':
			if control['manual']['change']:
				if control['manual']['fan'] and not current_output_status['fan']:
					grill_platform.fan_on()
					write_event(settings, '* Fan ON')
				elif not control['manual']['fan'] and current_output_status['fan']:
					grill_platform.fan_off()
					write_event(settings, '* Fan OFF')
				if control['manual']['auger'] and not current_output_status['auger']:
					grill_platform.auger_on()
					write_event(settings, '* Auger ON')
				elif not control['manual']['auger'] and current_output_status['auger']:
					grill_platform.auger_off()
					write_event(settings, '* Auger OFF')
				if control['manual']['igniter'] and not current_output_status['igniter']:
					grill_platform.igniter_on()
					write_event(settings, '* Igniter ON')
				elif not control['manual']['igniter'] and current_output_status['igniter']:
					grill_platform.igniter_off()
					write_event(settings, '* Igniter OFF')
				if control['manual']['power'] and not current_output_status['power']:
					grill_platform.power_on()
					write_event(settings, '* Power ON')
				elif not control['manual']['power'] and current_output_status['power']:
					grill_platform.power_off()
					write_event(settings, '* Power OFF')
				if dc_fan and control['manual']['fan'] and current_output_status['fan'] and \
					not control['manual']['pwm'] == current_output_status['pwm']:
					speed = control['manual']['pwm']
					write_event(settings, '* PWM Speed: ' + str(speed) + '%')
					grill_platform.set_duty_cycle(speed)

				control['manual']['change'] = False
				write_control(control)

		# Change Auger State based on Cycle Time
		if mode in ('Startup', 'Reignite', 'Smoke', 'Hold'):
			# If Auger is OFF and time since toggle is greater than Off Time
			if not current_output_status['auger'] and (now - auger_toggle_time) > (CycleTime * (1 - CycleRatio)):
				grill_platform.auger_on()
				auger_toggle_time = now
				write_event(settings, '* Cycle Event: Auger On')
				# Reset Cycle Time for HOLD Mode
				if mode == 'Hold':
					CycleRatio = PIDControl.update(AvgGT.average())
					CycleRatio = max(CycleRatio, settings['cycle_data']['u_min'])
					CycleRatio = min(CycleRatio, settings['cycle_data']['u_max'])
					OnTime = settings['cycle_data']['HoldCycleTime'] * CycleRatio
					OffTime = settings['cycle_data']['HoldCycleTime'] * (1 - CycleRatio)
					CycleTime = OnTime + OffTime
					write_event(settings, '* On Time = ' + str(OnTime) + ', OffTime = ' + str(
						OffTime) + ', CycleTime = ' + str(CycleTime) + ', CycleRatio = ' + str(CycleRatio))

			# If Auger is ON and time since toggle is greater than On Time
			if current_output_status['auger'] and (now - auger_toggle_time) > (CycleTime * CycleRatio):
				grill_platform.auger_off()
				# Add auger ON time to the metrics
				metrics['augerontime'] += now - auger_toggle_time
				write_metrics(metrics)
				# Set current last toggle time to now
				auger_toggle_time = now
				write_event(settings, '* Cycle Event: Auger Off')

		# Grab current probe profiles if they have changed since the last loop.
		if control['probe_profile_update']:
			settings = read_settings()
			control['probe_profile_update'] = False
			write_control(control)
			# Get new probe profiles
			grill1type = settings['probe_types']['grill1type']
			grill2type = settings['probe_types']['grill2type']
			probe1type = settings['probe_types']['probe1type']
			probe2type = settings['probe_types']['probe2type']
			# Add new probe profiles to ADC Object
			adc_device.set_profiles(settings['probe_settings']['probe_profiles'][grill1type],
								   settings['probe_settings']['probe_profiles'][grill2type],
								   settings['probe_settings']['probe_profiles'][probe1type],
								   settings['probe_settings']['probe_profiles'][probe2type])

		# Get temperatures from all probes
		adc_data = _read_probes(settings, adc_device, units)

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
		in_data['GrillNotifyPoint'] = control['setpoints']['grill_notify']

		if settings['globals']['four_probes']:
			if settings['grill_probe_settings']['grill_probe_enabled'][2] == 1:
				in_data['GrillTr'] = 0 # This is an average of two probes, so it should be disabled for editing.
			elif settings['grill_probe_settings']['grill_probe_enabled'][1] == 1:
				in_data['GrillTr'] = adc_data['Grill2Tr']  # For Temp Resistance Tuning
			else:
				in_data['GrillTr'] = adc_data['Grill1Tr']  # For Temp Resistance Tuning
		else:
			in_data['GrillTr'] = adc_data['Grill1Tr']  # For Temp Resistance Tuning

		in_data['Probe1Tr'] = adc_data['Probe1Tr']  # For Temp Resistance Tuning
		in_data['Probe2Tr'] = adc_data['Probe2Tr']  # For Temp Resistance Tuning

		# Check to see if there are any pending notifications (i.e. Timer / Temperature Settings)
		control = check_notify(in_data, control, settings, pelletdb, grill_platform)

		# Send Current Status / Temperature Data to Display Device every 0.5 second (Display Refresh)
		if (now - display_toggle_time) > 0.5:
			status_data = _get_status(grill_platform, control, settings, pelletdb)
			status_data['start_time'] = start_time
			status_data['start_duration'] = startup_timer
			status_data['shutdown_duration'] = settings['globals']['shutdown_timer']
			display_device.display_status(in_data, status_data)
			display_toggle_time = time.time()  # Reset the display_toggle_time to current time

		# Safety Controls
		if mode in ('Startup', 'Reignite'):
			control['safety']['afterstarttemp'] = AvgGT.average()
		elif mode in ('Smoke', 'Hold'):
			if AvgGT.average() < control['safety']['startuptemp']:
				if control['safety']['reigniteretries'] == 0:
					display_device.display_text('ERROR')
					control['mode'] = 'Error'
					control['updated'] = True
					write_control(control)
					send_notifications("Grill_Error_02", control, settings, pelletdb)
					break
				else:
					control['safety']['reigniteretries'] -= 1
					control['safety']['reignitelaststate'] = mode
					display_device.display_text('Re-Ignite')
					control['mode'] = 'Reignite'
					control['updated'] = True
					write_control(control)
					send_notifications("Grill_Error_03", control, settings, pelletdb)
					break


		if mode in ('Smoke', 'Hold'):
			# Check if target temperature has been achieved before utilizing Smoke Plus Mode
			if mode == 'Hold' and AvgGT.average() >= control['setpoints']['grill'] and not target_temp_achieved:
				target_temp_achieved = True

			# If PWM Fan Control enabled set duty_cycle based on temperature
			if (dc_fan and mode == 'Hold' and control['pwm_control'] and
					(now - fan_update_time) > settings['pwm']['update_time']):
				fan_update_time = now
				if AvgGT.average() > control['setpoints']['grill']:
					control['duty_cycle'] = settings['pwm']['min_duty_cycle']
					write_control(control)
				else:
					# Cycle through profiles, and set duty cycle if setpoint temp is within range
					for temp_profile in range(0, len(settings['pwm']['temp_range_list'])):
						if ((control['setpoints']['grill'] - AvgGT.average()) <=
								settings['pwm']['temp_range_list'][temp_profile]):
							duty_cycle = settings['pwm']['profiles'][temp_profile]['duty_cycle']
							duty_cycle = max(duty_cycle, settings['pwm']['min_duty_cycle'])
							duty_cycle = min(duty_cycle, settings['pwm']['max_duty_cycle'])
							control['duty_cycle'] = duty_cycle
							write_control(control)
							break # Break out of the loop
						if temp_profile == len(settings['pwm']['temp_range_list']) - 1:
							control['duty_cycle'] = settings['pwm']['max_duty_cycle']
							write_control(control)

			# If in Smoke Plus Mode, Cycle the Fan
			if (mode == 'Smoke' or (mode == 'Hold' and target_temp_achieved)) and control['s_plus']:
				# If Temperature is > settings['smoke_plus']['max_temp']
				# or Temperature is < settings['smoke_plus']['min_temp'] then turn on fan
				if (AvgGT.average() > settings['smoke_plus']['max_temp'] or
						AvgGT.average() < settings['smoke_plus']['min_temp']):
					if not current_output_status['fan']:
						_start_fan(settings, control['duty_cycle'])
						write_event(settings, '* Smoke Plus: Over or Under Temp Fan ON')
				elif (now - sp_cycle_toggle_time) > settings['smoke_plus']['on_time'] and current_output_status['fan']:
					grill_platform.fan_off()
					sp_cycle_toggle_time = now
					write_event(settings, '* Smoke Plus: Fan OFF')
				elif ((now - sp_cycle_toggle_time) > settings['smoke_plus']['off_time'] and
					  not current_output_status['fan']):
					sp_cycle_toggle_time = now
					if (dc_fan and (mode == 'Smoke' or (mode == 'Hold' and not control['pwm_control'])) and
							settings['smoke_plus']['fan_ramp']):
						on_time = settings['smoke_plus']['on_time']
						max_duty_cycle = settings['pwm']['max_duty_cycle']
						min_duty_cycle = settings['pwm']['min_duty_cycle']
						sp_duty_cycle = settings['smoke_plus']['duty_cycle']
						grill_platform.pwm_fan_ramp(on_time, min_duty_cycle, max_duty_cycle * (sp_duty_cycle / 100))
						pwm_fan_ramping = True
						write_event(settings, '* Smoke Plus: Fan Ramping Up')
					else:
						_start_fan(settings, control['duty_cycle'])
						write_event(settings, '* Smoke Plus: Fan ON')

			# If Smoke Plus was disabled when fan is OFF return fan to ON
			elif not current_output_status['fan'] and not control['s_plus']:
				_start_fan(settings, control['duty_cycle'])
				write_event(settings, '* Smoke Plus: Fan Returned to On')

			# If Smoke Plus was disabled while fan was ramping return it to the correct duty cycle
			elif (dc_fan and current_output_status['pwm'] != control['duty_cycle'] and not
					control['s_plus'] and pwm_fan_ramping):
				pwm_fan_ramping = False
				grill_platform.set_duty_cycle(control['duty_cycle'])
				write_event(settings, '* Smoke Plus: Fan Returned to ' + str(control['duty_cycle']) + '% duty cycle')

			# Set Fan Duty Cycle based on Average Grill Temp Using Profile
			elif dc_fan and control['pwm_control'] and current_output_status['pwm'] != control['duty_cycle']:
				grill_platform.set_duty_cycle(control['duty_cycle'])
				write_event(settings, '* Temp Fan Control: Fan Set to ' + str(control['duty_cycle']) + '% duty cycle')

			# If PWM Fan Control is turned off check current Duty Cycle and set back to max_duty_cycle if required
			elif (dc_fan and not control['pwm_control'] and current_output_status['pwm'] !=
				  	settings['pwm']['max_duty_cycle']):
				control['duty_cycle'] = settings['pwm']['max_duty_cycle']
				write_control(control)
				grill_platform.set_duty_cycle(control['duty_cycle'])
				write_event(settings, '* Temp Fan Control: Set to OFF, Fan Returned to Max Duty Cycle')

		# Write History after 3 seconds has passed
		if (now - temp_toggle_time) > 3:
			temp_toggle_time = time.time()
			write_history(in_data, tuning_mode=control['tuning_mode'])

		# Check if startup time has elapsed since startup/reignite mode started
		if mode in ('Startup', 'Reignite'):
			if settings['smartstart']['enabled']:
				profile_selected = control['smartstart']['profile_selected']
				startup_timer = settings['smartstart']['profiles'][profile_selected]['startuptime']
			else: 
				startup_timer = settings['globals']['startup_timer']
			if (now - start_time) > startup_timer:
				break

		# Check if shutdown time has elapsed since shutdown mode started
		if mode == 'Shutdown' and (now - start_time) > settings['globals']['shutdown_timer']:
			break

		# Max Temp Safety Control
		if AvgGT.average() > settings['safety']['maxtemp']:
			display_device.display_text('ERROR')
			control['mode'] = 'Error'
			control['updated'] = True
			write_control(control)
			send_notifications("Grill_Error_01", control, settings, pelletdb)
			break

		time.sleep(0.05)

	# *********
	# END Mode Loop
	# *********

	# Clean-up and Exit
	grill_platform.auger_off()
	grill_platform.igniter_off()

	write_event(settings, '* Auger OFF, Igniter OFF')

	if mode in ('Shutdown', 'Monitor', 'Manual'):
		grill_platform.fan_off()
		grill_platform.power_off()
		write_event(settings, '* Fan OFF, Power OFF')
	if mode in ('Startup', 'Reignite'):
		control['safety']['afterstarttemp'] = AvgGT.average()
		write_control(control)

	write_event(settings, mode + ' mode ended.')

	# Log the end time
	metrics['endtime'] = time.time()
	metrics['pellet_level_end'] = pelletdb['current']['hopper_level']
	write_metrics(metrics)

	return ()

def _next_mode(next_mode, setpoint=0):			
	control = read_control()
	# If no other request, then transition to next mode, otherwise exit
	if not control['updated']:
		control['mode'] = next_mode
		control['setpoints']['grill'] = setpoint  # If next mode is 'Hold'
		control['updated'] = True 
		write_control(control)
	return control 

def _recipe_mode(grill_platform, adc_device, display_device, dist_device):
	"""
	Recipe Mode Control

	:param grill_platform: Grill Platform
	:param adc_device: ADC Device
	:param display_device: Display Device
	:param dist_device: Distance Device
	"""
	settings = read_settings()
	write_event(settings, 'Recipe Mode started.')

	# Find Recipe
	control = read_control()
	recipe_name = control['recipe']
	cookbook = read_recipes()

	if recipe_name in cookbook:
		recipe = cookbook[recipe_name]
		write_event(settings, '* Found recipe: ' + recipe_name)

	# Execute Recipe Steps
	# for(item in recipe['steps'].sort()):
	# 	if('grill_temp' in recipe['steps'][item]):
	# 		temp = recipe['steps'][item]['grill_temp']
	# 		notify = recipe['steps'][item]['notify']
	# 		desc = recipe['steps'][item]['description']
	# 		write_event(settings, item + ': Setting Grill Temp: ' + str(temp) + 'F, Notify: ' + str(
	# 			notify) + ', Desc: ' + desc)

	# Read Control, Check for updates, break
	# Read Switch, Check if changed to off, break
	else:
		# Error Recipe Not Found
		write_event(settings, 'Recipe not found')

	write_event(settings, 'Recipe mode ended.')

	return()


# *****************************************
# Main Program Start / Init and Loop
# *****************************************
write_event(settings, 'Control Script Starting Up.')

last = grill_platform.get_input_status()

while True:

	# Check the On/Off switch for changes
	if not standalone and last != grill_platform.get_input_status():
		last = grill_platform.get_input_status()
		if not last:
			write_event(settings, 'Switch set to off, going to stop mode.')
			control['updated'] = True  # Change mode
			control['mode'] = 'Stop'
			write_control(control)

	# 1. Check control for commands
	control = read_control()

	# Check if there is a timer running, see if it has expired, send notification and reset
	if control['notify_req']['timer']:
		if time.time() >= control['timer']['end']:
			send_notifications("Timer_Expired", control, settings, pelletdb)
			control['notify_req']['timer'] = False
			control['timer']['start'] = 0
			control['timer']['paused'] = 0
			control['timer']['end'] = 0
			control['notify_data']['timer_shutdown'] = False
			control['notify_data']['timer_keep_warm'] = False
			write_control(control)

	# Check if user changed hopper levels and update if required
	if control['distance_update']:
		empty = settings['pelletlevel']['empty']
		full = settings['pelletlevel']['full']
		dist_device.update_distances(empty, full)
		control['distance_update'] = False
		write_control(control)

	if control['hopper_check']:
		pelletdb = read_pellet_db()
		# Get current hopper level and save it to the current pellet information
		pelletdb['current']['hopper_level'] = dist_device.get_level()
		write_pellet_db(pelletdb)
		write_event(settings, "* Hopper Level Checked @ " + str(pelletdb['current']['hopper_level']) + "%")
		control['hopper_check'] = False
		write_control(control)

	if control['updated']:
		write_event(settings, f'* Control Settings Updated.  Mode: {control["mode"]}, Units Change: {control["units_change"]} ')
		# Clear control flag
		control['updated'] = False  # Reset Control Updated to False
		write_control(control)  # Commit change in 'updated' status to the file

		if control['units_change']:
			write_event(settings, '* Changing Base Units.')
			settings = read_settings()
			# Update ADC object and set profiles
			adc_device.update_units(settings['globals']['units'])
			control['mode'] = 'Stop'  # Stop any activity
			control['units_change'] = False
			read_history(0, flushhistory=True)  # Clear history data

		# Check if there was an Error flagged in Monitor Mode - If no, then change status to active
		if control['status'] != 'monitor' and control['mode'] != 'Error':
			control['status'] = 'active'  # Set status to active
			write_control(control)

		if control['mode'] in ('Stop', 'Error'):
			grill_platform.auger_off()
			grill_platform.igniter_off()
			grill_platform.fan_off()
			# Register Stop Mode in Metrics DB if this is not initial stop-mode on startup (i.e. DB is empty)
			metrics_list = read_metrics(all=True)
			if len(metrics_list) != 0:
				write_metrics(new_metric=True)
				metrics = read_metrics()
				metrics['mode'] = 'Stop'
				write_metrics(metrics)
				write_cookfile()

			if control['status'] == 'monitor' and control['mode'] == 'Error':
				grill_platform.power_on()
			else:
				grill_platform.power_off()
			if control['mode'] == 'Stop':
				write_event(settings, 'Stop Mode Started.')
				display_device.clear_display()  # When in error mode, leave the display showing ERROR
				control['status'] = 'inactive'
				# Reset Control to Defaults
				control = read_control(flush=True)
				control['updated'] = False
				control['tuning_mode'] = False  # Turn off Tuning Mode on Stop just in case it is on
				control['next_mode'] = 'Stop'
				write_control(control)
			else:
				write_event(settings, 'ERROR: An error has occurred, Stop Mode enabled.')
				# Reset Control to Defaults but preserve 'Error' mode condition
				control = default_control()
				control['mode'] = 'Error'
				control['status'] = 'inactive'
				control['tuning_mode'] = False  # Turn off Tuning Mode on Stop just in case it is on
				control['updated'] = False
				control['next_mode'] = 'Stop'
				write_control(control)

			read_current(zero_out=True)  # Zero out the current values

		# Startup (startup sequence)
		elif control['mode'] == 'Startup':
			if not standalone and not grill_platform.get_input_status():
				write_event(settings, "Warning: PiFire is set to OFF. This doesn't prevent startup, "
									   "but this means the switch won't behave as normal.")
			settings = read_settings()
			# Clear History (in the case it wasn't already cleared fromt he last run)
			write_event(settings, '* Clearing History and Current Log on Startup Mode.')
			read_history(0, flushhistory=True)  # Clear all history
			# Setup Next Mode (after startup mode)
			control['next_mode'] = settings['start_to_mode']['after_startup_mode']
			write_control(control)
			# Call Work Cycle for Startup Mode
			_work_cycle('Startup', grill_platform, adc_device, display_device, dist_device)
			# TODO: Implement Next Mode
			# Select Next Mode
			settings = read_settings()
			_next_mode(control['next_mode'], setpoint=settings['start_to_mode']['grill1_setpoint'])			

		# Smoke (smoke cycle)
		elif control['mode'] == 'Smoke':
			control['next_mode'] = 'Stop'
			write_control(control)
			_work_cycle('Smoke', grill_platform, adc_device, display_device, dist_device)
			_next_mode(control['next_mode'])			

		# Hold (hold at setpoint)
		elif control['mode'] == 'Hold':
			control['next_mode'] = 'Stop'
			write_control(control)
			_work_cycle('Hold', grill_platform, adc_device, display_device, dist_device)
			_next_mode(control['next_mode'])			

		# Shutdown (shutdown sequence)
		elif control['mode'] == 'Shutdown':
			control['next_mode'] = 'Stop'
			write_control(control)
			_work_cycle('Shutdown', grill_platform, adc_device, display_device, dist_device)
			_next_mode(control['next_mode'])			
			if settings['globals']['auto_power_off']:
				write_event(settings, 'Shutdown mode ended powering off grill')
				os.system("sleep 3 && sudo shutdown -h now &")

		# Monitor (monitor the OEM controller)
		elif control['mode'] == 'Monitor':
			control['status'] = 'monitor'  # Set status to monitor
			write_control(control)
			_work_cycle('Monitor', grill_platform, adc_device, display_device, dist_device)

		# Manual Mode
		elif control['mode'] == 'Manual':
			_work_cycle('Manual', grill_platform, adc_device, display_device, dist_device)
		
		# Recipe Mode (TBD)
		elif control['mode'] == 'Recipe':
			_recipe_mode(grill_platform, adc_device, display_device, dist_device)
		
		# Reignite (reignite sequence)
		elif control['mode'] == 'Reignite':
			if (not standalone) and (not grill_platform.get_input_status()):
				write_event(settings, "Warning: PiFire is set to OFF. This doesn't prevent reignite, "
									   "but this means the switch won't behave as normal.")
			control['next_mode'] = control['safety']['reignitelaststate']
			setpoint = control['setpoints']['grill']
			write_control(control)
			_work_cycle('Reignite', grill_platform, adc_device, display_device, dist_device)
			_next_mode(control['next_mode'], setpoint=setpoint)

	time.sleep(0.1)
# ===================
# End of Main Loop
# ===================
