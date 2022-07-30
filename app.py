#!/usr/bin/env python3

# *****************************************
# PiFire Web UI (Flask App)
# *****************************************
#
# Description: This script will start at boot, and start up the web user
#  interface.
#
# This script runs as a separate process from the control program
# implementation which handles interfacing and running I2C devices & GPIOs.
#
# *****************************************

from flask import Flask, request, abort, render_template, make_response, send_file, jsonify, redirect
from flask_mobility import Mobility
from flask_socketio import SocketIO
from flask_qrcode import QRcode
from io import BytesIO
from werkzeug.utils import secure_filename
from collections.abc import Mapping
import threading
import zipfile
from threading import Thread
from datetime import timedelta
from datetime import datetime
import time
import os
import json
import datetime
import math
from common import *  # Common Library for WebUI and Control Program
from updater import *  # Library for doing project updates from GitHub

BACKUPPATH = './backups/'  # Path to backups of settings.json, pelletdb.json
UPLOAD_FOLDER = BACKUPPATH  # Point uploads to the backup path
HISTORY_FOLDER = './history/'  # Path to historical cook files
ALLOWED_EXTENSIONS = {'json', 'pifire'}

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
QRcode(app)
Mobility(app)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['HISTORY_FOLDER'] = HISTORY_FOLDER

@app.route('/')
def index():
	global settings
	
	if settings['globals']['first_time_setup']:
		return redirect('/wizard/welcome')
	else: 
		return redirect('/dash')

@app.route('/dash')
def dash():
	global settings
	control = ReadControl()
	errors = ReadErrors()

	return render_template('dash.html', set_points=control['setpoints'], notify_req=control['notify_req'], probes_enabled=settings['probe_settings']['probes_enabled'], control=control, page_theme=settings['globals']['page_theme'], grill_name=settings['globals']['grill_name'], units=settings['globals']['units'], errors=errors)

@app.route('/dashdata')
def dashdata():
	global settings
	control = ReadControl()

	probes_enabled = settings['probe_settings']['probes_enabled']
	cur_probe_temps = []
	cur_probe_temps = ReadCurrent()

	return jsonify({ 'cur_probe_temps' : cur_probe_temps, 'probes_enabled' : probes_enabled, 'current_mode' : control['mode'], 'set_points' : control['setpoints'], 'notify_req' : control['notify_req'], 'splus' : control['s_plus'], 'splus_default' : settings['smoke_plus']['enabled'] })

@app.route('/hopperlevel')
def hopper_level():
	pelletdb = ReadPelletDB()
	cur_pellets_string = pelletdb['archive'][pelletdb['current']['pelletid']]['brand'] + ' ' + pelletdb['archive'][pelletdb['current']['pelletid']]['wood']
	return jsonify({ 'hopper_level' : pelletdb['current']['hopper_level'], 'cur_pellets' : cur_pellets_string })

@app.route('/timer', methods=['POST','GET'])
def timer():
	global settings 
	control = ReadControl() 

	if request.method == "GET":
		return jsonify({ 'start' : control['timer']['start'], 'paused' : control['timer']['paused'], 'end' : control['timer']['end'], 'shutdown': control['timer']['shutdown']})
	elif request.method == "POST": 
		if 'input' in request.form:
			if 'timer_start' == request.form['input']: 
				control['notify_req']['timer'] = True
				# If starting new timer
				if control['timer']['paused'] == 0:
					now = time.time()
					control['timer']['start'] = now
					if(('hoursInputRange' in request.form) and ('minsInputRange' in request.form)):
						seconds = int(request.form['hoursInputRange']) * 60 * 60
						seconds = seconds + int(request.form['minsInputRange']) * 60
						control['timer']['end'] = now + seconds
					else:
						control['timer']['end'] = now + 60
					if('shutdownTimer' in request.form):
						if(request.form['shutdownTimer'] == 'true'):
							control['notify_data']['timer_shutdown'] = True
						else: 
							control['notify_data']['timer_shutdown'] = False
					if('keepWarmTimer' in request.form):
						if(request.form['keepWarmTimer'] == 'true'):
							control['notify_data']['timer_keep_warm'] = True
						else:
							control['notify_data']['timer_keep_warm'] = False
					WriteLog('Timer started.  Ends at: ' + epoch_to_time(control['timer']['end']))
					WriteControl(control)
				else:	# If Timer was paused, restart with new end time.
					now = time.time()
					control['timer']['end'] = (control['timer']['end'] - control['timer']['paused']) + now
					control['timer']['paused'] = 0
					WriteLog('Timer unpaused.  Ends at: ' + epoch_to_time(control['timer']['end']))
					WriteControl(control)
			elif 'timer_pause' == request.form['input']:
				if control['timer']['start'] != 0:
					control['notify_req']['timer'] = False
					now = time.time()
					control['timer']['paused'] = now
					WriteLog('Timer paused.')
					WriteControl(control)
				else:
					control['notify_req']['timer'] = False
					control['timer']['start'] = 0
					control['timer']['end'] = 0
					control['timer']['paused'] = 0
					control['notify_data']['timer_shutdown'] = False
					control['notify_data']['timer_keep_warm'] = False
					WriteLog('Timer cleared.')
					WriteControl(control)
			elif 'timer_stop' == request.form['input']:
				control['notify_req']['timer'] = False
				control['timer']['start'] = 0
				control['timer']['end'] = 0
				control['timer']['paused'] = 0
				control['notify_data']['timer_shutdown'] = False
				control['notify_data']['timer_keep_warm'] = False
				WriteLog('Timer stopped.')
				WriteControl(control)
		return jsonify({'result':'success'})

@app.route('/history/<action>', methods=['POST','GET'])
@app.route('/history', methods=['POST','GET'])
def historypage(action=None):

	global settings
	control = ReadControl()

	# Grab list of Historical Cook Files
	dirfiles = os.listdir(HISTORY_FOLDER)
	cookfiles = []
	for file in dirfiles:
		if file.endswith('.pifire'):
			cookfiles.append(file)

	if (request.method == 'POST'):
		response = request.form
		if(action == 'cookfile'):
			if('delcookfile' in response):
				filename = './history/' + response["delcookfile"]
				os.remove(filename)
				return redirect('/history')
			if('opencookfile' in response):
				cookfilename = HISTORY_FOLDER + response['opencookfile']
				cookfilestruct, status = ReadCookFile(cookfilename)
				if(status == 'OK'):
					events = cookfilestruct['events']
					comments = cookfilestruct['comments']
					for comment in comments:
						comment['text'] = comment['text'].replace('\n', '<br>')
					metadata = cookfilestruct['metadata']
					metadata['starttime'] = epoch_to_time(metadata['starttime'] / 1000)
					metadata['endtime'] = epoch_to_time(metadata['endtime'] / 1000)
					labels = cookfilestruct['graph_labels']
					assets = cookfilestruct['assets']
					filenameonly = response['opencookfile']
					return render_template('cookfile.html', settings=settings, cookfilename=cookfilename, filenameonly=filenameonly, events=events, comments=comments, metadata=metadata, labels=labels, assets=assets, page_theme=settings['globals']['page_theme'], grill_name=settings['globals']['grill_name'])
			if('dlcookfile' in response):
				filename = './history/' + response['dlcookfile']
				return send_file(filename, as_attachment=True, max_age=0)

		if(action == 'setmins'):
			if('minutes' in response):
				if(response['minutes'] != ''):
					num_items = int(response['minutes']) * 20
					settings['history_page']['minutes'] = int(response['minutes'])
					WriteSettings(settings)

		elif(action == 'clear'):
			if('clearhistory' in response):
				if(response['clearhistory'] == 'true'):
					WriteLog('Clearing History Log.')
					ReadHistory(0, flushhistory=True)

	elif (request.method == 'GET') and (action == 'export'):
		exportfilename = prepare_graph_csv()
		return send_file(exportfilename, as_attachment=True, max_age=0)

	num_items = settings['history_page']['minutes'] * 20
	probes_enabled = settings['probe_settings']['probes_enabled']

	data_blob = {}
	data_blob = prepare_data(num_items, True, settings['history_page']['datapoints'])

	autorefresh = settings['history_page']['autorefresh']
	if control['mode'] == 'Stop':
		autorefresh = 'off'

	# Calculate Displayed Start Time
	displayed_starttime = time.time() - (settings['history_page']['minutes'] * 60)
	annotations = prepare_annotations(displayed_starttime)

	return render_template('history.html', control=control, grill_temp_list=data_blob['grill_temp_list'], grill_settemp_list=data_blob['grill_settemp_list'], probe1_temp_list=data_blob['probe1_temp_list'], probe1_settemp_list=data_blob['probe1_settemp_list'], probe2_temp_list=data_blob['probe2_temp_list'], probe2_settemp_list=data_blob['probe2_settemp_list'], label_time_list=data_blob['label_time_list'], probes_enabled=probes_enabled, num_mins=settings['history_page']['minutes'], num_datapoints=settings['history_page']['datapoints'], autorefresh=autorefresh, annotations=annotations, cookfiles=cookfiles, page_theme=settings['globals']['page_theme'], grill_name=settings['globals']['grill_name'])

@app.route('/historyupdate/<action>', methods=['POST','GET'])    
@app.route('/historyupdate')
def historyupdate(action=None):
	global settings

	control = ReadControl()
	if(action == 'stream'):
		# GET - Read current temperatures and set points for history streaming 
		if control['mode'] == 'Stop':
			set_temps = [0,0,0]
			cur_probe_temps = [0,0,0]
		else:
			set_temps = control['setpoints']
			set_temps[0] = control['setpoints']['grill']
			set_temps[1] = control['setpoints']['probe1']
			set_temps[2] = control['setpoints']['probe2']
			cur_probe_temps = []
			cur_probe_temps = ReadCurrent()

		# Calculate Displayed Start Time
		displayed_starttime = time.time() - (settings['history_page']['minutes'] * 60)
		annotations = prepare_annotations(displayed_starttime)

		json_data = { 
			'probe0_temp' : int(float(cur_probe_temps[0])), 
			'probe0_settemp' : set_temps[0], 
			'probe1_temp' : int(float(cur_probe_temps[1])), 
			'probe1_settemp' : set_temps[1], 
			'probe2_temp' : int(float(cur_probe_temps[2])), 
			'probe2_settemp' : set_temps[2],
			'annotations' : annotations,
			'mode' : control['mode']
		}
		return jsonify(json_data)

	elif(action == 'refresh'):
		# POST - Get number of minutes into the history to refresh the history chart
		requestjson = request.json 
		if('num_mins' in requestjson):
			data_blob = {}
			num_items = int(requestjson['num_mins']) * 20  # Calculate number of items requested 
			settings['history_page']['minutes'] = int(requestjson['num_mins'])
			WriteSettings(settings)
			data_blob = prepare_data(num_items, True, settings['history_page']['datapoints'])

			# Calculate Displayed Start Time
			displayed_starttime = time.time() - (settings['history_page']['minutes'] * 60)
			annotations = prepare_annotations(displayed_starttime)

			json_data = { 
				'grill_temp_list' : data_blob['grill_temp_list'],
				'grill_settemp_list' : data_blob['grill_settemp_list'],
				'probe1_temp_list' : data_blob['probe1_temp_list'],
				'probe1_settemp_list' : data_blob['probe1_settemp_list'],
				'probe2_temp_list' : data_blob['probe2_temp_list'],
				'probe2_settemp_list' : data_blob['probe2_settemp_list'],
				'label_time_list' : data_blob['label_time_list'], 
				'annotations' : annotations, 
				'mode' : control['mode']
			}
			return jsonify(json_data)
	return jsonify({'status' : 'ERROR'})

