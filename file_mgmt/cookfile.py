#!/usr/bin/env python3
'''
PiFire - File / Cookfile Functions
==================================

This file contains functions for file managing the coofile file format. 

'''

'''
Imported Modules
================
'''
import datetime
import os
import json
import zipfile 
import pathlib

from common import read_settings, read_history, generate_uuid, read_metrics, write_metrics, process_metrics, semantic_ver_to_list, epoch_to_time, unpack_history, default_probe_config
from file_mgmt.common import read_json_file_data, update_json_file_data

HISTORY_FOLDER = './history/'  # Path to historical cook files

'''
Functions
=========
'''
def _default_cookfilestruct():
	settings = read_settings()

	cookfilestruct = {}

	cookfilestruct['metadata'] = {
		'title' : '',
		'starttime' : '',
		'endtime' : '',
		'units' : settings['globals']['units'],
		'thumbnail' : '',  # UUID of the thumbnail for this cook file - found in assets
		'id' : generate_uuid(),
		'version' : settings['versions']['cookfile']  #  PiFire Cook File Version
	}
	
	cookfilestruct['graph_data'] = {}

	cookfilestruct['raw_data'] = []

	cookfilestruct['graph_labels'] = {}
	
	cookfilestruct['events'] = []

	cookfilestruct['comments'] = []

	cookfilestruct['assets'] = []

	return cookfilestruct

def create_cookfile(): 
	'''
	This function gathers all of the data from the previous cook
	from startup to stop mode, and saves this to a Cook File stored
	at ./history/

	The metrics and cook data are purged from memory, after stop mode is initiated.  
	'''
	#global cmdsts
	global HISTORY_FOLDER

	settings = read_settings()

	cook_file_struct = {}

	now = datetime.datetime.now()
	nowstring = now.strftime('%Y-%m-%d--%H%M')
	title = nowstring + '-CookFile'

	chart_data = prepare_chartdata(settings['history_page']['probe_config'], num_items=0, reduce=False, data_points=0)
	raw_data = read_history()

	if len(chart_data['time_labels']):
		starttime = chart_data['time_labels'][0]

		endtime = chart_data['time_labels'][-1]

		cook_file_struct = _default_cookfilestruct()

		cook_file_struct['metadata']['title'] = title
		cook_file_struct['metadata']['starttime'] = starttime
		cook_file_struct['metadata']['endtime'] = endtime

		cook_file_struct['graph_data'] = {
			'time_labels' : chart_data['time_labels'], 
			'chart_data' : chart_data['chart_data'], 
			'probe_mapper' : chart_data['probe_mapper']
		} 

		cook_file_struct['graph_labels'] = chart_data['graph_labels']

		cook_file_struct['raw_data'] = raw_data 

		cook_file_struct['events'] = process_metrics(read_metrics(all=True), augerrate=settings['globals']['augerrate'])

		# 1. Create all JSON data files
		files_list = ['metadata', 'graph_data', 'raw_data', 'graph_labels', 'events', 'comments', 'assets']
		if not os.path.exists(HISTORY_FOLDER):
			os.mkdir(HISTORY_FOLDER)
		os.mkdir(f'{HISTORY_FOLDER}{title}')  # Make temporary folder for all files
		for item in files_list:
			json_data_string = json.dumps(cook_file_struct[item], indent=2, sort_keys=True)
			filename = f'{HISTORY_FOLDER}{title}/{item}.json'
			with open(filename, 'w+') as cook_file:
				cook_file.write(json_data_string)
		
		# 2. Create empty data folder(s) & add default data 
		os.mkdir(f'{HISTORY_FOLDER}{title}/assets')
		os.mkdir(f'{HISTORY_FOLDER}{title}/assets/thumbs')
		#shutil.copy2('./static/img/pifire-cf-thumb.png', f'{HISTORY_FOLDER}{title}/assets/{thumbnail_UUID}.png')
		#shutil.copy2('./static/img/pifire-cf-thumb.png', f'{HISTORY_FOLDER}{title}/assets/thumbs/{thumbnail_UUID}.png')

		# 3. Create ZIP file of the folder 
		directory = pathlib.Path(f'{HISTORY_FOLDER}{title}/')
		filename = f'{HISTORY_FOLDER}{title}.pifire'

		with zipfile.ZipFile(filename, "w", zipfile.ZIP_DEFLATED) as archive:
			for file_path in directory.rglob("*"):
				archive.write(file_path, arcname=file_path.relative_to(directory))

		# 4. Cleanup temporary files
		command = f'rm -rf {HISTORY_FOLDER}{title}'
		os.system(command)

	# Delete Redis DB for history / current
	read_history(0, flushhistory=True)
	# Flush metrics DB for tracking certain metrics
	write_metrics(flush=True)

