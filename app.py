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

from flask import Flask, request, render_template, make_response, send_file, jsonify
import time
import os
import json
import datetime
import math
from common import *  # Common Library for WebUI and Control Program

app = Flask(__name__)

@app.route('/<action>', methods=['POST','GET'])
@app.route('/', methods=['POST','GET'])
def index(action=None):

	# TODO:  Recipe Status
	settings = ReadSettings()

	control = ReadControl()

	if (request.method == 'POST'):
		response = request.form

		if('start' in response):
			if(response['start']=='true'):
				control['notify_req']['timer'] = True
				if(control['timer']['paused'] == 0):
					now = time.time()
					control['timer']['start'] = now
					if(('hoursInputRange' in response) and ('minsInputRange' in response)):
						seconds = int(response['hoursInputRange']) * 60 * 60
						seconds = seconds + int(response['minsInputRange']) * 60
						control['timer']['end'] = now + seconds
					else:
						control['timer']['end'] = now + 60
					DebugWrite('Timer started.  Ends at: ' + str(control['timer']['end']))
					WriteControl(control)
				else:	# If Timer was paused, restart with new end time.
					now = time.time()
					control['timer']['end'] = (control['timer']['end'] - control['timer']['paused']) + now
					control['timer']['start'] = now
					control['timer']['paused'] = 0
					DebugWrite('Timer unpaused.  Ends at: ' + str(control['timer']['end']))
					WriteControl(control)
		if('pause' in response):
			if(response['pause']=='true'):
				if(control['timer']['start'] != 0):
					control['notify_req']['timer'] = False
					now = time.time()
					control['timer']['paused'] = now
					DebugWrite('Timer paused.')
					WriteControl(control)
				else:
					control['notify_req']['timer'] = False
					control['timer']['start'] = 0
					control['timer']['end'] = 0
					DebugWrite('Timer cleared.')
					WriteControl(control)
		if('stop' in response):
			if(response['stop']=='true'):
				control['notify_req']['timer'] = False
				control['timer']['start'] = 0
				control['timer']['end'] = 0
				DebugWrite('Timer stopped.')
				WriteControl(control)

	if (request.method == 'POST') and (action == 'setnotify'):
		response = request.form

		if('grillnotify' in response):
			if(response['grillnotify']=='true'):
				set_point = int(response['grilltempInputRange'])
				control['setpoints']['grill'] = set_point
				if (control['mode'] == 'Hold'):
					control['updated'] = True
				control['notify_req']['grill'] = True
				WriteControl(control)
			else:
				control['notify_req']['grill'] = False
				WriteControl(control)

		if('probe1notify' in response):
			if(response['probe1notify']=='true'):
				set_point = int(response['probe1tempInputRange'])
				control['setpoints']['probe1'] = set_point
				control['notify_req']['probe1'] = True
				WriteControl(control)
			else:
				control['notify_req']['probe1'] = False
				WriteControl(control)

		if('probe2notify' in response):
			if(response['probe2notify']=='true'):
				set_point = int(response['probe2tempInputRange'])
				control['setpoints']['probe2'] = set_point
				control['notify_req']['probe2'] = True
				WriteControl(control)
			else:
				control['notify_req']['probe2'] = False
				WriteControl(control)

	if (request.method == 'POST') and (action == 'setmode'):
		response = request.form

		if('setpointtemp' in response):
			if(response['setpointtemp']=='true'):
				set_point = int(response['tempInputRange'])
				control['setpoints']['grill'] = set_point
				control['updated'] = True
				control['mode'] = 'Hold'
				WriteControl(control)
		if('setmodestartup' in response):
			if(response['setmodestartup']=='true'):
				control['updated'] = True
				control['mode'] = 'Startup'
				WriteControl(control)
		if('setmodesmoke' in response):
			if(response['setmodesmoke']=='true'):
				control['updated'] = True
				control['mode'] = 'Smoke'
				WriteControl(control)
		if('setmodeshutdown' in response):
			if(response['setmodeshutdown']=='true'):
				control['updated'] = True
				control['mode'] = 'Shutdown'
				WriteControl(control)
		if('setmodemonitor' in response):
			if(response['setmodemonitor']=='true'):
				control['updated'] = True
				control['mode'] = 'Monitor'
				WriteControl(control)
		if('setmodestop' in response):
			if(response['setmodestop']=='true'):
				control['updated'] = True
				control['mode'] = 'Stop'
				WriteControl(control)

	probes_enabled = settings['probes_enabled']

	cur_probe_temps = []
	cur_probe_temps = ReadCurrent()

	return render_template('index.html', cur_probe_temps=cur_probe_temps, probes_enabled=probes_enabled, set_points=control['setpoints'], current_mode=control['mode'], mode_status=control['status'], notify_req=control['notify_req'], control=control, page_theme=settings['page_theme'])