@app.route('/cookfiledata', methods=['POST', 'GET'])
def cookfiledata(action=None):
	global settings 
	
	if(request.method == 'POST') and ('json' in request.content_type):
		requestjson = request.json
		if('full_graph' in requestjson):
			filename = requestjson['filename']
			cookfiledata, status = ReadCookFile(filename)

			if(status == 'OK'):
				annotations = prepare_annotations(0, cookfiledata['events'])

				json_data = { 
					'GT1_label' : cookfiledata['graph_labels']['grill1_label'],
					'GSP1_label' : cookfiledata['graph_labels']['grill1_label'] + " SetPoint",
					'PT1_label' : cookfiledata['graph_labels']['probe1_label'],
					'PSP1_label' : cookfiledata['graph_labels']['probe1_label'] + " SetPoint",
					'PT2_label' : cookfiledata['graph_labels']['probe2_label'],
					'PSP2_label' : cookfiledata['graph_labels']['probe2_label'] + " SetPoint",
					'GT1_data' : cookfiledata['graph_data']['grill1_temp'], 
					'GSP1_data' : cookfiledata['graph_data']['grill1_setpoint'], 
					'PT1_data' : cookfiledata['graph_data']['probe1_temp'], 
					'PT2_data' : cookfiledata['graph_data']['probe2_temp'], 
					'PSP1_data' : cookfiledata['graph_data']['probe1_setpoint'],
					'PSP2_data' : cookfiledata['graph_data']['probe2_setpoint'],
					'time_labels' : cookfiledata['graph_data']['time_labels'],
					'annotations' : annotations
				}
				return jsonify(json_data)
		
		if('getTitles' in requestjson):
			# Grab list of Historical Cook Files
			dirfiles = os.listdir(HISTORY_FOLDER)
			cookfiles = []
			for file in dirfiles:
				if file.endswith('.pifire'):
					cookfiles.append(file)

			cookfiletitles = []
			for file in cookfiles:
				filename = HISTORY_FOLDER + file
				cookfiledata, status = ReadCFJSONData(filename, 'metadata')
				if(status == 'OK'):
					cookfiletitles.append({'filename' : file, 'title' : cookfiledata['title']})
				else:
					cookfiletitles.append({'filename' : file, 'title' : 'ERROR'})
			return jsonify(cookfiletitles)

	if(request.method == 'POST') and ('form' in request.content_type):
		requestform = request.form 
		if('dl_cookfile' in requestform):
			# Download the full JSON Cook File Locally
			filename = requestform['dl_cookfile']
			return send_file(filename, as_attachment=True, max_age=0)

		if('dl_eventfile' in requestform):
			filename = requestform['dl_eventfile']
			cookfiledata, status = ReadCookFile(filename)
			if(status == 'OK'):
				csvfilename = prepare_metrics_csv(cookfiledata['events'], filename)
				return send_file(csvfilename, as_attachment=True, max_age=0)

		if('dl_graphfile' in requestform):
			# Download CSV of the Graph Data Only
			filename = requestform['dl_graphfile']
			cookfiledata, status = ReadCookFile(filename)
			if(status == 'OK'):
				csvfilename = prepare_graph_csv(cookfiledata['graph_data'], cookfiledata['graph_labels'], filename)
				return send_file(csvfilename, as_attachment=True, max_age=0)

		if('ulcookfilereq' in requestform):
			# Assume we have request.files and localfile in response
			remotefile = request.files['ulcookfile']
			
			if (remotefile.filename != ''):
				# If the user does not select a file, the browser submits an
				# empty file without a filename.
				if remotefile and allowed_file(remotefile.filename):
					filename = secure_filename(remotefile.filename)
					remotefile.save(os.path.join(app.config['HISTORY_FOLDER'], filename))
				else:
					print('Disallowed File Upload.')
				return redirect('/history')

	print('Something unexpected has happened.')	
	return jsonify({'result' : 'ERROR'})

@app.route('/updatecookfile', methods=['POST','GET'])
def updatecookdata(action=None):
	global settings 

	if(request.method == 'POST'):
		requestjson = request.json 
		if('comments' in requestjson):
			filename = requestjson['filename']
			cookfiledata, status = ReadCFJSONData(filename, 'comments')

			if('commentnew' in requestjson):
				now = datetime.datetime.now()
				comment_struct = {}
				comment_struct['text'] = requestjson['commentnew']
				comment_struct['id'] = generateUUID()
				comment_struct['edited'] = ''
				comment_struct['date'] = now.strftime('%Y-%m-%d')
				comment_struct['time'] = now.strftime('%H:%M')
				cookfiledata.append(comment_struct)
				result = UpdateCookFile(cookfiledata, filename, 'comments')
				if(result == 'OK'):
					return jsonify({'result' : 'OK', 'newcommentid' : comment_struct['id'], 'newcommentdt': comment_struct['date'] + ' ' + comment_struct['time']})
			if('delcomment' in requestjson):
				for item in cookfiledata:
					if item['id'] == requestjson['delcomment']:
						cookfiledata.remove(item)
						result = UpdateCookFile(cookfiledata, filename, 'comments')
						if(result == 'OK'):
							return jsonify({'result' : 'OK'})
			if('editcomment' in requestjson):
				for item in cookfiledata:
					if item['id'] == requestjson['editcomment']:
						return jsonify({'result' : 'OK', 'text' : item['text']})
			if('savecomment' in requestjson):
				for item in cookfiledata:
					if item['id'] == requestjson['savecomment']:
						now = datetime.datetime.now()
						item['text'] = requestjson['text']
						item['edited'] = now.strftime('%Y-%m-%d %H:%M')
						result = UpdateCookFile(cookfiledata, filename, 'comments')
						if(result == 'OK'):
							return jsonify({'result' : 'OK', 'text' : item['text'].replace('\n', '<br>'), 'edited' : item['edited'], 'datetime' : item['date'] + ' ' + item['time']})
		
		if('metadata' in requestjson):
			filename = requestjson['filename']
			cookfiledata, status = ReadCFJSONData(filename, 'metadata')
			if(status == 'OK'):
				if('editTitle' in requestjson):
					cookfiledata['title'] = requestjson['editTitle']
					result = UpdateCookFile(cookfiledata, filename, 'metadata')
					if(result == 'OK'):
						return jsonify({'result' : 'OK'})
					else: 
						print(f'Result: {result}')
		
		if('graph_labels' in requestjson):
			filename = requestjson['filename']
			cookfiledata, status = ReadCFJSONData(filename, 'graph_labels')
			if(status == 'OK'):
				if('grill1_label' in requestjson):
					cookfiledata['grill1_label'] = requestjson['grill1_label']
					result = UpdateCookFile(cookfiledata, filename, 'graph_labels')
					if(result == 'OK'):
						return jsonify({'result' : 'OK'})
				if('probe1_label' in requestjson):
					cookfiledata['probe1_label'] = requestjson['probe1_label']
					result = UpdateCookFile(cookfiledata, filename, 'graph_labels')
					if(result == 'OK'):
						return jsonify({'result' : 'OK'})
				if('probe2_label' in requestjson):
					cookfiledata['probe2_label'] = requestjson['probe2_label']
					result = UpdateCookFile(cookfiledata, filename, 'graph_labels')
					if(result == 'OK'):
						return jsonify({'result' : 'OK'})
			else:
				print(f'ERROR: {status}')

	return jsonify({'result' : 'ERROR'})
	

@app.route('/tuning/<action>', methods=['POST','GET'])
@app.route('/tuning', methods=['POST','GET'])
def tuningpage(action=None):

	global settings
	control = ReadControl()

	if(control['mode'] == 'Stop'): 
		alert = 'Warning!  Grill must be in an active mode to perform tuning (i.e. Monitor Mode, Smoke Mode, Hold Mode, etc.)'
	else: 
		alert = ''

	pagectrl = {}

	pagectrl['refresh'] = 'off'
	pagectrl['selected'] = 'none'
	pagectrl['showcalc'] = 'false'
	pagectrl['low_trvalue'] = ''
	pagectrl['med_trvalue'] = ''
	pagectrl['high_trvalue'] = ''
	pagectrl['low_tempvalue'] = ''
	pagectrl['med_tempvalue'] = ''
	pagectrl['high_tempvalue'] = ''

	if (request.method == 'POST'):
		response = request.form
		if('probe_select' in response):
			pagectrl['selected'] = response['probe_select']
			pagectrl['refresh'] = 'on'
			control['tuning_mode'] = True  # Enable tuning mode
			WriteControl(control)

			if(('pause' in response)):
				if(response['low_trvalue'] != ''):
					pagectrl['low_trvalue'] = response['low_trvalue']
				if(response['med_trvalue'] != ''):
					pagectrl['med_trvalue'] = response['med_trvalue']
				if(response['high_trvalue'] != ''):
					pagectrl['high_trvalue'] = response['high_trvalue']

				if(response['low_tempvalue'] != ''):
					pagectrl['low_tempvalue'] = response['low_tempvalue']
				if(response['med_tempvalue'] != ''):
					pagectrl['med_tempvalue'] = response['med_tempvalue']
				if(response['high_tempvalue'] != ''):
					pagectrl['high_tempvalue'] = response['high_tempvalue']

				pagectrl['refresh'] = 'off'	
				control['tuning_mode'] = False  # Disable tuning mode while paused
				WriteControl(control)

			elif(('save' in response)):
				if(response['low_trvalue'] != ''):
					pagectrl['low_trvalue'] = response['low_trvalue']
				if(response['med_trvalue'] != ''):
					pagectrl['med_trvalue'] = response['med_trvalue']
				if(response['high_trvalue'] != ''):
					pagectrl['high_trvalue'] = response['high_trvalue']

				if(response['low_tempvalue'] != ''):
					pagectrl['low_tempvalue'] = response['low_tempvalue']
				if(response['med_tempvalue'] != ''):
					pagectrl['med_tempvalue'] = response['med_tempvalue']
				if(response['high_tempvalue'] != ''):
					pagectrl['high_tempvalue'] = response['high_tempvalue']

				if(pagectrl['low_tempvalue'] != '') and (pagectrl['med_tempvalue'] != '') and (pagectrl['high_tempvalue'] != ''):
					pagectrl['refresh'] = 'off'
					control['tuning_mode'] = False  # Disable tuning mode when complete
					WriteControl(control)
					pagectrl['showcalc'] = 'true'
					a, b, c = calc_shh_coefficients(int(pagectrl['low_tempvalue']), int(pagectrl['med_tempvalue']), int(pagectrl['high_tempvalue']), int(pagectrl['low_trvalue']), int(pagectrl['med_trvalue']), int(pagectrl['high_trvalue']))
					pagectrl['a'] = a
					pagectrl['b'] = b
					pagectrl['c'] = c
					
					pagectrl['templist'] = ''
					pagectrl['trlist'] = ''

					range_size = abs(int(pagectrl['low_trvalue']) - int(pagectrl['high_trvalue']))
					range_step = int(range_size / 20)

					if(int(pagectrl['low_trvalue']) < int(pagectrl['high_trvalue'])): 
						low_tr_range = int(int(pagectrl['low_trvalue']) - (range_size * 0.05)) # Add 5% to the resistance at the low temperature side
						high_tr_range = int(int(pagectrl['high_trvalue']) + (range_size * 0.05)) # Add 5% to the resistance at the high temperature side
						high_tr_range, low_tr_range = low_tr_range, high_tr_range # Swap Tr values for the loop below, so that we start with a low value and go high
						# Swapped Value Case (i.e. Low Temp = Low Resistance)
						for index in range(high_tr_range, low_tr_range, range_step):
							if(index == high_tr_range):
								pagectrl['trlist'] = str(index)
								pagectrl['templist'] = str(tr_to_temp(index, a, b, c))
							else:
								pagectrl['trlist'] = str(index) + ', ' + pagectrl['trlist']
								pagectrl['templist'] = str(tr_to_temp(index, a, b, c)) + ', ' + pagectrl['templist']
					else:
						low_tr_range = int(int(pagectrl['low_trvalue']) + (range_size * 0.05)) # Add 5% to the resistance at the low temperature side
						high_tr_range = int(int(pagectrl['high_trvalue']) - (range_size * 0.05)) # Add 5% to the resistance at the high temperature side
						# Normal Value Case (i.e. Low Temp = High Resistance)
						for index in range(high_tr_range, low_tr_range, range_step):
							if(index == high_tr_range):
								pagectrl['trlist'] = str(index)
								pagectrl['templist'] = str(tr_to_temp(index, a, b, c))
							else:
								pagectrl['trlist'] += ', ' + str(index)
								pagectrl['templist'] += ', ' + str(tr_to_temp(index, a, b, c))
				else:
					pagectrl['refresh'] = 'on'
					control['tuning_mode'] = True  # Enaable tuning mode
					WriteControl(control)
	
	return render_template('tuning.html', control=control, settings=settings, pagectrl=pagectrl, page_theme=settings['globals']['page_theme'], grill_name=settings['globals']['grill_name'], alert=alert)

@app.route('/_grilltr', methods = ['GET'])
def grilltr():

	cur_probe_tr = ReadTr()
	tr = {}
	tr['trohms'] = cur_probe_tr[0]

	return json.dumps(tr)