def read_cookfile(filename):
	'''
	Read FULL Cook File into Python Dictionary
	'''
	settings = read_settings()

	cook_file_struct = {}
	status = 'OK'
	json_types = ['metadata', 'graph_data', 'raw_data', 'graph_labels', 'events', 'comments', 'assets']
	for jsonfile in json_types:
		cook_file_struct[jsonfile], status = read_json_file_data(filename, jsonfile)
		if jsonfile == 'metadata':
			fileversion = semantic_ver_to_list(cook_file_struct['metadata']['version'])
			minfileversion = semantic_ver_to_list(settings['versions']['cookfile']) # Minimum file version to load assets
			if not ( (fileversion[0] >= minfileversion[0]) and (fileversion[1] >= minfileversion[1]) and (fileversion[2] >= minfileversion[2]) ):
				status = 'WARNING: Older cookfile version format! '
		if status != 'OK':
			break  # Exit loop and function, error string in status

	return(cook_file_struct, status)

def upgrade_cookfile(cookfilename, repair=False):
	settings = read_settings()

	status = 'OK'
	cookfilestruct = _default_cookfilestruct()
	current_version = [0, 0, 0]

	json_types = ['metadata', 'raw_data', 'graph_data', 'graph_labels', 'events', 'comments', 'assets']
	for jsonfile in json_types:
		jsondata, status = read_json_file_data(cookfilename, jsonfile, unpackassets=False)
		if status != 'OK' and jsonfile == 'raw_data':
			cookfilestruct['raw_data'] = []
			graph_data, status = read_json_file_data(cookfilename, 'graph_data', unpackassets=False)
			list_length = len(graph_data['time_labels'])
			jsondata = [] 
			# Build out Raw Data Set
			for index in range(0, list_length):
				list_item = {
					'T' : graph_data['time_labels'][index], 
					'P' : {
						'grill1' : graph_data['grill1_temp'][index]
					},
					'PSP' : graph_data['grill1_setpoint'][index],
					'F' : {
						'probe1' : graph_data['probe1_temp'][index],
						'probe2' : graph_data['probe2_temp'][index],
					}, 
					'NT' : {
						'grill1' : graph_data['grill1_setpoint'][index],
						'probe1' : graph_data['probe1_setpoint'][index],
						'probe2' : graph_data['probe2_setpoint'][index]
					},
					'AUX' : {}
				}
				jsondata.append(list_item)
			cookfilestruct[jsonfile] = jsondata
		elif status != 'OK':
			break  # Exit loop and function, error string in status
		elif jsonfile == 'metadata':
			# Update to the latest cookfile version
			current_version = semantic_ver_to_list(jsondata['version'])
			jsondata['version'] = settings['versions']['cookfile']
			cookfilestruct[jsonfile].update(jsondata)
		elif jsonfile == 'comments':
			# Add assets list to each comment v1.0 -> v1.0.1+ 
			for index, comment in enumerate(jsondata):
				if not 'assets' in comment.keys():
					jsondata[index]['assets'] = []
			cookfilestruct[jsonfile] = jsondata
		elif jsonfile == 'assets' and jsondata == {}:
			# Some version 1.0 files may have an empty assets file with a dictionary instead of a list
			cookfilestruct[jsonfile] = []
		elif jsonfile == 'graph_labels':
			# Convert prior to v1.5.0 versions of cookfile to new graph label format
			if current_version[0] <= 1 and current_version[1] < 5:
				cookfilestruct[jsonfile] = {
					'primarysp' : {
						'grill1' : jsondata['grill1_label'] + ' Set Point'
					}, 
					'probes' : {
						'grill1' : jsondata['grill1_label'], 
						'probe1' : jsondata['probe1_label'],
						'probe2' : jsondata['probe2_label']
					},
					'targets' : {
						'grill1' : jsondata['grill1_label'] + ' Target', 
						'probe1' : jsondata['probe1_label'] + ' Target',
						'probe2' : jsondata['probe2_label'] + ' Target'
					}
				}
			else: 
				cookfilestruct[jsonfile] = jsondata
		elif jsonfile == 'graph_data':
			# Convert prior to v1.5.0 versions of cookfile to new graph label format
			if current_version[0] <= 1 and current_version[1] < 5:
				probe_info = {
					'probe_settings' : {
						'probe_map': {
							'probe_info' : [
								{
									'name' : 'Grill',
									'label' : 'grill1',
									'type' : 'Primary', 
									'enabled' : True 
								},
								{
									'name' : 'Probe 1',
									'label' : 'probe1',
									'type' : 'Food', 
									'enabled' : True 
								},
								{
									'name' : 'Probe 2',
									'label' : 'probe2',
									'type' : 'Food', 
									'enabled' : True 
								},
							]
						}
					}
				}
				probe_config = default_probe_config(probe_info)
				history = {
					'T' : jsondata['time_labels'],
					'PSP' : jsondata['grill1_setpoint'], 
					'P' : {
						'grill1' : jsondata['grill1_temp'], 
					}, 
					'F' : {
						'probe1' : jsondata['probe1_temp'],
						'probe2' : jsondata['probe2_temp'],
					}, 
					'NT' : {
						'grill1' : jsondata['grill1_setpoint'],
						'probe1' : jsondata['probe1_setpoint'],
						'probe2' : jsondata['probe2_setpoint'],
					}
				}
				cookfilestruct[jsonfile] = prepare_chartdata(probe_config, num_items=0, reduce=False, history=history)
			else:
				cookfilestruct[jsonfile] = jsondata
		else:
			cookfilestruct[jsonfile] = jsondata
		# Update the original file with new data
		update_json_file_data(cookfilestruct[jsonfile], cookfilename, jsonfile)

	return(cookfilestruct, status)

