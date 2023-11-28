#!/usr/bin/env python3

'''
==============================================================================
 PiFire Main Control Process 
==============================================================================

Description: This script will start at boot, initialize the relays and
  wait for further commands from the web user interface.

 This script runs as a separate process from the Flask / Gunicorn
 implementation which handles the web interface.

==============================================================================
'''

'''
==============================================================================
 Imported Modules
==============================================================================
'''
import logging
import importlib
from common import *  # Common Module for WebUI and Control Program
from common.process_mon import Process_Monitor
from notify.notifications import *
from file_mgmt.recipes import convert_recipe_units
from file_mgmt.cookfile import create_cookfile
from file_mgmt.common import read_json_file_data
from os.path import exists


'''
==============================================================================
 Read and initialize Settings, Control, History, Metrics, and Error Data
==============================================================================
'''
# Read Settings & Wizard Manifest to Get Modules Configuration 
settings = read_settings(init=True)
wizard_data = read_wizard()

# Setup logging
log_level = logging.DEBUG if settings['globals']['debug_mode'] else logging.ERROR
controlLogger = create_logger('control', filename='./logs/control.log', messageformat='%(asctime)s [%(levelname)s] %(message)s', level=log_level)

log_level = logging.DEBUG if settings['globals']['debug_mode'] else logging.INFO
eventLogger = create_logger('events', filename='/tmp/events.log', messageformat='%(asctime)s [%(levelname)s] %(message)s', level=log_level)

# Flush Redis DB and create JSON structure
control = read_control(flush=True)
# Delete Redis DB for history / current
read_history(0, flushhistory=True)
# Flush metrics DB for tracking certain metrics
write_metrics(flush=True)
# Create/Flush errors list 
errors = read_errors(flush=True)

eventLogger.info('Flushing Redis DB and creating new control structure')

'''
Set up GrillPlatform Module
'''
try: 
	grill_platform = settings['modules']['grillplat']
	GrillPlatModule = importlib.import_module(f'grillplat.{grill_platform}')

except:
	controlLogger.exception(f'Error occurred loading grillplatform module ({filename}). Trace dump: ')
	GrillPlatModule = importlib.import_module('grillplat.prototype')
	error_event = f'An error occurred loading the [{settings["modules"]["grillplat"]}] platform module.  The ' \
		f'prototype module has been loaded instead.  This sometimes means that the hardware is not connected ' \
		f'properly, or the module is not configured.  Please run the configuration wizard again from the admin ' \
		f'panel to fix this issue.'
	errors.append(error_event)
	write_errors(errors)
	eventLogger.error(error_event)
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
	controlLogger.exception(f'Error occurred configuring grillplatform module ({filename}). Trace dump: ')
	from grillplat.prototype import GrillPlatform  # Simulated Library for controlling the grill platform
	grill_platform = GrillPlatform(out_pins, in_pins, trigger_level)
	error_event = f'An error occurred configuring the [{settings["modules"]["grillplat"]}] platform object.  The ' \
		f'prototype module has been loaded instead.  This sometimes means that the hardware is not ' \
		f'connected properly, or the module is not configured.  Please run the configuration wizard ' \
		f'again from the admin panel to fix this issue.'
	errors.append(error_event)
	write_errors(errors)
	eventLogger.error(error_event)
	if settings['globals']['debug_mode']:
		raise

'''
Set up Probes Input Module
'''
try: 
	from probes.main import ProbesMain  # Probe device libary: loads probe devices and maps them to ports
	probe_complex = ProbesMain(settings["probe_settings"]["probe_map"], settings['globals']['units'])

except:
	controlLogger.exception(f'Error occurred loading probes modules. Trace dump: ')
	settings['probe_settings']['probe_map'] = default_probe_map(settings["probe_settings"]['probe_profiles'])
	probe_complex = ProbesMain(settings["probe_settings"]["probe_map"], settings['globals']['units'])
	error_event = f'An error occurred loading the probes module(s).  The prototype ' \
		f'module has been loaded instead.  This sometimes means that the hardware is not connected ' \
		f'properly, or the module is not configured.  Please run the configuration wizard again from ' \
		f'the admin panel to fix this issue.'
	errors.append(error_event)
	write_errors(errors)
	eventLogger.error(error_event)
	if settings['globals']['debug_mode']:
		raise

'''
Set up Display Module
'''
try: 
	display_name = settings['modules']['display']
	DisplayModule = importlib.import_module(f'display.{display_name}')
	display_config = settings['display']['config'][display_name]
	display_config['probe_info'] = get_probe_info(settings['probe_settings']['probe_map']['probe_info'])

except:
	controlLogger.exception(f'Error occurred loading the display module ({display_name}). Trace dump: ')
	DisplayModule = importlib.import_module('display_none')
	error_event = f'An error occurred loading the [{settings["modules"]["display"]}] display module.  The ' \
		f'"display_none" module has been loaded instead.  This sometimes means that the hardware is ' \
		f'not connected properly, or the module is not configured.  Please run the configuration wizard ' \
		f'again from the admin panel to fix this issue.'
	errors.append(error_event)
	write_errors(errors)
	eventLogger.error(error_event)
	if settings['globals']['debug_mode']:
		raise

try:
	display_device = DisplayModule.Display(dev_pins=dev_pins, buttonslevel=buttons_level,
										   rotation=disp_rotation, units=units, config=display_config)
except:
	controlLogger.exception(f'Error occurred configuring the display module ({filename}). Trace dump: ')
	from display.none import Display  # Simulated Library for controlling the grill platform
	display_device = Display(dev_pins=dev_pins, buttonslevel=buttons_level, rotation=disp_rotation, units=units, config={})
	error_event = f'An error occurred configuring the [{settings["modules"]["display"]}] display object.  The ' \
		f'"display_none" module has been loaded instead.  This sometimes means that the hardware is ' \
		f'not connected properly, or the module is not configured.  Please run the configuration wizard ' \
		f'again from the admin panel to fix this issue.'
	errors.append(error_event)
	write_errors(errors)
	eventLogger.error(error_event)
	if settings['globals']['debug_mode']:
		raise