@app.route('/_probe1tr', methods = ['GET'])
def probe1tr():

	cur_probe_tr = ReadTr()
	tr = {}
	tr['trohms'] = cur_probe_tr[1]

	return json.dumps(tr)

@app.route('/_probe2tr', methods = ['GET'])
def probe2tr():

	cur_probe_tr = ReadTr()
	tr = {}
	tr['trohms'] = cur_probe_tr[2]

	return json.dumps(tr)


@app.route('/events/<action>', methods=['POST','GET'])
@app.route('/events', methods=['POST','GET'])
def eventspage(action=None):
	# Show list of logged events and debug event list
	event_list, num_events = ReadLog()
	global settings

	return render_template('events.html', event_list=event_list, num_events=num_events, page_theme=settings['globals']['page_theme'], grill_name=settings['globals']['grill_name'])

@app.route('/pellets/<action>', methods=['POST','GET'])
@app.route('/pellets', methods=['POST','GET'])
def pelletsspage(action=None):
	# Pellet Management page
	global settings
	pelletdb = ReadPelletDB()
	
	event = {}

	event = {
		'type' : 'none',
		'text' : ''
	}

	if (request.method == 'POST' and action == 'loadprofile'):
		response = request.form
		if('load_profile' in response):
			if(response['load_profile'] == 'true'):
				pelletdb['current']['pelletid'] = response['load_id']
				# TODO: Implement Hopper Level Check
				pelletdb['current']['hopper_level'] = 100
				now = str(datetime.datetime.now())
				now = now[0:19] # Truncate the microseconds
				pelletdb['current']['date_loaded'] = now 
				pelletdb['log'][now] = response['load_id']
				WritePelletDB(pelletdb)
				event['type'] = 'updated'
				event['text'] = 'Successfully loaded profile and logged.'
	elif (request.method == 'GET' and action == 'hopperlevel'):
		control = ReadControl()
		control['hopper_check'] = True
		WriteControl(control)
	elif (request.method == 'POST' and action == 'editbrands'):
		response = request.form
		if('delBrand' in response):
			delBrand = response['delBrand']
			if(delBrand in pelletdb['brands']): 
				pelletdb['brands'].remove(delBrand)
				WritePelletDB(pelletdb)
				event['type'] = 'updated'
				event['text'] = delBrand + ' successfully deleted.'
			else: 
				event['type'] = 'error'
				event['text'] = delBrand + ' not found in pellet brands.'
		elif('newBrand' in response):
			newBrand = response['newBrand']
			if(newBrand in pelletdb['brands']):
				event['type'] = 'error'
				event['text'] = newBrand + ' already in pellet brands list.'
			else: 
				pelletdb['brands'].append(newBrand)
				WritePelletDB(pelletdb)
				event['type'] = 'updated'
				event['text'] = newBrand + ' successfully added.'

	elif (request.method == 'POST' and action == 'editwoods'):
		response = request.form
		if('delWood' in response):
			delWood = response['delWood']
			if(delWood in pelletdb['woods']): 
				pelletdb['woods'].remove(delWood)
				WritePelletDB(pelletdb)
				event['type'] = 'updated'
				event['text'] = delWood + ' successfully deleted.'
			else: 
				event['type'] = 'error'
				event['text'] = delWood + ' not found in pellet wood list.'
		elif('newWood' in response):
			newWood = response['newWood']
			if(newWood in pelletdb['woods']):
				event['type'] = 'error'
				event['text'] = newWood + ' already in pellet wood list.'
			else: 
				pelletdb['woods'].append(newWood)
				WritePelletDB(pelletdb)
				event['type'] = 'updated'
				event['text'] = newWood + ' successfully added.'

	elif (request.method == 'POST' and action == 'addprofile'):
		response = request.form
		if('addprofile' in response):
			profile_id = ''.join(filter(str.isalnum, str(datetime.datetime.now())))

			pelletdb['archive'][profile_id] = {
				'id' : profile_id,
				'brand' : response['brand_name'],
				'wood' : response['wood_type'],
				'rating' : int(response['rating']),
				'comments' : response['comments']
			}
			event['type'] = 'updated'
			event['text'] = 'Successfully added profile to database.'

			if(response['addprofile'] == 'add_load'):
				pelletdb['current']['pelletid'] = profile_id
				# TODO: Implement Hopper Level Check
				pelletdb['current']['hopper_level'] = 100
				now = str(datetime.datetime.now())
				now = now[0:19] # Truncate the microseconds
				pelletdb['current']['date_loaded'] = now 
				pelletdb['log'][now] = profile_id
				event['text'] = 'Successfully added profile and loaded.'

			WritePelletDB(pelletdb)

	elif (request.method == 'POST' and action == 'editprofile'):
		response = request.form
		if('editprofile' in response):
			profile_id = response['editprofile']
			pelletdb['archive'][profile_id]['brand'] = response['brand_name']
			pelletdb['archive'][profile_id]['wood'] = response['wood_type']
			pelletdb['archive'][profile_id]['rating'] = int(response['rating'])
			pelletdb['archive'][profile_id]['comments'] = response['comments']
			WritePelletDB(pelletdb)
			event['type'] = 'updated'
			event['text'] = 'Successfully updated ' + response['brand_name'] + ' ' + response['wood_type'] + ' profile in database.'
		elif('delete' in response):
			profile_id = response['delete']
			if(pelletdb['current']['pelletid'] == profile_id):
				event['type'] = 'error'
				event['text'] = 'Error: ' + response['brand_name'] + ' ' + response['wood_type'] + ' profile cannot be deleted if it is currently loaded.'
			else: 
				pelletdb['archive'].pop(profile_id) # Remove the profile from the archive
				for index in pelletdb['log']:  # Remove this profile ID for the logs
					if(pelletdb['log'][index] == profile_id):
						pelletdb['log'][index] = 'deleted'
				WritePelletDB(pelletdb)
				event['type'] = 'updated'
				event['text'] = 'Successfully deleted ' + response['brand_name'] + ' ' + response['wood_type'] + ' profile in database.'

	elif (request.method == 'POST' and action == 'deletelog'):
		response = request.form
		if('delLog' in response):
			delLog = response['delLog']
			if(delLog in pelletdb['log']):
				pelletdb['log'].pop(delLog)
				WritePelletDB(pelletdb)
				event['type'] = 'updated'
				event['text'] = 'Log successfully deleted.'
			else:
				event['type'] = 'error'
				event['text'] = 'Item not found in pellet log.'

	return render_template('pellets.html', alert=event, pelletdb=pelletdb, page_theme=settings['globals']['page_theme'], grill_name=settings['globals']['grill_name'])


@app.route('/recipes', methods=['POST','GET'])
def recipespage(action=None):

	# Show current recipes
	# Add a recipe
	# Delete a Recipe
	# Run a Recipe
	global settings

	return render_template('recipes.html', page_theme=settings['globals']['page_theme'], grill_name=settings['globals']['grill_name'])