def prepare_chartdata(probe_config, chart_info={}, num_items=10, reduce=True, data_points=60, history=None):
	''' Build Probe Mapper and Chart Data Struct '''
	chart_data = []

	if chart_info == {}:
		chart_info = {
			'label' : '',
			'fill': False,
			'lineTension': 0.1,
			'backgroundColor': '',
			'borderColor': '',
			'borderCapStyle': 'butt',
			'borderDash': [],
			'borderDashOffset': 0.0,
			'borderJoinStyle': 'miter',
			'pointBorderColor': '',
			'pointBackgroundColor': '#fff',
			'pointBorderWidth': 1,
			'pointHoverRadius': 10,
			'pointHoverBackgroundColor': '',
			'pointHoverBorderColor': '',
			'pointHoverBorderWidth': 2,
			'pointRadius': 1,
			'pointHitRadius': 10,
			'pointStyle': 'line',
			'data': [],
			'spanGaps': False,
			'hidden': False
		}

	index = 0
	probe_mapper = { 'probes' : {}, 'targets' : {}, 'primarysp' : {} }
	graph_labels = { 'probes' : {}, 'targets' : {}, 'primarysp' : {} }

	for probe in probe_config:
		''' First Object is Temperature Data for Probe '''
		chart_obj = chart_info.copy()
		chart_obj['label'] = probe_config[probe]['name']
		chart_obj['backgroundColor'] = probe_config[probe]['bg_color']
		chart_obj['borderColor'] = probe_config[probe]['line_color']
		chart_obj['borderDash'] = []
		chart_obj['pointBorderColor'] = probe_config[probe]['line_color']
		chart_obj['pointHoverBackgroundColor'] = probe_config[probe]['bg_color']
		chart_obj['pointHoverBorderColor'] = probe_config[probe]['line_color']
		chart_obj['hidden'] = not probe_config[probe]['enabled']
		chart_obj['data'] = []
		chart_data.append(chart_obj)
		probe_mapper['probes'][probe] = index 
		graph_labels['probes'][probe] = probe_config[probe]['name']
		''' Second Object is the Target Temperature Data for Probe '''
		index += 1
		chart_obj = chart_info.copy()
		chart_obj['label'] = probe_config[probe]['name'] + ' Target'
		chart_obj['backgroundColor'] = probe_config[probe]['bg_color_target']
		chart_obj['borderColor'] = probe_config[probe]['line_color_target']
		chart_obj['borderDash'] = [8, 4]
		chart_obj['pointBorderColor'] = probe_config[probe]['line_color_target']
		chart_obj['pointHoverBackgroundColor'] = probe_config[probe]['bg_color_target']
		chart_obj['pointHoverBorderColor'] = probe_config[probe]['line_color_target']
		chart_obj['hidden'] = not probe_config[probe]['enabled']
		chart_obj['data'] = []
		chart_data.append(chart_obj)
		probe_mapper['targets'][probe] = index
		graph_labels['targets'][probe] = probe_config[probe]['name'] + ' Target'
		''' Third Object is the Primary Setpoint Temperature Data for Probe (if it is primary) '''
		if probe_config[probe]['type'] == 'Primary':
			index += 1
			chart_obj = chart_info.copy()
			chart_obj['label'] = probe_config[probe]['name'] + ' Set Point'
			chart_obj['backgroundColor'] = probe_config[probe]['bg_color_setpoint']
			chart_obj['borderColor'] = probe_config[probe]['line_color_setpoint']
			chart_obj['borderDash'] = [8, 4]
			chart_obj['pointBorderColor'] = probe_config[probe]['line_color_setpoint']
			chart_obj['pointHoverBackgroundColor'] = probe_config[probe]['bg_color_setpoint']
			chart_obj['pointHoverBorderColor'] = probe_config[probe]['line_color_setpoint']
			chart_obj['hidden'] = not probe_config[probe]['enabled']
			chart_obj['data'] = []
			chart_data.append(chart_obj)
			probe_mapper['primarysp'][probe] = index
			graph_labels['primarysp'][probe] = probe_config[probe]['name'] + ' Set Point'
		''' Increment Index '''
		index += 1

	''' Populate history data into chart data '''
	if history == None:
		history = read_history(num_items)
		if history !=[]: 
			history = unpack_history(history)
			list_length = len(history['T']) # Length of list(s)
		else: 
			list_length = 0
	else: 
		list_length = len(history['T']) # Length of list(s)

	if (list_length < num_items) and (list_length > 0):
		num_items = list_length

	if reduce and (num_items > data_points):
		step = int(num_items/data_points)
	else:
		step = 1

	if num_items == 0: 
		num_items = list_length

	time_labels = []

	if (list_length > 0):
		# Build all lists from file data
		for index in range(list_length - num_items, list_length, step):
			for key, value in history['P'].items():
				chart_data[probe_mapper['probes'][key]]['data'].append(history['P'][key][index])
			for key, value in history['F'].items():
				chart_data[probe_mapper['probes'][key]]['data'].append(history['F'][key][index])
			for key, value in history['NT'].items():
				chart_data[probe_mapper['targets'][key]]['data'].append(history['NT'][key][index])
			for key in probe_mapper['primarysp']: 
				chart_data[probe_mapper['primarysp'][key]]['data'].append(history['PSP'][index])
				break 

			time_labels.append(history['T'][index])
	else:
		now = datetime.datetime.now()
		time_now = int(now.timestamp() * 1000)  # Use timestamp format * 1000 for JavaScript usages
		time_labels.append(time_now)
		for key in probe_mapper['probes'].keys():
			chart_data[probe_mapper['probes'][key]]['data'].append(0)
		for key in probe_mapper['targets'].keys():
			chart_data[probe_mapper['targets'][key]]['data'].append(0)
		for key in probe_mapper['primarysp'].keys(): 
			chart_data[probe_mapper['primarysp'][key]]['data'].append(0)

	''' Create data structure to return '''
	data_blob = {
		'time_labels' : time_labels,
		'probe_mapper' : probe_mapper, 
		'chart_data' : chart_data, 
		'graph_labels' : graph_labels
	}

	return data_blob