@app.route('/data/<action>', methods=['POST','GET'])
@app.route('/data', methods=['POST','GET'])
def data_dump(action=None):

	control = ReadControl()
	settings = ReadSettings()
	probes_enabled = settings['probes_enabled']

	cur_probe_temps = []
	cur_probe_temps = ReadCurrent()

	return render_template('data.html', cur_probe_temps=cur_probe_temps, probes_enabled=probes_enabled, set_points=control['setpoints'], current_mode=control['mode'], mode_status=control['status'], page_theme=settings['page_theme'])

@app.route('/history/<action>', methods=['POST','GET'])
@app.route('/history', methods=['POST','GET'])
def historypage(action=None):

	settings = ReadSettings()
	control = ReadControl()

	if (request.method == 'POST'):
		response = request.form

		if('start' in response):
			if(response['start']=='true'):
				control['notify_req']['timer'] = True
				if(control['timer']['paused'] == 0):
					now = time.time()
					control['timer']['start'] = now
					if(('hoursInputRange' in response) and ('minsInputRange' in response)):
						seconds = int(response['hoursInputRange']) * 60 * 60
						seconds = seconds + int(response['minsInputRange']) * 60
						control['timer']['end'] = now + seconds
					else:
						control['timer']['end'] = now + 60
					DebugWrite('Timer started.  Ends at: ' + str(control['timer']['end']))
					WriteControl(control)
				else:	# If Timer was paused, restart with new end time.
					now = time.time()
					control['timer']['end'] = (control['timer']['end'] - control['timer']['paused']) + now
					control['timer']['start'] = now
					control['timer']['paused'] = 0
					DebugWrite('Timer unpaused.  Ends at: ' + str(control['timer']['end']))
					WriteControl(control)
		if('pause' in response):
			if(response['pause']=='true'):
				if(control['timer']['start'] != 0):
					control['notify_req']['timer'] = False
					now = time.time()
					control['timer']['paused'] = now
					DebugWrite('Timer paused.')
					WriteControl(control)
				else:
					control['notify_req']['timer'] = False
					control['timer']['start'] = 0
					control['timer']['end'] = 0
					DebugWrite('Timer cleared.')
					WriteControl(control)
		if('stop' in response):
			if(response['stop']=='true'):
				control['notify_req']['timer'] = False
				control['timer']['start'] = 0
				control['timer']['end'] = 0
				DebugWrite('Timer stopped.')
				WriteControl(control)

	if (request.method == 'POST'):
		response = request.form
		if('autorefresh' in response):
			if(response['autorefresh'] == 'on'):
				settings['autorefresh'] = 'on'
				WriteSettings(settings)
			else:
				settings['autorefresh'] = 'off'
				WriteSettings(settings)

		if(action == 'setmins'):
			if('minutes' in response):
				if(response['minutes'] != ''):
					num_items = int(response['minutes']) * 20
					settings['minutes'] = int(response['minutes'])
					WriteSettings(settings)

		elif(action == 'clear'):
			if('clearhistory' in response):
				if(response['clearhistory'] == 'true'):
					DebugWrite('Clearing History Log.')
					os.system('rm /tmp/history.log')
					os.system('rm /tmp/current.log')

	elif (request.method == 'GET') and (action == 'export'):
		data_list = ReadHistory((settings['minutes'] * 20))

		exportfilename = "export.csv"
		csvfile = open('/tmp/'+exportfilename, "w")

		list_length = len(data_list) # Length of list

		if(list_length > 0):
			# Build Time_List, Settemp_List, Probe_List, cur_probe_temps
			writeline = 'Time,Grill Temp,Grill SetTemp,Probe 1 Temp,Probe 1 SetTemp,Probe 2 Temp, Probe 2 SetTemp\n'
			csvfile.write(writeline)
			last = -1
			for index in range(0, list_length):
				if (int((index/list_length)*100) > last):
					print('Generating Data: ' + str(int((index/list_length)*100)) + "%")
					last = int((index/list_length)*100)
				writeline = ','.join(data_list[index])
				csvfile.write(writeline + '\n')
		else:
			writeline = 'No Data\n'
			csvfile.write(writeline)

		csvfile.close()

		return send_file('/tmp/'+exportfilename, as_attachment=True, cache_timeout=0)

	num_items = settings['minutes'] * 20
	probes_enabled = settings['probes_enabled']

	data_blob = {}
	data_blob = prepare_data(num_items, True, settings['datapoints'])

	return render_template('history.html', control=control, time_list=data_blob['time_list'], probe_list=data_blob['probe_list'], settemp_list=data_blob['settemp_list'], cur_probe_temps=data_blob['cur_probe_temps'], probes_enabled=probes_enabled, num_mins=settings['minutes'], autorefresh=settings['autorefresh'], page_theme=settings['page_theme'])