@app.route('/settings/<action>', methods=['POST','GET'])
@app.route('/settings', methods=['POST','GET'])
def settingspage(action=None):

	global settings
	control = ReadControl()
	pelletdb = ReadPelletDB()

	event = {}

	event = {
		'type' : 'none',
		'text' : ''
	}

	if (request.method == 'POST') and (action == 'probes'):
		response = request.form

		if('grill1enable' in response):
			if(response['grill1enable'] == "0"):
				settings['probe_settings']['grill_probe_enabled'][0] = 0
			else:
				settings['probe_settings']['grill_probe_enabled'][0] = 1
		if('grill2enable' in response):
			if(response['grill2enable'] == "0"):
				settings['probe_settings']['grill_probe_enabled'][1] = 0
			else:
				settings['probe_settings']['grill_probe_enabled'][1] = 1
		if('probe1enable' in response):
			if(response['probe1enable'] == "0"):
				settings['probe_settings']['probes_enabled'][1] = 0
			else:
				settings['probe_settings']['probes_enabled'][1] = 1
		if('probe2enable' in response):
			if(response['probe2enable'] == "0"):
				settings['probe_settings']['probes_enabled'][2] = 0
			else:
				settings['probe_settings']['probes_enabled'][2] = 1
		if('grill_probes' in response):
			if(response['grill_probes'] == 'grill_probe1'):
				settings['grill_probe_settings']['grill_probe_enabled'][0] = 1
				settings['grill_probe_settings']['grill_probe_enabled'][1] = 0
				settings['grill_probe_settings']['grill_probe_enabled'][2] = 0
				settings['grill_probe_settings']['grill_probe'] = response['grill_probes']
				event['type'] = 'updated'
				event['text'] = 'Grill Probe selection updated. Settings saved.'
			elif(response['grill_probes'] == 'grill_probe2'):
				settings['grill_probe_settings']['grill_probe_enabled'][0] = 0
				settings['grill_probe_settings']['grill_probe_enabled'][1] = 1
				settings['grill_probe_settings']['grill_probe_enabled'][2] = 0
				settings['grill_probe_settings']['grill_probe'] = response['grill_probes']
				event['type'] = 'updated'
				event['text'] = 'Grill Probe selection updated. Settings saved.'
			elif(response['grill_probes'] == 'grill_probe3'):
				settings['grill_probe_settings']['grill_probe_enabled'][0] = 0
				settings['grill_probe_settings']['grill_probe_enabled'][1] = 0
				settings['grill_probe_settings']['grill_probe_enabled'][2] = 1
				settings['grill_probe_settings']['grill_probe'] = response['grill_probes']
				event['type'] = 'updated'
				event['text'] = 'Grill Probe selection updated. Settings saved.'
		if('grill_probe1_type' in response):
			if(response['grill_probe1_type'] != settings['probe_types']['grill1type']):
				settings['probe_types']['grill1type'] = response['grill_probe1_type']
				control['probe_profile_update'] = True
				event['type'] = 'updated'
				event['text'] = 'Probe type updated. Settings saved.'
		if('grill_probe2_type' in response):
			if(response['grill_probe2_type'] != settings['probe_types']['grill2type']):
				settings['probe_types']['grill2type'] = response['grill_probe2_type']
				control['probe_profile_update'] = True
				event['type'] = 'updated'
				event['text'] = 'Probe type updated. Settings saved.'
		if('probe1_type' in response):
			if(response['probe1_type'] != settings['probe_types']['probe1type']):
				settings['probe_types']['probe1type'] = response['probe1_type']
				control['probe_profile_update'] = True
				event['type'] = 'updated'
				event['text'] = 'Probe type updated. Settings saved.'
		if('probe2_type' in response):
			if(response['probe2_type'] != settings['probe_types']['probe2type']):
				settings['probe_types']['probe2type'] = response['probe2_type']
				control['probe_profile_update'] = True
				event['type'] = 'updated'
				event['text'] = 'Probe type updated. Settings saved.'

		# Take all settings and write them
		WriteSettings(settings)
		WriteControl(control)

	if (request.method == 'POST') and (action == 'notify'):
		response = request.form

		if('ifttt_enabled' in response):
			if(response['ifttt_enabled'] == 'on'):
				settings['ifttt']['enabled'] = True
		else:
			settings['ifttt']['enabled'] = False

		if('pushbullet_enabled' in response):
			if(response['pushbullet_enabled'] == 'on'):
				settings['pushbullet']['enabled'] = True
		else:
			settings['pushbullet']['enabled'] = False

		if('pushover_enabled' in response):
			if(response['pushover_enabled'] == 'on'):
				settings['pushover']['enabled'] = True
		else:
			settings['pushover']['enabled'] = False

		if('onesignal_enabled' in response):
			if(response['onesignal_enabled'] == 'on'):
				settings['onesignal']['enabled'] = True
		else:
			settings['onesignal']['enabled'] = False

		if('iftttapi' in response):
			if(response['iftttapi'] == "0") or (response['iftttapi'] == ''):
				settings['ifttt']['APIKey'] = ''
			else:
				settings['ifttt']['APIKey'] = response['iftttapi']

		if('pushover_apikey' in response):
			if((response['pushover_apikey'] == "0") or (response['pushover_apikey'] == '')) and (settings['pushover']['APIKey'] != ''):
				settings['pushover']['APIKey'] = ''
			elif(response['pushover_apikey'] != settings['pushover']['APIKey']):
				settings['pushover']['APIKey'] = response['pushover_apikey']

		if('pushover_userkeys' in response):
			if((response['pushover_userkeys'] == "0") or (response['pushover_userkeys'] == '')) and (settings['pushover']['UserKeys'] != ''):
				settings['pushover']['UserKeys'] = ''
			elif(response['pushover_userkeys'] != settings['pushover']['UserKeys']):
				settings['pushover']['UserKeys'] = response['pushover_userkeys']
		
		if('pushover_publicurl' in response):
			if((response['pushover_publicurl'] == "0") or (response['pushover_publicurl'] == '')) and (settings['pushover']['PublicURL'] != ''):
				settings['pushover']['PublicURL'] = ''
			elif(response['pushover_publicurl'] != settings['pushover']['PublicURL']):
				settings['pushover']['PublicURL'] = response['pushover_publicurl']

		if('pushbullet_apikey' in response):
			if((response['pushbullet_apikey'] == "0") or (response['pushbullet_apikey'] == '')) and (settings['pushbullet']['APIKey'] != ''):
				settings['pushbullet']['APIKey'] = ''
			elif(response['pushbullet_apikey'] != settings['pushbullet']['APIKey']):
				settings['pushbullet']['APIKey'] = response['pushbullet_apikey']
		
		if('pushbullet_publicurl' in response):
			if((response['pushbullet_publicurl'] == "0") or (response['pushbullet_publicurl'] == '')) and (settings['pushbullet']['PublicURL'] != ''):
				settings['pushbullet']['PublicURL'] = ''
			elif(response['pushbullet_publicurl'] != settings['pushbullet']['PublicURL']):
				settings['pushbullet']['PublicURL'] = response['pushbullet_publicurl']

		if 'influxdb_enabled' in response:
			settings['influxdb']['enabled'] = response['influxdb_enabled'] == 'on'
		if 'influxdb_url' in response:
			settings['influxdb']['url'] = response['influxdb_url']
		if 'influxdb_token' in response:
			settings['influxdb']['token'] = response['influxdb_token']
		if 'influxdb_org' in response:
			settings['influxdb']['org'] = response['influxdb_org']
		if 'influxdb_bucket' in response:
			settings['influxdb']['bucket'] = response['influxdb_bucket']

		if('delete_device' in response):
			DeviceID = response['delete_device']
			settings['onesignal']['devices'].pop(DeviceID)

		if('edit_device' in response):
			if(response['edit_device'] != ''):
				DeviceID = response['edit_device']
				settings['onesignal']['devices'][DeviceID] = {
					'friendly_name' : response['FriendlyName_' + DeviceID],
					'device_name' : response['DeviceName_' + DeviceID],
					'app_version' : response['AppVersion_' + DeviceID]
				}

		event['type'] = 'updated'
		event['text'] = 'Successfully updated notification settings.'

		# Take all settings and write them
		WriteSettings(settings)

	if (request.method == 'POST') and (action == 'editprofile'):
		response = request.form

		if('delete' in response):
			UniqueID = response['delete'] # Get the string of the UniqueID
			try:
				settings['probe_settings']['probe_profiles'].pop(UniqueID)
				WriteSettings(settings)
				event['type'] = 'updated'
				event['text'] = 'Successfully removed ' + response['Name_' + UniqueID] + ' profile.'
			except:
				event['type'] = 'error'
				event['text'] = 'Error: Failed to remove ' + response['Name_' + UniqueID] + ' profile.'

		if('editprofile' in response):
			if(response['editprofile'] != ''):
				# Try to convert input values
				try:
					UniqueID = response['editprofile'] # Get the string of the UniqueID
					settings['probe_settings']['probe_profiles'][UniqueID] = {
						'Vs' : float(response['Vs_' + UniqueID]),
						'Rd' : int(response['Rd_' + UniqueID]),
						'A' : float(response['A_' + UniqueID]),
						'B' : float(response['B_' + UniqueID]),
						'C' : float(response['C_' + UniqueID]),
						'name' : response['Name_' + UniqueID]
					}

					if (response['UniqueID_' + UniqueID] != UniqueID):
						# Copy Old Profile to New Profile
						settings['probe_settings']['probe_profiles'][response['UniqueID_' + UniqueID]] = settings['probe_settings']['probe_profiles'][UniqueID]
						# Remove the Old Profile
						settings['probe_settings']['probe_profiles'].pop(UniqueID)
					event['type'] = 'updated'
					event['text'] = 'Successfully added ' + response['Name_' + UniqueID] + ' profile.'
					# Write the new probe profile to disk
					WriteSettings(settings)
				except:
					event['type'] = 'error'
					event['text'] = 'Something bad happened when trying to format your inputs.  Try again.'
			else:
				event['type'] = 'error'
				event['text'] = 'Error. Profile NOT saved.'

	if (request.method == 'POST') and (action == 'addprofile'):
		response = request.form

		if(response['UniqueID'] != '') and (response['Name'] != '') and (response['Vs'] != '') and (response['Rd'] != '') and (response['A'] != '') and (response['B'] != '') and (response['C'] != ''):
			# Try to convert input values
			try:
				settings['probe_settings']['probe_profiles'][response['UniqueID']] = {
					'Vs' : float(response['Vs']),
					'Rd' : int(response['Rd']),
					'A' : float(response['A']),
					'B' : float(response['B']),
					'C' : float(response['C']),
					'name' : response['Name']
				}
				event['type'] = 'updated'
				event['text'] = 'Successfully added ' + response['Name'] + ' profile.'
				# Write the new probe profile to disk
				WriteSettings(settings)

			except:
				event['type'] = 'error'
				event['text'] = 'Something bad happened when trying to format your inputs.  Try again.'
		else:
			event['type'] = 'error'
			event['text'] = 'All fields must be completed before submitting. Profile NOT saved.'

	if (request.method == 'POST') and (action == 'cycle'):
		response = request.form

		if('pmode' in response):
			if(response['pmode'] != ''):
				settings['cycle_data']['PMode'] = int(response['pmode'])
		if('holdcycletime' in response):
			if(response['holdcycletime'] != ''):
				settings['cycle_data']['HoldCycleTime'] = int(response['holdcycletime'])
		if('smokecycletime' in response):
			if(response['smokecycletime'] != ''):
				settings['cycle_data']['SmokeCycleTime'] = int(response['smokecycletime'])
		if('propband' in response):
			if(response['propband'] != ''):
				settings['cycle_data']['PB'] = float(response['propband'])
		if('integraltime' in response):
			if(response['integraltime'] != ''):
				settings['cycle_data']['Ti'] = float(response['integraltime'])
		if('derivtime' in response):
			if(response['derivtime'] != ''):
				settings['cycle_data']['Td'] = float(response['derivtime'])
		if('u_min' in response):
			if(response['u_min'] != ''):
				settings['cycle_data']['u_min'] = float(response['u_min'])
		if('u_max' in response):
			if(response['u_max'] != ''):
				settings['cycle_data']['u_max'] = float(response['u_max'])
		if('center' in response):
			if(response['center'] != ''):
				settings['cycle_data']['center'] = float(response['center'])
		if('sp_cycle' in response):
			if(response['sp_cycle'] != ''):
				settings['smoke_plus']['cycle'] = int(response['sp_cycle'])
		if('minsptemp' in response):
			if(response['minsptemp'] != ''):
				settings['smoke_plus']['min_temp'] = int(response['minsptemp'])
		if('maxsptemp' in response):
			if(response['maxsptemp'] != ''):
				settings['smoke_plus']['max_temp'] = int(response['maxsptemp'])
		if('defaultsmokeplus' in response):
			if(response['defaultsmokeplus'] == 'on'):
				settings['smoke_plus']['enabled'] = True 
		else:
			settings['smoke_plus']['enabled'] = False
		if('keep_warm_temp' in response):
			if(response['keep_warm_temp'] != ''):
				settings['keep_warm']['temp'] = int(response['keep_warm_temp'])
		if('keep_warm_s_plus' in response):
			if(response['keep_warm_s_plus'] == 'on'):
				settings['keep_warm']['s_plus'] = True
		else:
			settings['keep_warm']['s_plus'] = False
				
		event['type'] = 'updated'
		event['text'] = 'Successfully updated cycle settings.'

		WriteSettings(settings)

	if (request.method == 'POST') and (action == 'timers'):
		response = request.form

		if('shutdown_timer' in response):
			if(response['shutdown_timer'] != ''):
				settings['globals']['shutdown_timer'] = int(response['shutdown_timer'])

		if('startup_timer' in response):
			if(response['startup_timer'] != ''):
				settings['globals']['startup_timer'] = int(response['startup_timer'])

		if('auto_power_off' in response):
			if(response['auto_power_off'] == 'on'):
				settings['globals']['auto_power_off'] = True
		else:
			settings['globals']['auto_power_off'] = False

		if('smartstart_enable' in response):
			if(response['smartstart_enable'] == 'on'):
				settings['smartstart']['enabled'] = True
		else:
			settings['smartstart']['enabled'] = False

		event['type'] = 'updated'
		event['text'] = 'Successfully updated startup/shutdown settings.'

		WriteSettings(settings)

	if (request.method == 'POST') and (action == 'history'):
		response = request.form

		if('historymins' in response):
			if(response['historymins'] != ''):
				settings['history_page']['minutes'] = int(response['historymins'])

		if('clearhistorystartup' in response):
			if(response['clearhistorystartup'] == 'on'):
				settings['history_page']['clearhistoryonstart'] = True
		else:
			settings['history_page']['clearhistoryonstart'] = False

		if('historyautorefresh' in response):
			if(response['historyautorefresh'] == 'on'):
				settings['history_page']['autorefresh'] = 'on'
		else:
			settings['history_page']['autorefresh'] = 'off'

		if('datapoints' in response):
			if(response['datapoints'] != ''):
				settings['history_page']['datapoints'] = int(response['datapoints'])

		event['type'] = 'updated'
		event['text'] = 'Successfully updated history settings.'

		WriteSettings(settings)

	if (request.method == 'POST') and (action == 'pagesettings'):
		response = request.form

		if('darkmode' in response):
			if(response['darkmode'] == 'on'):
				settings['globals']['page_theme'] = 'dark'
		else:
			settings['globals']['page_theme'] = 'light'

		event['type'] = 'updated'
		event['text'] = 'Successfully updated page settings.'

		WriteSettings(settings)

	if (request.method == 'POST') and (action == 'safety'):
		response = request.form

		if('minstartuptemp' in response):
			if(response['minstartuptemp'] != ''):
				settings['safety']['minstartuptemp'] = int(response['minstartuptemp'])
		if('maxstartuptemp' in response):
			if(response['maxstartuptemp'] != ''):
				settings['safety']['maxstartuptemp'] = int(response['maxstartuptemp'])
		if('reigniteretries' in response):
			if(response['reigniteretries'] != ''):
				settings['safety']['reigniteretries'] = int(response['reigniteretries'])
		if('maxtemp' in response):
			if(response['maxtemp'] != ''):
				settings['safety']['maxtemp'] = int(response['maxtemp'])

		event['type'] = 'updated'
		event['text'] = 'Successfully updated safety settings.'

		WriteSettings(settings)

	if (request.method == 'POST') and (action == 'grillname'):
		response = request.form

		if('grill_name' in response):
			settings['globals']['grill_name'] = response['grill_name']
			event['type'] = 'updated'
			event['text'] = 'Successfully updated grill name.'


		WriteSettings(settings)

	if (request.method == 'POST') and (action == 'pellets'):
		response = request.form

		if('pelletwarning' in response):
			if('pelletwarning' == 'on'):
				settings['pelletlevel']['warning_enabled'] = True
		else:
			settings['pelletlevel']['warning_enabled'] = False

		if('warninglevel' in response):
			settings['pelletlevel']['warning_level'] = int(response['warninglevel'])

		if('empty' in response):
			settings['pelletlevel']['empty'] = int(response['empty'])

		if('full' in response):
			settings['pelletlevel']['full'] = int(response['full'])

		event['type'] = 'updated'
		event['text'] = 'Successfully updated pellet settings.'

		WritePelletDB(pelletdb)

	if (request.method == 'POST') and (action == 'units'):
		response = request.form

		if('units' in response):
			if(response['units'] == 'C') and (settings['globals']['units'] == 'F'):
				settings = convert_settings_units('C', settings)
				WriteSettings(settings)
				event['type'] = 'updated'
				event['text'] = 'Successfully updated units to Celsius.'
				control = ReadControl()
				control['updated'] = True
				control['units_change'] = True 
				WriteControl(control)
			elif(response['units'] == 'F') and (settings['globals']['units'] == 'C'):
				settings = convert_settings_units('F', settings)
				WriteSettings(settings)
				event['type'] = 'updated'
				event['text'] = 'Successfully updated units to Fahrenheit.'
				control = ReadControl()
				control['updated'] = True
				control['units_change'] = True 
				WriteControl(control)
	'''
	Smart Start Settings
	'''
	if (request.method == 'GET') and (action == 'smartstart'):
		temps = settings['smartstart']['temp_range_list']
		profiles = settings['smartstart']['profiles']
		return(jsonify({'temps_list' : temps, 'profiles' : profiles}))

	if (request.method == 'POST') and (action == 'smartstart'):
		response = request.json 
		settings['smartstart']['temp_range_list'] = response['temps_list']
		settings['smartstart']['profiles'] = response['profiles']
		WriteSettings(settings)
		return(jsonify({'result' : 'success'}))

	return render_template('settings.html', settings=settings, alert=event, page_theme=settings['globals']['page_theme'], grill_name=settings['globals']['grill_name'], pelletdb=pelletdb)