'''
Set up Distance (Hopper Level) Module
'''
try: 
	dist_name = settings['modules']['dist']
	DistanceModule = importlib.import_module(f'distance.{dist_name}')

except:
	controlLogger.exception(f'Error occurred loading the distance module ({dist_name}). Trace dump: ')
	DistanceModule = importlib.import_module('distance.none')
	error_event = f'An error occurred loading the [{settings["modules"]["dist"]}] distance module.  The none ' \
		f'module has been loaded instead.  This sometimes means that the hardware is not connected ' \
		f'properly, or the module is not configured.  Please run the configuration wizard again from the ' \
		f'admin panel to fix this issue.'
	errors.append(error_event)
	write_errors(errors)
	eventLogger.error(error_event)

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
	controlLogger.exception(f'Error occurred configuring the distance module ({dist_name}). Trace dump: ')
	from distance.none import HopperLevel  # Simulated Library for controlling the grill platform
	dist_device = HopperLevel(
		dev_pins=dev_pins, empty=settings['pelletlevel']['empty'], full=settings['pelletlevel']['full'],
		debug=settings['globals']['debug_mode'])
	error_event = f'An error occurred configuring the [{settings["modules"]["dist"]}] distance object.  The ' \
		f'none module has been loaded instead.  This sometimes means that the hardware is not ' \
		f'connected properly, or the module is not configured.  Please run the configuration wizard again ' \
		f'from the admin panel to fix this issue.'
	errors.append(error_event)
	write_errors(errors)
	eventLogger.error(error_event)

# Get current hopper level and save it to the current pellet information
pelletdb = read_pellet_db()
pelletdb['current']['hopper_level'] = dist_device.get_level()
write_pellet_db(pelletdb)
eventLogger.info(f'Hopper Level Checked @ {pelletdb["current"]["hopper_level"]}%')

'''
*****************************************
 	Function Definitions
*****************************************
'''
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