@app.route('/historyupdate')
def historyupdate(action=None):

	settings = ReadSettings()

	num_items = settings['minutes'] * 20
	probes_enabled = settings['probes_enabled']

	data_blob = {}
	data_blob = prepare_data(num_items, True, settings['datapoints'])

	return render_template('historyupdate.html', time_list=data_blob['time_list'], probe_list=data_blob['probe_list'], settemp_list=data_blob['settemp_list'], cur_probe_temps=data_blob['cur_probe_temps'], probes_enabled=probes_enabled, num_mins=settings['minutes'])

@app.route('/tuning/<action>', methods=['POST','GET'])
@app.route('/tuning', methods=['POST','GET'])
def tuningpage(action=None):

	settings = ReadSettings()
	control = ReadControl()

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
	
	return render_template('tuning.html', control=control, settings=settings, pagectrl=pagectrl)

@app.route('/_grilltr', methods = ['GET'])
def grilltr(action=None):

	cur_probe_tr = ReadTr()
	tr = {}
	tr['trohms'] = cur_probe_tr[0]

	return json.dumps(tr)

@app.route('/_probe1tr', methods = ['GET'])
def probe1tr(action=None):

	cur_probe_tr = ReadTr()
	tr = {}
	tr['trohms'] = cur_probe_tr[1]

	return json.dumps(tr)

@app.route('/_probe2tr', methods = ['GET'])
def probe2tr(action=None):

	cur_probe_tr = ReadTr()
	tr = {}
	tr['trohms'] = cur_probe_tr[1]

	return json.dumps(tr)


@app.route('/events/<action>', methods=['POST','GET'])
@app.route('/events', methods=['POST','GET'])
def eventspage(action=None):

	# Show list of logged events and debug event list
	event_list, num_events = ReadLog()
	debug_event_list, debug_num_events = DebugRead()
	settings = ReadSettings()

	return render_template('events.html', event_list=event_list, num_events=num_events, debug_event_list=debug_event_list, debug_num_events=debug_num_events, page_theme=settings['page_theme'])


@app.route('/recipes', methods=['POST','GET'])
def recipespage(action=None):

	print('Recipes Page')
	# Show current recipes
	# Add a recipe
	# Delete a Recipe
	# Run a Recipe
	settings = ReadSettings()

	return render_template('recipes.html', page_theme=settings['page_theme'])