@app.route('/admin/<action>', methods=['POST','GET'])
@app.route('/admin', methods=['POST','GET'])
def adminpage(action=None):

	global settings
	pelletdb = ReadPelletDB()
	notify = ''
	files = os.listdir(BACKUPPATH)
	for file in files:
		if not allowed_file(file):
			files.remove(file)

	if action == 'reboot':
		event = "Admin: Reboot"
		WriteLog(event)
		if(isRaspberryPi()):
			os.system("sleep 3 && sudo reboot &")
		return render_template('shutdown.html', action=action, page_theme=settings['globals']['page_theme'], grill_name=settings['globals']['grill_name'])

	elif action == 'shutdown':
		event = "Admin: Shutdown"
		WriteLog(event)
		if(isRaspberryPi()):
			os.system("sleep 3 && sudo shutdown -h now &")
		return render_template('shutdown.html', action=action, page_theme=settings['globals']['page_theme'], grill_name=settings['globals']['grill_name'])

	elif action == 'restart':
		event = "Admin: Restart Server"
		WriteLog(event)
		restart_scripts()
		return render_template('shutdown.html', action=action, page_theme=settings['globals']['page_theme'], grill_name=settings['globals']['grill_name'])

	if (request.method == 'POST') and (action == 'setting'):
		response = request.form

		if('debugenabled' in response):
			if(response['debugenabled']=='disabled'):
				WriteLog('Debug Mode Disabled.')
				settings['globals']['debug_mode'] = False
				WriteSettings(settings)
			else:
				settings['globals']['debug_mode'] = True
				WriteSettings(settings)
				WriteLog('Debug Mode Enabled.')

		if('clearhistory' in response):
			if(response['clearhistory']=='true'):
				WriteLog('Clearing History Log.')
				ReadHistory(0, flushhistory=True)

		if('clearevents' in response):
			if(response['clearevents']=='true'):
				WriteLog('Clearing Events Log.')
				os.remove('/tmp/events.log')

		if('clearpelletdb' in response):
			if(response['clearpelletdb']=='true'):
				WriteLog('Clearing Pellet Database.')
				os.remove('pelletdb.json')

		if('clearpelletdblog' in response):
			if(response['clearpelletdblog']=='true'):
				WriteLog('Clearing Pellet Database Log.')
				pelletdb['log'].clear()
				WritePelletDB(pelletdb)

		if('factorydefaults' in response):
			if(response['factorydefaults']=='true'):
				WriteLog('Resetting Settings, Control, History to factory defaults.')
				ReadHistory(0, flushhistory=True)
				ReadControl(flush=True)
				os.remove('settings.json')
				os.remove('pelletdb.json')
				settings = DefaultSettings()
				control = DefaultControl()
				WriteSettings(settings)
				WriteControl(control)

		if('download_logs' in response):
			timenow = datetime.datetime.now()
			timestr = timenow.strftime('%m-%d-%y_%H%M%S') # Truncate the microseconds
			file_name = 'PiFire_Logs_' + timestr + '.zip'
			zip_file = zip_files_dir('logs')
			return send_file(zip_file, as_attachment=True, attachment_filename=file_name, max_age=0)
		
		if('backupsettings' in response):
			timenow = datetime.datetime.now()
			timestr = timenow.strftime('%m-%d-%y_%H%M%S') # Truncate the microseconds
			backupfile = BACKUPPATH + 'PiFire_' + timestr + '.json'
			os.system(f'cp settings.json {backupfile}')
			return send_file(backupfile, as_attachment=True, max_age=0)

		if('restoresettings' in response):
			# Assume we have request.files and localfile in response
			remotefile = request.files['uploadfile']
			localfile = request.form['localfile']
			
			if (localfile != 'none'):
				settings = ReadSettings(filename=BACKUPPATH+localfile)
				notify = "success"
			elif (remotefile.filename != ''):
				# If the user does not select a file, the browser submits an
				# empty file without a filename.
				if remotefile and allowed_file(remotefile.filename):
					filename = secure_filename(remotefile.filename)
					remotefile.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
					notify = "success"
					settings = ReadSettings(filename=BACKUPPATH+filename)
				else:
					notify = "error"
			else:
				notify = "error"

		if('backuppelletdb' in response):
			timenow = datetime.datetime.now()
			timestr = timenow.strftime('%m-%d-%y_%H%M%S') # Truncate the microseconds
			backupfile = BACKUPPATH + 'PelletDB_' + timestr + '.json'
			os.system(f'cp pelletdb.json {backupfile}')
			return send_file(backupfile, as_attachment=True, max_age=0)

		if('restorepelletdb' in response):
			# Assume we have request.files and localfile in response
			remotefile = request.files['uploadfile']
			localfile = request.form['localfile']
			
			if (localfile != 'none'):
				pelletdb = ReadPelletDB(filename=BACKUPPATH+localfile)
				notify = "success"
			elif (remotefile.filename != ''):
				# If the user does not select a file, the browser submits an
				# empty file without a filename.
				if remotefile and allowed_file(remotefile.filename):
					filename = secure_filename(remotefile.filename)
					remotefile.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
					notify = "success"
					pelletdb = ReadPelletDB(filename=BACKUPPATH+filename)
				else:
					notify = "error"
			else:
				notify = "error"

	uptime = os.popen('uptime').readline()

	cpuinfo = os.popen('cat /proc/cpuinfo').readlines()

	ifconfig = os.popen('ifconfig').readlines()

	if(isRaspberryPi()):
		temp = checkcputemp()
	else:
		temp = '---'

	debug_mode = settings['globals']['debug_mode']

	url = request.url_root

	return render_template('admin.html', settings=settings, notify=notify, uptime=uptime, cpuinfo=cpuinfo, temp=temp, ifconfig=ifconfig, debug_mode=debug_mode, qr_content=url, page_theme=settings['globals']['page_theme'], grill_name=settings['globals']['grill_name'], files=files)

@app.route('/manual/<action>', methods=['POST','GET'])
@app.route('/manual', methods=['POST','GET'])
def manual_page(action=None):

	global settings
	control = ReadControl()

	if (request.method == 'POST'):
		response = request.form

		if('setmode' in response):
			if(response['setmode']=='manual'):
				control['updated'] = True
				control['mode'] = 'Manual'
			else:
				control['updated'] = True
				control['mode'] = 'Stop'

		if('change_output_fan' in response):
			if(response['change_output_fan']=='on'):
				control['manual']['change'] = True
				control['manual']['fan'] = True
			elif(response['change_output_fan']=='off'):
				control['manual']['change'] = True
				control['manual']['fan'] = False
		elif('change_output_auger' in response):
			if(response['change_output_auger']=='on'):
				control['manual']['change'] = True
				control['manual']['auger'] = True
			elif(response['change_output_auger']=='off'):
				control['manual']['change'] = True
				control['manual']['auger'] = False
		elif('change_output_igniter' in response):
			if(response['change_output_igniter']=='on'):
				control['manual']['change'] = True
				control['manual']['igniter'] = True
			elif(response['change_output_igniter']=='off'):
				control['manual']['change'] = True
				control['manual']['igniter'] = False
		elif('change_output_power' in response):
			if(response['change_output_power']=='on'):
				control['manual']['change'] = True
				control['manual']['power'] = True
			elif(response['change_output_power']=='off'):
				control['manual']['change'] = True
				control['manual']['power'] = False

		WriteControl(control)

		time.sleep(1)
		control = ReadControl()

	return render_template('manual.html', settings=settings, control=control, page_theme=settings['globals']['page_theme'], grill_name=settings['globals']['grill_name'])

@app.route('/api/<action>', methods=['POST','GET'])
@app.route('/api', methods=['POST','GET'])
def api_page(action=None):
	global settings

	if (request.method == 'GET'):
		if(action == 'settings'):
			return jsonify({'settings':settings}), 201
		elif(action == 'control'):
			control=ReadControl()
			return jsonify({'control':control}), 201
		elif(action == 'current'):
			current=ReadCurrent()
			current_temps = {
				'grill_temp' : int(float(current[0])),
				'probe1_temp' : int(float(current[1])),
				'probe2_temp' : int(float(current[2]))
			}
			control=ReadControl()
			current_setpoints = control['setpoints']
			pelletdb=ReadPelletDB()
			status = {}
			status['mode'] = control['mode']
			status['status'] = control['status']
			status['s_plus'] = control['s_plus']
			status['units'] = settings['globals']['units']
			status['name'] = settings['globals']['grill_name']
			status['pelletlevel'] = pelletdb['current']['hopper_level']
			pelletid = pelletdb['current']['pelletid']
			status['pellets'] = f'{pelletdb["archive"][pelletid]["brand"]} {pelletdb["archive"][pelletid]["wood"]}'
			return jsonify({'current':current_temps, 'setpoints':current_setpoints, 'status':status}), 201
		else:
			return jsonify({'Error':'Recieved GET request, without valid action'}), 404
	elif (request.method == 'POST'):
		if not request.json:
			event = "Local API Call Failed"
			WriteLog(event)
			abort(400)
		else:
			requestjson = request.json 
			if(action == 'settings'):
				for key in settings.keys():
					if key in requestjson.keys():
						settings[key].update(requestjson.get(key, {}))
				WriteSettings(settings)
				return jsonify({'settings':'success'}), 201
			elif(action == 'control'):
				control=ReadControl()
				for key in control.keys():
					if key in requestjson.keys():
						if key in ['setpoints', 'safety', 'notify_req', 'notify_data', 'timer', 'manual']:
							control[key].update(requestjson.get(key, {}))
						else:
							control[key] = requestjson[key]
				WriteControl(control)
				return jsonify({'control':'success'}), 201
			else:
				return jsonify({'Error':'Recieved POST request no valid action.'}), 404
	else:
		return jsonify({'Error':'Recieved undefined/unsupported request.'}), 404

'''
Wizard Route for PiFire Setup
'''
@app.route('/wizard/<action>', methods=['POST','GET'])
@app.route('/wizard', methods=['GET', 'POST'])
def wizard(action=None):
	global settings

	wizardData = ReadWizard()

	if(request.method == 'GET'):
		if(action=='welcome'):
			return render_template('wizard.html', settings=settings, page_theme=settings['globals']['page_theme'], grill_name=settings['globals']['grill_name'], wizardData=wizardData)
		elif(action=='installstatus'):
			percent, status, output = GetWizardInstallStatus()
			return jsonify({'percent' : percent, 'status' : status, 'output' : output}) 
	elif(request.method == 'POST'):
		r = request.form
		if(action=='cancel'):
			settings['globals']['first_time_setup'] = False
			WriteSettings(settings)
			return redirect('/')
		if(action=='finish'):
			wizardInstallInfo = prepare_wizard_data(r)
			StoreWizardInstallInfo(wizardInstallInfo)
			SetWizardInstallStatus(0, 'Starting Install...', '')
			os.system('python3 wizard.py &')	# Kickoff Installation
			return render_template('wizard-finish.html', page_theme=settings['globals']['page_theme'], grill_name=settings['globals']['grill_name'], wizardData=wizardData)
		if(action=='modulecard'):
			module = r['module']
			section = r['section']
			if section in ['grillplatform', 'probes', 'display', 'distance']:
				moduleData = wizardData['modules'][section][module]
			else:
				return '<strong color="red">No Data</strong>'
			return render_template('wizard-card.html', moduleData=moduleData, moduleSection=section)	

	return render_template('wizard.html', settings=settings, page_theme=settings['globals']['page_theme'], grill_name=settings['globals']['grill_name'], wizardData=wizardData)