def _work_cycle(mode, grill_platform, probe_complex, display_device, dist_device):
	"""
	Work Cycle Function

	:param mode: Requested Mode
	:param grill_platform: Grill Platform
	:param probe_complex: ADC Device
	:param display_device: Display Device
	:param dist_device: Distance Device
	"""

	# Setup Process Monitor and Start 
	monitor = Process_Monitor('control', ['supervisorctl', 'restart', 'control'], timeout=30)
	monitor.start_monitor()

	# Precondition for entering into main control loop 
	status = 'Active'

	# Setup Cycle Parameters
	settings = read_settings()
	control = read_control()
	pelletdb = read_pellet_db()

	eventLogger.info(f'{mode} Mode started.')

	# Pre-Loop Setup Recipe Triggers
	if control['mode'] == "Recipe":
		if mode in ['Smoke', 'Hold']:
			recipe_trigger_set = False
			# If requested, set Timer Trigger
			if control['recipe']['step_data']['timer'] > 0:
				# Set notify/trigger for timer
				for index, item in enumerate(control['notify_data']):
					if item['type'] == 'timer':
						control['notify_data'][index]['req'] = True
						timer_start = time.time()
						control['timer']['start'] = timer_start
						control['timer']['paused'] = 0
						control['timer']['end'] = timer_start + (control['recipe']['step_data']['timer'] * 60)
						control['timer']['shutdown'] = False
						control['notify_data'][index]['shutdown'] = False
						control['notify_data'][index]['keep_warm'] = False
						recipe_trigger_set = True 

			# If requested, set Probe Temp Triggers
			for probe, value in control['recipe']['step_data']['trigger_temps'].items():
				if value > 0:
					# Set notify/trigger for probe
					for index, item in enumerate(control['notify_data']):
						if item['type'] == 'probe' and item['label'] == probe:
							control['notify_data'][index]['target'] = value
							control['notify_data'][index]['req'] = True
							recipe_trigger_set = True
							break 

			if recipe_trigger_set: 
				write_control(control, direct_write=True, origin='control')
			else: 
				eventLogger.warning('No trigger set for Hold/Smoke mode in recipe.')
			
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
		eventLogger.debug('Power ON, Fan ON, Igniter OFF, Auger OFF')
	elif mode in ('Prime'):
		grill_platform.fan_off()
		grill_platform.power_on()
		eventLogger.debug('Power ON, Fan OFF, Igniter OFF, Auger OFF')
	else: # (Monitor, Manual)
		grill_platform.fan_off()
		grill_platform.power_off()
		eventLogger.debug('Power OFF, Fan OFF, Igniter OFF, Auger OFF')

	write_metrics(new_metric=True)
	metrics = read_metrics()
	metrics['mode'] = mode
	metrics['smokeplus'] = control['s_plus'] 
	metrics['primary_setpoint'] = control['primary_setpoint']
	metrics['pellet_level_start'] = pelletdb['current']['hopper_level']
	current_pellet_id = pelletdb['current']['pelletid']
	pellet_brand = pelletdb['archive'][current_pellet_id]['brand']
	pellet_type = pelletdb['archive'][current_pellet_id]['wood']
	metrics['pellet_brand_type'] = f'{pellet_brand} {pellet_type}'
	write_metrics(metrics)

	if mode in ('Startup', 'Reignite'):
		grill_platform.igniter_on()
		eventLogger.debug('Igniter ON')
	if mode in ('Startup', 'Reignite', 'Smoke', 'Hold', 'Prime'):
		grill_platform.auger_on()
		eventLogger.debug('Auger ON')

	if mode in ('Startup', 'Reignite', 'Smoke'):
		OnTime = settings['cycle_data']['SmokeOnCycleTime']  # Auger On Time (Default 15s) 
		OffTime = settings['cycle_data']['SmokeOffCycleTime'] + (settings['cycle_data']['PMode'] * 10)  # Auger Off Time
		CycleTime = OnTime + OffTime  # Total Cycle Time
		CycleRatio = RawCycleRatio = OnTime / CycleTime  # Ratio of OnTime to CycleTime
		# Write Metrics (note these will be overwritten if smart start is enabled)
		metrics['p_mode'] = settings['cycle_data']['PMode']
		metrics['auger_cycle_time'] = settings['cycle_data']['SmokeOnCycleTime']
		write_metrics(metrics)

	if mode == 'Hold':
		OnTime = settings['cycle_data']['HoldCycleTime'] * settings['cycle_data']['u_min']  # Auger On Time
		OffTime = settings['cycle_data']['HoldCycleTime'] * (1 - settings['cycle_data']['u_min'])  # Auger Off Time
		CycleTime = settings['cycle_data']['HoldCycleTime']  # Total Cycle Time
		CycleRatio = RawCycleRatio = settings['cycle_data']['u_min']  # Ratio of OnTime to CycleTime
		LidOpenDetect = False
		LidOpenEventExpires = 0
		'''
			Load Controller Module (i.e. PID)
		'''
		try: 
			controller_type = settings['controller']['selected']
			controller_module = importlib.import_module(f'controller.{controller_type}')
		except:
			controlLogger.exception(f'Error occurred loading controller module({controller_type}). Trace dump: ')
			status = 'Inactive'
		controllerCore = controller_module.Controller(settings['controller']['config'][controller_type], settings['globals']['units'], settings['cycle_data'])
		controllerCore.set_target(control['primary_setpoint'])  # Initialize with Set Point for grill
		eventLogger.debug('On Time = ' + str(OnTime) + ', OffTime = ' + str(OffTime) + ', CycleTime = ' + str(
			CycleTime) + ', CycleRatio = ' + str(CycleRatio))

	if mode == 'Prime':
		auger_rate = settings['globals']['augerrate']
		prime_amount = control['prime_amount']
		prime_duration = int(prime_amount / auger_rate) # Auger On Time = Prime Amount (Grams) / (Grams per Second)
		OnTime = prime_duration
		OffTime = 1  # Auger Off Time
		CycleTime = OnTime + OffTime  # Total Cycle Time
		CycleRatio = RawCycleRatio = OnTime / CycleTime  # Ratio of OnTime to CycleTime
		''' Allow for the igniter to be turned on during prime mode - user selected '''
		if settings['globals']['prime_ignition'] and control['next_mode'] == 'Startup':
			grill_platform.igniter_on()
			eventLogger.debug('Igniter ON')

	# Get initial probe sensor data, temperatures 
	sensor_data = probe_complex.read_probes()
	ptemp = list(sensor_data['primary'].values())[0]  # Primary Temperature or the Pit Temperature

	# Safety Controls
	if mode in ('Startup', 'Reignite'):
		control['safety']['startuptemp'] = int(max((ptemp * 0.9), settings['safety']['minstartuptemp']))
		control['safety']['startuptemp'] = int(
			min(control['safety']['startuptemp'], settings['safety']['maxstartuptemp']))
		control['safety']['afterstarttemp'] = ptemp
		write_control(control, direct_write=True, origin='control')
	# Check if the temperature of the grill dropped below the startuptemp
	elif mode in ('Smoke', 'Hold'):
		if control['safety']['afterstarttemp'] < control['safety']['startuptemp']:
			if control['safety']['reigniteretries'] == 0:
				status = 'Inactive'
				display_device.display_text('ERROR')
				control['mode'] = 'Error'
				control['updated'] = True
				write_control(control, direct_write=True, origin='control')
				send_notifications("Grill_Error_02", control, settings, pelletdb)
			else:
				control['safety']['reigniteretries'] -= 1
				control['safety']['reignitelaststate'] = mode
				status = 'Inactive'
				display_device.display_text('Re-Ignite')
				control['mode'] = 'Reignite'
				control['updated'] = True
				write_control(control, direct_write=True, origin='control')
				send_notifications("Grill_Error_03", control, settings, pelletdb)

	# Apply Smart Start Settings if Enabled 
	startup_timer = settings['globals']['startup_timer']
	if settings['smartstart']['enabled'] and mode in ('Startup', 'Reignite', 'Smoke'):
		# If Startup, then save initial temperature & select the profile
		if mode in ('Startup', 'Reignite'):
			control['smartstart']['startuptemp'] = int(ptemp)
			# Cycle through profiles, and set profile if startup temperature falls below the minimum temperature
			for profile_selected in range(0, len(settings['smartstart']['temp_range_list'])):
				if control['smartstart']['startuptemp'] < settings['smartstart']['temp_range_list'][profile_selected]:
					control['smartstart']['profile_selected'] = profile_selected
					write_control(control, direct_write=True, origin='control')
					break  # Break out of the loop
				if profile_selected == len(settings['smartstart']['temp_range_list']) - 1:
					control['smartstart']['profile_selected'] = profile_selected + 1
					write_control(control, direct_write=True, origin='control')
		# Apply the profile 
		profile_selected = control['smartstart']['profile_selected']
		OnTime = settings['smartstart']['profiles'][profile_selected]['augerontime']  # Auger On Time (Default 15s)
		OffTime = settings['cycle_data']['SmokeOffCycleTime'] + (settings['smartstart']['profiles'][profile_selected]['p_mode'] * 10)  # Auger Off Time
		CycleTime = OnTime + OffTime  # Total Cycle Time
		CycleRatio = RawCycleRatio = OnTime / CycleTime  # Ratio of OnTime to CycleTime
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

	# Set time since fan speed update
	fan_update_time = start_time

	# Set Hold Mode Target Temp Boolean
	target_temp_achieved = False

	# Set Fan Ramping Boolean
	pwm_fan_ramping = False

	# Setup Display Data
	status_data = {} 
	in_data = {}

	# ============ Main Work Cycle ============
	while status == 'Active':
		now = time.time()

		execute_commands()
		control = read_control()

		# Check if new mode has been requested
		if control['updated']:
			break

		# Check if user changed settings and reload
		if control['settings_update']:
			control['settings_update'] = False
			write_control(control, direct_write=True, origin='control')
			settings = read_settings()
			if mode in ('Startup', 'Reignite', 'Smoke'):
				OnTime = settings['cycle_data']['SmokeOnCycleTime']  # Auger On Time (Default 15s) 
				OffTime = settings['cycle_data']['SmokeOffCycleTime'] + (settings['cycle_data']['PMode'] * 10)  # Auger Off Time
				CycleTime = OnTime + OffTime  # Total Cycle Time
				CycleRatio = RawCycleRatio = OnTime / CycleTime  # Ratio of OnTime to CycleTime
				# Write Metrics (note these will overwrite the previous value)
				metrics['p_mode'] = settings['cycle_data']['PMode']
				metrics['auger_cycle_time'] = settings['cycle_data']['SmokeOnCycleTime']
				write_metrics(metrics)

		# Check if user changed hopper levels and update if required
		if control['distance_update']:
			empty = settings['pelletlevel']['empty']
			full = settings['pelletlevel']['full']
			dist_device.update_distances(empty, full)
			control['distance_update'] = False
			write_control(control, direct_write=True, origin='control')

		# Check hopper level when requested or every 300 seconds
		if control['hopper_check'] or (now - hopper_toggle_time) > 300:
			pelletdb = read_pellet_db()
			override = False 
			if control['hopper_check']:
				control['hopper_check'] = False
				write_control(control, direct_write=True, origin='control')
				override = True
			# Get current hopper level and save it to the current pellet information
			pelletdb['current']['hopper_level'] = dist_device.get_level(override=override)			
			write_pellet_db(pelletdb)
			hopper_toggle_time = now
			eventLogger.info("Hopper Level Checked @ " + str(pelletdb['current']['hopper_level']) + "%")

		# Check for update in ON/OFF Switch
		if not standalone and last != grill_platform.get_input_status():
			last = grill_platform.get_input_status()
			if not last:
				eventLogger.info('Switch set to off, going to monitor mode.')
				control['updated'] = True  # Change mode
				control['mode'] = 'Stop'
				control['status'] = 'active'
				write_control(control, direct_write=True, origin='control')
				break

		current_output_status = grill_platform.get_output_status()

		if mode == 'Manual':
			if control['manual']['change']:
				if control['manual']['fan'] and not current_output_status['fan']:
					grill_platform.fan_on()
					eventLogger.debug('Fan ON')
				elif not control['manual']['fan'] and current_output_status['fan']:
					grill_platform.fan_off()
					eventLogger.debug('Fan OFF')
				if control['manual']['auger'] and not current_output_status['auger']:
					grill_platform.auger_on()
					eventLogger.debug('Auger ON')
				elif not control['manual']['auger'] and current_output_status['auger']:
					grill_platform.auger_off()
					eventLogger.debug('Auger OFF')
				if control['manual']['igniter'] and not current_output_status['igniter']:
					grill_platform.igniter_on()
					eventLogger.debug('Igniter ON')
				elif not control['manual']['igniter'] and current_output_status['igniter']:
					grill_platform.igniter_off()
					eventLogger.debug('Igniter OFF')
				if control['manual']['power'] and not current_output_status['power']:
					grill_platform.power_on()
					eventLogger.debug('Power ON')
				elif not control['manual']['power'] and current_output_status['power']:
					grill_platform.power_off()
					eventLogger.debug('Power OFF')
				if dc_fan and control['manual']['fan'] and current_output_status['fan'] and \
					not control['manual']['pwm'] == current_output_status['pwm']:
					speed = control['manual']['pwm']
					eventLogger.debug('PWM Speed: ' + str(speed) + '%')
					grill_platform.set_duty_cycle(speed)
				control['manual']['change'] = False
				write_control(control, direct_write=True, origin='control')

		# Change Auger State based on Cycle Time
		if mode in ('Startup', 'Reignite', 'Smoke', 'Hold', 'Prime'):
			# If Auger is OFF and time since toggle is greater than Off Time
			if not current_output_status['auger'] and (now - auger_toggle_time) > (CycleTime * (1 - CycleRatio)):
				grill_platform.auger_on()
				auger_toggle_time = now
				eventLogger.debug('Cycle Event: Auger On')
				# Reset Cycle Time for HOLD Mode
				if mode == 'Hold':
					CycleRatio = RawCycleRatio = settings['cycle_data']['u_min'] if LidOpenDetect else controllerCore.update(ptemp)
					CycleRatio = max(CycleRatio, settings['cycle_data']['u_min'])
					CycleRatio = min(CycleRatio, settings['cycle_data']['u_max'])
					OnTime = settings['cycle_data']['HoldCycleTime'] * CycleRatio
					OffTime = settings['cycle_data']['HoldCycleTime'] * (1 - CycleRatio)
					CycleTime = OnTime + OffTime
					eventLogger.debug('On Time = ' + str(OnTime) + ', OffTime = ' + str(
						OffTime) + ', CycleTime = ' + str(CycleTime) + ', CycleRatio = ' + str(CycleRatio))

			# If Auger is ON and time since toggle is greater than On Time
			if current_output_status['auger'] and (now - auger_toggle_time) > (CycleTime * CycleRatio):
				grill_platform.auger_off()
				# Add auger ON time to the metrics
				metrics['augerontime'] += now - auger_toggle_time
				write_metrics(metrics)
				# Set current last toggle time to now
				auger_toggle_time = now
				eventLogger.debug('Cycle Event: Auger Off')

		# Grab current probe profiles if they have changed since the last loop.
		if control['probe_profile_update']:
			settings = read_settings()
			control['probe_profile_update'] = False
			write_control(control, direct_write=True, origin='control')
			# Add new probe profiles to probe complex object
			probe_complex.update_probe_profiles(settings['probe_settings']['probe_map']['probe_info'])

		# Get temperatures from all probes
		sensor_data = probe_complex.read_probes()
		ptemp = list(sensor_data['primary'].values())[0]  # Primary Temperature or the Pit Temperature

		in_data['probe_history'] = sensor_data 
		in_data['primary_setpoint'] = control['primary_setpoint'] if mode == 'Hold' else 0
		in_data['notify_targets'] = get_notify_targets(control['notify_data'])

		# If Extended Data Mode is Enabled, Populate Extra Data Here
		if settings['globals']['ext_data']:
			in_data['ext_data'] = {}
			in_data['ext_data']['CR'] = CycleRatio if 'CycleRatio' in locals() else 0
			in_data['ext_data']['RCR'] = RawCycleRatio if 'RawCycleRatio' in locals() else 0

		# Save current data to the database 
		write_current(in_data)

		# Write Tr data to the database if in tuning mode 
		if control['tuning_mode']:
			write_tr(in_data['probe_history']['tr'])

		# Check to see if there are any pending notifications (i.e. Timer / Temperature Settings)
		control = check_notify(in_data, control, settings, pelletdb, grill_platform)

		# Send Current Status / Temperature Data to Display Device every 0.5 second (Display Refresh)
		if (now - display_toggle_time) > 0.5:
			status_data['notify_data'] = control['notify_data']  # Get any flagged notifications
			status_data['timer'] = control['timer']  # Get the timer information
			status_data['s_plus'] = control['s_plus']
			status_data['hopper_level'] = pelletdb['current']['hopper_level']
			status_data['units'] = settings['globals']['units']
			status_data['mode'] = mode
			status_data['recipe'] = True if control['mode'] == 'Recipe' else False
			status_data['start_time'] = start_time
			status_data['start_duration'] = startup_timer
			status_data['shutdown_duration'] = settings['globals']['shutdown_timer']
			status_data['prime_duration'] = prime_duration if mode == 'Prime' else 0  # Enable Timer for Prime Mode 
			status_data['prime_amount'] = prime_amount if mode == 'Prime' else 0  # Enable Display of Prime Amount
			status_data['lid_open_detected'] = LidOpenDetect if mode == 'Hold' else False
			status_data['lid_open_endtime'] = LidOpenEventExpires if mode == 'Hold' else 0
			status_data['p_mode'] = metrics.get('p_mode', None)
			if control['mode'] == 'Recipe':
				status_data['recipe_paused'] = True if control['recipe']['step_data']['triggered'] and control['recipe']['step_data']['pause'] else False
			else: 
				status_data['recipe_paused'] = False
			status_data['outpins'] = {}
			current = grill_platform.get_output_status()  # Get current pin settings
			for item in settings['outpins']:
				try:
					status_data['outpins'][item] = current[item]
				except KeyError:
					continue
			# Send Data to Display
			display_device.display_status(in_data, status_data)
			# Save Status Data to Redis 
			write_status(status_data)
			display_toggle_time = time.time()  # Reset the display_toggle_time to current time

		# Safety Controls
		if mode in ('Startup', 'Reignite'):
			control['safety']['afterstarttemp'] = ptemp
		elif mode in ('Smoke', 'Hold'):
			if ptemp < control['safety']['startuptemp']:
				if control['safety']['reigniteretries'] == 0:
					display_device.display_text('ERROR')
					control['mode'] = 'Error'
					control['updated'] = True
					write_control(control, direct_write=True, origin='control')
					send_notifications("Grill_Error_02", control, settings, pelletdb)
					break
				else:
					control['safety']['reigniteretries'] -= 1
					control['safety']['reignitelaststate'] = mode
					display_device.display_text('Re-Ignite')
					control['mode'] = 'Reignite'
					control['updated'] = True
					write_control(control, direct_write=True, origin='control')
					send_notifications("Grill_Error_03", control, settings, pelletdb)
					break


		if mode in ('Smoke', 'Hold'):
			# Check if target temperature has been achieved before utilizing Smoke Plus Mode
			if mode == 'Hold' and ptemp >= control['primary_setpoint'] and not target_temp_achieved:
				target_temp_achieved = True

			# Check if a lid open event has occurred only after hold mode has been achieved
			if target_temp_achieved and settings['cycle_data']['LidOpenDetectEnabled'] and (ptemp < (control['primary_setpoint'] * ((100 - settings['cycle_data']['LidOpenThreshold']) / 100))):
				LidOpenDetect = True
				grill_platform.auger_off()
				_start_fan(settings)
				auger_toggle_time = now 
				LidOpenEventExpires = now + settings['cycle_data']['LidOpenPauseTime']
				target_temp_achieved = False

			# Clear Lid Open Detect Event, Reset 
			if mode == 'Hold':
				if LidOpenDetect and time.time() > LidOpenEventExpires:
					LidOpenDetect = False

			# If PWM Fan Control enabled set duty_cycle based on temperature
			if (dc_fan and mode == 'Hold' and control['pwm_control'] and
					(now - fan_update_time) > settings['pwm']['update_time']):
				fan_update_time = now
				if ptemp > control['primary_setpoint']:
					control['duty_cycle'] = settings['pwm']['min_duty_cycle']
					write_control(control, direct_write=True, origin='control')
				else:
					# Cycle through profiles, and set duty cycle if setpoint temp is within range
					for temp_profile in range(0, len(settings['pwm']['temp_range_list'])):
						if ((control['primary_setpoint'] - ptemp) <=
								settings['pwm']['temp_range_list'][temp_profile]):
							duty_cycle = settings['pwm']['profiles'][temp_profile]['duty_cycle']
							duty_cycle = max(duty_cycle, settings['pwm']['min_duty_cycle'])
							duty_cycle = min(duty_cycle, settings['pwm']['max_duty_cycle'])
							control['duty_cycle'] = duty_cycle
							write_control(control, direct_write=True, origin='control')
							break # Break out of the loop
						if temp_profile == len(settings['pwm']['temp_range_list']) - 1:
							control['duty_cycle'] = settings['pwm']['max_duty_cycle']
							write_control(control, direct_write=True, origin='control')

			# If in Smoke Plus Mode, Cycle the Fan
			if (mode == 'Smoke' or (mode == 'Hold' and target_temp_achieved)) and control['s_plus']:
				# If Temperature is > settings['smoke_plus']['max_temp']
				# or Temperature is < settings['smoke_plus']['min_temp'] then turn on fan
				if (ptemp > settings['smoke_plus']['max_temp'] or
						ptemp < settings['smoke_plus']['min_temp']):
					if not current_output_status['fan']:
						_start_fan(settings, control['duty_cycle'])
						eventLogger.debug('Smoke Plus: Over or Under Temp Fan ON')
				elif (now - sp_cycle_toggle_time) > settings['smoke_plus']['on_time'] and current_output_status['fan']:
					grill_platform.fan_off()
					sp_cycle_toggle_time = now
					eventLogger.debug('Smoke Plus: Fan OFF')
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
						eventLogger.debug('Smoke Plus: Fan Ramping Up')
					else:
						_start_fan(settings, control['duty_cycle'])
						eventLogger.debug('Smoke Plus: Fan ON')

			# If Smoke Plus was disabled when fan is OFF return fan to ON
			elif not current_output_status['fan'] and not control['s_plus']:
				_start_fan(settings, control['duty_cycle'])
				eventLogger.debug('Smoke Plus: Fan Returned to On')

			# If Smoke Plus was disabled while fan was ramping return it to the correct duty cycle
			elif (dc_fan and current_output_status['pwm'] != control['duty_cycle'] and not
					control['s_plus'] and pwm_fan_ramping):
				pwm_fan_ramping = False
				grill_platform.set_duty_cycle(control['duty_cycle'])
				eventLogger.debug('Smoke Plus: Fan Returned to ' + str(control['duty_cycle']) + '% duty cycle')

			# Set Fan Duty Cycle based on Average Grill Temp Using Profile
			elif dc_fan and control['pwm_control'] and current_output_status['pwm'] != control['duty_cycle']:
				grill_platform.set_duty_cycle(control['duty_cycle'])
				eventLogger.debug('Temp Fan Control: Fan Set to ' + str(control['duty_cycle']) + '% duty cycle')

			# If PWM Fan Control is turned off check current Duty Cycle and set back to max_duty_cycle if required
			elif (dc_fan and not control['pwm_control'] and current_output_status['pwm'] !=
				  	settings['pwm']['max_duty_cycle']):
				control['duty_cycle'] = settings['pwm']['max_duty_cycle']
				write_control(control, direct_write=True, origin='control')
				grill_platform.set_duty_cycle(control['duty_cycle'])
				eventLogger.debug('Temp Fan Control: Set to OFF, Fan Returned to Max Duty Cycle')

		# Write History & Issue Heartbeat after 3 seconds has passed
		if (now - temp_toggle_time) > 3:
			temp_toggle_time = time.time()
			ext_data = True if settings['globals']['ext_data'] else False  # If passing in extended data, set to True
			write_history(in_data, ext_data=ext_data)
			monitor.heartbeat()  # Issue a heartbeat for the process monitor

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

		# Check if prime time has elapsed
		if mode == 'Prime' and (now - start_time) > prime_duration:
			break

		# Max Temp Safety Control
		if ptemp > settings['safety']['maxtemp']:
			display_device.display_text('ERROR')
			control['mode'] = 'Error'
			control['updated'] = True
			write_control(control, direct_write=True, origin='control')
			send_notifications("Grill_Error_01", control, settings, pelletdb)
			break

		# End of Loop Recipe Check
		if control['mode'] == 'Recipe':
			# If a recipe event was triggered and no pause is requested
			if control['recipe']['step_data']['triggered'] and not control['recipe']['step_data']['pause']:
				# If a notification / message was requested
				if control['recipe']['step_data']['notify']:
					send_notifications('Recipe_Step_Message', control, settings, pelletdb)
				# Exit the main work cycle
				break
			# If a recipe event was triggered and a pause was requested
			elif control['recipe']['step_data']['triggered'] and control['recipe']['step_data']['pause']:
				# If notification / message was requested, notify and clear notification 
				if control['recipe']['step_data']['notify']:
					send_notifications('Recipe_Step_Message', control, settings, pelletdb)
					control['recipe']['step_data']['notify'] = False
					write_control(control, direct_write=True, origin='control')
				# Continue until 'pause' variable is cleared 

		time.sleep(0.05)

	# *********
	# END Mode Loop
	# *********

	# Clean-up and Exit
	grill_platform.auger_off()
	grill_platform.igniter_off()

	eventLogger.debug('Auger OFF, Igniter OFF')

	if mode in ('Shutdown', 'Monitor', 'Manual', 'Prime'):
		grill_platform.fan_off()
		grill_platform.power_off()
		eventLogger.debug('Fan OFF, Power OFF')
	
	if mode in ('Startup', 'Reignite'):
		control['safety']['afterstarttemp'] = ptemp
		write_control(control, direct_write=True, origin='control')

	eventLogger.info(f'{mode} mode ended.')

	# Save Pellets Used
	pelletdb = read_pellet_db()
	pelletdb['current']['est_usage'] += metrics['augerontime'] * settings['globals']['augerrate'] 
	write_pellet_db(pelletdb)

	# Log the end time
	metrics['endtime'] = time.time() * 1000
	metrics['pellet_level_end'] = pelletdb['current']['hopper_level']
	write_metrics(metrics)

	monitor.stop_monitor()

	# Clean up display
	status_data['mode'] = mode

	display_device.display_status(in_data, status_data)

	return ()

