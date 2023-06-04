'''
Hacks to convert certain APIs / Formats to PiFire v1.3.5 format to maintain compatibility with the current Android App
'''
import datetime
from common import read_control, write_control, read_settings, write_settings, read_history, read_current, unpack_history

def hack_read_settings():
	settings = read_settings()
    # Move notification settings out of ['notify_services']
	notify_services = settings['notify_services']
	for service in notify_services:
		settings[service] = notify_services[service]
	settings.pop('notify_services')

	# Add 'grill_probe_settings'
	settings['grill_probe_settings'] = {
		"grill_probe" : "grill_probe1",
		"grill_probe_enabled" : [1,	0, 0],
		"grill_probes": {
			"grill_probe1": {
				"name": "Grill Probe 1"
			},
			"grill_probe2": {
				"name": "Grill Probe 2"
			},
			"grill_probe3": {
				"name": "Avg Grill Probes"
			}
		}
  	}
	
	# Add items to 'probe_settings' 
	settings['probe_settings']['probe_options'] = [
      "ADC0",
      "ADC1",
      "ADC2",
      "ADC3"
    ]
	settings['probe_settings']['probe_sources'] = [
      "ADC0",
      "ADC1",
      "ADC2",
      "ADC3"
    ]
	settings['probe_settings']['probes_enabled'] = [
      1,
      1,
      1
    ]

	# Add 'probe_types' (Copy from probe_settings)
	settings['probe_types'] = {
    "grill1type": "PT-1000-OEM",
    "grill2type": "TWPS00",
    "probe1type": "TWPS00",
    "probe2type": "TWPS00"
  	}

	current = read_current()
	grill1_key = list(current['P'].keys())[0]

	probe1_key = ''
	if len(list(current['F'].keys())) > 0:
		probe1_key = list(current['F'].keys())[0]

	probe2_key = ''
	if len(list(current['F'].keys())) > 1:
		probe2_key = list(current['F'].keys())[1] 

	grill2_key = ''
	if len(list(current['F'].keys())) > 2:
		grill2_key = list(current['F'].keys())[2]

	for item in settings['probe_settings']['probe_map']['probe_info']:
		if item['label'] == grill1_key:
			settings['probe_types']['grill1type'] = item['profile']['id']
		if item['label'] == probe1_key:
			settings['probe_types']['probe1type'] = item['profile']['id']
		if item['label'] == probe2_key:
			settings['probe_types']['probe2type'] = item['profile']['id']
		if item['label'] == grill2_key:
			settings['probe_types']['grill2type'] = item['profile']['id']

	return settings

def hack_write_settings(settings):
    # Move notification settings into ['notify_services']
	settings['notify_services'] = {}
	for key in ['apprise', 'ifttt', 'influxdb', 'onesignal', 'pushbullet', 'pushover']:
		settings['notify_services'][key] = settings[key]
		settings.pop(key)

	# Remove 'grill_probe_settings'
	settings.pop('grill_probe_settings')
	
	# Remove 'probe_settings' items 
	settings['probe_settings'].pop('probe_options')
	settings['probe_settings'].pop('probe_sources')
	settings['probe_settings'].pop('probes_enabled')

	# Remove 'probe_types' item
	settings.pop('probe_types') 

	write_settings(settings)