def prepare_wizard_data(formdata): 
	wizardData = ReadWizard()
	
	wizardInstallInfo = {}
	wizardInstallInfo['modules'] = {
		'grillplatform' : {
			'module_selected' : formdata['grillplatformSelect'],
			'settings' : {}
		}, 
		'probes' : {
			'module_selected' : formdata['probesSelect'],
			'settings' : {}
		}, 
		'display' : {
			'module_selected' : formdata['displaySelect'],
			'settings' : {}
		}, 
		'distance' : {
			'module_selected' : formdata['distanceSelect'],
			'settings' : {}
		}, 
	}

	for module in ['grillplatform', 'probes', 'display', 'distance']:
		module_ = module + '_'
		moduleSelect = module + 'Select'
		selected = formdata[moduleSelect]
		for setting in wizardData['modules'][module][selected]['settings_dependencies']:
			settingName = module_ + setting
			if(settingName in formdata):
				wizardInstallInfo['modules'][module]['settings'][setting] = formdata[settingName]

	return(wizardInstallInfo)

'''
Manifest Route for Web Application Integration
'''
@app.route('/manifest')
def manifest():
    res = make_response(render_template('manifest.json'), 200)
    res.headers["Content-Type"] = "text/cache-manifest"
    return res

'''
Updater Function Routes
'''
@app.route('/checkupdate', methods=['GET'])
def checkupdate(action=None):
	global settings
	update_data = {}
	update_data['version'] = settings['versions']['server']

	avail_updates_struct = get_available_updates()

	if(avail_updates_struct['success']): 
		commits_behind = avail_updates_struct['commits_behind']
	else:
		event = avail_updates_struct['message']
		WriteLog(event)
		return jsonify({'result' : 'failure', 'message' : avail_updates_struct['message'] })

	return jsonify({'result' : 'success', 'current' : update_data['version'], 'behind' : commits_behind})

@app.route('/update/<action>', methods=['POST','GET'])
@app.route('/update', methods=['POST','GET'])
def update_page(action=None):
	global settings

	# Create Alert Structure for Alert Notification
	alert = {
		'type' : '',
		'text' : ''
	}

	if(request.method == 'GET'):
		if(action is None):
			update_data = get_update_data(settings)
			return render_template('updater.html', alert=alert, settings=settings, page_theme=settings['globals']['page_theme'], grill_name=settings['globals']['grill_name'], update_data=update_data)
		elif(action=='updatestatus'):
			percent, status, output = GetUpdaterInstallStatus()
			return jsonify({'percent' : percent, 'status' : status, 'output' : output})

	if(request.method == 'POST'):
		r = request.form
		update_data = get_update_data(settings)

		if('update_remote_branches' in r):
			if isRaspberryPi():
				os.system('python3 %s %s &' % ('updater.py', '-r'))	 # Update branches from remote 
				time.sleep(4)  # Artificial delay to avoid race condition
			return redirect('/update')

		if('change_branch' in r):
			if(update_data['branch_target'] in r['branch_target']):
				alert = {
					'type' : 'success',
					'text' : f'Current branch {update_data["branch_target"]} already set to {r["branch_target"]}'
				}
				return render_template('updater.html', alert=alert, settings=settings, page_theme=settings['globals']['page_theme'], update_data=update_data, grill_name=settings['globals']['grill_name'])
			else:
				SetUpdaterInstallStatus(0, 'Starting Branch Change...', '')
				os.system('python3 %s %s %s &' % ('updater.py', '-b', r['branch_target']))	# Kickoff Branch Change
				return render_template('updater-status.html', page_theme=settings['globals']['page_theme'], grill_name=settings['globals']['grill_name'])

		if('do_update' in r):
			SetUpdaterInstallStatus(0, 'Starting Update...', '')
			os.system('python3 %s %s %s &' % ('updater.py', '-u', update_data['branch_target']))  # Kickoff Update
			return render_template('updater-status.html', page_theme=settings['globals']['page_theme'], grill_name=settings['globals']['grill_name'])

		if('show_log' in r):
			if(r['show_log'].isnumeric()):
				action='log'
				result, error_msg = get_log(num_commits=int(r['show_log']))
				if error_msg == '':
					output_html = f'*** Getting latest updates from origin/{update_data["branch_target"]} ***<br><br>' 
					output_html += result
				else: 
					output_html = f'*** Getting latest updates from origin/{update_data["branch_target"]} ERROR Occurred ***<br><br>' 
					output_html += error_msg
			else:
				output_html = '*** Error, Number of Commits Not Defined! ***<br><br>'
			
			return render_template('updater_out.html', settings=settings, page_theme=settings['globals']['page_theme'], action=action, output_html=output_html, grill_name=settings['globals']['grill_name'])

'''
End Updater Section
'''

''' 
Metrics Routes
'''
@app.route('/metrics/<action>', methods=['POST','GET'])
@app.route('/metrics', methods=['POST','GET'])
def metrics_page(action=None):
	global settings

	metrics_data = ProcessMetrics(ReadMetrics(all=True))

	if (request.method == 'GET') and (action == 'export'):
		filename = datetime.datetime.now().strftime('%Y%m%d-%H%M') + '-PiFire-Metrics-Export'
		csvfilename = prepare_metrics_csv(metrics_data, filename)
		return send_file(csvfilename, as_attachment=True, max_age=0)

	return render_template('metrics.html', settings=settings, page_theme=settings['globals']['page_theme'], grill_name=settings['globals']['grill_name'], metrics_data=metrics_data)

'''
Supporting Functions
'''

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def checkcputemp():
	temp = os.popen('vcgencmd measure_temp').readline()
	return temp.replace("temp=","")

def prepare_data(num_items=10, reduce=True, datapoints=60):
	# num_items: Number of items to store in the data blob
	global settings
	units = settings['globals']['units']

	data_list = ReadHistory(num_items)

	data_blob = {}

	data_blob['label_time_list'] = []
	data_blob['grill_temp_list'] = []
	data_blob['grill_settemp_list'] = []
	data_blob['probe1_temp_list'] = []
	data_blob['probe1_settemp_list'] = []
	data_blob['probe2_temp_list'] = []
	data_blob['probe2_settemp_list'] = []
	
	list_length = len(data_list) # Length of list

	if((list_length < num_items) and (list_length > 0)):
		num_items = list_length

	if((reduce==True) and (num_items > datapoints)):
		step = int(num_items/datapoints)
	else:
		step = 1

	if(list_length > 0):
		# Build all lists from file data
		for index in range(list_length - num_items, list_length, step):
			if(units == 'F'):
				data_blob['label_time_list'].append(int(data_list[index][0]))  # Timestamp format is int, so convert from str
				data_blob['grill_temp_list'].append(int(data_list[index][1]))
				data_blob['grill_settemp_list'].append(int(data_list[index][2]))
				data_blob['probe1_temp_list'].append(int(data_list[index][3]))
				data_blob['probe1_settemp_list'].append(int(data_list[index][4]))
				data_blob['probe2_temp_list'].append(int(data_list[index][5]))
				data_blob['probe2_settemp_list'].append(int(data_list[index][6]))
			else: 
				data_blob['label_time_list'].append(int(data_list[index][0]))  # Timestamp format is int, so convert from str
				data_blob['grill_temp_list'].append(float(data_list[index][1]))
				data_blob['grill_settemp_list'].append(float(data_list[index][2]))
				data_blob['probe1_temp_list'].append(float(data_list[index][3]))
				data_blob['probe1_settemp_list'].append(float(data_list[index][4]))
				data_blob['probe2_temp_list'].append(float(data_list[index][5]))
				data_blob['probe2_settemp_list'].append(float(data_list[index][6]))
	else:
		now = datetime.datetime.now()
		#timenow = now.strftime('%H:%M:%S')
		timenow = int(now.timestamp() * 1000)  # Use timestamp format (int) instead of H:M:S format in string
		for index in range(num_items):
			data_blob['label_time_list'].append(timenow) 
			data_blob['grill_temp_list'].append(0)
			data_blob['grill_settemp_list'].append(0)
			data_blob['probe1_temp_list'].append(0)
			data_blob['probe1_settemp_list'].append(0)
			data_blob['probe2_temp_list'].append(0)
			data_blob['probe2_settemp_list'].append(0)

	return(data_blob)

def prepare_annotations(displayed_starttime, metrics_data=[]):
	if(metrics_data == []):
		metrics_data = ReadMetrics(all=True)
	annotation_json = {}
	# Process Additional Metrics Information for Display
	for index in range(0, len(metrics_data)):
		# Check if metric falls in the displayed time window
		if(metrics_data[index]['starttime'] > displayed_starttime):
			# Convert Start Time
			# starttime = epoch_to_time(metrics_data[index]['starttime']/1000)
			mode = metrics_data[index]['mode']
			color = 'blue'
			if mode == 'Startup':
				color = 'green'
			elif mode == 'Stop': 
				color = 'red'
			elif mode == 'Shutdown':
				color = 'black'
			elif mode == 'Reignite':
				color = 'orange'
			elif mode == 'Error':
				color = 'red'
			elif mode == 'Hold': 
				color = 'blue'
			elif mode == 'Smoke':
				color = 'grey'
			elif mode in ['Monitor', 'Manual']:
				color = 'purple'
			annotation = {
							'type' : 'line',
							'xMin' : metrics_data[index]['starttime'],
							'xMax' : metrics_data[index]['starttime'],
							'borderColor' : color,
							'borderWidth' : 2,
							'label': {
								'backgroundColor': color,
								'borderColor' : 'black',
								'color': 'white',
								'content': mode,
								'enabled': True, 
								'position': 'end',
								'rotation': 0,
								}, 
							'display': True
						}
			annotation_json[f'event_{index}'] = annotation

	return(annotation_json)

def prepare_graph_csv(graph_data=[], graph_labels=[], filename=''):
		if(graph_data == []):
			graph_data = ReadHistory((settings['history_page']['minutes'] * 20))
		else:
			# Unpack data from dictionary to list
			temp_list = []
			for index in range(len(graph_data['time_labels'])):
				temp_data = [str(int(graph_data['time_labels'][index])), str(graph_data['grill1_temp'][index]), str(graph_data['grill1_setpoint'][index]), str(graph_data['probe1_temp'][index]), str(graph_data['probe1_setpoint'][index]), str(graph_data['probe2_temp'][index]), str(graph_data['probe2_setpoint'][index])]
				temp_list.append(temp_data)
			graph_data = temp_list 

		if(graph_labels == []):
			labels = 'Time,Grill Temp,Grill SetTemp,Probe 1 Temp,Probe 1 SetTemp,Probe 2 Temp, Probe 2 SetTemp\n'
		else:
			labels = 'Time,' 
			labels += graph_labels['grill1_label'] + ' Temp,'
			labels += graph_labels['grill1_label'] + ' Setpoint,'
			labels += graph_labels['probe1_label'] + ' Temp,'
			labels += graph_labels['probe1_label'] + ' Setpoint,'
			labels += graph_labels['probe2_label'] + ' Temp,'
			labels += graph_labels['probe2_label'] + ' Setpoint\n'

		if(filename == ''):
			now = datetime.datetime.now()
			filename = now.strftime('%Y%m%d-%H%M') + '-PiFire-Export'
		else:
			filename = filename.replace('.json', '')
			filename = filename.replace('./history/', '')
			filename += '-Pifire-Export'
		
		exportfilename = '/tmp/' + filename + ".csv"
		
		csvfile = open(exportfilename, "w")

		list_length = len(graph_data)

		if(list_length > 0):
			writeline = labels
			csvfile.write(writeline)
			last = -1
			for index in range(0, list_length):
				if (int((index/list_length)*100) > last):
					last = int((index/list_length)*100)
				converted_dt = datetime.datetime.fromtimestamp(int(graph_data[index][0]) / 1000)
				graph_data[index][0] = converted_dt.strftime('%Y-%m-%d %H:%M:%S')
				writeline = ','.join(graph_data[index])
				csvfile.write(writeline + '\n')
		else:
			writeline = 'No Data\n'
			csvfile.write(writeline)

		csvfile.close()

		return(exportfilename)