def _next_mode(next_mode, setpoint=0):			
	execute_commands()
	control = read_control()
	# If no other request, then transition to next mode, otherwise exit
	if not control['updated']:
		control['mode'] = next_mode
		control['primary_setpoint'] = setpoint if next_mode == 'Hold' else 0 # If next mode is 'Hold'
		control['updated'] = True 
		write_control(control, direct_write=True, origin='control')
	return control 

def _recipe_mode(grill_platform, probe_complex, display_device, dist_device, start_step=0):
	"""
	Recipe Mode Control

	:param grill_platform: Grill Platform
	:param probe_complex: ADC Device
	:param display_device: Display Device
	:param dist_device: Distance Device
	"""
	settings = read_settings()
	eventLogger.info('Recipe Mode started.')

	# Find Recipe File
	control = read_control()
	recipe_file = control['recipe']['filename']

	if not exists(recipe_file):
		# File not found, exit
		eventLogger.warning(f'Recipe file {recipe_file} not found!')
		return()

	# 1. Read metadata from the recipe file
	metadata, status = read_json_file_data(recipe_file, 'metadata')
	if status != 'OK':
		eventLogger.warning(f'Failed to load metadata for {recipe_file}.')
		return()
	
	# 2. Read recipe steps (& other data) from the recipe file
	recipe, status = read_json_file_data(recipe_file, 'recipe')
	if status != 'OK':
		eventLogger.warning(f'Failed to load recipe data for {recipe_file}.')
		return()

	# 3. Check and convert temperature units, if there is a mismatch
	if settings['globals']['units'] != metadata['units']:
		recipe = convert_recipe_units(recipe, settings['globals']['units'])

	num_steps = len(recipe['steps'])
	step_num = start_step  # Start at step 0 by default unless requested to start at a later step

	# 4. Walk through steps, and execute work cycle
	while (step_num < num_steps):
		# 4a. Setup all step data and write to control
		control['recipe']['step'] = step_num 
		control['recipe']['step_data'] = recipe['steps'][step_num]
		''' Setup trigger_temps structure that the work_cycle expects, mapping to real probes '''
		trigger_temps = {}
		trigger_temps[settings['recipe']['probe_map']['primary']] = recipe['steps'][step_num]['trigger_temps']['primary']
		for index, value in enumerate(recipe['steps'][step_num]['trigger_temps']['food']):
			trigger_temps[settings['recipe']['probe_map']['food'][index]] = value 
		control['recipe']['step_data']['trigger_temps'] = trigger_temps
		control['recipe']['step_data']['triggered'] = False
		control['primary_setpoint'] = recipe['steps'][step_num]['hold_temp']  # Set Hold Temp if applicable.  
		control['updated'] = False  # Clear Updated Flag if Set
		write_control(control, direct_write=True, origin='control')
		# 4b. Start the recipe step work cycle
		_work_cycle(recipe['steps'][step_num]['mode'], grill_platform, probe_complex, display_device, dist_device)
		
		# 4c. If reignite is required, run a reignite cycle and retry current step
		execute_commands()
		control = read_control()
		if control['mode'] == 'Reignite' and control['updated']:
			control['updated'] = False
			control['mode'] = 'Recipe'
			write_control(control, direct_write=True, origin='control')
			_work_cycle('Reignite', grill_platform, probe_complex, display_device, dist_device)
			control = read_control()
			if control['updated'] and control['mode'] != 'Recipe':
				# If another mode was requested (or an error occurred) then exit recipe mode
				eventLogger.info(f'Recipe mode cancelled due to mode change: {control["mode"]}')
				break
			# 4c-2. Rerun current step
		# 4d. If another mode was requested (or an error occurred) then exit recipe mode
		elif control['mode'] != 'Recipe' and control['updated']:
			eventLogger.info(f'Recipe mode cancelled due to mode change: {control["mode"]}')
			break
		else:
			# 4e. Continue to next step number
			step_num += 1
	
	# 5. Clean up control data and exit
	control['recipe']['step'] = 0
	control['recipe']['step_data'] = {}
	control['recipe']['filename'] = ''

	# If recipe is exiting normally (i.e. no other mode requested, then initiate stop mode)
	if not control['updated'] or (step_num == num_steps):
		control['updated'] = True
		control['mode'] = 'Stop'
		eventLogger.info('Recipe mode ended.')
	write_control(control, direct_write=True, origin='control')

	return()