def hack_read_control():
	control = read_control()
	current = read_current()
	grill1_key = list(current['P'].keys())[0]

	probe1_key = ''
	if len(list(current['F'].keys())) > 0:
		probe1_key = list(current['F'].keys())[0]

	probe2_key = ''
	if len(list(current['F'].keys())) > 1:
		probe2_key = list(current['F'].keys())[1] 

	grill2_key = ''
	if len(list(current['F'].keys())) > 2:
		grill2_key = list(current['F'].keys())[2]
	
	notify_data = control['notify_data'].copy()
	
	control['setpoints'] = {
		'grill' : control['primary_setpoint'],
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

	control['probe_titles'] = {
		'grill_title' : 'Grill',
		'probe1_title' : 'Probe 1',
		'probe2_title' : 'Probe 2',
	}

	for item in notify_data: 
		if item['label'] == grill1_key:
			control['setpoints']['grill_notify'] = item['target']
			control['notify_req']['grill'] = item['req']
			control['probe_titles']['grill_title'] = item['name']
		if item['label'] == probe1_key:
			control['setpoints']['probe1'] = item['target']
			control['notify_req']['probe1'] = item['req']
			control['notify_data']['p1_shutdown'] = item['shutdown']
			control['notify_data']['p1_keep_warm'] = item['keep_warm']
			control['probe_titles']['probe1_title'] = item['name']
		if item['label'] == probe2_key:
			control['setpoints']['probe2'] = item['target']
			control['notify_req']['probe2'] = item['req']
			control['notify_data']['p2_shutdown'] = item['shutdown']
			control['notify_data']['p2_keep_warm'] = item['keep_warm']
			control['probe_titles']['probe2_title'] = item['name']
		if item['label'] == 'Timer':
			control['notify_req']['timer'] = item['req']
			control['notify_data']['timer_shutdown'] = item['shutdown']
			control['notify_data']['timer_keep_warm'] = item['keep_warm']
		if item['label'] == 'Hopper':
			control['notify_data']['hopper_low'] = item['req']

	return control 

def hack_write_control(control_in, direct_write=False, origin='unknown'):
	control_cur = read_control()
	current = read_current()
	control = control_in.copy() 

	control['notify_data'] = control_cur['notify_data']	 # Overwrite with new notify structure 

	control.pop('setpoints') # Not used in updated control
	control.pop('notify_req')  # Not used in updated control
	control.pop('probe_titles')  # Not used in updated control 

	# If you are changing the set point temperature while in Hold Mode, then you may need a direct write
	if (control_cur['mode'] == 'Hold') and (control_cur['primary_setpoint'] != control_in['setpoints']['grill']):
		direct_write=True
	# If you are changing from any mode to hold mode, then you may need a direct write 
	if (control_cur['mode'] != 'Hold') and (control['mode'] == 'Hold'):
		direct_write=True

	control['primary_setpoint'] = control_in['setpoints']['grill']

	grill1_key = list(current['P'].keys())[0]

	probe1_key = ''
	if len(list(current['F'].keys())) > 0:
		probe1_key = list(current['F'].keys())[0]

	probe2_key = ''
	if len(list(current['F'].keys())) > 1:
		probe2_key = list(current['F'].keys())[1] 

	for index, item in enumerate(control['notify_data']): 
		if item['label'] == grill1_key:
			control['notify_data'][index]['target'] = control_in['setpoints']['grill_notify']
			control['notify_data'][index]['req'] = control_in['notify_req']['grill']
		if item['label'] == probe1_key:
			control['notify_data'][index]['target'] = control_in['setpoints']['probe1']
			control['notify_data'][index]['req'] = control_in['notify_req']['probe1']
			control['notify_data'][index]['shutdown'] = control_in['notify_data']['p1_shutdown']
			control['notify_data'][index]['keep_warm'] = control_in['notify_data']['p1_keep_warm']
		if item['label'] == probe2_key:
			control['notify_data'][index]['target'] = control_in['setpoints']['probe2']
			control['notify_data'][index]['req'] = control_in['notify_req']['probe2']
			control['notify_data'][index]['shutdown'] = control_in['notify_data']['p2_shutdown']
			control['notify_data'][index]['keep_warm'] = control_in['notify_data']['p2_keep_warm']
		if item['label'] == 'Timer':
			control['notify_data'][index]['req'] = control_in['notify_req']['timer']
			control['notify_data'][index]['shutdown'] = control_in['notify_data']['timer_shutdown']
			control['notify_data'][index]['keep_warm'] = control_in['notify_data']['timer_keep_warm']
		if item['label'] == 'Hopper':
			control['notify_data'][index]['req'] = control_in['notify_data']['hopper_low']
	# Direct Write is required due to timing issues - however this may lead to some commands being missed during active modes.  
	write_control(control, direct_write=direct_write, origin=origin)

def hack_prepare_data(num_items=10, reduce=True, data_points=60):
	# num_items: Number of items to store in the data blob
	settings = read_settings()
	units = settings['globals']['units']

	data_struct = read_history(num_items)

	unpacked_history = unpack_history(data_struct)

	list_length = len(unpacked_history['T']) # Length of list(s)

	data_blob = {}

	data_blob['label_time_list'] = unpacked_history['T']

	grill_key = list(unpacked_history['P'].keys())[0]
	data_blob['grill_temp_list'] = unpacked_history['P'][grill_key]
	data_blob['grill_settemp_list'] = unpacked_history['PSP']

	probe1_key = ''
	if len(list(unpacked_history['F'].keys())) > 0:
		probe1_key = list(unpacked_history['F'].keys())[0]
		data_blob['probe1_temp_list'] = unpacked_history['F'][probe1_key]
		data_blob['probe1_settemp_list'] = unpacked_history['NT'][probe1_key]
	else:
		data_blob['probe1_temp_list'] = []
		data_blob['probe1_settemp_list'] = []
		for index in range(list_length):
			data_blob['probe1_temp_list'].append(0)
			data_blob['probe1_settemp_list'].append(0)

	probe2_key = ''
	if len(list(unpacked_history['F'].keys())) > 1:
		probe2_key = list(unpacked_history['F'].keys())[1] 
		data_blob['probe2_temp_list'] = unpacked_history['F'][probe2_key]
		data_blob['probe2_settemp_list'] = unpacked_history['NT'][probe2_key]
	else:
		data_blob['probe2_temp_list'] = []
		data_blob['probe2_settemp_list'] = []
		for index in range(list_length):
			data_blob['probe2_temp_list'].append(0)
			data_blob['probe2_settemp_list'].append(0)

	if (list_length < num_items) and (list_length > 0):
		num_items = list_length

	if reduce and (num_items > data_points):
		step = int(num_items/data_points)
		temp_blob = data_blob.copy()
		data_blob = {}
		for key, value in temp_blob.items():
			for index in range(list_length - num_items, list_length, step):
				data_blob[key].append(temp_blob[key][index])

	if (list_length == 0):
		now = datetime.datetime.now()
		#time_now = now.strftime('%H:%M:%S')
		time_now = int(now.timestamp() * 1000)  # Use timestamp format (int) instead of H:M:S format in string
		for index in range(num_items):
			data_blob['label_time_list'].append(time_now)
			data_blob['grill_temp_list'].append(0)
			data_blob['grill_settemp_list'].append(0)
			data_blob['probe1_temp_list'].append(0)
			data_blob['probe1_settemp_list'].append(0)
			data_blob['probe2_temp_list'].append(0)
			data_blob['probe2_settemp_list'].append(0)

	return(data_blob)

def hack_read_current():
	current = read_current()
	current_out = [0, 0, 0]

	current_out[0] = current['P'][list(current['P'].keys())[0]]

	if len(list(current['F'].keys())) > 0:
		current_out[1] = current['F'][list(current['F'].keys())[0]]

	if len(list(current['F'].keys())) > 1:
		current_out[2] = current['F'][list(current['F'].keys())[1]]

	return current_out