def prepare_metrics_csv(metrics_data, filename):
	filename = filename.replace('.json', '')
	filename = filename.replace('./history/', '')
	filename = '/tmp/' + filename + '-PiFire-Metrics-Export.csv'

	csvfile = open(filename, 'w')

	list_length = len(metrics_data) # Length of list

	if(list_length > 0):
		# Build the header row
		writeline=''
		for item in range(0, len(metrics_items)):
			writeline += f'{metrics_items[item][0]}, '
		writeline += '\n'
		csvfile.write(writeline)
		for index in range(0, list_length):
			writeline = ''
			for item in range(0, len(metrics_items)):
				writeline += f'{metrics_data[index][metrics_items[item][0]]}, '
			writeline += '\n'
			csvfile.write(writeline)
	else:
		writeline = 'No Data\n'
		csvfile.write(writeline)

	csvfile.close()
	return(filename)

def calc_shh_coefficients(T1, T2, T3, R1, R2, R3):
	try: 
    	# Convert Temps from Farenheit to Kelvin
		T1 = ((T1 - 32) * (5/9)) + 273.15
		T2 = ((T2 - 32) * (5/9)) + 273.15
		T3 = ((T3 - 32) * (5/9)) + 273.15

		# https://en.wikipedia.org/wiki/Steinhart%E2%80%93Hart_equation

		# Step 1: L1 = ln (R1), L2 = ln (R2), L3 = ln (R3)
		L1 = math.log(R1)
		L2 = math.log(R2)
		L3 = math.log(R3)

		# Step 2: Y1 = 1 / T1, Y2 = 1 / T2, Y3 = 1 / T3
		Y1 = 1/T1
		Y2 = 1/T2
		Y3 = 1/T3

		# Step 3: G2 = (Y2 - Y1) / (L2 - L1) , G3 = (Y3 - Y1) / (L3 - L1)
		G2 = (Y2 - Y1) / (L2 - L1)
		G3 = (Y3 - Y1) / (L3 - L1)

		# Step 4: C = ((G3 - G2) / (L3 - L2)) * (L1 + L2 + L3)^-1
		C = ((G3 - G2) / (L3 - L2)) * math.pow(L1 + L2 + L3, -1)

		# Step 5: B = G2 - C * (L1^2 + (L1*L2) + L2^2)
		B = G2 - C * (math.pow(L1,2) + (L1*L2) + math.pow(L2,2))

		# Step 6: A = Y1 - (B + L1^2*C) * L1
		A = Y1 - ((B + (math.pow(L1,2) * C)) * L1)
	except:
		A = 0
		B = 0
		C = 0
    
	return(A, B, C)

def temp_to_tr(tempF, A, B, C):
	try: 
		tempK = ((tempF - 32) * (5/9)) + 273.15

		# https://en.wikipedia.org/wiki/Steinhart%E2%80%93Hart_equation
		# Inverse of the equation, to determine Tr = Resistance Value of the thermistor

		# Not recommended for use, as it commonly produces a complex number

		x = (1/(2*C))*(A-(1/tempK))

		y = math.sqrt(math.pow((B/(3*C)),3)+math.pow(x,2))

		Tr = math.exp(((y-x)**(1/3)) - ((y+x)**(1/3)))
	except: 
		Tr = 0

	return int(Tr) 

def tr_to_temp(Tr, a, b, c):
    try:
        #Steinhart Hart Equation
        # 1/T = A + B(ln(R)) + C(ln(R))^3
        # T = 1/(a + b[ln(ohm)] + c[ln(ohm)]^3)
        lnohm = math.log(Tr) # ln(ohms)
        t1 = (b*lnohm) # b[ln(ohm)]
        t2 = c * math.pow(lnohm,3) # c[ln(ohm)]^3
        tempK = 1/(a + t1 + t2) # calculate temperature in Kelvin
        tempC = tempK - 273.15 # Kelvin to Celsius
        tempF = tempC * (9/5) + 32 # Celsius to Farenheit
    except:
        tempF = 0.0
    return int(tempF) # Return Calculated Temperature and Thermistor Value in Ohms

def str_td(td):
    s = str(td).split(", ", 1)
    a = s[-1]
    if a[1] == ':':
        a = "0" + a
    s2 = s[:-1] + [a]
    return ", ".join(s2)

def zip_files_dir(dir_name):
	memory_file = BytesIO()
	with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
		for root, dirs, files in os.walk(dir_name):
			for file in files:
				zipf.write(os.path.join(root, file))
	memory_file.seek(0)
	return memory_file

def deep_dict_update(orig_dict, new_dict):
	for key, value in new_dict.items():
		if isinstance(value, Mapping):
			orig_dict[key] = deep_dict_update(orig_dict.get(key, {}), value)
		else:
			orig_dict[key] = value
	return orig_dict

'''
Socket IO for Android Functionality
'''
thread = Thread()
thread_lock = threading.Lock()
clients = 0
force_refresh = False

@socketio.on("connect")
def connect():
	global clients
	clients += 1

@socketio.on("disconnect")
def disconnect():
	global clients
	clients -= 1

@socketio.on('get_dash_data')
def get_dash_data(force=False):
	global thread
	global force_refresh
	force_refresh = force

	with thread_lock:
		if not thread.is_alive():
			thread = socketio.start_background_task(emit_dash_data)

def emit_dash_data():
	global clients
	global force_refresh
	previous_data = ''

	while (clients > 0):
		global settings
		control = ReadControl()
		pelletdb = ReadPelletDB()

		probes_enabled = settings['probe_settings']['probes_enabled']
		cur_probe_temps = ReadCurrent()

		current_temps = {
			'grill_temp' : cur_probe_temps[0],
			'probe1_temp' : cur_probe_temps[1],
			'probe2_temp' : cur_probe_temps[2] }
		enabled_probes = {
			'grill' : bool(probes_enabled[0]),
			'probe1' : bool(probes_enabled[1]),
			'probe2' : bool(probes_enabled[2]) }

		if control['timer']['end'] - time.time() > 0 or bool(control['timer']['paused']):
			timer_info = {
				'timer_paused' : bool(control['timer']['paused']),
				'timer_start_time' : math.trunc(control['timer']['start']),
				'timer_end_time' : math.trunc(control['timer']['end']),
				'timer_paused_time' : math.trunc(control['timer']['paused']),
				'timer_active' : 'true' }
		else:
			timer_info = {
				'timer_paused' : 'false',
				'timer_start_time' : '0',
				'timer_end_time' : '0',
				'timer_paused_time' : '0',
				'timer_active' : 'false' }

		current_data = {
			'cur_probe_temps' : current_temps,
			'probes_enabled' : enabled_probes,
			'set_points' : control['setpoints'],
			'notify_req' : control['notify_req'],
			'notify_data' : control['notify_data'],
			'timer_info' : timer_info,
			'current_mode' : control['mode'],
			'smoke_plus' : control['s_plus'],
			'hopper_level' : pelletdb['current']['hopper_level'] }

		if force_refresh:
			socketio.emit('grill_control_data', current_data, broadcast=True)
			force_refresh = False
			socketio.sleep(2)
		elif previous_data != current_data:
			socketio.emit('grill_control_data', current_data, broadcast=True)
			previous_data = current_data
			socketio.sleep(2)
		else:
			socketio.sleep(2)

@socketio.on('get_app_data')
def get_app_data(action=None, type=None):
	global settings

	if action == 'settings_data':
		return settings

	elif action == 'pellets_data':
		return ReadPelletDB()

	elif action == 'events_data':
		event_list, num_events = ReadLog()
		events_trim = []
		for x in range(min(num_events, 60)):
			events_trim.append(event_list[x])
		return { 'events_list' : events_trim }

	elif action == 'history_data':
		num_items = settings['history_page']['minutes'] * 20
		data_blob = prepare_data(num_items, True, settings['history_page']['datapoints'])
		# Converting time format from 'time from epoch' to H:M:S
		# @weberbox:  Trying to keep the legacy format for the time labels so that I don't break the Android app
		for index in range(0, len(data_blob['label_time_list'])): 
			data_blob['label_time_list'][index] = datetime.datetime.fromtimestamp(int(data_blob['label_time_list'][index]) / 1000).strftime('%H:%M:%S')

		return { 'grill_temp_list' : data_blob['grill_temp_list'],
				 'grill_settemp_list' : data_blob['grill_settemp_list'],
				 'probe1_temp_list' : data_blob['probe1_temp_list'],
				 'probe1_settemp_list' : data_blob['probe1_settemp_list'],
				 'probe2_temp_list' : data_blob['probe2_temp_list'],
				 'probe2_settemp_list' : data_blob['probe2_settemp_list'],
				 'label_time_list' : data_blob['label_time_list'] }

	elif action == 'info_data':
		return {
			'uptime' : os.popen('uptime').readline(),
			'cpuinfo' : os.popen('cat /proc/cpuinfo').readlines(),
			'ifconfig' : os.popen('ifconfig').readlines(),
			'temp' : checkcputemp(),
			'outpins' : settings['outpins'],
			'inpins' : settings['inpins'],
			'server_version' : settings['versions']['server'] }

	elif action == 'manual_data':
		control = ReadControl()
		return {
			'manual' : control['manual'],
			'mode' : control['mode'] }

	elif action == 'backup_list':
		files = os.listdir(BACKUPPATH)
		for file in files[:]:
			if not allowed_file(file):
				files.remove(file)

		if type == 'settings':
			for file in files[:]:
				if not file.startswith('PiFire_'):
					files.remove(file)
			return json.dumps(files)

		if type == 'pelletdb':
			for file in files[:]:
				if not file.startswith('PelletDB_'):
					files.remove(file)
		return json.dumps(files)

	elif action == 'backup_data':
		timenow = datetime.datetime.now()
		timestr = timenow.strftime('%m-%d-%y_%H%M%S')

		if type == 'settings':
			backupfile = BACKUPPATH + 'PiFire_' + timestr + '.json'
			os.system(f'cp settings.json {backupfile}')
			return settings

		if type == 'pelletdb':
			backupfile = BACKUPPATH + 'PelletDB_' + timestr + '.json'
			os.system(f'cp pelletdb.json {backupfile}')
			return ReadPelletDB()

	elif action == 'updater_data':
		avail_updates_struct = get_available_updates()

		if avail_updates_struct['success']:
			commits_behind = avail_updates_struct['commits_behind']
		else:
			message = avail_updates_struct['message']
			WriteLog(message)
			return {'response': {'result':'error', 'message':'Error: ' + message }}

		if commits_behind > 0:
			logs_result = get_log(commits_behind)
		else:
			logs_result = None

		update_data = {}
		update_data['branch_target'], error_msg = get_branch()
		update_data['branches'], error_msg = get_available_branches()
		update_data['remote_url'], error_msg = get_remote_url()
		update_data['remote_version'], error_msg = get_remote_version()

		return { 'check_success' : avail_updates_struct['success'],
				 'version' : settings['versions']['server'],
				 'branches' : update_data['branches'],
				 'branch_target' : update_data['branch_target'],
				 'remote_url' : update_data['remote_url'],
				 'remote_version' : update_data['remote_version'],
				 'commits_behind' : commits_behind,
				 'logs_result' : logs_result,
				 'error_message' : error_msg }
	else:
		return {'response': {'result':'error', 'message':'Error: Received request without valid action'}}