@app.route('/settings/<action>', methods=['POST','GET'])
@app.route('/settings', methods=['POST','GET'])
def settingspage(action=None):

	settings = ReadSettings()

	event = {}

	event = {
		'type' : 'none',
		'text' : ''
	}

	if (request.method == 'POST') and (action == 'probes'):
		response = request.form

		if('grill0enable' in response):
			if(response['grill0enable'] == "0"):
				settings['probes_enabled'][0] = 0
			else:
				settings['probes_enabled'][0] = 1
		if('probe1enable' in response):
			if(response['probe1enable'] == "0"):
				settings['probes_enabled'][1] = 0
			else:
				settings['probes_enabled'][1] = 1
		if('probe2enable' in response):
			if(response['probe2enable'] == "0"):
				settings['probes_enabled'][2] = 0
			else:
				settings['probes_enabled'][2] = 1
		if('grill_probe_type' in response):
			if(response['grill_probe_type'] != settings['probe_types']['grill0type']):
				settings['probe_types']['grill0type'] = response['grill_probe_type']
				event['type'] = 'updated'
				event['text'] = 'Probe type updated. Settings saved.'
		if('probe1_type' in response):
			if(response['probe1_type'] != settings['probe_types']['probe1type']):
				settings['probe_types']['probe1type'] = response['probe1_type']
				event['type'] = 'updated'
				event['text'] = 'Probe type updated. Settings saved.'
		if('probe2_type' in response):
			if(response['probe2_type'] != settings['probe_types']['probe2type']):
				settings['probe_types']['probe2type'] = response['probe2_type']
				event['type'] = 'updated'
				event['text'] = 'Probe type updated. Settings saved.'

		# Take all settings and write them
		WriteSettings(settings)

	if (request.method == 'POST') and (action == 'notify'):
		response = request.form

		if('iftttapi' in response):
			if(response['iftttapi'] == "0") or (response['iftttapi'] == ''):
				settings['ifttt']['APIKey'] = ''
				event['type'] = 'warning'
				event['text'] = 'IFTTT API Key removed. Settings saved.'
			else:
				settings['ifttt']['APIKey'] = response['iftttapi']
				event['type'] = 'updated'
				event['text'] = 'IFTTT API Key updated. Settings saved.'

		if('pushover_apikey' in response):
			if((response['pushover_apikey'] == "0") or (response['pushover_apikey'] == '')) and (settings['pushover']['APIKey'] != ''):
				settings['pushover']['APIKey'] = ''
				event['type'] = 'warning'
				event['text'] = 'Pushover API Key removed. Settings saved.'
			elif(response['pushover_apikey'] != settings['pushover']['APIKey']):
				settings['pushover']['APIKey'] = response['pushover_apikey']
				event['type'] = 'updated'
				event['text'] = 'PushOver API Key updated. Settings saved.'

		if('pushover_userkeys' in response):
			if((response['pushover_userkeys'] == "0") or (response['pushover_userkeys'] == '')) and (settings['pushover']['UserKeys'] != ''):
				settings['pushover']['UserKeys'] = ''
				event['type'] = 'warning'
				event['text'] = 'Pushover User Keys removed. Settings saved.'
			elif(response['pushover_userkeys'] != settings['pushover']['UserKeys']):
				settings['pushover']['UserKeys'] = response['pushover_userkeys']
				event['type'] = 'updated'
				event['text'] = 'PushOver User Keys updated. Settings saved.'
		# Take all settings and write them
		WriteSettings(settings)

	if (request.method == 'POST') and (action == 'editprofile'):
		response = request.form

		if('delete' in response):
			UniqueID = response['delete'] # Get the string of the UniqueID
			try:
				settings['probe_profiles'].pop(UniqueID)
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
					settings['probe_profiles'][UniqueID] = {
						'Vs' : float(response['Vs_' + UniqueID]),
						'Rd' : int(response['Rd_' + UniqueID]),
						'A' : float(response['A_' + UniqueID]),
						'B' : float(response['B_' + UniqueID]),
						'C' : float(response['C_' + UniqueID]),
						'name' : response['Name_' + UniqueID]
					}

					if (response['UniqueID_' + UniqueID] != UniqueID):
						# Copy Old Profile to New Profile
						settings['probe_profiles'][response['UniqueID_' + UniqueID]] = settings['probe_profiles'][UniqueID]
						# Remove the Old Profile
						settings['probe_profiles'].pop(UniqueID)
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
				settings['probe_profiles'][response['UniqueID']] = {
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
		if('cycletime' in response):
			if(response['cycletime'] != ''):
				settings['cycle_data']['CycleTime'] = int(response['cycletime'])
		if('propband' in response):
			if(response['propband'] != ''):
				settings['cycle_data']['PB'] = float(response['propband'])
		if('integraltime' in response):
			if(response['integraltime'] != ''):
				settings['cycle_data']['Ti'] = float(response['integraltime'])
		if('derivtime' in response):
			if(response['derivtime'] != ''):
				settings['cycle_data']['Td'] = float(response['derivtime'])

		event['type'] = 'updated'
		event['text'] = 'Successfully updated cycle settings.'

		WriteSettings(settings)

	if (request.method == 'POST') and (action == 'history'):
		response = request.form

		if('historymins' in response):
			if(response['historymins'] != ''):
				settings['minutes'] = int(response['historymins'])

		if('clearhistorystartup' in response):
			if(response['clearhistorystartup'] == 'on'):
				settings['clearhistoryonstart'] = True
		else:
			settings['clearhistoryonstart'] = False

		if('historyautorefresh' in response):
			if(response['historyautorefresh'] == 'on'):
				settings['autorefresh'] = 'on'
		else:
			settings['autorefresh'] = 'off'

		if('datapoints' in response):
			if(response['datapoints'] != ''):
				settings['datapoints'] = int(response['datapoints'])

		event['type'] = 'updated'
		event['text'] = 'Successfully updated history settings.'

		WriteSettings(settings)

	if (request.method == 'POST') and (action == 'pagesettings'):
		response = request.form

		print(response)

		if('darkmode' in response):
			if(response['darkmode'] == 'on'):
				settings['page_theme'] = 'dark'
		else:
			settings['page_theme'] = 'light'

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

	return render_template('settings.html', settings=settings, alert=event)

@app.route('/admin/<action>', methods=['POST','GET'])
@app.route('/admin', methods=['POST','GET'])
def adminpage(action=None):

	settings = ReadSettings()

	if action == 'reboot':
		event = "Admin: Reboot"
		WriteLog(event)
		DebugWrite(event)
		os.system("sleep 3 && sudo reboot &")
		return render_template('shutdown.html', action=action, page_theme=settings['page_theme'])

	elif action == 'shutdown':
		event = "Admin: Shutdown"
		WriteLog(event)
		DebugWrite(event)
		os.system("sleep 3 && sudo shutdown -h now &")
		return render_template('shutdown.html', action=action, page_theme=settings['page_theme'])

	if (request.method == 'POST') and (action == 'setting'):
		response = request.form

		if('debugenabled' in response):
			if(response['debugenabled']=='disabled'):
				DebugWrite('Debug Mode Disabled.')
				settings['debug_mode'] = False
				WriteSettings(settings)
			else:
				settings['debug_mode'] = True
				WriteSettings(settings)
				DebugWrite('Debug Mode Enabled.')

		if('clearhistory' in response):
			if(response['clearhistory']=='true'):
				DebugWrite('Clearing History Log.')
				os.system('rm /tmp/history.log')
				os.system('rm /tmp/current.log')

		if('cleardebug' in response):
			if(response['cleardebug']=='true'):
				os.system('rm /tmp/debug.log')

		if('clearevents' in response):
			if(response['clearevents']=='true'):
				DebugWrite('Clearing Events Log.')
				os.system('rm /tmp/events.log')

		if('factorydefaults' in response):
			if(response['factorydefaults']=='true'):
				DebugWrite('Resetting Settings, Control, History to factory defaults.')
				os.system('rm /tmp/history.log')
				os.system('rm /tmp/current.log')
				os.system('rm settings.json')
				os.system('rm /tmp/control.json')
				settings = DefaultSettings()
				control = DefaultControl()
				WriteSettings(settings)
				WriteControl(control)

	uptime = os.popen('uptime').readline()

	cpuinfo = os.popen('cat /proc/cpuinfo').readlines()

	ifconfig = os.popen('ifconfig').readlines()

	temp = checkcputemp()

	debug_mode = settings['debug_mode']

	return render_template('admin.html', settings=settings, action=action, uptime=uptime, cpuinfo=cpuinfo, temp=temp, ifconfig=ifconfig, debug_mode=debug_mode)

@app.route('/manual/<action>', methods=['POST','GET'])
@app.route('/manual', methods=['POST','GET'])
def manual_page(action=None):

	settings = ReadSettings()
	control = ReadControl()

	if (request.method == 'POST'):
		response = request.form

		if('setmode' in response):
			if(response['setmode']=='manual'):
				control['updated'] = True
				control['mode'] = 'Manual'
				WriteControl(control)

		if('change_output_fan' in response):
			if(response['change_output_fan']=='on'):
				control['manual']['change'] = True
				control['manual']['output'] = 'fan'
				control['manual']['state'] = 'on'
				WriteControl(control)
			elif(response['change_output_fan']=='off'):
				control['manual']['change'] = True
				control['manual']['output'] = 'fan'
				control['manual']['state'] = 'off'
				WriteControl(control)
		elif('change_output_auger' in response):
			if(response['change_output_auger']=='on'):
				control['manual']['change'] = True
				control['manual']['output'] = 'auger'
				control['manual']['state'] = 'on'
				WriteControl(control)
			elif(response['change_output_auger']=='off'):
				control['manual']['change'] = True
				control['manual']['output'] = 'auger'
				control['manual']['state'] = 'off'
				WriteControl(control)
		elif('change_output_igniter' in response):
			if(response['change_output_igniter']=='on'):
				control['manual']['change'] = True
				control['manual']['output'] = 'igniter'
				control['manual']['state'] = 'on'
				WriteControl(control)
			elif(response['change_output_igniter']=='off'):
				control['manual']['change'] = True
				control['manual']['output'] = 'igniter'
				control['manual']['state'] = 'off'
				WriteControl(control)
		elif('change_output_power' in response):
			if(response['change_output_power']=='on'):
				control['manual']['change'] = True
				control['manual']['output'] = 'power'
				control['manual']['state'] = 'on'
				WriteControl(control)
			elif(response['change_output_power']=='off'):
				control['manual']['change'] = True
				control['manual']['output'] = 'power'
				control['manual']['state'] = 'off'
				WriteControl(control)
		time.sleep(1)
		control = ReadControl()

	return render_template('manual.html', settings=settings, control=control)

@app.route('/api/<action>', methods=['POST','GET'])
@app.route('/api', methods=['POST','GET'])
def api_page(action=None):

	if (request.method == 'GET'):
		if(action == 'settings'):
			settings=ReadSettings()
			return jsonify({'settings':settings}), 201
		elif(action == 'control'):
			control=ReadControl()
			return jsonify({'control':control}), 201
		elif(action == 'current'):
			current=ReadCurrent()
			current_temps = {
				'grill_temp' : current[0],
				'probe1_temp' : current[1],
				'probe2_temp' : current[2]
			}
			return jsonify({'current':current_temps}), 201
		else:
			return jsonify({'Error':'Recieved GET request with no action.'}), 404
	elif (request.method == 'POST'):
		if(action == 'settings'):
			#settings=ReadSettings()
			return jsonify({'settings':'updated successfully'}), 201
		elif(action == 'control'):
			#control=ReadControl()
			return jsonify({'control':'updated successfully'}), 201
		else:
			return jsonify({'Error':'Recieved POST request with no action.'}), 404
	else:
		return jsonify({'Error':'Recieved undefined/unsupported request.'}), 404
	#return jsonify({'settings':settings,'control':control, 'current':current_temps}), 201

@app.route('/manifest')
def manifest():
    res = make_response(render_template('manifest.json'), 200)
    res.headers["Content-Type"] = "text/cache-manifest"
    return res

def checkcputemp():
	temp = os.popen('vcgencmd measure_temp').readline()
	return temp.replace("temp=","")

def prepare_data(num_items=10, reduce=True, datapoints=60):

	# num_items Number of items to store in the data blob

	data_list = ReadHistory(num_items)

	data_blob = {}

	data_blob['time_list'] = ''
	data_blob['settemp_list'] = ['','','']
	data_blob['probe_list'] = ['','','']
	data_blob['cur_probe_temps'] = [0,0,0]

	list_length = len(data_list) # Length of list

	if((list_length < num_items) and (list_length > 0)):
		num_items = list_length

	if((reduce==True) and (num_items > datapoints)):
		step = int(num_items/datapoints)
	else:
		step = 1

	if(list_length > 0):
		# Build Time_List, Settemp_List, Probe_List, cur_probe_temps backwards from current time
		for index in range(list_length - num_items, list_length, step):
			if(index == 0):
				comma = ''
			else:
				comma = ', '

			data_blob['time_list'] = '"' + str(data_list[(list_length-1-index)][0]) + '"' + comma + data_blob['time_list']
			data_blob['probe_list'][0] = str(data_list[list_length-1-index][1]) + comma + data_blob['probe_list'][0]
			data_blob['settemp_list'][0] = str(data_list[list_length-1-index][2]) + comma + data_blob['settemp_list'][0]
			data_blob['probe_list'][1] = str(data_list[list_length-1-index][3]) + comma + data_blob['probe_list'][1]
			data_blob['settemp_list'][1] = str(data_list[list_length-1-index][4]) + comma + data_blob['settemp_list'][1]
			data_blob['probe_list'][2] = str(data_list[list_length-1-index][5]) + comma + data_blob['probe_list'][2]
			data_blob['settemp_list'][2] = str(data_list[list_length-1-index][6]) + comma + data_blob['settemp_list'][2]

		data_blob['cur_probe_temps'][0] = int(data_list[list_length-1][1])
		data_blob['cur_probe_temps'][1] = int(data_list[list_length-1][3])
		data_blob['cur_probe_temps'][2] = int(data_list[list_length-1][5])
	else:
		now = str(datetime.datetime.now())
		now = now[0:19] # Truncate the microseconds
		for index in range(num_items):
			data_blob['time_list'] = data_blob['time_list'] + '"' + str(now) + '"'
			data_blob['probe_list'][0] = data_blob['probe_list'][0] + "0"
			data_blob['settemp_list'][0] = data_blob['settemp_list'][0] + "0"
			data_blob['probe_list'][1] = data_blob['probe_list'][1] + "0"
			data_blob['settemp_list'][1] = data_blob['settemp_list'][1] + "0"
			data_blob['probe_list'][2] = data_blob['probe_list'][2] + "0"
			data_blob['settemp_list'][2] = data_blob['settemp_list'][2] + "0"

			if(index < num_items - 1):
				data_blob['time_list'] = data_blob['time_list'] + ", "
				data_blob['probe_list'][0] = data_blob['probe_list'][0] + ", "
				data_blob['settemp_list'][0] = data_blob['settemp_list'][0] + ", "
				data_blob['probe_list'][1] = data_blob['probe_list'][1] + ", "
				data_blob['settemp_list'][1] = data_blob['settemp_list'][1] + ", "
				data_blob['probe_list'][2] = data_blob['probe_list'][2] + ", "
				data_blob['settemp_list'][2] = data_blob['settemp_list'][2] + ", "

		data_blob['cur_probe_temps'][0] = 0
		data_blob['cur_probe_temps'][1] = 0
		data_blob['cur_probe_temps'][2] = 0

	return(data_blob)

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
		print('An error occurred when calculating coefficients.')
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
        print('Error occured while calculating temperature.')
        tempF = 0.0
    return int(tempF) # Return Calculated Temperature and Thermistor Value in Ohms

if __name__ == '__main__':
	app.run(host='0.0.0.0')
	#app.run(host='0.0.0.0',debug=True) # Use this instead of the above line for debug mode