# *****************************************
# Main Program Start / Init and Loop
# *****************************************
eventLogger.info('Control Script Starting Up.')
controlLogger.info(f'Control Script Starting Up.')

last = grill_platform.get_input_status()

''' If the user has selected boot-to-monitor mode, then issue the command prior to the main loop '''
if settings['globals']['boot_to_monitor']:
	control = read_control()
	control['mode'] = 'Monitor'
	control['updated'] = True
	write_control(control, direct_write=True, origin='control')

''' Initialize the status data on first run. '''
status = read_status(init=True)

while True:

	# Check the On/Off switch for changes
	if not standalone and last != grill_platform.get_input_status():
		last = grill_platform.get_input_status()
		if not last:
			eventLogger.info('Switch set to off, going to stop mode.')
			controlLogger.info(f'Switch set to off, going to stop mode.')
			control['updated'] = True  # Change mode
			control['mode'] = 'Stop'
			write_control(control, direct_write=True, origin='control')

	status = read_status()
	current = grill_platform.get_output_status()  # Get current pin settings
	for item in settings['outpins']:
		try:
			status['outpins'][item] = current[item]
		except KeyError:
			continue
	write_status(status)

	# 1. Check control for commands
	execute_commands()
	control = read_control()

	# Check if there is a timer running, see if it has expired, send notification and reset
	for index, item in enumerate(control['notify_data']):
		if item['type'] == 'timer' and item['req']:
			if time.time() >= control['timer']['end']:
				send_notifications("Timer_Expired", control, settings, pelletdb)
				control['notify_data'][index]['req'] = False
				control['timer']['start'] = 0
				control['timer']['paused'] = 0
				control['timer']['end'] = 0
				control['notify_data'][index]['shutdown'] = False
				control['notify_data'][index]['keep_warm'] = False
				write_control(control, direct_write=True, origin='control')

	# Check if user changed hopper levels and update if required
	if control['distance_update']:
		empty = settings['pelletlevel']['empty']
		full = settings['pelletlevel']['full']
		dist_device.update_distances(empty, full)
		control['distance_update'] = False
		write_control(control, direct_write=True, origin='control')

	if control['hopper_check']:
		pelletdb = read_pellet_db()
		# Get current hopper level and save it to the current pellet information
		pelletdb['current']['hopper_level'] = dist_device.get_level(override=True)
		write_pellet_db(pelletdb)
		eventLogger.info("Hopper Level Checked @ " + str(pelletdb['current']['hopper_level']) + "%")
		control['hopper_check'] = False
		write_control(control, direct_write=True, origin='control')

	# Grab current probe profiles if they have changed since the last loop.
	if control['probe_profile_update']:
		settings = read_settings()
		control['probe_profile_update'] = False
		write_control(control, direct_write=True, origin='control')
		# Add new probe profiles to probe complex object
		probe_complex.update_probe_profiles(settings['probe_settings']['probe_map']['probe_info'])
		eventLogger.info('Active probe profiles updated in control script.')

	if control['updated']:
		eventLogger.debug(f'Control Settings Updated.  Mode: {control["mode"]}, Units Change: {control["units_change"]} ')
		# Clear control flag
		control['updated'] = False  # Reset Control Updated to False
		write_control(control, direct_write=True, origin='control')  # Commit change in 'updated' status to the file

		if control['units_change']:
			eventLogger.debug('Changing Base Units.')
			settings = read_settings()
			# Update ADC objects and set profiles
			probe_complex.update_units(settings['globals']['units'])
			control['mode'] = 'Stop'  # Stop any activity
			control['units_change'] = False
			read_history(0, flushhistory=True)  # Clear history data

		# Check if there was an Error flagged in Monitor Mode - If no, then change status to active
		if control['status'] != 'monitor' and control['mode'] != 'Error':
			control['status'] = 'active'  # Set status to active
			write_control(control, direct_write=True, origin='control')

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
				if metrics_list[-1]['mode'] != 'Prime':
					create_cookfile()

			status['p_mode'] = 0  
			status['mode'] = "Stop"
			status['recipe'] = False
			status['recipe_paused'] = False
			status['start_time'] = 0
			status['lid_open_detected'] = False 
			status['lid_open_endtime'] = 0 
			write_status(status)

			if control['status'] == 'monitor' and control['mode'] == 'Error':
				grill_platform.power_on()
			else:
				grill_platform.power_off()
			if control['mode'] == 'Stop':
				eventLogger.info('Stop Mode Started.')
				display_device.clear_display()  # When in error mode, leave the display showing ERROR
				control['status'] = 'inactive'
				# Reset Control to Defaults
				control = read_control(flush=True)
				control['updated'] = False
				control['tuning_mode'] = False  # Turn off Tuning Mode on Stop just in case it is on
				control['next_mode'] = 'Stop'
				control['safety']['reigniteretries'] = settings['safety']['reigniteretries']  # Reset retry counter to default
				write_control(control, direct_write=True, origin='control')
			else:
				eventLogger.error('An error has occurred, Stop Mode enabled.')
				controlLogger.error('An error has occurred, Stop Mode enabled.')
				# Reset Control to Defaults but preserve 'Error' mode condition
				control = default_control()
				control['mode'] = 'Error'
				control['status'] = 'inactive'
				control['tuning_mode'] = False  # Turn off Tuning Mode on Stop just in case it is on
				control['updated'] = False
				control['next_mode'] = 'Stop'
				control['safety']['reigniteretries'] = settings['safety']['reigniteretries']  # Reset retry counter to default
				write_control(control, direct_write=True, origin='control')
				time.sleep(3)
				display_device.clear_display()  

			read_current(zero_out=True)  # Zero out the current values

		# Prime (dump preset amount of pellets into the firepot)
		elif control['mode'] == 'Prime':
			if not standalone and not grill_platform.get_input_status():
				eventLogger.warning('PiFire is set to OFF. This doesn\'t prevent startup, but this means the switch won\'t behave as normal.')
			# Call Work Cycle for Startup Mode
			_work_cycle('Prime', grill_platform, probe_complex, display_device, dist_device)
			# Select Next Mode
			settings = read_settings()
			_next_mode(control['next_mode'], setpoint=settings['start_to_mode']['primary_setpoint'])			

		# Startup (startup sequence)
		elif control['mode'] == 'Startup':
			if not standalone and not grill_platform.get_input_status():
				eventLogger.warning('PiFire is set to OFF. This doesn\'t prevent startup, but this means the switch won\'t behave as normal.')
			settings = read_settings()
			# Clear History (in the case it wasn't already cleared fromt he last run)
			eventLogger.debug('Clearing History and Current Log on Startup Mode.')
			read_history(0, flushhistory=True)  # Clear all history
			# Setup Next Mode (after startup mode)
			control['next_mode'] = settings['start_to_mode']['after_startup_mode']
			write_control(control, direct_write=True, origin='control')
			# Call Work Cycle for Startup Mode
			_work_cycle('Startup', grill_platform, probe_complex, display_device, dist_device)
			# Select Next Mode
			settings = read_settings()
			_next_mode(control['next_mode'], setpoint=settings['start_to_mode']['primary_setpoint'])			

		# Smoke (smoke cycle)
		elif control['mode'] == 'Smoke':
			_work_cycle('Smoke', grill_platform, probe_complex, display_device, dist_device)
			_next_mode(control['next_mode'])			

		# Hold (hold at setpoint)
		elif control['mode'] == 'Hold':
			_work_cycle('Hold', grill_platform, probe_complex, display_device, dist_device)
			_next_mode(control['next_mode'])			

		# Shutdown (shutdown sequence)
		elif control['mode'] == 'Shutdown':
			control['next_mode'] = 'Stop'
			write_control(control, direct_write=True, origin='control')
			_work_cycle('Shutdown', grill_platform, probe_complex, display_device, dist_device)
			_next_mode(control['next_mode'])			
			if settings['globals']['auto_power_off']:
				eventLogger.info('Shutdown mode ended powering off grill')
				os.system("sleep 3 && sudo shutdown -h now &")

		# Monitor (monitor the OEM controller)
		elif control['mode'] == 'Monitor':
			control['status'] = 'monitor'  # Set status to monitor
			write_control(control, direct_write=True, origin='control')
			_work_cycle('Monitor', grill_platform, probe_complex, display_device, dist_device)

		# Manual Mode
		elif control['mode'] == 'Manual':
			_work_cycle('Manual', grill_platform, probe_complex, display_device, dist_device)
		
		# Recipe Mode
		elif control['mode'] == 'Recipe':
			_recipe_mode(grill_platform, probe_complex, display_device, dist_device, start_step=control['recipe']['start_step'])
		
		# Reignite (reignite sequence)
		elif control['mode'] == 'Reignite':
			if (not standalone) and (not grill_platform.get_input_status()):
				eventLogger.warning("PiFire is set to OFF. This doesn't prevent reignite, "
									   "but this means the switch won't behave as normal.")
			control['next_mode'] = control['safety']['reignitelaststate']
			setpoint = control['primary_setpoint']
			write_control(control, direct_write=True, origin='control')
			_work_cycle('Reignite', grill_platform, probe_complex, display_device, dist_device)
			_next_mode(control['next_mode'], setpoint=setpoint)

	time.sleep(0.1)
# ===================
# End of Main Loop
# ===================