@socketio.on('post_app_data')
def post_app_data(action=None, type=None, json_data=None):
	global settings

	if json_data is not None:
		request = json.loads(json_data)
	else:
		request = {''}

	if action == 'update_action':
		if type == 'settings':
			for key in request.keys():
				if key in settings.keys():
					settings = deep_dict_update(settings, request)
					WriteSettings(settings)
					return {'response': {'result':'success'}}
				else:
					return {'response': {'result':'error', 'message':'Error: Key not found in settings'}}
		elif type == 'control':
			control = ReadControl()
			for key in request.keys():
				if key in control.keys():
					control = deep_dict_update(control, request)
					WriteControl(control)
					return {'response': {'result':'success'}}
				else:
					return {'response': {'result':'error', 'message':'Error: Key not found in control'}}
		else:
			return {'response': {'result':'error', 'message':'Error: Received request without valid type'}}

	elif action == 'admin_action':
		if type == 'clear_history':
			WriteLog('Clearing History Log.')
			ReadHistory(0, flushhistory=True)
			return {'response': {'result':'success'}}
		elif type == 'clear_events':
			WriteLog('Clearing Events Log.')
			os.remove('/tmp/events.log')
			return {'response': {'result':'success'}}
		elif type == 'clear_pelletdb':
			WriteLog('Clearing Pellet Database.')
			os.remove('pelletdb.json')
			return {'response': {'result':'success'}}
		elif type == 'clear_pelletdb_log':
			pelletdb = ReadPelletDB()
			pelletdb['log'].clear()
			WritePelletDB(pelletdb)
			WriteLog('Clearing Pellet Database Log.')
			return {'response': {'result':'success'}}
		elif type == 'factory_defaults':
			ReadHistory(0, flushhistory=True)
			ReadControl(flush=True)
			os.remove('settings.json')
			settings = DefaultSettings()
			control = DefaultControl()
			WriteSettings(settings)
			WriteControl(control)
			WriteLog('Resetting Settings, Control, History to factory defaults.')
			return {'response': {'result':'success'}}
		elif type == 'reboot':
			WriteLog("Admin: Reboot")
			os.system("sleep 3 && sudo reboot &")
			return {'response': {'result':'success'}}
		elif type == 'shutdown':
			WriteLog("Admin: Shutdown")
			os.system("sleep 3 && sudo shutdown -h now &")
			return {'response': {'result':'success'}}
		elif type == 'restart':
			WriteLog("Admin: Restart Server")
			restart_scripts()
			return {'response': {'result':'success'}}
		else:
			return {'response': {'result':'error', 'message':'Error: Received request without valid type'}}

	elif action == 'units_action':
		if type == 'f_units' and settings['globals']['units'] == 'C':
			settings = convert_settings_units('F', settings)
			WriteSettings(settings)
			control = ReadControl()
			control['updated'] = True
			control['units_change'] = True
			WriteControl(control)
			WriteLog("Changed units to Fahrenheit")
			return {'response': {'result':'success'}}
		elif type == 'c_units' and settings['globals']['units'] == 'F':
			settings = convert_settings_units('C', settings)
			WriteSettings(settings)
			control = ReadControl()
			control['updated'] = True
			control['units_change'] = True
			WriteControl(control)
			WriteLog("Changed units to Celsius")
			return {'response': {'result':'success'}}
		else:
			return {'response': {'result':'error', 'message':'Error: Units could not be changed'}}

	elif action == 'remove_action':
		if type == 'onesignal_device':
			if 'onesignal_player_id' in request['onesignal_device']:
				device = request['onesignal_device']['onesignal_player_id']
				if device in settings['onesignal']['devices']:
					settings['onesignal']['devices'].pop(device)
				WriteSettings(settings)
				return {'response': {'result':'success'}}
			else:
				return {'response': {'result':'error', 'message':'Error: Device not specified'}}
		else:
			return {'response': {'result':'error', 'message':'Error: Remove type not found'}}

	elif action == 'pellets_action':
		pelletdb = ReadPelletDB()
		if type == 'load_profile':
			if 'profile' in request['pellets_action']:
				pelletdb['current']['pelletid'] = request['pellets_action']['profile']
				now = str(datetime.datetime.now())
				now = now[0:19]
				pelletdb['current']['date_loaded'] = now
				pelletdb['log'][now] = request['pellets_action']['profile']
				control = ReadControl()
				control['hopper_check'] = True
				WriteControl(control)
				WritePelletDB(pelletdb)
				return {'response': {'result':'success'}}
			else:
				return {'response': {'result':'error', 'message':'Error: Profile not included in request'}}
		elif type == 'hopper_check':
			control = ReadControl()
			control['hopper_check'] = True
			WriteControl(control)
			return {'response': {'result':'success'}}
		elif type == 'edit_brands':
			if 'delete_brand' in request['pellets_action']:
				delBrand = request['pellets_action']['delete_brand']
				if delBrand in pelletdb['brands']:
					pelletdb['brands'].remove(delBrand)
				WritePelletDB(pelletdb)
				return {'response': {'result':'success'}}
			elif 'new_brand' in request['pellets_action']:
				newBrand = request['pellets_action']['new_brand']
				if newBrand not in pelletdb['brands']:
					pelletdb['brands'].append(newBrand)
				WritePelletDB(pelletdb)
				return {'response': {'result':'success'}}
			else:
				return {'response': {'result':'error', 'message':'Error: Function not specified'}}
		elif type == 'edit_woods':
			if 'delete_wood' in request['pellets_action']:
				delWood = request['pellets_action']['delete_wood']
				if delWood in pelletdb['woods']:
					pelletdb['woods'].remove(delWood)
				WritePelletDB(pelletdb)
				return {'response': {'result':'success'}}
			elif 'new_wood' in request['pellets_action']:
				newWood = request['pellets_action']['new_wood']
				if newWood not in pelletdb['woods']:
					pelletdb['woods'].append(newWood)
				WritePelletDB(pelletdb)
				return {'response': {'result':'success'}}
			else:
				return {'response': {'result':'error', 'message':'Error: Function not specified'}}
		elif type == 'add_profile':
			profile_id = ''.join(filter(str.isalnum, str(datetime.datetime.now())))
			pelletdb['archive'][profile_id] = {
				'id' : profile_id,
				'brand' : request['pellets_action']['brand_name'],
				'wood' : request['pellets_action']['wood_type'],
				'rating' : request['pellets_action']['rating'],
				'comments' : request['pellets_action']['comments'] }
			if request['pellets_action']['add_and_load']:
				pelletdb['current']['pelletid'] = profile_id
				control = ReadControl()
				control['hopper_check'] = True
				WriteControl(control)
				now = str(datetime.datetime.now())
				now = now[0:19]
				pelletdb['current']['date_loaded'] = now
				pelletdb['log'][now] = profile_id
				WritePelletDB(pelletdb)
				return {'response': {'result':'success'}}
			else:
				WritePelletDB(pelletdb)
				return {'response': {'result':'success'}}
		if type == 'edit_profile':
			if 'profile' in request['pellets_action']:
				profile_id = request['pellets_action']['profile']
				pelletdb['archive'][profile_id]['brand'] = request['pellets_action']['brand_name']
				pelletdb['archive'][profile_id]['wood'] = request['pellets_action']['wood_type']
				pelletdb['archive'][profile_id]['rating'] = request['pellets_action']['rating']
				pelletdb['archive'][profile_id]['comments'] = request['pellets_action']['comments']
				WritePelletDB(pelletdb)
				return {'response': {'result':'success'}}
			else:
				return {'response': {'result':'error', 'message':'Error: Profile not included in request'}}
		if type == 'delete_profile':
			if 'profile' in request['pellets_action']:
				profile_id = request['pellets_action']['profile']
				if pelletdb['current']['pelletid'] == profile_id:
					return {'response': {'result':'error', 'message':'Error: Cannot delete current profile'}}
				else:
					pelletdb['archive'].pop(profile_id)
					for index in pelletdb['log']:
						if pelletdb['log'][index] == profile_id:
							pelletdb['log'][index] = 'deleted'
				WritePelletDB(pelletdb)
				return {'response': {'result':'success'}}
			else:
				return {'response': {'result':'error', 'message':'Error: Profile not included in request'}}
		elif type == 'delete_log':
			if 'log_item' in request['pellets_action']:
				delLog = request['pellets_action']['log_item']
				if delLog in pelletdb['log']:
					pelletdb['log'].pop(delLog)
				WritePelletDB(pelletdb)
				return {'response': {'result':'success'}}
			else:
				return {'response': {'result':'error', 'message':'Error: Function not specified'}}
		else:
			return {'response': {'result':'error', 'message':'Error: Received request without valid type'}}

	elif action == 'timer_action':
		control = ReadControl()
		if type == 'start_timer':
			control['notify_req']['timer'] = True
			if control['timer']['paused'] == 0:
				now = time.time()
				control['timer']['start'] = now
				if 'hours_range' in request['timer_action'] and 'minutes_range' in request['timer_action']:
					seconds = request['timer_action']['hours_range'] * 60 * 60
					seconds = seconds + request['timer_action']['minutes_range'] * 60
					control['timer']['end'] = now + seconds
					control['notify_data']['timer_shutdown'] = request['timer_action']['timer_shutdown']
					control['notify_data']['timer_keep_warm'] = request['timer_action']['timer_keep_warm']
					WriteLog('Timer started.  Ends at: ' + epoch_to_time(control['timer']['end']))
					WriteControl(control)
					return {'response': {'result':'success'}}
				else:
					return {'response': {'result':'error', 'message':'Error: Start time not specified'}}
			else:
				now = time.time()
				control['timer']['end'] = (control['timer']['end'] - control['timer']['paused']) + now
				control['timer']['paused'] = 0
				WriteLog('Timer unpaused.  Ends at: ' + epoch_to_time(control['timer']['end']))
				WriteControl(control)
				return {'response': {'result':'success'}}
		elif type == 'pause_timer':
			control['notify_req']['timer'] = False
			now = time.time()
			control['timer']['paused'] = now
			WriteLog('Timer paused.')
			WriteControl(control)
			return {'response': {'result':'success'}}
		elif type == 'stop_timer':
			control['notify_req']['timer'] = False
			control['timer']['start'] = 0
			control['timer']['end'] = 0
			control['timer']['paused'] = 0
			control['notify_data']['timer_shutdown'] = False
			control['notify_data']['timer_keep_warm'] = False
			WriteLog('Timer stopped.')
			WriteControl(control)
			return {'response': {'result':'success'}}
		else:
			return {'response': {'result':'error', 'message':'Error: Received request without valid type'}}
	else:
		return {'response': {'result':'error', 'message':'Error: Received request without valid action'}}

@socketio.on('post_updater_data')
def updater_action(type='none', branch=None):

	if type == 'change_branch':
		if branch is not None:
			success, status, output = change_branch(branch)
			message = f'Changing to {branch} branch \n'
			if success:
				dependencies = 'Installing any required dependencies \n'
				message += dependencies
				if install_dependencies() == 0:
					message += output
					restart_scripts()
					return {'response': {'result':'success', 'message': message }}
				else:
					return {'response': {'result':'error', 'message':'Error: Dependencies were not installed properly'}}
			else:
				return {'response': {'result':'error', 'message':'Error: ' + output }}
		else:
			return {'response': {'result':'error', 'message':'Error: Branch not specified in request'}}

	elif type == 'do_update':
		if branch is not None:
			success, status, output = install_update()
			message = f'Attempting update on {branch} \n'
			if success:
				dependencies = 'Installing any required dependencies \n'
				message += dependencies
				if install_dependencies() == 0:
					message += output
					restart_scripts()
					return {'response': {'result':'success', 'message': message }}
				else:
					return {'response': {'result':'error', 'message':'Error: Dependencies were not installed properly'}}
			else:
				return {'response': {'result':'error', 'message':'Error: ' + output }}
		else:
			return {'response': {'result':'error', 'message':'Error: Branch not specified in request'}}

	elif type == 'update_remote_branches':
		if isRaspberryPi():
			os.system('python3 %s %s &' % ('updater.py', '-r'))	 # Update branches from remote
			time.sleep(2)
			return {'response': {'result':'success', 'message': 'Branches successfully updated from remote' }}
		else:
			return {'response': {'result':'error', 'message': 'Could not update branches from remote' }}
	else:
		return {'response': {'result':'error', 'message':'Error: Received request without valid action'}}

@socketio.on('post_restore_data')
def post_restore_data(type='none', filename='none', json_data=None):

	if type == 'settings':
		if filename != 'none':
			ReadSettings(filename=BACKUPPATH+filename)
			restart_scripts()
			return {'response': {'result':'success'}}
		elif json_data is not None:
			WriteSettings(json.loads(json_data))
			return {'response': {'result':'success'}}
		else:
			return {'response': {'result':'error', 'message':'Error: Filename or JSON data not supplied'}}

	elif type == 'pelletdb':
		if filename != 'none':
			ReadPelletDB(filename=BACKUPPATH+filename)
			return {'response': {'result':'success'}}
		elif json_data is not None:
			WritePelletDB(json.loads(json_data))
			return {'response': {'result':'success'}}
		else:
			return {'response': {'result':'error', 'message':'Error: Filename or JSON data not supplied'}}
	else:
		return {'response': {'result':'error', 'message':'Error: Received request without valid type'}}

'''
Main Program Start
'''
settings = ReadSettings()

if __name__ == '__main__':
	if(isRaspberryPi()):
		socketio.run(app, host='0.0.0.0')
	else:
		socketio.run(app, host='0.0.0.0', debug=True)
