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

from common import read_settings, read_history, generate_uuid, read_metrics, write_metrics, process_metrics, semantic_ver_to_list, _epoch_to_time
from file_common import read_json_file_data, update_json_file_data

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
	
	cookfilestruct['graph_data'] = {
		"time_labels" : [], 
        "grill1_temp" : [],
        "probe1_temp" : [], 
        "probe2_temp" : [], 
        "grill1_setpoint" : [],
        "probe1_setpoint" : [], 
        "probe2_setpoint" : []
	}

	cookfilestruct['graph_labels'] = {
        "grill1_label" : "Grill", 
        "probe1_label" : "Probe 1", 
        "probe2_label" : "Probe 2"
    }
	
	cookfilestruct['events'] = []

	cookfilestruct['comments'] = []

	cookfilestruct['assets'] = []

	return cookfilestruct

def create_cookfile(historydata): 
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

	if len(historydata):
		starttime = json.loads(historydata[0])
		starttime = starttime['T']

		endtime = json.loads(historydata[-1])
		endtime = endtime['T']

		cook_file_struct = _default_cookfilestruct()

		cook_file_struct['metadata']['title'] = title
		cook_file_struct['metadata']['starttime'] = starttime
		cook_file_struct['metadata']['endtime'] = endtime

		standard_data_keys = ['T', 'GT1', 'GSP1', 'PT1', 'PSP1', 'PT2', 'PSP2']  # Standard Labels / Data To Export
		# Add any extended keys if they exists
		ext_keys = []
		for key in json.loads(historydata[0]).keys():
			if key not in standard_data_keys:
				ext_keys.append(key)
				cook_file_struct['graph_data'][key] = []

		# Unpack data from json to list
		for index in range(len(historydata)):
			datastruct = json.loads(historydata[index])
			cook_file_struct['graph_data']['time_labels'].append(datastruct['T'])
			cook_file_struct['graph_data']['grill1_temp'].append(datastruct['GT1'])
			cook_file_struct['graph_data']['probe1_temp'].append(datastruct['PT1'])
			cook_file_struct['graph_data']['probe2_temp'].append(datastruct['PT2'])
			cook_file_struct['graph_data']['grill1_setpoint'].append(datastruct['GSP1'])
			cook_file_struct['graph_data']['probe1_setpoint'].append(datastruct['PSP1'])
			cook_file_struct['graph_data']['probe2_setpoint'].append(datastruct['PSP2'])
			# Add any extended keys
			for key in ext_keys:
				cook_file_struct['graph_data'][key].append(datastruct[key])

		cook_file_struct['events'] = process_metrics(read_metrics(all=True), augerrate=settings['globals']['augerrate'])

		# 1. Create all JSON data files
		files_list = ['metadata', 'graph_data', 'graph_labels', 'events', 'comments', 'assets']
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
	json_types = ['metadata', 'graph_data', 'graph_labels', 'events', 'comments', 'assets']
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

def upgrade_cookfile(cookfilename):
	settings = read_settings()

	status = 'OK'
	cookfilestruct = _default_cookfilestruct()
	
	json_types = ['metadata', 'graph_data', 'graph_labels', 'events', 'comments', 'assets']
	for jsonfile in json_types:
		jsondata, status = read_json_file_data(cookfilename, jsonfile, unpackassets=False)
		if status != 'OK':
			break  # Exit loop and function, error string in status
		elif jsonfile == 'metadata':
			# Update to the latest cookfile version
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
			pass
		else:
			cookfilestruct[jsonfile] = jsondata
		# Update the original file with new data
		update_json_file_data(cookfilestruct[jsonfile], cookfilename, jsonfile)

	return(cookfilestruct, status)


