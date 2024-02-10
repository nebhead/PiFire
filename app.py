'''
==============================================================================
 PiFire Web UI (Flask App) Process
==============================================================================

Description: This script will start at boot, and start up the web user
  interface.
 
   This script runs as a separate process from the control program
  implementation which handles interfacing and running I2C devices & GPIOs.

==============================================================================
'''

'''
==============================================================================
 Imported Modules
==============================================================================
'''

from flask import Flask, request, abort, render_template, make_response, send_file, jsonify, redirect, render_template_string
from flask_mobility import Mobility
from flask_socketio import SocketIO
from flask_qrcode import QRcode
from io import BytesIO
from werkzeug.utils import secure_filename
from collections.abc import Mapping
import threading
import zipfile
import pathlib
from threading import Thread
from datetime import datetime
from updater import *  # Library for doing project updates from GitHub
from file_mgmt.common import fixup_assets, read_json_file_data, update_json_file_data, remove_assets
from file_mgmt.cookfile import read_cookfile, upgrade_cookfile, prepare_chartdata
from file_mgmt.media import add_asset, set_thumbnail, unpack_thumb
from file_mgmt.recipes import read_recipefile, create_recipefile

'''
==============================================================================
 Constants & Globals 
==============================================================================
'''

BACKUP_PATH = './backups/'  # Path to backups of settings.json, pelletdb.json
UPLOAD_FOLDER = BACKUP_PATH  # Point uploads to the backup path
HISTORY_FOLDER = './history/'  # Path to historical cook files
RECIPE_FOLDER = './recipes/'  # Path to recipe files 
LOGS_FOLDER = './logs/'  # Path to log files 
ALLOWED_EXTENSIONS = {'json', 'pifire', 'pfrecipe', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'log'}
server_status = 'available'

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
QRcode(app)
Mobility(app)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['HISTORY_FOLDER'] = HISTORY_FOLDER
app.config['RECIPE_FOLDER'] = RECIPE_FOLDER

'''
==============================================================================
 App Routes
==============================================================================
'''
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
	control = read_control()
	errors = read_errors()
	warnings = read_warnings()

	current = settings['dashboard']['current']
	dash_template = settings['dashboard']['dashboards'][current].get('html_name', 'dash_default.html')
	dash_data = settings['dashboard']['dashboards'].get(current, {})

	return render_template(dash_template,
						   settings=settings,
						   control=control,
						   dash_data=dash_data,
						   errors=errors,
						   warnings=warnings,
						   page_theme=settings['globals']['page_theme'],
						   grill_name=settings['globals']['grill_name'])

@app.route('/hopperlevel')
def hopper_level():
	pelletdb = read_pellet_db()
	cur_pellets_string = pelletdb['archive'][pelletdb['current']['pelletid']]['brand'] + ' ' + \
						 pelletdb['archive'][pelletdb['current']['pelletid']]['wood']
	return jsonify({ 'hopper_level' : pelletdb['current']['hopper_level'], 'cur_pellets' : cur_pellets_string })

@app.route('/timer', methods=['POST','GET'])
def timer():
	global settings 
	control = read_control()

	if request.method == "GET":
		return jsonify({ 'start' : control['timer']['start'], 'paused' : control['timer']['paused'],
						 'end' : control['timer']['end'], 'shutdown': control['timer']['shutdown']})
	elif request.method == "POST": 
		if 'input' in request.form:
			for index, notify_obj in enumerate(control['notify_data']):
				if notify_obj['type'] == 'timer':
					break 
			if 'timer_start' == request.form['input']: 
				control['notify_data'][index]['req'] = True
				# If starting new timer
				if control['timer']['paused'] == 0:
					now = time.time()
					control['timer']['start'] = now
					if 'hoursInputRange' in request.form and 'minsInputRange' in request.form:
						seconds = int(request.form['hoursInputRange']) * 60 * 60
						seconds = seconds + int(request.form['minsInputRange']) * 60
						control['timer']['end'] = now + seconds
					else:
						control['timer']['end'] = now + 60
					if 'shutdownTimer' in request.form:
						if request.form['shutdownTimer'] == 'true':
							control['notify_data'][index]['shutdown'] = True
						else: 
							control['notify_data'][index]['shutdown'] = False
					if 'keepWarmTimer' in request.form:
						if request.form['keepWarmTimer'] == 'true':
							control['notify_data'][index]['keep_warm'] = True
						else:
							control['notify_data'][index]['keep_warm'] = False
					write_log('Timer started.  Ends at: ' + epoch_to_time(control['timer']['end']))
					write_control(control, origin='app')
				else:	# If Timer was paused, restart with new end time.
					now = time.time()
					control['timer']['end'] = (control['timer']['end'] - control['timer']['paused']) + now
					control['timer']['paused'] = 0
					write_log('Timer unpaused.  Ends at: ' + epoch_to_time(control['timer']['end']))
					write_control(control, origin='app')
			elif 'timer_pause' == request.form['input']:
				if control['timer']['start'] != 0:
					control['notify_data'][index]['req'] = False
					now = time.time()
					control['timer']['paused'] = now
					write_log('Timer paused.')
					write_control(control, origin='app')
				else:
					control['notify_data'][index]['req'] = False
					control['timer']['start'] = 0
					control['timer']['end'] = 0
					control['timer']['paused'] = 0
					control['notify_data'][index]['shutdown'] = False
					control['notify_data'][index]['keep_warm'] = False
					write_log('Timer cleared.')
					write_control(control, origin='app')
			elif 'timer_stop' == request.form['input']:
				control['notify_data'][index]['req'] = False
				control['timer']['start'] = 0
				control['timer']['end'] = 0
				control['notify_data'][index]['shutdown'] = False
				control['notify_data'][index]['keep_warm'] = False
				write_log('Timer stopped.')
				write_control(control, origin='app')
		return jsonify({'result':'success'})

@app.route('/history/<action>', methods=['POST','GET'])
@app.route('/history', methods=['POST','GET'])
def history_page(action=None):
	global settings
	control = read_control()
	errors = []

	if request.method == 'POST':
		response = request.form
		if(action == 'cookfile'):
			if('delcookfile' in response):
				filename = './history/' + response["delcookfile"]
				os.remove(filename)
				return redirect('/history')
			if('opencookfile' in response):
				cookfilename = HISTORY_FOLDER + response['opencookfile']
				cookfilestruct, status = read_cookfile(cookfilename)
				if(status == 'OK'):
					events = cookfilestruct['events']
					event_totals = _prepare_event_totals(events)
					comments = cookfilestruct['comments']
					for comment in comments:
						comment['text'] = comment['text'].replace('\n', '<br>')
					metadata = cookfilestruct['metadata']
					metadata['starttime'] = epoch_to_time(metadata['starttime'] / 1000)
					metadata['endtime'] = epoch_to_time(metadata['endtime'] / 1000)
					labels = cookfilestruct['graph_labels']
					assets = cookfilestruct['assets']
					filenameonly = response['opencookfile']
					return render_template('cookfile.html', settings=settings, cookfilename=cookfilename, 
						filenameonly=filenameonly, events=events, event_totals=event_totals, comments=comments, 
						metadata=metadata, labels=labels, assets=assets, errors=errors, 
						page_theme=settings['globals']['page_theme'], grill_name=settings['globals']['grill_name'])
				else:
					errors.append(status)
					if 'version' in status:
						errortype = 'version'
					elif 'asset' in status: 
						errortype = 'asset'
					else: 
						errortype = 'other'
					return render_template('cferror.html', settings=settings, cookfilename=cookfilename, errortype=errortype, errors=errors, page_theme=settings['globals']['page_theme'], grill_name=settings['globals']['grill_name'])
			if('dlcookfile' in response):
				filename = './history/' + response['dlcookfile']
				return send_file(filename, as_attachment=True, max_age=0)

		if(action == 'setmins'):
			if('minutes' in response):
				if(response['minutes'] != ''):
					num_items = int(response['minutes']) * 20
					settings['history_page']['minutes'] = int(response['minutes'])
					write_settings(settings)

	elif (request.method == 'GET') and (action == 'export'):
		exportfilename = prepare_csv()
		return send_file(exportfilename, as_attachment=True, max_age=0)

	return render_template('history.html',
						   control=control, settings=settings,
						   page_theme=settings['globals']['page_theme'],
						   grill_name=settings['globals']['grill_name'])

@app.route('/historyupdate/<action>', methods=['POST','GET'])    
@app.route('/historyupdate')
def history_update(action=None):
	global settings

	if action == 'stream':
		# GET - Read current temperatures and set points for history streaming 
		control = read_control()
		json_response = {}
		if control['mode'] in ['Stop', 'Error']:
			json_response['current'] = read_current(zero_out=True) # Probe Temps Zero'd Out
		else:
			json_response['current'] = read_current() # Probe Temps Zero'd Out

		# Calculate Displayed Start Time
		displayed_starttime = time.time() - (settings['history_page']['minutes'] * 20)
		json_response['annotations'] = _prepare_annotations(displayed_starttime)
		json_response['mode'] = control['mode']
		json_response['ui_hash'] = create_ui_hash()
		json_response['timestamp'] = int(time.time() * 1000)
		
		return jsonify(json_response)

	elif action == 'refresh':
		# POST - Get number of minutes into the history to refresh the history chart
		control = read_control()
		request_json = request.json
		if 'num_mins' in request_json:
			num_items = int(request_json['num_mins']) * 20 if int(request_json['num_mins']) > 0 else 20 # Calculate number of items requested
			settings['history_page']['minutes'] = int(request_json['num_mins']) if int(request_json['num_mins']) > 0 else 1
			write_settings(settings)
		elif 'zoom' in request_json:
			num_items = int(request_json['zoom']) * 20
		else: 
			num_items = int(settings['history_page']['minutes'] * 20)

		# Get Chart Data Structures
		json_response = prepare_chartdata(settings['history_page']['probe_config'], num_items=num_items, reduce=True, data_points=settings['history_page']['datapoints'])
		json_response['ui_hash'] = create_ui_hash()
		# Calculate Displayed Start Time
		displayed_starttime = time.time() - (int(num_items / 20) * 60)
		json_response['annotations'] = _prepare_annotations(displayed_starttime)
		'''
		json_response = {
			'annotations' : [], 
			'time_labels' : time_labels,
			'probe_mapper' : probe_mapper, 
			'chart_data' : chart_data
		}		
		'''
		return jsonify(json_response)

	return jsonify({'status' : 'ERROR'})

@app.route('/cookfiledata', methods=['POST', 'GET'])
def cookfiledata(action=None):
	global settings 

	errors = []
	
	if(request.method == 'POST') and ('json' in request.content_type):
		requestjson = request.json
		if('full_graph' in requestjson):
			filename = requestjson['filename']
			cookfiledata, status = read_cookfile(filename)

			if(status == 'OK'):
				annotations = _prepare_annotations(0, cookfiledata['events'])

				json_data = {
					'chart_data' : cookfiledata['graph_data']['chart_data'],
					'time_labels' : cookfiledata['graph_data']['time_labels'],
					'probe_mapper' : cookfiledata['graph_data']['probe_mapper'],
					'annotations' : annotations
				}
				return jsonify(json_data)

		if('getcommentassets' in requestjson):
			assetlist = []
			cookfilename = requestjson['cookfilename']
			commentid = requestjson['commentid']
			comments, status = read_json_file_data(cookfilename, 'comments')
			for comment in comments:
				if comment['id'] == commentid:
					assetlist = comment['assets']
					break
			return jsonify({'result' : 'OK', 'assetlist' : assetlist})

		if('managemediacomment' in requestjson):
			# Grab list of all assets in file, build assetlist
			assetlist = []
			cookfilename = requestjson['cookfilename']
			commentid = requestjson['commentid']
			
			assets, status = read_json_file_data(cookfilename, 'assets')
			metadata, status = read_json_file_data(cookfilename, 'metadata')
			for asset in assets:
				asset_object = {
					'assetname' : asset['filename'],
					'assetid' : asset['id'],
					'selected' : False
				}
				assetlist.append(asset_object)

			# Grab list of selected assets in comment currently
			selectedassets = []
			comments, status = read_json_file_data(cookfilename, 'comments')
			for comment in comments:
				if comment['id'] == commentid:
					selectedassets = comment['assets']
					break 

			# For each item in asset list, if in comment, mark selected
			for object in assetlist:
				if object['assetname'] in selectedassets:
					object['selected'] = True 

			return jsonify({'result' : 'OK', 'assetlist' : assetlist}) 

		if('getallmedia' in requestjson):
			# Grab list of all assets in file, build assetlist
			assetlist = []
			cookfilename = requestjson['cookfilename']
			assets, status = read_json_file_data(cookfilename, 'assets')

			for asset in assets:
				asset_object = {
					'assetname' : asset['filename'],
					'assetid' : asset['id'],
				}
				assetlist.append(asset_object)

			return jsonify({'result' : 'OK', 'assetlist' : assetlist}) 

		if('navimage' in requestjson):
			direction = requestjson['navimage']
			mediafilename = requestjson['mediafilename'] 
			commentid = requestjson['commentid']
			cookfilename = requestjson['cookfilename']

			comments, status = read_json_file_data(cookfilename, 'comments')
			if status == 'OK':
				assetlist = []
				for comment in comments:
					if comment['id'] == commentid:
						assetlist = comment['assets']
						break 
				current = 0
				found = False 
				for index in range(0, len(assetlist)):
					if assetlist[index] == mediafilename:
						current = index
						found = True 
						break 
				
				if found and direction == 'next':
					if current == len(assetlist)-1:
						mediafilename = assetlist[0]
					else:
						mediafilename = assetlist[current+1]
					return jsonify({'result' : 'OK', 'mediafilename' : mediafilename})
				elif found and direction == 'prev':
					if current == 0:
						mediafilename = assetlist[-1]
					else:
						mediafilename = assetlist[current-1]
					return jsonify({'result' : 'OK', 'mediafilename' : mediafilename})

		errors.append('Something unexpected has happened.')
		return jsonify({'result' : 'ERROR', 'errors' : errors})

	if(request.method == 'POST') and ('form' in request.content_type):
		requestform = request.form 
		if('dl_cookfile' in requestform):
			# Download the full JSON Cook File Locally
			filename = requestform['dl_cookfile']
			return send_file(filename, as_attachment=True, max_age=0)

		if('dl_eventfile' in requestform):
			filename = requestform['dl_eventfile']
			cookfiledata, status = read_json_file_data(filename, 'events')
			if(status == 'OK'):
				csvfilename = _prepare_metrics_csv(cookfiledata, filename)
				return send_file(csvfilename, as_attachment=True, max_age=0)

		if('dl_graphfile' in requestform):
			# Download CSV of the raw temperature data (and extended data)
			filename = requestform['dl_graphfile']
			cookfiledata, status = read_cookfile(filename)
			if(status == 'OK'):
				csvfilename = prepare_csv(cookfiledata['raw_data'], filename)
				return send_file(csvfilename, as_attachment=True, max_age=0)

		if('ulcookfilereq' in requestform):
			# Assume we have request.files and localfile in response
			remotefile = request.files['ulcookfile']
			
			if (remotefile.filename != ''):
				# If the user does not select a file, the browser submits an
				# empty file without a filename.
				if remotefile and _allowed_file(remotefile.filename):
					filename = secure_filename(remotefile.filename)
					remotefile.save(os.path.join(app.config['HISTORY_FOLDER'], filename))
				else:
					errors.append('Disallowed File Upload.')
				return redirect('/history')

		if('thumbSelected' in requestform):
			thumbnail = requestform['thumbSelected']
			filename = requestform['filename']
			# Reload Cook File
			cookfilename = HISTORY_FOLDER + filename
			cookfilestruct, status = read_cookfile(cookfilename)
			if status=='OK':
				cookfilestruct['metadata']['thumbnail'] = thumbnail
				update_json_file_data(cookfilestruct['metadata'], HISTORY_FOLDER + filename, 'metadata')
				events = cookfilestruct['events']
				event_totals = _prepare_event_totals(events)
				comments = cookfilestruct['comments']
				for comment in comments:
					comment['text'] = comment['text'].replace('\n', '<br>')
				metadata = cookfilestruct['metadata']
				metadata['starttime'] = epoch_to_time(metadata['starttime'] / 1000)
				metadata['endtime'] = epoch_to_time(metadata['endtime'] / 1000)
				labels = cookfilestruct['graph_labels']
				assets = cookfilestruct['assets']
				
				return render_template('cookfile.html', settings=settings, \
					cookfilename=cookfilename, filenameonly=filename, \
					events=events, event_totals=event_totals, \
					comments=comments, metadata=metadata, labels=labels, \
					assets=assets, errors=errors, \
					page_theme=settings['globals']['page_theme'], \
					grill_name=settings['globals']['grill_name'])

		if('ulmediafn' in requestform) or ('ulthumbfn' in requestform):
			# Assume we have request.files and localfile in response
			if 'ulmediafn' in requestform:
				#uploadedfile = request.files['ulmedia']
				uploadedfiles = request.files.getlist('ulmedia')
				cookfilename = HISTORY_FOLDER + requestform['ulmediafn']
				filenameonly = requestform['ulmediafn']
			else: 
				uploadedfile = request.files['ulthumbnail']
				cookfilename = HISTORY_FOLDER + requestform['ulthumbfn']
				filenameonly = requestform['ulthumbfn']
				uploadedfiles = [uploadedfile]

			status = 'ERROR'
			for remotefile in uploadedfiles:
				if (remotefile.filename != ''):
					# Reload Cook File
					cookfilestruct, status = read_cookfile(cookfilename)
					parent_id = cookfilestruct['metadata']['id']
					tmp_path = f'/tmp/pifire/{parent_id}'
					if not os.path.exists(tmp_path):
						os.mkdir(tmp_path)

					if remotefile and _allowed_file(remotefile.filename):
						filename = secure_filename(remotefile.filename)
						pathfile = os.path.join(tmp_path, filename)
						remotefile.save(pathfile)
						asset_id, asset_filetype = add_asset(cookfilename, tmp_path, filename)
						if 'ulthumbfn' in requestform:
							set_thumbnail(cookfilename, f'{asset_id}.{asset_filetype}')
						#  Reload all of the data
						cookfilestruct, status = read_cookfile(cookfilename)
					else:
						errors.append('Disallowed File Upload.')

			if(status == 'OK'):
				events = cookfilestruct['events']
				event_totals = _prepare_event_totals(events)
				comments = cookfilestruct['comments']
				for comment in comments:
					comment['text'] = comment['text'].replace('\n', '<br>')
				metadata = cookfilestruct['metadata']
				metadata['starttime'] = epoch_to_time(metadata['starttime'] / 1000)
				metadata['endtime'] = epoch_to_time(metadata['endtime'] / 1000)
				labels = cookfilestruct['graph_labels']
				assets = cookfilestruct['assets']

				return render_template('cookfile.html', settings=settings, \
					cookfilename=cookfilename, filenameonly=filenameonly, \
					events=events, event_totals=event_totals, \
					comments=comments, metadata=metadata, labels=labels, \
					assets=assets, errors=errors, \
					page_theme=settings['globals']['page_theme'], \
					grill_name=settings['globals']['grill_name'])

		if('cookfilelist' in requestform):
			page = int(requestform['page'])
			reverse = True if requestform['reverse'] == 'true' else False
			itemsperpage = int(requestform['itemsperpage'])
			filelist = _get_cookfilelist()
			cookfilelist = []
			for filename in filelist:
				cookfilelist.append({'filename' : filename, 'title' : '', 'thumbnail' : ''})
			paginated_cookfile = _paginate_list(cookfilelist, 'filename', reverse, itemsperpage, page)
			paginated_cookfile['displaydata'] = _get_cookfilelist_details(paginated_cookfile['displaydata'])
			return render_template('_cookfile_list.html', pgntdcf = paginated_cookfile)

		if('repairCF' in requestform):
			cookfilename = requestform['repairCF']
			filenameonly = requestform['repairCF'].replace(HISTORY_FOLDER, '')
			cookfilestruct, status = upgrade_cookfile(cookfilename, repair=True)
			if status != 'OK':
				errors.append(status)
				if 'version' in status:
					errortype = 'version'
				elif 'asset' in status: 
					errortype = 'asset'
				else: 
					errortype = 'other'
				errors.append('Repair Failed.')
				return render_template('cferror.html', settings=settings, \
					cookfilename=cookfilename, errortype=errortype, \
					errors=errors, page_theme=settings['globals']['page_theme'], \
					grill_name=settings['globals']['grill_name'])
			# Fix issues with assets
			cookfilestruct, status = read_cookfile(cookfilename)
			cookfilestruct, status = fixup_assets(cookfilename, cookfilestruct)
			if status != 'OK':
				errors.append(status)
				if 'version' in status:
					errortype = 'version'
				elif 'asset' in status: 
					errortype = 'asset'
				else: 
					errortype = 'other'
				errors.append('Repair Failed.')
				return render_template('cferror.html', settings=settings, \
					cookfilename=cookfilename, errortype=errortype, \
					errors=errors, page_theme=settings['globals']['page_theme'], \
					grill_name=settings['globals']['grill_name'])
			else: 
				events = cookfilestruct['events']
				event_totals = _prepare_event_totals(events)
				comments = cookfilestruct['comments']
				for comment in comments:
					comment['text'] = comment['text'].replace('\n', '<br>')
				metadata = cookfilestruct['metadata']
				metadata['starttime'] = epoch_to_time(metadata['starttime'] / 1000)
				metadata['endtime'] = epoch_to_time(metadata['endtime'] / 1000)
				labels = cookfilestruct['graph_labels']
				assets = cookfilestruct['assets']

				return render_template('cookfile.html', settings=settings, \
					cookfilename=cookfilename, filenameonly=filenameonly, \
					events=events, event_totals=event_totals, \
					comments=comments, metadata=metadata, labels=labels, \
					assets=assets, errors=errors, \
					page_theme=settings['globals']['page_theme'], \
					grill_name=settings['globals']['grill_name'])

		if('upgradeCF' in requestform):
			cookfilename = requestform['upgradeCF']
			filenameonly = requestform['upgradeCF'].replace(HISTORY_FOLDER, '')
			cookfilestruct, status = upgrade_cookfile(cookfilename)
			if status != 'OK':
				errors.append(status)
				if 'version' in status:
					errortype = 'version'
				elif 'asset' in status: 
					errortype = 'asset'
				else: 
					errortype = 'other'
				return render_template('cferror.html', settings=settings, \
					cookfilename=cookfilename, errortype=errortype, \
					errors=errors, page_theme=settings['globals']['page_theme'], \
					grill_name=settings['globals']['grill_name'])
			else: 
				events = cookfilestruct['events']
				event_totals = _prepare_event_totals(events)
				comments = cookfilestruct['comments']
				for comment in comments:
					comment['text'] = comment['text'].replace('\n', '<br>')
				metadata = cookfilestruct['metadata']
				metadata['starttime'] = epoch_to_time(metadata['starttime'] / 1000)
				metadata['endtime'] = epoch_to_time(metadata['endtime'] / 1000)
				labels = cookfilestruct['graph_labels']
				assets = cookfilestruct['assets']

				return render_template('cookfile.html', settings=settings, \
					cookfilename=cookfilename, filenameonly=filenameonly, \
					events=events, event_totals=event_totals, \
					comments=comments, metadata=metadata, labels=labels, \
					assets=assets, errors=errors, \
					page_theme=settings['globals']['page_theme'], \
					grill_name=settings['globals']['grill_name'])

		if('delmedialist' in requestform):
			cookfilename = HISTORY_FOLDER + requestform['delmedialist']
			filenameonly = requestform['delmedialist']
			assetlist = requestform['delAssetlist'].split(',') if requestform['delAssetlist'] != '' else []
			status = remove_assets(cookfilename, assetlist)
			cookfilestruct, status = read_cookfile(cookfilename)
			if status != 'OK':
				errors.append(status)
				if 'version' in status:
					errortype = 'version'
				elif 'asset' in status: 
					errortype = 'asset'
				else: 
					errortype = 'other'
				return render_template('cferror.html', settings=settings, \
					cookfilename=cookfilename, errortype=errortype, \
					errors=errors, page_theme=settings['globals']['page_theme'], \
					grill_name=settings['globals']['grill_name'])
			else: 
				events = cookfilestruct['events']
				event_totals = _prepare_event_totals(events)
				comments = cookfilestruct['comments']
				for comment in comments:
					comment['text'] = comment['text'].replace('\n', '<br>')
				metadata = cookfilestruct['metadata']
				metadata['starttime'] = epoch_to_time(metadata['starttime'] / 1000)
				metadata['endtime'] = epoch_to_time(metadata['endtime'] / 1000)
				labels = cookfilestruct['graph_labels']
				assets = cookfilestruct['assets']

				return render_template('cookfile.html', settings=settings, \
					cookfilename=cookfilename, filenameonly=filenameonly, \
					events=events, event_totals=event_totals, \
					comments=comments, metadata=metadata, labels=labels, \
					assets=assets, errors=errors, \
					page_theme=settings['globals']['page_theme'], \
					grill_name=settings['globals']['grill_name'])

	errors.append('Something unexpected has happened.')
	return jsonify({'result' : 'ERROR', 'errors' : errors})

@app.route('/updatecookfile', methods=['POST','GET'])
def updatecookdata(action=None):
	global settings 

	if(request.method == 'POST'):
		requestjson = request.json 
		if('comments' in requestjson):
			filename = requestjson['filename']
			cookfiledata, status = read_json_file_data(filename, 'comments')

			if('commentnew' in requestjson):
				now = datetime.datetime.now()
				comment_struct = {}
				comment_struct['text'] = requestjson['commentnew']
				comment_struct['id'] = generate_uuid()
				comment_struct['edited'] = ''
				comment_struct['date'] = now.strftime('%Y-%m-%d')
				comment_struct['time'] = now.strftime('%H:%M')
				comment_struct['assets'] = []
				cookfiledata.append(comment_struct)
				result = update_json_file_data(cookfiledata, filename, 'comments')
				if(result == 'OK'):
					return jsonify({'result' : 'OK', 'newcommentid' : comment_struct['id'], 'newcommentdt': comment_struct['date'] + ' ' + comment_struct['time']})
			if('delcomment' in requestjson):
				for item in cookfiledata:
					if item['id'] == requestjson['delcomment']:
						cookfiledata.remove(item)
						result = update_json_file_data(cookfiledata, filename, 'comments')
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
						result = update_json_file_data(cookfiledata, filename, 'comments')
						if(result == 'OK'):
							return jsonify({'result' : 'OK', 'text' : item['text'].replace('\n', '<br>'), 'edited' : item['edited'], 'datetime' : item['date'] + ' ' + item['time']})
		
		if('metadata' in requestjson):
			filename = requestjson['filename']
			cookfiledata, status = read_json_file_data(filename, 'metadata')
			if(status == 'OK'):
				if('editTitle' in requestjson):
					cookfiledata['title'] = requestjson['editTitle']
					result = update_json_file_data(cookfiledata, filename, 'metadata')
					if(result == 'OK'):
						return jsonify({'result' : 'OK'})
					else: 
						return jsonify({'result' : 'ERROR'})
		
		if('graph_labels' in requestjson):
			filename = requestjson['filename']
			
			''' Update graph_labels.json '''
			cookfiledata, result = read_json_file_data(filename, 'graph_labels')
			if(result != 'OK'):
				return jsonify({'result' : 'ERROR'})

			old_label = requestjson['old_label']
			new_label = requestjson['new_label']
			new_label_safe = _create_safe_name(new_label)

			for category in cookfiledata:
				if new_label_safe in cookfiledata[category].keys():
					result = 'Label already exists!'
					break
				if old_label in cookfiledata[category].keys():
					cookfiledata[category].pop(old_label)
					cookfiledata[category][new_label_safe] = new_label 
			
			if(result != 'OK'):
				return jsonify({'result' : 'ERROR'})

			result = update_json_file_data(cookfiledata, filename, 'graph_labels')
			if(result != 'OK'):
				return jsonify({'result' : 'ERROR'})

			''' Update graph_data.json '''
			cookfiledata, result = read_json_file_data(filename, 'graph_data')
			if(result != 'OK'):
				return jsonify({'result' : 'ERROR'})

			for category in cookfiledata['probe_mapper']:
				if old_label in cookfiledata['probe_mapper'][category].keys():
					cookfiledata['probe_mapper'][category][new_label_safe] = cookfiledata['probe_mapper'][category][old_label]
					cookfiledata['probe_mapper'][category].pop(old_label)
					list_position = cookfiledata['probe_mapper'][category][new_label_safe]
					if category == 'targets': 
						addendum = ' Target'
					elif category == 'primarysp':
						addendum = ' Set Point'
					else:
						addendum = ''
					cookfiledata['chart_data'][list_position]['label'] = new_label + addendum 

			result = update_json_file_data(cookfiledata, filename, 'graph_data')
			if(result != 'OK'):
				return jsonify({'result' : 'ERROR'})

			return jsonify({'result' : 'OK', 'new_label_safe' : new_label_safe})



		if('media' in requestjson):
			filename = requestjson['filename']
			assetfilename = requestjson['assetfilename']
			commentid = requestjson['commentid']
			state = requestjson['state']
			comments, status = read_json_file_data(filename, 'comments')
			result = 'OK'
			for index in range(0, len(comments)):
				if comments[index]['id'] == commentid:
					if assetfilename in comments[index]['assets'] and state == 'selected':
						comments[index]['assets'].remove(assetfilename)
						result = update_json_file_data(comments, filename, 'comments')
					elif assetfilename not in comments[index]['assets'] and state == 'unselected':
						comments[index]['assets'].append(assetfilename)
						result = update_json_file_data(comments, filename, 'comments')
					break

			return jsonify({'result' : result})

	return jsonify({'result' : 'ERROR'})

@app.route('/tuner/<action>', methods=['POST','GET'])
@app.route('/tuner', methods=['POST','GET'])
def tuner_page(action=None):
	global settings 
	control = read_control()
	
	# This POST path will load/render portions of the tuner page
	if request.method == 'POST' and ('form' in request.content_type):
		requestform = request.form
		if 'command' in requestform.keys():
			if 'render' in requestform['command']:
				render_string = "{% from '_macro_tuner.html' import render_" + requestform["value"] + " %}{{ render_" + requestform["value"] + "(settings, control) }}"
				return render_template_string(render_string, settings=settings, control=control)
	
	# This POST path provides data back to the page
	if request.method == 'POST' and 'json' in request.content_type:
		requestjson = request.json 
		command = requestjson.get('command', None)
		if command == 'stop_tuning':
			if control['tuning_mode']:
				control['tuning_mode'] = False  # Disable tuning mode
				write_control(control, origin='app')
			if control['mode'] == 'Monitor':
				# If in Monitor Mode, stop
				control['mode'] = 'Stop'  # Go to Stop mode
				control['updated'] = True
				write_control(control, origin='app')	
		if command == 'read_tr':
			if not control['tuning_mode']:
				control['tuning_mode'] = True  # Enable tuning mode
				write_control(control, origin='app')

			if control['mode'] == 'Stop':
				# Turn on Monitor Mode if the system is stopped
				control['mode'] = 'Monitor'  # Enable monitor mode
				control['updated'] = True
				write_control(control, origin='app')

			cur_probe_tr = read_tr()
			if requestjson['probe_selected'] in cur_probe_tr.keys():
				return jsonify({ 'trohms' : cur_probe_tr[requestjson['probe_selected']]})
			else:
				return jsonify({ 'trohms' : 0 })
		if command == 'manual_finish' or command == 'auto_finish':
			if control['tuning_mode']:
				control['tuning_mode'] = False  # Disable tuning mode
				write_control(control, origin='app')
			if control['mode'] == 'Monitor':
				# If in Monitor Mode, stop
				control['mode'] = 'Stop'  # Go to Stop mode
				control['updated'] = True
				write_control(control, origin='app')
			
			tunerManualHighTemp = requestjson.get('tunerManualHighTemp', 0.1)
			tunerManualHighTemp = 0 if tunerManualHighTemp == '' else int(tunerManualHighTemp)
			tunerManualHighTr = requestjson.get('tunerManualHighTr', 0.1)
			tunerManualHighTr = 0 if tunerManualHighTr == '' else int(tunerManualHighTr)

			tunerManualMediumTemp = requestjson.get('tunerManualMediumTemp', 0.1)
			tunerManualMediumTemp = 0 if tunerManualMediumTemp == '' else int(tunerManualMediumTemp)
			tunerManualMediumTr = requestjson.get('tunerManualMediumTr', 0.1)
			tunerManualMediumTr = 0 if tunerManualMediumTr == '' else int(tunerManualMediumTr)

			tunerManualLowTemp = requestjson.get('tunerManualLowTemp', 0.1)
			tunerManualLowTemp = 0 if tunerManualLowTemp == '' else int(tunerManualLowTemp)
			tunerManualLowTr = requestjson.get('tunerManualLowTr', 0.1)
			tunerManualLowTr = 0 if tunerManualLowTr == '' else int(tunerManualLowTr)

			a, b, c = _calc_shh_coefficients(tunerManualLowTemp, tunerManualMediumTemp,
											tunerManualHighTemp, tunerManualLowTr,
											tunerManualMediumTr, tunerManualHighTr,
											units=settings['globals']['units'])
			tr_points = [int(tunerManualHighTr), int(tunerManualMediumTr), int(tunerManualLowTr)]
			labels, chart_data = _calc_shh_chart(a, b, c, units=settings['globals']['units'], temp_range=220, tr_points=tr_points)
			return jsonify({'labels' : labels, 'chart_data' : chart_data, 'coefficients' : {'a' : a, 'b': b, 'c': c}})
		if command == 'read_auto_status':
			first_run = False 
			if not control['tuning_mode']:
				control['tuning_mode'] = True  # Enable tuning mode
				write_control(control, origin='app')
				read_autotune(flush=True)  # Flush autotune data
				first_run = True

			if control['mode'] == 'Stop':
				# Turn on Monitor Mode if the system is stopped
				control['mode'] = 'Monitor'  # Enable monitor mode
				control['updated'] = True
				write_control(control, origin='app')

			status_data = {
				'current_tr' : 0,
				'current_temp' : 0,
				'high_tr' : 0,
				'high_temp' : 0, 
				'medium_tr' : 0,
				'medium_temp' : 0,
				'low_tr' : 0,
				'low_temp' : 0,
				'ready' : False
			}
			
			# Get Tr Data from all probes 
			cur_probe_tr = read_tr()
			if requestjson['probe_selected'] in cur_probe_tr.keys():
				status_data['current_tr'] = cur_probe_tr[requestjson['probe_selected']]
			else:
				status_data['current_tr'] = -1
			
			# Get Temp Data from all probes 
			cur_probe_temps = read_current()
			if requestjson['probe_reference'] in cur_probe_temps['P'].keys():
				status_data['current_temp'] = cur_probe_temps['P'][requestjson['probe_reference']]
			elif requestjson['probe_reference'] in cur_probe_temps['F'].keys():
				status_data['current_temp'] = cur_probe_temps['F'][requestjson['probe_reference']]
			elif requestjson['probe_reference'] in cur_probe_temps['AUX'].keys():
				status_data['current_temp'] = cur_probe_temps['AUX'][requestjson['probe_reference']]
			else:
				status_data['current_temp'] = -1

			# Some probes (i.e. the DS18B20) may be slow to respond when Monitor mode starts, and may report 0 degrees
			# Thus we should ignore these first few data points if they are 0
			autotune_data_size = read_autotune(size_only=True)
			if (autotune_data_size > 4 or status_data['current_temp'] > 0) and \
					status_data['current_tr'] >= 0 and \
	  				status_data['current_temp'] >= 0 and \
					not first_run:
				# Record Temperature / Tr Values in Auto-Tune Record
				data = {
					'ref_T' : status_data['current_temp'],
					'probe_Tr' : status_data['current_tr']
				}
				write_autotune(data)

			data = read_autotune()
			if len(data) > 10:
				temp_list = []
				tr_list = []
				for datapoint in data:
					temp_list.append(datapoint['ref_T'])
					tr_list.append(datapoint['probe_Tr'])

				# Determine High Temp / Tr
				status_data['high_temp'] = max(temp_list)
				index = temp_list.index(max(temp_list))
				status_data['high_tr'] = tr_list[index]

				# Determine Low Temp / Tr 
				status_data['low_temp'] = min(temp_list)
				index = temp_list.index(min(temp_list))
				status_data['low_tr'] = tr_list[index]

				# Determine Medium Temp / Tr
				# Find best fit to Medium Temp
				medium_temp = ((status_data['high_temp'] - status_data['low_temp']) // 2) + status_data['low_temp']
				delta_temp = 1000  # Initial value is outside of any normal expected bounds
				for index, temp in enumerate(temp_list):
					if abs(temp - medium_temp) < delta_temp:
						delta_temp = abs(temp - medium_temp)
						delta_index = index
				status_data['medium_temp'] = temp_list[delta_index]
				status_data['medium_tr'] = tr_list[delta_index]
				# Minimum range to be able to calculate temp
				if settings['globals']['units'] == 'F':
					min_range = 50
				else:
					min_range = 25

				if (status_data['high_temp'] - status_data['low_temp']) >= min_range:
					status_data['ready'] = True

			return jsonify(status_data)

	return render_template('tuner.html',
						control=control,
						settings=settings,
						page_theme=settings['globals']['page_theme'],
						grill_name=settings['globals']['grill_name'])

@app.route('/events/<action>', methods=['POST','GET'])
@app.route('/events', methods=['POST','GET'])
def events_page(action=None):
	global settings
	control = read_control()

	if(request.method == 'POST') and ('form' in request.content_type):
		requestform = request.form 
		if 'eventslist' in requestform:
			event_list = read_events(legacy=False)
			page = int(requestform['page'])
			reverse = True if requestform['reverse'] == 'true' else False
			itemsperpage = int(requestform['itemsperpage'])
			pgntd_data = _paginate_list(event_list, reversesortorder=reverse, itemsperpage=itemsperpage, page=page)
			return render_template('_events_list.html', pgntd_data = pgntd_data)
		else:
			return ('Error')

	return render_template('events.html',
							settings=settings,
						   	control=control,
						   	page_theme=settings['globals']['page_theme'],
						   	grill_name=settings['globals']['grill_name'])

@app.route('/logs/<action>', methods=['POST','GET'])
@app.route('/logs', methods=['POST','GET'])
def logs_page(action=None):
	global settings
	control = read_control()
	# Get list of log files 
	if not os.path.exists(LOGS_FOLDER):
		os.mkdir(LOGS_FOLDER)
	log_file_list = os.listdir(LOGS_FOLDER)
	for file in log_file_list:
		if not _allowed_file(file):
			log_file_list.remove(file)

	if(request.method == 'POST') and ('form' in request.content_type):
		requestform = request.form 

		if 'download' in requestform:
			log_file_name = LOGS_FOLDER + requestform['selectLog']
			return send_file(log_file_name, as_attachment=True, max_age=0)
		elif 'eventslist' in requestform:
			log_file_name = requestform['logfile']
			event_list = read_log_file(LOGS_FOLDER + log_file_name)
			event_list = add_line_numbers(event_list)
			page = int(requestform['page'])
			reverse = True if requestform['reverse'] == 'true' else False
			itemsperpage = int(requestform['itemsperpage'])
			pgntd_data = _paginate_list(event_list, reversesortorder=reverse, itemsperpage=itemsperpage, page=page)
			return render_template('_log_list.html', pgntd_data = pgntd_data, log_file_name=log_file_name)
		else:
			return ('Error')

	return render_template('logs.html',
							settings=settings,
							control=control,
							log_file_list=log_file_list,
						   	page_theme=settings['globals']['page_theme'],
						   	grill_name=settings['globals']['grill_name'])

@app.route('/pellets/<action>', methods=['POST','GET'])
@app.route('/pellets', methods=['POST','GET'])
def pellets_page(action=None):
	# Pellet Management page
	global settings
	pelletdb = read_pellet_db()
	control = read_control()

	event = {
		'type' : 'none',
		'text' : ''
	}

	if request.method == 'POST' and action == 'loadprofile':
		response = request.form
		if 'load_profile' in response:
			if response['load_profile'] == 'true':
				pelletdb['current']['pelletid'] = response['load_id']
				pelletdb['current']['est_usage'] = 0
				control = read_control()
				control['hopper_check'] = True
				write_control(control, origin='app')
				now = str(datetime.datetime.now())
				now = now[0:19] # Truncate the microseconds
				pelletdb['current']['date_loaded'] = now 
				pelletdb['log'][now] = response['load_id']
				write_pellet_db(pelletdb)
				event['type'] = 'updated'
				event['text'] = 'Successfully loaded profile and logged.'
				backup_pellet_db(action='backup')
	elif request.method == 'GET' and action == 'hopperlevel':
		control = {}
		control['hopper_check'] = True
		write_control(control, origin='app')
	elif request.method == 'POST' and action == 'editbrands':
		response = request.form
		if 'delBrand' in response:
			del_brand = response['delBrand']
			if del_brand in pelletdb['brands']:
				pelletdb['brands'].remove(del_brand)
				write_pellet_db(pelletdb)
				event['type'] = 'updated'
				event['text'] = del_brand + ' successfully deleted.'
			else: 
				event['type'] = 'error'
				event['text'] = del_brand + ' not found in pellet brands.'
		elif 'newBrand' in response:
			new_brand = response['newBrand']
			if(new_brand in pelletdb['brands']):
				event['type'] = 'error'
				event['text'] = new_brand + ' already in pellet brands list.'
			else: 
				pelletdb['brands'].append(new_brand)
				write_pellet_db(pelletdb)
				event['type'] = 'updated'
				event['text'] = new_brand + ' successfully added.'

	elif request.method == 'POST' and action == 'editwoods':
		response = request.form
		if 'delWood' in response:
			del_wood = response['delWood']
			if del_wood in pelletdb['woods']:
				pelletdb['woods'].remove(del_wood)
				write_pellet_db(pelletdb)
				event['type'] = 'updated'
				event['text'] = del_wood + ' successfully deleted.'
			else: 
				event['type'] = 'error'
				event['text'] = del_wood + ' not found in pellet wood list.'
		elif 'newWood' in response:
			new_wood = response['newWood']
			if(new_wood in pelletdb['woods']):
				event['type'] = 'error'
				event['text'] = new_wood + ' already in pellet wood list.'
			else: 
				pelletdb['woods'].append(new_wood)
				write_pellet_db(pelletdb)
				event['type'] = 'updated'
				event['text'] = new_wood + ' successfully added.'

	elif request.method == 'POST' and action == 'addprofile':
		response = request.form
		if 'addprofile' in response:
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

			if response['addprofile'] == 'add_load':
				pelletdb['current']['pelletid'] = profile_id
				control = {}
				control['hopper_check'] = True
				write_control(control, origin='app')
				now = str(datetime.datetime.now())
				now = now[0:19] # Truncate the microseconds
				pelletdb['current']['date_loaded'] = now
				pelletdb['current']['est_usage'] = 0
				pelletdb['log'][now] = profile_id
				event['text'] = 'Successfully added profile and loaded.'

			write_pellet_db(pelletdb)

	elif request.method == 'POST' and action == 'editprofile':
		response = request.form
		if 'editprofile' in response:
			profile_id = response['editprofile']
			pelletdb['archive'][profile_id]['brand'] = response['brand_name']
			pelletdb['archive'][profile_id]['wood'] = response['wood_type']
			pelletdb['archive'][profile_id]['rating'] = int(response['rating'])
			pelletdb['archive'][profile_id]['comments'] = response['comments']
			write_pellet_db(pelletdb)
			event['type'] = 'updated'
			event['text'] = 'Successfully updated ' + response['brand_name'] + ' ' + response['wood_type'] + \
							' profile in database.'
		elif 'delete' in response:
			profile_id = response['delete']
			if pelletdb['current']['pelletid'] == profile_id:
				event['type'] = 'error'
				event['text'] = 'Error: ' + response['brand_name'] + ' ' + response['wood_type'] + \
								' profile cannot be deleted if it is currently loaded.'
			else: 
				pelletdb['archive'].pop(profile_id) # Remove the profile from the archive
				for index in pelletdb['log']:  # Remove this profile ID for the logs
					if(pelletdb['log'][index] == profile_id):
						pelletdb['log'][index] = 'deleted'
				write_pellet_db(pelletdb)
				event['type'] = 'updated'
				event['text'] = 'Successfully deleted ' + response['brand_name'] + ' ' + response['wood_type'] + \
								' profile in database.'

	elif request.method == 'POST' and action == 'deletelog':
		response = request.form
		if 'delLog' in response:
			del_log = response['delLog']
			if del_log in pelletdb['log']:
				pelletdb['log'].pop(del_log)
				write_pellet_db(pelletdb)
				event['type'] = 'updated'
				event['text'] = 'Log successfully deleted.'
			else:
				event['type'] = 'error'
				event['text'] = 'Item not found in pellet log.'

	grams = pelletdb['current']['est_usage']
	pounds = round(grams * 0.00220462, 2)
	ounces = round(grams * 0.03527392, 2)
	est_usage_imperial = f'{pounds} lbs' if pounds > 1 else f'{ounces} ozs'
	est_usage_metric = f'{round(grams, 2)} g' if grams < 1000 else f'{round(grams / 1000, 2)} kg'

	return render_template('pellets.html',
						   alert=event,
						   pelletdb=pelletdb,
						   est_usage_imperial=est_usage_imperial,
						   est_usage_metric=est_usage_metric,
						   settings=settings,
						   control=control,
						   units=settings['globals']['units'],
						   page_theme=settings['globals']['page_theme'],
						   grill_name=settings['globals']['grill_name'])


@app.route('/recipes', methods=['POST','GET'])
def recipes_page(action=None):
	global settings
	control = read_control()
	# Placholder for Recipe UI
	return render_template('recipes.html',
							settings=settings,
						   	control=control,
						   	page_theme=settings['globals']['page_theme'],
						   	grill_name=settings['globals']['grill_name'])

@app.route('/recipedata', methods=['POST', 'GET'])
@app.route('/recipedata/upload', methods=['POST', 'GET'])
@app.route('/recipedata/download/<filename>', methods=['GET'])
def recipes_data(filename=None):
	global settings
	control = read_control()

	if(request.method == 'GET') and (filename is not None):
		filepath = f'{RECIPE_FOLDER}{filename}'
		#print(f'Sending: {filepath}')
		return send_file(filepath, as_attachment=True, max_age=0)

	if(request.method == 'POST') and ('form' in request.content_type):
		requestform = request.form
		#print(f'Request FORM: {requestform}')
		if('upload' in requestform):
			#print(f'Files: {request.files}')
			remote_file = request.files['recipefile']
			result = "error"
			if remote_file.filename != '':
				if remote_file and _allowed_file(remote_file.filename):
					filename = secure_filename(remote_file.filename)
					remote_file.save(os.path.join(app.config['RECIPE_FOLDER'], filename))
					result = "success"
			return jsonify({ 'result' : result})
		if('uploadassets' in requestform):
			# Assume we have request.files and localfile in response
			uploadedfiles = request.files.getlist('assetfiles')
			filename = requestform['filename']
			filepath = f'{RECIPE_FOLDER}{filename}'

			errors = []
			for remotefile in uploadedfiles:
				if (remotefile.filename != ''):
					# Load the Recipe File 
					recipe_data, status = read_recipefile(filepath)
					parent_id = recipe_data['metadata']['id']
					tmp_path = f'/tmp/pifire/{parent_id}'
					if not os.path.exists(tmp_path):
						os.mkdir(tmp_path)

					if remotefile and _allowed_file(remotefile.filename):
						asset_filename = secure_filename(remotefile.filename)
						pathfile = os.path.join(tmp_path, asset_filename)
						remotefile.save(pathfile)
						add_asset(filepath, tmp_path, asset_filename)
					else:
						errors.append('Disallowed File Upload.')
			if len(errors):
				status = 'error'
			else:
				status = 'success'
			return jsonify({ 'result' : status, 'errors' : errors})
		if('recipefilelist' in requestform):
			page = int(requestform['page'])
			reverse = True if requestform['reverse'] == 'true' else False
			itemsperpage = int(requestform['itemsperpage'])
			filelist = _get_recipefilelist()
			recipefilelist = []
			for filename in filelist:
				recipefilelist.append({'filename' : filename, 'title' : '', 'thumbnail' : ''})
			paginated_recipefile = _paginate_list(recipefilelist, 'filename', reverse, itemsperpage, page)
			paginated_recipefile['displaydata'] = _get_recipefilelist_details(paginated_recipefile['displaydata'])
			return render_template('_recipefile_list.html', pgntdrf = paginated_recipefile)
		if('recipeview' in requestform):
			filename = requestform['filename']
			filepath = f'{RECIPE_FOLDER}{filename}'
			recipe_data, status = read_recipefile(filepath)
			return render_template('_recipe_view.html', recipe_data=recipe_data, recipe_filename=filename, recipe_filepath=filepath)
		if('recipeedit' in requestform):
			filename = requestform['filename']
			if filename == '':
				filepath = create_recipefile()
				filename = filepath.replace(RECIPE_FOLDER, '')
			else: 
				filepath = f'{RECIPE_FOLDER}{filename}'
			recipe_data, status = read_recipefile(filepath)
			return render_template('_recipe_edit.html', recipe_data=recipe_data, recipe_filename=filename, recipe_filepath=filepath)
		if('update' in requestform):
			filename = requestform['filename']
			filepath = f'{RECIPE_FOLDER}{filename}'
			recipe_data, status = read_recipefile(filepath)
			if requestform['update'] in ['metadata']:
				field = requestform['field']
				if field in ['prep_time', 'cook_time', 'rating']:
					recipe_data['metadata'][field] = int(requestform['value'])
				elif field == 'food_probes':
					food_probes = int(requestform['value'])
					recipe_data['metadata'][field] = food_probes 
					for index, step in enumerate(recipe_data['recipe']['steps']):
						while len(step['trigger_temps']['food']) > food_probes:
							recipe_data['recipe']['steps'][index]['trigger_temps']['food'].pop()
						while len(step['trigger_temps']['food']) < food_probes:
							recipe_data['recipe']['steps'][index]['trigger_temps']['food'].append(0)
					update_json_file_data(recipe_data['recipe'], filepath, 'recipe')
				else:	
					recipe_data['metadata'][field] = requestform['value']
				update_json_file_data(recipe_data['metadata'], filepath, 'metadata')
				if field == 'title': 
					render_string = "{% from '_macro_recipes.html' import render_recipe_edit_title %}{{ render_recipe_edit_title(recipe_data, recipe_filename) }}"
				elif field == 'description':
					render_string = "{% from '_macro_recipes.html' import render_recipe_edit_description %}{{ render_recipe_edit_description(recipe_data) }}"
				else:
					render_string = "{% from '_macro_recipes.html' import render_recipe_edit_metadata %}{{ render_recipe_edit_metadata(recipe_data) }}"
				return render_template_string(render_string, recipe_data=recipe_data, recipe_filename=filename)
			elif requestform['update'] == 'ingredients':
				recipe = recipe_data['recipe']
				ingredient_index = int(requestform['index'])
				if recipe['ingredients'][ingredient_index]['name'] != requestform['name']:
					# Go Fixup any Instruction Step that includes this Ingredient First
					for index, direction in enumerate(recipe['instructions']):
						if recipe['ingredients'][ingredient_index]['name'] in recipe['instructions'][index]['ingredients']:
							recipe['instructions'][index]['ingredients'].remove(recipe['ingredients'][ingredient_index]['name'])
							recipe['instructions'][index]['ingredients'].append(requestform['name'])
				recipe['ingredients'][ingredient_index]['name'] = requestform['name']
				recipe['ingredients'][ingredient_index]['quantity'] = requestform['quantity']
				recipe_data['recipe'] = recipe 
				update_json_file_data(recipe, filepath, 'recipe')
				render_string = "{% from '_macro_recipes.html' import render_recipe_edit_ingredients %}{{ render_recipe_edit_ingredients(recipe_data) }}"
				return render_template_string(render_string, recipe_data=recipe_data)
			elif requestform['update'] == 'instructions':
				instruction_index = int(requestform['index'])
				if 'ingredients[]' in requestform:
					ingredients = request.form.getlist('ingredients[]')
				else:
					ingredients = []
				recipe_data['recipe']['instructions'][instruction_index]['ingredients'] = ingredients 
				recipe_data['recipe']['instructions'][instruction_index]['text'] = requestform['text']
				recipe_data['recipe']['instructions'][instruction_index]['step'] = int(requestform['step'])
				update_json_file_data(recipe_data['recipe'], filepath, 'recipe')
				render_string = "{% from '_macro_recipes.html' import render_recipe_edit_instructions %}{{ render_recipe_edit_instructions(recipe_data) }}"
				return render_template_string(render_string, recipe_data=recipe_data)
			elif requestform['update'] == 'steps':
				step_index = int(requestform['index'])
				food = request.form.getlist('food[]')
				for i in range(0, len(food)):
					food[i] = int(food[i])
				recipe_data['recipe']['steps'][step_index]['hold_temp'] = int(requestform['hold_temp'])
				recipe_data['recipe']['steps'][step_index]['timer'] = int(requestform['timer'])
				recipe_data['recipe']['steps'][step_index]['mode'] = requestform['mode']
				recipe_data['recipe']['steps'][step_index]['trigger_temps']['primary'] = int(requestform['primary'])
				recipe_data['recipe']['steps'][step_index]['trigger_temps']['food'] = food
				recipe_data['recipe']['steps'][step_index]['pause'] = True if requestform['pause'] == 'true' else False 
				recipe_data['recipe']['steps'][step_index]['notify'] = True if requestform['notify']== 'true' else False 
				recipe_data['recipe']['steps'][step_index]['message'] = requestform['message']

				update_json_file_data(recipe_data['recipe'], filepath, 'recipe')
				render_string = "{% from '_macro_recipes.html' import render_recipe_edit_steps %}{{ render_recipe_edit_steps(recipe_data) }}"
				return render_template_string(render_string, recipe_data=recipe_data)
			else:
				return '<strong color="red">No Data</strong>'
		if('delete' in requestform):
			filename = requestform['filename']
			filepath = f'{RECIPE_FOLDER}{filename}'
			recipe_data, status = read_recipefile(filepath)
			if requestform['delete'] == 'ingredients':
				recipe = recipe_data['recipe']
				ingredient_index = int(requestform['index'])
				# Go Fixup any Instruction Step that includes this Ingredient First
				for index, direction in enumerate(recipe['instructions']):
					if recipe['ingredients'][ingredient_index]['name'] in recipe['instructions'][index]['ingredients']:
						recipe['instructions'][index]['ingredients'].remove(recipe['ingredients'][ingredient_index]['name'])
				recipe['ingredients'].pop(ingredient_index)
				recipe_data['recipe'] = recipe 
				update_json_file_data(recipe, filepath, 'recipe')
				render_string = "{% from '_macro_recipes.html' import render_recipe_edit_ingredients %}{{ render_recipe_edit_ingredients(recipe_data) }}"
				return render_template_string(render_string, recipe_data=recipe_data)
			elif requestform['delete'] == 'instructions':
				instruction_index = int(requestform['index'])
				recipe_data['recipe']['instructions'].pop(instruction_index)
				update_json_file_data(recipe_data['recipe'], filepath, 'recipe')
				render_string = "{% from '_macro_recipes.html' import render_recipe_edit_instructions %}{{ render_recipe_edit_instructions(recipe_data) }}"
				return render_template_string(render_string, recipe_data=recipe_data)
			elif requestform['delete'] == 'steps':
				step_index = int(requestform['index'])
				recipe_data['recipe']['steps'].pop(step_index)
				update_json_file_data(recipe_data['recipe'], filepath, 'recipe')
				render_string = "{% from '_macro_recipes.html' import render_recipe_edit_steps %}{{ render_recipe_edit_steps(recipe_data) }}"
				return render_template_string(render_string, recipe_data=recipe_data)
			else:
				return '<strong color="red">No Data</strong>'
		if('add' in requestform):
			filename = requestform['filename']
			filepath = f'{RECIPE_FOLDER}{filename}'
			recipe_data, status = read_recipefile(filepath)
			if requestform['add'] == 'ingredients':
				new_ingredient = {
        			"name" : "",
        			"quantity" : "",
        			"assets" : []
    			}
				recipe_data['recipe']['ingredients'].append(new_ingredient)
				update_json_file_data(recipe_data['recipe'], filepath, 'recipe')
				render_string = "{% from '_macro_recipes.html' import render_recipe_edit_ingredients %}{{ render_recipe_edit_ingredients(recipe_data) }}"
				return render_template_string(render_string, recipe_data=recipe_data)
			elif requestform['add'] == 'instructions': 
				new_instruction = {
					"text" : "",
      				"ingredients" : [],
      				"assets" : [],
      				"step" : 0
				}
				recipe_data['recipe']['instructions'].append(new_instruction)
				update_json_file_data(recipe_data['recipe'], filepath, 'recipe')
				render_string = "{% from '_macro_recipes.html' import render_recipe_edit_instructions %}{{ render_recipe_edit_instructions(recipe_data) }}"
				return render_template_string(render_string, recipe_data=recipe_data)
			elif requestform['add'] == 'steps':
				step_index = int(requestform['index'])
				food_list = []
				for count in range(0, recipe_data['metadata']['food_probes']):
					food_list.append(0)
				new_step = {
      				"hold_temp": 0,
      				"message": "",
      				"mode": "Smoke",
      				"notify": False,
      				"pause": False,
      				"timer": 0,
      				"trigger_temps": {
        				"primary": 0,
        				"food": food_list,
      				}
				}
				recipe_data['recipe']['steps'].insert(step_index, new_step)
				update_json_file_data(recipe_data['recipe'], filepath, 'recipe')
				render_string = "{% from '_macro_recipes.html' import render_recipe_edit_steps %}{{ render_recipe_edit_steps(recipe_data) }}"
				return render_template_string(render_string, recipe_data=recipe_data)
			else:
				return '<strong color="red">No Data</strong>'
		if('refresh' in requestform):
			filename = requestform['filename']
			filepath = f'{RECIPE_FOLDER}{filename}'
			recipe_data, status = read_recipefile(filepath)
			if requestform['refresh'] == 'metadata':
				render_string = "{% from '_macro_recipes.html' import render_recipe_edit_metadata %}{{ render_recipe_edit_metadata(recipe_data) }}"
				return render_template_string(render_string, recipe_data=recipe_data)
			if requestform['refresh'] == 'description':
				render_string = "{% from '_macro_recipes.html' import render_recipe_edit_description %}{{ render_recipe_edit_description(recipe_data) }}"
				return render_template_string(render_string, recipe_data=recipe_data)
			if requestform['refresh'] == 'ingredients':
				render_string = "{% from '_macro_recipes.html' import render_recipe_edit_ingredients %}{{ render_recipe_edit_ingredients(recipe_data) }}"
				return render_template_string(render_string, recipe_data=recipe_data)
			if requestform['refresh'] == 'instructions':
				render_string = "{% from '_macro_recipes.html' import render_recipe_edit_instructions %}{{ render_recipe_edit_instructions(recipe_data) }}"
				return render_template_string(render_string, recipe_data=recipe_data)
			if requestform['refresh'] == 'steps':
				render_string = "{% from '_macro_recipes.html' import render_recipe_edit_steps %}{{ render_recipe_edit_steps(recipe_data) }}"
				return render_template_string(render_string, recipe_data=recipe_data)
		if('reciperunstatus' in requestform):
			control = read_control()
			if control['mode'] != 'Recipe':
				filename = requestform['filename']
				filepath = f'{RECIPE_FOLDER}{filename}'
			else: 
				filepath = control['recipe']['filename']
				filename = filepath.replace(RECIPE_FOLDER, '')

			recipe_data, status = read_recipefile(filepath)
			return render_template('_recipe_status.html', control=control, recipe_data=recipe_data, recipe_filename=filename, recipe_filepath=filepath)
		if('recipeassetmanager' in requestform):
			filename = requestform['filename']
			filepath = f'{RECIPE_FOLDER}{filename}'
			recipe_data, status = read_recipefile(filepath)
			section = requestform['section']
			section_index = int(requestform['index'])
			if section == 'splash':
				assets_selected = [recipe_data['metadata']['image']]
			elif section in ['ingredients', 'instructions']: 
				assets_selected = recipe_data['recipe'][section][section_index]['assets']
			elif section == 'comments': 
				assets_selected = recipe_data['comments'][section_index]['assets']
			else:
				assets_selected = []
			return render_template('_recipe_assets.html', recipe_data=recipe_data, recipe_filename=filename, recipe_filepath=filepath, section=section, section_index=section_index, selected=assets_selected)

		if('recipeshowasset' in requestform):
			filename = requestform['filename']
			filepath = f'{RECIPE_FOLDER}{filename}'
			recipe_data, status = read_recipefile(filepath)
			section = requestform['section']
			section_index = int(requestform['section_index'])
			selected_asset = requestform['asset']
			if(section == 'metadata'):
				assets = [recipe_data['metadata']['title']]
			else:
				assets = recipe_data['recipe'][section][section_index]['assets']
			recipe_id = recipe_data['metadata']['id']
			render_string = "{% from '_macro_recipes.html' import render_recipe_asset_viewer %}{{ render_recipe_asset_viewer(assets, recipe_id, selected_asset) }}"
			return render_template_string(render_string, assets=assets, recipe_id=recipe_id, selected_asset=selected_asset)

	''' AJAX POST JSON Type Method Handler '''
	if(request.method == 'POST') and ('json' in request.content_type): 
		requestjson = request.json
		#print(f'Request JSON: {requestjson}')
		if('deletefile' in requestjson): 
			filename = requestjson['filename']
			filepath = f'{RECIPE_FOLDER}{filename}'
			os.system(f'rm {filepath}')
			return jsonify({'result' : 'success'})
		if('assetchange' in requestjson):
			filename = requestjson['filename']
			filepath = f'{RECIPE_FOLDER}{filename}'
			recipe_data, status = read_recipefile(filepath)
			section = requestjson['section']
			section_index = requestjson['index']
			asset_name = requestjson['asset_name']
			asset_id = requestjson['asset_id']
			action = requestjson['action']
			if(action == 'add'):
				if(section in ['ingredients', 'instructions']):
					if asset_name not in recipe_data['recipe'][section][section_index]['assets']:
						recipe_data['recipe'][section][section_index]['assets'].append(asset_name)
						update_json_file_data(recipe_data['recipe'], filepath, 'recipe')
				elif(section in ['splash']):
					recipe_data['metadata']['image'] = asset_name
					recipe_data['metadata']['thumbnail'] = asset_name 
					update_json_file_data(recipe_data['metadata'], filepath, 'metadata')
				elif(section in ['delete']):
					remove_assets(filepath, [asset_name], filetype='recipefile')
			elif(action == 'remove'):
				if(section in ['ingredients', 'instructions']):
					if asset_name in recipe_data['recipe'][section][section_index]['assets']:
						recipe_data['recipe'][section][section_index]['assets'].remove(asset_name)
						update_json_file_data(recipe_data['recipe'], filepath, 'recipe')
				elif(section in ['splash']):
					recipe_data['metadata']['image'] = ''
					recipe_data['metadata']['thumbnail'] = ''
					update_json_file_data(recipe_data['metadata'], filepath, 'metadata')
				elif(section in ['delete']):
					remove_assets(filepath, [asset_name], filetype='recipefile')
			return jsonify({'result' : 'success'})

	return jsonify({'result' : 'error'})

@app.route('/settings/<action>', methods=['POST','GET'])
@app.route('/settings', methods=['POST','GET'])
def settings_page(action=None):

	global settings
	control = read_control()

	controller = read_generic_json('./controller/controllers.json')

	event = {
		'type' : 'none',
		'text' : ''
	}

	if request.method == 'POST' and action == 'probes':
		response = request.form

		for item in response.items():
			if 'profile_select_' in item[0]:
				probe_label = item[0].replace('profile_select_', '')
				for index, probe in enumerate(settings['probe_settings']['probe_map']['probe_info']):
					if probe['label'] == probe_label:
						settings['probe_settings']['probe_map']['probe_info'][index]['profile'] = settings['probe_settings']['probe_profiles'][item[1]]
			if 'probe_name_' in item[0]:
				probe_label = item[0].replace('probe_name_', '')
				for index, probe in enumerate(settings['probe_settings']['probe_map']['probe_info']):
					if probe['label'] == probe_label:
						settings['probe_settings']['probe_map']['probe_info'][index]['name'] = item[1]
						settings['history_page']['probe_config'][probe_label]['name'] = item[1]

		event['type'] = 'updated'
		event['text'] = 'Successfully updated probe settings.'

		control['probe_profile_update'] = True

		# Take all settings and write them
		write_settings(settings)
		write_control(control, origin='app')

	if request.method == 'POST' and action == 'notify':
		response = request.form

		if _is_checked(response, 'apprise_enabled'):
			settings['notify_services']['apprise']['enabled'] = True
		else:
			settings['notify_services']['apprise']['enabled'] = False
		if 'appriselocations' in response:
			locations = []
			for location in response.getlist('appriselocations'):
				if(len(location)):
					locations.append(location)
			settings['notify_services']['apprise']['locations'] = locations
		else:
			settings['notify_services']['apprise']['locations'] = []
		if _is_checked(response, 'ifttt_enabled'):
			settings['notify_services']['ifttt']['enabled'] = True
		else:
			settings['notify_services']['ifttt']['enabled'] = False
		if 'iftttapi' in response:
			settings['notify_services']['ifttt']['APIKey'] = response['iftttapi']
		if _is_checked(response, 'pushbullet_enabled'):
			settings['notify_services']['pushbullet']['enabled'] = True
		else:
			settings['notify_services']['pushbullet']['enabled'] = False
		if 'pushbullet_apikey' in response:
			settings['notify_services']['pushbullet']['APIKey'] = response['pushbullet_apikey']
		if 'pushbullet_publicurl' in response:
			settings['notify_services']['pushbullet']['PublicURL'] = response['pushbullet_publicurl']
		if _is_checked(response, 'pushover_enabled'):
			settings['notify_services']['pushover']['enabled'] = True
		else:
			settings['notify_services']['pushover']['enabled'] = False
		if 'pushover_apikey' in response:
			settings['notify_services']['pushover']['APIKey'] = response['pushover_apikey']
		if 'pushover_userkeys' in response:
			settings['notify_services']['pushover']['UserKeys'] = response['pushover_userkeys']
		if 'pushover_publicurl' in response:
			settings['notify_services']['pushover']['PublicURL'] = response['pushover_publicurl']
		if _is_checked(response, 'onesignal_enabled'):
			settings['notify_services']['onesignal']['enabled'] = True
		else:
			settings['notify_services']['onesignal']['enabled'] = False

		if _is_checked(response, 'influxdb_enabled'):
			settings['notify_services']['influxdb']['enabled'] = True
		else:
			settings['notify_services']['influxdb']['enabled'] = False
		if 'influxdb_url' in response:
			settings['notify_services']['influxdb']['url'] = response['influxdb_url']
		if 'influxdb_token' in response:
			settings['notify_services']['influxdb']['token'] = response['influxdb_token']
		if 'influxdb_org' in response:
			settings['notify_services']['influxdb']['org'] = response['influxdb_org']
		if 'influxdb_bucket' in response:
			settings['notify_services']['influxdb']['bucket'] = response['influxdb_bucket']

		if _is_checked(response, 'mqtt_enabled'):
			settings['notify_services']['mqtt']['enabled'] = True
		else:
			settings['notify_services']['mqtt']['enabled'] = False
		if 'mqtt_id' in response:
			settings['notify_services']['mqtt']['id'] = response['mqtt_id']
		if 'mqtt_broker' in response:
			settings['notify_services']['mqtt']['broker'] = response['mqtt_broker']
		if 'mqtt_port' in response:
			settings['notify_services']['mqtt']['port'] = response['mqtt_port']
		if 'mqtt_user' in response:
			settings['notify_services']['mqtt']['username'] = response['mqtt_user']
		if 'mqtt_pw' in response:
			settings['notify_services']['mqtt']['password'] = response['mqtt_pw']
		if 'mqtt_auto_d' in response:
			settings['notify_services']['mqtt']['homeassistant_autodiscovery_topic'] = response['mqtt_auto_d']
		if 'mqtt_freq' in response:
			settings['notify_services']['mqtt']['update_sec'] = response['mqtt_freq']

		if 'delete_device' in response:
			DeviceID = response['delete_device']
			settings['notify_services']['onesignal']['devices'].pop(DeviceID)

		if 'edit_device' in response:
			if response['edit_device'] != '':
				DeviceID = response['edit_device']
				settings['notify_services']['onesignal']['devices'][DeviceID] = {
					'friendly_name' : response['FriendlyName_' + DeviceID],
					'device_name' : response['DeviceName_' + DeviceID],
					'app_version' : response['AppVersion_' + DeviceID]
				}

		control['settings_update'] = True

		event['type'] = 'updated'
		event['text'] = 'Successfully updated notification settings.'

		# Take all settings and write them
		write_settings(settings)
		write_control(control, origin='app')

	if request.method == 'POST' and action == 'editprofile':
		response = request.form

		if 'delete' in response:
			UniqueID = response['delete'] # Get the string of the UniqueID
			try:
				# Check if this profile is in use
				for item in settings['probe_settings']['probe_map']['probe_info']:
					if item['profile']['id'] == UniqueID:
						event['type'] = 'error'
						event['text'] = f'Error: Cannot delete this profile, as it is selected for a probe.  Go to the probe settings tab and select a different profile for {item["name"]}.  Then try to delete this profile again.'
				if event['type'] != 'error':
					# Attempt to remove the profile 
					settings['probe_settings']['probe_profiles'].pop(UniqueID)
					write_settings(settings)
					event['type'] = 'updated'
					event['text'] = 'Successfully removed ' + response['Name_' + UniqueID] + ' profile.'
			except:
				event['type'] = 'error'
				event['text'] = 'Error: Failed to remove ' + response['Name_' + UniqueID] + ' profile.'

		if 'editprofile' in response:
			if response['editprofile'] != '':
				# Try to convert input values
				try:
					UniqueID = response['editprofile'] # Get the string of the UniqueID
					settings['probe_settings']['probe_profiles'][UniqueID] = {
						'A' : float(response['A_' + UniqueID]),
						'B' : float(response['B_' + UniqueID]),
						'C' : float(response['C_' + UniqueID]),
						'name' : response['Name_' + UniqueID], 
						'id' : UniqueID
					}
					# Update profile info in probe map 
					profile_in_use = False 
					for index, probe in enumerate(settings['probe_settings']['probe_map']['probe_info']):
						if probe['profile']['id'] == UniqueID:
							settings['probe_settings']['probe_map']['probe_info'][index]['profile'] = settings['probe_settings']['probe_profiles'][UniqueID]
							profile_in_use = True

					event['type'] = 'updated'
					event['text'] = 'Successfully edited ' + response['Name_' + UniqueID] + ' profile.'
					# Write the new probe profile to disk
					write_settings(settings)
					# If this profile is currently in use, update the profile in the control script as well 
					if profile_in_use:					
						control['probe_profile_update'] = True
						write_control(control, origin='app')
				except:
					event['type'] = 'error'
					event['text'] = 'Something bad happened when trying to format your inputs.  Try again.'
			else:
				event['type'] = 'error'
				event['text'] = 'Error. Profile NOT saved.'

	if request.method == 'POST' and action == 'addprofile':
		response = request.form

		if (response['Name'] != '' and response['A'] != '' and response['B'] != '' and response['C'] != ''):
			# Try to convert input values
			try:
				UniqueID = generate_uuid()
				settings['probe_settings']['probe_profiles'][UniqueID] = {
					'A' : float(response['A']),
					'B' : float(response['B']),
					'C' : float(response['C']),
					'name' : response['Name'], 
					'id' : UniqueID
				}
				print(f'Response: {response}')
				if response.get('apply_profile', False):
					probe_selected = response['apply_profile']
					for index, probe in enumerate(settings['probe_settings']['probe_map']['probe_info']):
						if probe['label'] == probe_selected:
							settings['probe_settings']['probe_map']['probe_info'][index]['profile'] = settings['probe_settings']['probe_profiles'][UniqueID]

				# Write the new probe profile to disk
				write_settings(settings)
				event['type'] = 'updated'
				event['text'] = 'Successfully added ' + response['Name'] + ' profile.'

			except:
				event['type'] = 'error'
				event['text'] = 'Something bad happened when trying to format your inputs.  Try again.'
		else:
			event['type'] = 'error'
			event['text'] = 'All fields must be completed before submitting. Profile NOT saved.'

	if request.method == 'POST' and action == 'controller_card':
		response = request.form
		render_string = "{% from '_macro_settings.html' import render_controller_config %}{{ render_controller_config(selected, metadata, settings, cycle_data) }}"
		return render_template_string(render_string, 
				selected=response['selected'], 
				metadata=controller['metadata'], 
				settings=settings['controller'],
				cycle_data=settings['cycle_data'])

	if request.method == 'POST' and action == 'cycle':
		response = request.form

		if _is_not_blank(response, 'pmode'):
			settings['cycle_data']['PMode'] = int(response['pmode'])
		if _is_not_blank(response, 'holdcycletime'):
			settings['cycle_data']['HoldCycleTime'] = int(response['holdcycletime'])
		if _is_not_blank(response, 'SmokeOnCycleTime'):
			settings['cycle_data']['SmokeOnCycleTime'] = int(response['SmokeOnCycleTime'])
		if _is_not_blank(response, 'SmokeOffCycleTime'):
			settings['cycle_data']['SmokeOffCycleTime'] = int(response['SmokeOffCycleTime'])

		if _is_not_blank(response, 'u_min'):
			settings['cycle_data']['u_min'] = float(response['u_min'])
		if _is_not_blank(response, 'u_max'):
			settings['cycle_data']['u_max'] = float(response['u_max'])

		if _is_checked(response, 'lid_open_detect_enable'):
			settings['cycle_data']['LidOpenDetectEnabled'] = True
		else:
			settings['cycle_data']['LidOpenDetectEnabled'] = False
		if _is_not_blank(response, 'lid_open_threshold'):
			settings['cycle_data']['LidOpenThreshold'] = int(response['lid_open_threshold'])
		if _is_not_blank(response, 'lid_open_pausetime'):
			settings['cycle_data']['LidOpenPauseTime'] = int(response['lid_open_pausetime'])
		if _is_not_blank(response, 'sp_on_time'):
			settings['smoke_plus']['on_time'] = int(response['sp_on_time'])
		if _is_not_blank(response, 'sp_off_time'):
			settings['smoke_plus']['off_time'] = int(response['sp_off_time'])
		if _is_checked(response, 'sp_fan_ramp'):
			settings['smoke_plus']['fan_ramp'] = True
		else:
			settings['smoke_plus']['fan_ramp'] = False
		if _is_not_blank(response, 'sp_duty_cycle'):
			settings['smoke_plus']['duty_cycle'] = int(response['sp_duty_cycle'])
		if _is_not_blank(response, 'sp_min_temp'):
			settings['smoke_plus']['min_temp'] = int(response['sp_min_temp'])
		if _is_not_blank(response, 'sp_max_temp'):
			settings['smoke_plus']['max_temp'] = int(response['sp_max_temp'])
		if _is_checked(response, 'default_smoke_plus'):
			settings['smoke_plus']['enabled'] = True
		else:
			settings['smoke_plus']['enabled'] = False
		if _is_not_blank(response, 'keep_warm_temp'):
			settings['keep_warm']['temp'] = int(response['keep_warm_temp'])
		if _is_checked(response, 'keep_warm_s_plus'):
			settings['keep_warm']['s_plus'] = True
		else:
			settings['keep_warm']['s_plus'] = False

		if _is_not_blank(response, 'selectController'):
			# Select Controller Type
			selected = response['selectController']
			settings['controller']['selected'] = selected
			settings['controller']['config'][selected] = {}
			# Save Controller Configuration 
			for item, value in response.items(): 
				if item.startswith('controller_config_'):
					option_name = item.replace('controller_config_', '')
					for option in controller['metadata'][selected]['config']:
						if option_name == option['option_name']: 
							if option['option_type'] == 'float':
								settings['controller']['config'][selected][option_name] = float(value) 
							elif option['option_type'] == 'int':
								settings['controller']['config'][selected][option_name] = int(value)
							elif option['option_type'] == 'bool':
								settings['controller']['config'][selected][option_name] = True if value == 'true' else False 
							elif option['option_type'] == 'numlist':
								settings['controller']['config'][selected][option_name] = float(value)
							else: 
								settings['controller']['config'][selected][option_name] = value
 
		event['type'] = 'updated'
		event['text'] = 'Successfully updated cycle settings.'

		control['settings_update'] = True

		write_settings(settings)
		write_control(control, origin='app')

	if request.method == 'POST' and action == 'pwm':
		response = request.form

		if _is_checked(response, 'pwm_control'):
			settings['pwm']['pwm_control'] = True
		else:
			settings['pwm']['pwm_control'] = False
		if _is_not_blank(response, 'pwm_update'):
			settings['pwm']['update_time'] = int(response['pwm_update'])
		if _is_not_blank(response, 'min_duty_cycle'):
			settings['pwm']['min_duty_cycle'] = int(response['min_duty_cycle'])
		if _is_not_blank(response, 'max_duty_cycle'):
			settings['pwm']['max_duty_cycle'] = int(response['max_duty_cycle'])
		if _is_not_blank(response, 'frequency'):
			settings['pwm']['frequency'] = int(response['frequency'])

		event['type'] = 'updated'
		event['text'] = 'Successfully updated PWM settings.'

		control['settings_update'] = True

		write_settings(settings)
		write_control(control, origin='app')

	if request.method == 'POST' and action == 'startup':
		response = request.form

		if _is_not_blank(response, 'shutdown_duration'):
			settings['shutdown']['shutdown_duration'] = int(response['shutdown_duration'])
		if _is_not_blank(response, 'startup_duration'):
			settings['startup']['duration'] = int(response['startup_duration'])
		if _is_checked(response, 'auto_power_off'):
			settings['shutdown']['auto_power_off'] = True
		else:
			settings['shutdown']['auto_power_off'] = False
		if _is_checked(response, 'smartstart_enable'):
			settings['startup']['smartstart']['enabled'] = True
		else:
			settings['startup']['smartstart']['enabled'] = False
		if _is_not_blank(response, 'smartstart_exit_temp'):
			settings['startup']['smartstart']['exit_temp'] = int(response['smartstart_exit_temp'])
		if _is_not_blank(response, 'startup_exit_temp'):
			settings['startup']['startup_exit_temp'] = int(response['startup_exit_temp'])
		if _is_not_blank(response, 'prime_on_startup'):
			prime_amount = int(response['prime_on_startup'])
			if prime_amount < 0 or prime_amount > 200:
				prime_amount = 0  # Validate input, set to disabled if exceeding limits.  
			settings['startup']['prime_on_startup'] = int(response['prime_on_startup'])

		settings['startup']['start_to_mode']['after_startup_mode'] = response['after_startup_mode']
		settings['startup']['start_to_mode']['primary_setpoint'] = int(response['startup_mode_setpoint'])
		
		event['type'] = 'updated'
		event['text'] = 'Successfully updated startup/shutdown settings.'

		control['settings_update'] = True

		write_settings(settings)
		write_control(control, origin='app')

	if request.method == 'POST' and action == 'dashboard':
		response = request.form
		if _is_not_blank(response, 'dashboardSelect'):
			settings['dashboard']['current'] = response['dashboardSelect']
			write_settings(settings)
			event['type'] = 'updated'
			event['text'] = 'Successfully updated dashboard settings.'

	if request.method == 'POST' and action == 'history':
		response = request.form

		if _is_not_blank(response, 'historymins'):
			settings['history_page']['minutes'] = int(response['historymins'])
		if _is_checked(response, 'clearhistorystartup'):
			settings['history_page']['clearhistoryonstart'] = True
		else:
			settings['history_page']['clearhistoryonstart'] = False
		if _is_checked(response, 'historyautorefresh'):
			settings['history_page']['autorefresh'] = 'on'
		else:
			settings['history_page']['autorefresh'] = 'off'
		if _is_not_blank(response, 'datapoints'):
			settings['history_page']['datapoints'] = int(response['datapoints'])

		# This check should be the last in this group
		if control['mode'] != 'Stop' and _is_checked(response, 'ext_data') != settings['globals']['ext_data']:
			event['type'] = 'error'
			event['text'] = 'This setting cannot be changed in any active mode.  Stop the grill and try again.'
		else: 
			if _is_checked(response, 'ext_data'):
				settings['globals']['ext_data'] = True
			else:
				settings['globals']['ext_data'] = False 

			event['type'] = 'updated'
			event['text'] = 'Successfully updated history settings.'

		# Edit Graph Color Config
		for item in response:
			if 'clr_temp_' in item: 
				probe_label = item.replace('clr_temp_', '')
				settings['history_page']['probe_config'][probe_label]['line_color'] = response[item]
			if 'clrbg_temp_' in item: 
				probe_label = item.replace('clrbg_temp_', '')
				settings['history_page']['probe_config'][probe_label]['bg_color'] = response[item]
			if 'clr_setpoint_' in item: 
				probe_label = item.replace('clr_setpoint_', '')
				settings['history_page']['probe_config'][probe_label]['line_color_setpoint'] = response[item]
			if 'clrbg_setpoint_' in item: 
				probe_label = item.replace('clrbg_setpoint_', '')
				settings['history_page']['probe_config'][probe_label]['bg_color_setpoint'] = response[item]
			if 'clr_target_' in item: 
				probe_label = item.replace('clr_target_', '')
				settings['history_page']['probe_config'][probe_label]['line_color_target'] = response[item]
			if 'clrbg_target_' in item: 
				probe_label = item.replace('clrbg_target_', '')
				settings['history_page']['probe_config'][probe_label]['bg_color_target'] = response[item]

		write_settings(settings)

	if request.method == 'POST' and action == 'pagesettings':
		response = request.form

		if _is_checked(response, 'darkmode'):
			settings['globals']['page_theme'] = 'dark'
		else:
			settings['globals']['page_theme'] = 'light'

		if _is_checked(response, 'global_control_panel'):
			settings['globals']['global_control_panel'] = True
		else:
			settings['globals']['global_control_panel'] = False

		event['type'] = 'updated'
		event['text'] = 'Successfully updated page settings.'

		write_settings(settings)

	if request.method == 'POST' and action == 'safety':
		response = request.form

		if _is_not_blank(response, 'minstartuptemp'):
			settings['safety']['minstartuptemp'] = int(response['minstartuptemp'])
		if _is_not_blank(response, 'maxstartuptemp'):
			settings['safety']['maxstartuptemp'] = int(response['maxstartuptemp'])
		if _is_not_blank(response, 'reigniteretries'):
			settings['safety']['reigniteretries'] = int(response['reigniteretries'])
		if _is_not_blank(response, 'maxtemp'):
			settings['safety']['maxtemp'] = int(response['maxtemp'])
		if _is_checked(response, 'startup_check'):
			settings['safety']['startup_check'] = True
		else:
			settings['safety']['startup_check'] = False

		event['type'] = 'updated'
		event['text'] = 'Successfully updated safety settings.'

		write_settings(settings)

	if request.method == 'POST' and action == 'grillname':
		response = request.form

		if 'grill_name' in response:
			settings['globals']['grill_name'] = response['grill_name']
			event['type'] = 'updated'
			event['text'] = 'Successfully updated grill name.'

		write_settings(settings)

	if request.method == 'POST' and action == 'pellets':
		response = request.form

		if _is_checked(response, 'pellet_warning'):
			settings['pelletlevel']['warning_enabled'] = True
		else:
			settings['pelletlevel']['warning_enabled'] = False
		if _is_not_blank(response, 'warning_time'):
			settings['pelletlevel']['warning_time'] = int(response['warning_time'])
		if _is_not_blank(response, 'warning_level'):
			settings['pelletlevel']['warning_level'] = int(response['warning_level'])
		if _is_not_blank(response, 'empty'):
			settings['pelletlevel']['empty'] = int(response['empty'])
			control['distance_update'] = True
		if _is_not_blank(response, 'full'):
			settings['pelletlevel']['full'] = int(response['full'])
			control['distance_update'] = True
		if _is_not_blank(response, 'auger_rate'):
			settings['globals']['augerrate'] = float(response['auger_rate'])

		if _is_checked(response, 'prime_ignition'):
			settings['globals']['prime_ignition'] = True
		else:
			settings['globals']['prime_ignition'] = False

		event['type'] = 'updated'
		event['text'] = 'Successfully updated pellet settings.'

		control['settings_update'] = True

		write_settings(settings)
		write_control(control, origin='app')

	if request.method == 'POST' and action == 'units':
		response = request.form

		if 'units' in response:
			if response['units'] == 'C' and settings['globals']['units'] == 'F':
				settings = convert_settings_units('C', settings)
				write_settings(settings)
				event['type'] = 'updated'
				event['text'] = 'Successfully updated units to Celsius.'
				control = {}
				control['updated'] = True
				control['units_change'] = True
				write_control(control, origin='app')
			elif response['units'] == 'F' and settings['globals']['units'] == 'C':
				settings = convert_settings_units('F', settings)
				write_settings(settings)
				event['type'] = 'updated'
				event['text'] = 'Successfully updated units to Fahrenheit.'
				control = {}
				control['updated'] = True
				control['units_change'] = True
				write_control(control, origin='app')
	'''
	Smart Start Settings
	'''
	if request.method == 'GET' and action == 'smartstart':
		temps = settings['startup']['smartstart']['temp_range_list']
		profiles = settings['startup']['smartstart']['profiles']
		return(jsonify({'temps_list' : temps, 'profiles' : profiles}))

	if request.method == 'POST' and action == 'smartstart':
		response = request.json 
		settings['startup']['smartstart']['temp_range_list'] = response['temps_list']
		settings['startup']['smartstart']['profiles'] = response['profiles']
		write_settings(settings)
		return(jsonify({'result' : 'success'}))

	'''
	PWM Duty Cycle
	'''
	if request.method == 'GET' and action == 'pwm_duty_cycle':
		temps = settings['pwm']['temp_range_list']
		profiles = settings['pwm']['profiles']
		return(jsonify({'dc_temps_list' : temps, 'dc_profiles' : profiles}))

	if request.method == 'POST' and action == 'pwm_duty_cycle':
		response = request.json
		settings['pwm']['temp_range_list'] = response['dc_temps_list']
		settings['pwm']['profiles'] = response['dc_profiles']
		write_settings(settings)
		return(jsonify({'result' : 'success'}))

	return render_template('settings.html',
						   settings=settings,
						   alert=event,
						   control=control,
						   controller_metadata=controller['metadata'],
						   page_theme=settings['globals']['page_theme'],
						   grill_name=settings['globals']['grill_name'])

@app.route('/admin/<action>', methods=['POST','GET'])
@app.route('/admin', methods=['POST','GET'])
def admin_page(action=None):
	global server_status
	global settings
	control = read_control()
	pelletdb = read_pellet_db()
	notify = ''

	if not os.path.exists(BACKUP_PATH):
		os.mkdir(BACKUP_PATH)
	files = os.listdir(BACKUP_PATH)
	for file in files:
		if not _allowed_file(file):
			files.remove(file)

	if action == 'reboot':
		event = "Admin: Reboot"
		write_log(event)
		server_status = 'rebooting'
		reboot_system()
		return render_template('shutdown.html', action=action, page_theme=settings['globals']['page_theme'],
							   grill_name=settings['globals']['grill_name'])

	elif action == 'shutdown':
		event = "Admin: Shutdown"
		write_log(event)
		server_status = 'shutdown'
		shutdown_system()
		return render_template('shutdown.html', action=action, page_theme=settings['globals']['page_theme'],
							   grill_name=settings['globals']['grill_name'])

	elif action == 'restart':
		event = "Admin: Restart Server"
		write_log(event)
		server_status = 'restarting'
		restart_scripts()
		return render_template('shutdown.html', action=action, page_theme=settings['globals']['page_theme'],
							   grill_name=settings['globals']['grill_name'])

	if request.method == 'POST' and action == 'setting':
		response = request.form

		if 'debugenabled' in response:
			control['settings_update'] = True
			if response['debugenabled'] == 'disabled':
				write_log('Debug Mode Disabled.')
				settings['globals']['debug_mode'] = False
				write_settings(settings)
				write_control(control, origin='app')
			else:
				settings['globals']['debug_mode'] = True
				write_settings(settings)
				write_control(control, origin='app')
				write_log('Debug Mode Enabled.')

		if 'clearhistory' in response:
			if response['clearhistory'] == 'true':
				write_log('Clearing History Log.')
				read_history(0, flushhistory=True)

		if 'clearevents' in response:
			if response['clearevents'] == 'true':
				write_log('Clearing Events Log.')
				os.system('rm /tmp/events.log')

		if 'clearpelletdb' in response:
			if response['clearpelletdb'] == 'true':
				write_log('Clearing Pellet Database.')
				os.system('rm pelletdb.json')

		if 'clearpelletdblog' in response:
			if response['clearpelletdblog'] == 'true':
				write_log('Clearing Pellet Database Log.')
				pelletdb['log'].clear()
				write_pellet_db(pelletdb)

		if 'factorydefaults' in response:
			if response['factorydefaults'] == 'true':
				write_log('Resetting Settings, Control and History to factory defaults.')
				read_history(0, flushhistory=True)
				read_control(flush=True)
				os.system('rm settings.json')
				os.system('rm pelletdb.json')
				settings = default_settings()
				control = default_control()
				write_settings(settings)
				write_control(control, origin='app')
				server_status = 'restarting'
				restart_scripts()
				return render_template('shutdown.html', action='restart', page_theme=settings['globals']['page_theme'],
									   grill_name=settings['globals']['grill_name'])

		if 'download_logs' in response:
			zip_file = _zip_files_logs('logs')
			return send_file(zip_file, as_attachment=True, max_age=0)
		
		if 'backupsettings' in response:
			backup_file = backup_settings()
			return send_file(backup_file, as_attachment=True, max_age=0)

		if 'restoresettings' in response:
			# Assume we have request.files and local file in response
			remote_file = request.files['uploadfile']
			local_file = request.form['localfile']
			
			if local_file != 'none':
				new_settings = read_settings(filename=BACKUP_PATH+local_file)
				write_settings(new_settings)
				server_status = 'restarting'
				restart_scripts()
				return render_template('shutdown.html', action='restart', page_theme=settings['globals']['page_theme'],
									   grill_name=settings['globals']['grill_name'])
			elif remote_file.filename != '':
				# If the user does not select a file, the browser submits an
				# empty file without a filename.
				if remote_file and _allowed_file(remote_file.filename):
					filename = secure_filename(remote_file.filename)
					remote_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
					notify = "success"
					new_settings = read_settings(filename=BACKUP_PATH+filename)
					write_settings(new_settings)
					server_status = 'restarting'
					restart_scripts()
					return render_template('shutdown.html', action='restart', page_theme=settings['globals']['page_theme'],
									   		grill_name=settings['globals']['grill_name'])
				else:
					notify = "error"
			else:
				notify = "error"

		if 'backuppelletdb' in response:
			backup_file = backup_pellet_db(action='backup')
			return send_file(backup_file, as_attachment=True, max_age=0)

		if 'restorepelletdb' in response:
			# Assume we have request.files and local file in response
			remote_file = request.files['uploadfile']
			local_file = request.form['localfile']
			
			if local_file != 'none':
				pelletdb = read_pellet_db(filename=BACKUP_PATH+local_file)
				write_pellet_db(pelletdb)
				notify = "success"
			elif remote_file.filename != '':
				# If the user does not select a file, the browser submits an
				# empty file without a filename.
				if remote_file and _allowed_file(remote_file.filename):
					filename = secure_filename(remote_file.filename)
					remote_file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
					notify = "success"
					pelletdb = read_pellet_db(filename=BACKUP_PATH+filename)
					write_pellet_db(pelletdb)
				else:
					notify = "error"
			else:
				notify = "error"
	
	if request.method == 'POST' and action == 'boot':
		response = request.form

		if 'boot_to_monitor' in response:
			settings['globals']['boot_to_monitor'] = True 
		else:
			settings['globals']['boot_to_monitor'] = False 
		
		write_settings(settings)

	uptime = os.popen('uptime').readline()

	cpu_info = os.popen('cat /proc/cpuinfo').readlines()

	ifconfig = os.popen('ifconfig').readlines()

	if is_real_hardware():
		temp = _check_cpu_temp()
	else:
		temp = '---'

	debug_mode = settings['globals']['debug_mode']

	url = request.url_root

	return render_template('admin.html', settings=settings, notify=notify, uptime=uptime, cpuinfo=cpu_info, temp=temp,
						   ifconfig=ifconfig, debug_mode=debug_mode, qr_content=url,
						   control=control,
						   page_theme=settings['globals']['page_theme'],
						   grill_name=settings['globals']['grill_name'], files=files)

@app.route('/manual/<action>', methods=['POST','GET'])
@app.route('/manual', methods=['POST','GET'])
def manual_page(action=None):

	global settings
	control = read_control()

	if request.method == 'POST':
		response = request.form

		if 'setmode' in response:
			if response['setmode'] == 'manual':
				control['updated'] = True
				control['mode'] = 'Manual'
			else:
				control['updated'] = True
				control['mode'] = 'Stop'

		if 'change_output_fan' in response:
			if response['change_output_fan'] == 'on':
				control['manual']['change'] = True
				control['manual']['fan'] = True
			elif response['change_output_fan'] == 'off':
				control['manual']['change'] = True
				control['manual']['fan'] = False
				control['manual']['pwm'] = 100
		elif 'change_output_auger' in response:
			if response['change_output_auger'] == 'on':
				control['manual']['change'] = True
				control['manual']['auger'] = True
			elif response['change_output_auger'] == 'off':
				control['manual']['change'] = True
				control['manual']['auger'] = False
		elif 'change_output_igniter' in response:
			if response['change_output_igniter'] == 'on':
				control['manual']['change'] = True
				control['manual']['igniter'] = True
			elif response['change_output_igniter'] == 'off':
				control['manual']['change'] = True
				control['manual']['igniter'] = False
		elif 'change_output_power' in response:
			if response['change_output_power'] == 'on':
				control['manual']['change'] = True
				control['manual']['power'] = True
			elif response['change_output_power'] == 'off':
				control['manual']['change'] = True
				control['manual']['power'] = False
		elif 'duty_cycle_range' in response:
			speed = int(response['duty_cycle_range'])
			control['manual']['change'] = True
			control['manual']['pwm'] = speed

		write_control(control, origin='app')

		time.sleep(1)
		control = read_control()

	return render_template('manual.html', settings=settings, control=control,
						   	page_theme=settings['globals']['page_theme'],
						   	grill_name=settings['globals']['grill_name'])

@app.route('/api', methods=['POST','GET'])
@app.route('/api/<action>', methods=['POST','GET'])
@app.route('/api/<action>/<arg0>', methods=['POST','GET'])
@app.route('/api/<action>/<arg0>/<arg1>', methods=['POST','GET'])
@app.route('/api/<action>/<arg0>/<arg1>/<arg2>', methods=['POST','GET'])
@app.route('/api/<action>/<arg0>/<arg1>/<arg2>/<arg3>', methods=['POST','GET'])
def api_page(action=None, arg0=None, arg1=None, arg2=None, arg3=None):
	global settings
	global server_status

	if action in ['get', 'set', 'cmd']:
		#print(f'action={action}\narg0={arg0}\narg1={arg1}\narg2={arg2}\narg3={arg3}')
		arglist = []
		arglist.extend([arg0, arg1, arg2, arg3])

		data = process_command(action=action, arglist=arglist, origin='api')
		return jsonify(data), 201
	
	elif request.method == 'GET':
		if action == 'settings':
			return jsonify({'settings':settings}), 201
		elif action == 'server':
			return jsonify({'server_status' : server_status}), 201
		elif action == 'control':
			control=read_control()
			return jsonify({'control':control}), 201
		elif action == 'current':
			''' Only fetch data from RedisDB or locally available, to improve performance '''
			current_temps = read_current()
			control = read_control()
			display = read_status()  # Get status of display items

			''' Create string of probes that can be hashed to ensure UI integrity '''
			probe_string = ''
			for group in current_temps:
				if group in ['P', 'F']:
					for probe in current_temps[group]:
						probe_string += probe
			probe_string += settings['globals']['units']

			notify_data = control['notify_data']

			status = {}
			status['mode'] = control['mode']
			status['display_mode'] = display['mode']
			status['status'] = control['status']
			status['s_plus'] = control['s_plus']
			status['units'] = settings['globals']['units']
			status['name'] = settings['globals']['grill_name']
			status['start_time'] = display['start_time']
			status['start_duration'] = display['start_duration']
			status['shutdown_duration'] = display['shutdown_duration']
			status['prime_duration'] = display['prime_duration']
			status['prime_amount'] = display['prime_amount']
			status['lid_open_detected'] = display['lid_open_detected']
			status['lid_open_endtime'] = display['lid_open_endtime']
			status['p_mode'] = display['p_mode']
			status['outpins'] = display['outpins']
			status['startup_timestamp'] = display['startup_timestamp']
			status['ui_hash'] = create_ui_hash()
			return jsonify({'current':current_temps, 'notify_data':notify_data, 'status':status}), 201
		elif action == 'hopper':
			pelletdb = read_pellet_db()
			pelletlevel = pelletdb['current']['hopper_level']
			pelletid = pelletdb['current']['pelletid']
			pellets = f'{pelletdb["archive"][pelletid]["brand"]} {pelletdb["archive"][pelletid]["wood"]}'
			return jsonify({'hopper_level': pelletlevel, 'hopper_pellets': pellets}) 
		else:
			return jsonify({'Error':'Received GET request, without valid action'}), 404
	
	elif request.method == 'POST':
		if not request.json:
			event = "Local API Call Failed"
			write_log(event)
			abort(400)
		else:
			request_json = request.json
			if(action == 'settings'):
				settings = deep_update(settings, request.json)
				'''
				for key in settings.keys():
					if key in request_json.keys():
						settings[key].update(request_json.get(key, {}))
				'''
				write_settings(settings)
				return jsonify({'settings':'success'}), 201
			elif(action == 'control'):
				'''
					Updating of control input data is now done in common.py > execute_commands() 
				'''
				write_control(request.json, origin='app')
				return jsonify({'control':'success'}), 201
			else:
				return jsonify({'Error':'Received POST request no valid action.'}), 404
	else:
		return jsonify({'Error':'Received undefined/unsupported request.'}), 404

'''
Wizard Route for PiFire Setup
'''
@app.route('/wizard/<action>', methods=['POST','GET'])
@app.route('/wizard', methods=['GET', 'POST'])
def wizard(action=None):
	global settings
	control = read_control()

	wizardData = read_wizard()
	errors = []

	if settings['globals']['venv']:
		python_exec = 'bin/python'
	else:
		python_exec = 'python'

	if request.method == 'GET':
		if action=='installstatus':
			percent, status, output = get_wizard_install_status()
			return jsonify({'percent' : percent, 'status' : status, 'output' : output}) 
	elif request.method == 'POST':
		r = request.form
		if action=='cancel':
			settings['globals']['first_time_setup'] = False
			write_settings(settings)
			return redirect('/')
		if action=='finish':
			if control['mode'] == 'Stop':
				wizardInstallInfo = prepare_wizard_data(r)
				store_wizard_install_info(wizardInstallInfo)
				set_wizard_install_status(0, 'Starting Install...', '')
				os.system(f'{python_exec} wizard.py &')	# Kickoff Installation
				return render_template('wizard-finish.html', page_theme=settings['globals']['page_theme'],
									grill_name=settings['globals']['grill_name'], wizardData=wizardData)

		if action=='modulecard':
			module = r['module']
			section = r['section']
			if section in ['grillplatform', 'display', 'distance']:
				moduleData = wizardData['modules'][section][module]
				moduleSettings = get_settings_dependencies_values(settings, moduleData)
				render_string = "{% from '_macro_wizard_card.html' import render_wizard_card %}{{ render_wizard_card(moduleData, moduleSection, moduleSettings) }}"
				return render_template_string(render_string, moduleData=moduleData, moduleSection=section, moduleSettings=moduleSettings)
			else:
				return '<strong color="red">No Data</strong>'
	
	''' Create Temporary Probe Device/Port Structure for Setup, Use Existing unless First Time Setup '''
	if settings['globals']['first_time_setup']: 
		wizardInstallInfo = wizardInstallInfoDefaults(wizardData)
	else:
		wizardInstallInfo = wizardInstallInfoExisting(wizardData, settings)

	store_wizard_install_info(wizardInstallInfo)

	if control['mode'] != 'Stop':
		errors.append('PiFire configuration wizard cannot be run while the system is active.  Please stop the current cook before continuing.')

	return render_template('wizard.html', settings=settings, page_theme=settings['globals']['page_theme'],
						   grill_name=settings['globals']['grill_name'], wizardData=wizardData, wizardInstallInfo=wizardInstallInfo, control=control, errors=errors)

def get_settings_dependencies_values(settings, moduleData):
	moduleSettings = {}
	for setting, data in moduleData['settings_dependencies'].items():
		setting_location = data['settings']
		setting_value = settings
		for setting_name in setting_location:
			setting_value = setting_value[setting_name]
		moduleSettings[setting] = setting_value 
	print(moduleSettings)
	return moduleSettings 

def wizardInstallInfoDefaults(wizardData):
	
	wizardInstallInfo = {
		'modules' : {
			'grillplatform' : {
				'module_selected' : [],
				'settings' : {}
			}, 
			'display' : {
				'module_selected' : [],
				'settings' : {}
			}, 
			'distance' : {
				'module_selected' : [],
				'settings' : {}
			}, 
			'probes' : {
				'module_selected' : [],
				'settings' : {
					'units' : 'F'
				}
			}
		},
		'probe_map' : wizardData['boards']['PiFirev2x']['probe_map']
	}
	''' Populate Modules Info with Defaults from Wizard Data including Settings '''
	for component in ['grillplatform', 'display', 'distance']:
		for module in wizardData['modules'][component]:
			if wizardData['modules'][component][module]['default']:
				''' Populate Module Filename'''
				wizardInstallInfo['modules'][component]['module_selected'].append(wizardData['modules'][component][module]['filename'])
				for setting in wizardData['modules'][component][module]['settings_dependencies']: 
					''' Populate all settings with default value '''
					wizardInstallInfo['modules'][component]['settings'][setting] = list(wizardData['modules'][component][module]['settings_dependencies'][setting]['options'].keys())[0]

	''' Populate Probes Module List with all configured probe devices '''
	for device in wizardInstallInfo['probe_map']['probe_devices']:
		wizardInstallInfo['modules']['probes']['module_selected'].append(device['module'])

	return wizardInstallInfo

def wizardInstallInfoExisting(wizardData, settings):
	wizardInstallInfo = {
		'modules' : {
			'grillplatform' : {
				'module_selected' : [settings['modules']['grillplat']],
				'settings' : {}
			}, 
			'display' : {
				'module_selected' : [settings['modules']['display']],
				'settings' : {}
			}, 
			'distance' : {
				'module_selected' : [settings['modules']['dist']],
				'settings' : {}
			}, 
			'probes' : {
				'module_selected' : [],
				'settings' : {
					'units' : settings['globals']['units']
				}
			}
		}, 
		'probe_map' : settings['probe_settings']['probe_map']
	} 
	''' Populate Probes Module List with all configured probe devices '''
	for device in wizardInstallInfo['probe_map']['probe_devices']:
		wizardInstallInfo['modules']['probes']['module_selected'].append(device['module'])
	
	''' Populate Modules Info with current Settings '''
	for module in ['grillplatform', 'display', 'distance']:
		selected = wizardInstallInfo['modules'][module]['module_selected'][0]
		for setting in wizardData['modules'][module][selected]['settings_dependencies']:
			settingsLocation = wizardData['modules'][module][selected]['settings_dependencies'][setting]['settings']
			settingsValue = settings.copy() 
			for index in range(0, len(settingsLocation)):
				settingsValue = settingsValue[settingsLocation[index]]
			wizardInstallInfo['modules'][module]['settings'][setting] = str(settingsValue)

	return wizardInstallInfo

def prepare_wizard_data(form_data):
	wizardData = read_wizard()
	
	wizardInstallInfo = load_wizard_install_info()

	wizardInstallInfo['modules'] = {
		'grillplatform' : {
			'module_selected' : [form_data['grillplatformSelect']],
			'settings' : {}
		}, 
		'display' : {
			'module_selected' : [form_data['displaySelect']],
			'settings' : {}
		}, 
		'distance' : {
			'module_selected' : [form_data['distanceSelect']],
			'settings' : {}
		}, 
		'probes' : {
			'module_selected' : [],
			'settings' : {
				'units' : form_data['probes_units']
			}
		}
	}

	for device in wizardInstallInfo['probe_map']['probe_devices']:
		wizardInstallInfo['modules']['probes']['module_selected'].append(device['module'])

	for module in ['grillplatform', 'display', 'distance']:
		module_ = module + '_'
		moduleSelect = module + 'Select'
		selected = form_data[moduleSelect]
		for setting in wizardData['modules'][module][selected]['settings_dependencies']:
			settingName = module_ + setting
			if(settingName in form_data):
				wizardInstallInfo['modules'][module]['settings'][setting] = form_data[settingName]

	return(wizardInstallInfo)

'''
Probe Configuration Route
'''
@app.route('/probeconfig', methods=['GET', 'POST'])
def probe_config():
	global settings
	wizardData = read_wizard()
	wizardInstallInfo = load_wizard_install_info()
	alerts = []
	errors = 0

	if request.method == 'GET':
		render_string = "{% from '_macro_probes_config.html' import render_probe_devices, render_probe_ports %}{{ render_probe_devices(probe_map, modules, alerts) }}{{ render_probe_ports(probe_map, modules) }}"
		return render_template_string(render_string, probe_map=wizardInstallInfo['probe_map'], modules=wizardData['modules']['probes'], alerts=alerts)
	elif request.method == 'POST':
		r = request.form
		if r['section'] == 'devices':
			if r['action'] == 'delete_device':
				for index, device in enumerate(wizardInstallInfo['probe_map']['probe_devices']):
					if device['device'] == r['name']:
						# Remove the device from the device list
						wizardInstallInfo['probe_map']['probe_devices'].pop(index)
						# Remove probes associated with device from the probe list
						probe_info = []
						for index, probe in enumerate(wizardInstallInfo['probe_map']['probe_info']):
							# to maintain consistency while iterating, create a new list of probes
							if probe['device'] != r['name']:
								probe_info.append(probe)
						wizardInstallInfo['probe_map']['probe_info'] = probe_info
						store_wizard_install_info(wizardInstallInfo)
						break 
			if r['action'] == 'add_config':
				''' Populate Configuration Settings into Modal '''
				moduleData = wizardData['modules']['probes'][r['module']]
				friendlyName = wizardData['modules']['probes'][r['module']]['friendly_name']
				deviceName = "".join([x for x in friendlyName if x.isalnum()])
				available_probes = []
				''' Get a list of port-labels that can be used by the virtual port '''
				for index, probe in enumerate(wizardInstallInfo['probe_map']['probe_info']):
					available_probes.append(probe['label'])
				''' Set default configuration data '''
				defaultConfig = {}
				for config_setting in moduleData['device_specific']['config']:
					if config_setting['label'] == 'probes_list':
						defaultConfig[config_setting['label']] = []
					else:
						defaultConfig[config_setting['label']] = config_setting['default']
				render_string = "{% from '_macro_probes_config.html' import render_probe_device_settings %}{{ render_probe_device_settings(moduleData, moduleSection, defaultName, defaultConfig, available_probes, mode) }}"
				return render_template_string(render_string, moduleData=moduleData, moduleSection='probes', defaultName=deviceName, defaultConfig=defaultConfig, available_probes=available_probes, mode='Add')
			if r['action'] == 'add_device':
				''' Add device to the Wizard Install Info Probe Map Devices '''
				device_name = "".join([x for x in r['name'] if x.isalnum()])
				# Check if any other devices are using that name
				for index, device in enumerate(wizardInstallInfo['probe_map']['probe_devices']):
					if device['device'] == device_name: 
						alert = {
							'message' : 'Device name already exists.  Please select a unique device name.',
							'type' : 'error'
						}
						alerts.append(alert)
						errors += 1
						break 
				
				if r['name'] == '': 
					alert = {
						'message' : 'Device name is blank.  Please select a unique device name.',
						'type' : 'error'
					}
					alerts.append(alert)
					errors += 1

				if errors == 0:
					# Configure new device entry
					new_device = {
						"config": {},
						"device": device_name,
						"module": r['module'],
						"ports": wizardData['modules']['probes'][r['module']]['device_specific']['ports']
					}
					# If any device specific configuration settings, set them here
					for key, config_value in r.items():
						if 'probes_devspec_' in key:
							if '[]' in key:
								config_item = key.replace('probes_devspec_', '').replace('[]', '')
								new_device['config'][config_item] = request.form.getlist(key)
							else:
								config_item = key.replace('probes_devspec_', '')
								new_device['config'][config_item] = config_value 
					
					wizardInstallInfo['probe_map']['probe_devices'].append(new_device)
					store_wizard_install_info(wizardInstallInfo)
			if r['action'] == 'edit_config':
				''' Populate Configuration Settings into Modal '''
				device_name = r['name']
				for index, device in enumerate(wizardInstallInfo['probe_map']['probe_devices']):
					if device['device'] == device_name: 
						#wizardInstallInfo['probe_map']['probe_devices'][index]
						moduleData = wizardData['modules']['probes'][device['module']]
						defaultConfig = device['config']
						break 
					
				''' Get a list of port-labels that can be used by the virtual port '''
				available_probes = []
				for index, probe in enumerate(wizardInstallInfo['probe_map']['probe_info']):
					available_probes.append(probe['label'])

				render_string = "{% from '_macro_probes_config.html' import render_probe_device_settings %}{{ render_probe_device_settings(moduleData, moduleSection, defaultName, defaultConfig, available_probes, mode) }}"
				return render_template_string(render_string, moduleData=moduleData, moduleSection='probes', defaultName=device_name, defaultConfig=defaultConfig, available_probes=available_probes, mode='Edit')
			if r['action'] == 'edit_device':
				''' Save changes from edited device to WizardInstallInfo structure '''
				if r['newname'] == '': 
					alert = {
						'message' : 'Device name is blank.  Please select a unique device name.',
						'type' : 'error'
					}
					alerts.append(alert)
					errors += 1
				
				if not errors: 
					# Configure new device entry
					new_device = {
						"config": {},
						"device": r['newname'],
						"module": "",
						"ports": []
					}
					# If any device specific configuration settings, set them here
					for key, config_value in r.items():
						if 'probes_devspec_' in key:
							if '[]' in key:
								config_item = key.replace('probes_devspec_', '').replace('[]', '')
								new_device['config'][config_item] = request.form.getlist(key)
							else:
								config_item = key.replace('probes_devspec_', '')
								new_device['config'][config_item] = config_value 
					for index, probe in enumerate(wizardInstallInfo['probe_map']['probe_devices']):
						if probe['device'] == r['name']:
							new_device['ports'] = probe['ports']
							new_device['module'] = probe['module']
							wizardInstallInfo['probe_map']['probe_devices'][index] = new_device
							store_wizard_install_info(wizardInstallInfo)
							break
			render_string = "{% from '_macro_probes_config.html' import render_probe_devices, render_probe_ports %}{{ render_probe_devices(probe_map, modules, alerts) }}"
			return render_template_string(render_string, probe_map=wizardInstallInfo['probe_map'], modules=wizardData['modules']['probes'], alerts=alerts)
		elif r['section'] == 'ports':
			if r['action'] == 'delete_probe':
				for probe_index, probe in enumerate(wizardInstallInfo['probe_map']['probe_info']):
					if probe['label'] == r['label']:
						# Check if probe is being used in a virtual device, and delete it from there. 
						for index, device in enumerate(wizardInstallInfo['probe_map']['probe_devices']):
							if 'virtual' in device['module']:
								if probe['label'] in device['config']['probes_list']: 
									wizardInstallInfo['probe_map']['probe_devices'][index]['config']['probes_list'].remove(probe['label'])
						wizardInstallInfo['probe_map']['probe_info'].pop(probe_index)
						store_wizard_install_info(wizardInstallInfo)
						break

			if r['action'] == 'config':
				defaultLabel = r['label']
				defaultConfig = {
					'name' : '', 
					'device_port' : '',
					'type' : '',
					'profile_id' : '',
					'enabled' : 'true'
				}

				if r['label'] != '':
					for index, probe in enumerate(wizardInstallInfo['probe_map']['probe_info']):
						if probe['label'] == r['label']:
							defaultConfig['name'] = probe['name']
							defaultConfig['device_port'] = f'{probe["device"]}:{probe["port"]}'
							defaultConfig['type'] = probe['type']
							defaultConfig['profile_id'] = probe['profile']['id']
							defaultConfig['enabled'] = 'true' if probe['enabled'] else 'false'
							break
				
				configOptions = wizardData['probe_config_options']

				# Populate Device & Port Options
				for index, device in enumerate(wizardInstallInfo['probe_map']['probe_devices']):
					device_name = device['device']
					for port in device['ports']:
						option_id = f'{device_name}:{port}'
						option_name = f'{device_name} -> {port}'
						configOptions['device_port']['options'][option_id] = option_name 

				# Populate Probe Profiles
				for profile in settings['probe_settings']['probe_profiles']:
					configOptions['profile_id']['options'][profile] = settings['probe_settings']['probe_profiles'][profile]['name']

				render_string = "{% from '_macro_probes_config.html' import render_probe_port_settings %}{{ render_probe_port_settings(defaultLabel, defaultConfig, configOptions) }}"
				return render_template_string(render_string, defaultLabel=defaultLabel, defaultConfig=defaultConfig, configOptions=configOptions)

			if r['action'] == 'add_probe' or r['action'] == 'edit_probe':
				new_probe = {} 
				for key, config_value in r.items():
					if 'probe_config_' in key:
						config_item = key.replace('probe_config_', '')
						new_probe[config_item] = config_value 

				if new_probe['name'] == '':
					errors += 1
					# Error: Probe Name is empty. 
					alert = {
						'message' : 'Probe name is empty.  Please select a probe name.',
						'type' : 'error'
					}
					alerts.append(alert)					

				new_probe['enabled'] = True if new_probe['enabled'] == 'true' else False 
				new_probe['label'] = "".join([x for x in new_probe['name'] if x.isalnum()])
				new_probe['device'] = new_probe['device_port'].split(':')[0]
				new_probe['port'] = new_probe['device_port'].split(':')[1]
				new_probe.pop('device_port')

				for profile in settings['probe_settings']['probe_profiles']:
					if profile == new_probe['profile_id']:
						new_probe['profile'] = settings['probe_settings']['probe_profiles'][profile].copy()
						break 
				new_probe.pop('profile_id') 

				# Look for existing probe with the same name
				found = None
				for index, probe in enumerate(wizardInstallInfo['probe_map']['probe_info']):
					if r['name'] != '' and probe['label'] == r['name']:
						found = index
						break 
					elif probe['label'] == new_probe['label']:
						found = index 
						break 
				
				# Check for primary probe conflict
				if new_probe['type'] == 'Primary': 
					for index, probe in enumerate(wizardInstallInfo['probe_map']['probe_info']):
						if probe['label'] == r['name']:
							pass
						elif probe['type'] == 'Primary':
							# Found a conflict, report error  
							errors += 1
							# Error: Probe Name is empty. 
							alert = {
								'message' : f'There must only be one Primary probe defined. The probe named {probe["name"]} is already set to primary.  Delete or edit that probe to a different type, before setting a new primary probbe.',
								'type' : 'error'
							}
							alerts.append(alert)
							break

				if errors: 
					pass 
				elif found is not None and r['name'] == '':
					# Error Adding New Probe: There is already a probe with the same name
					alert = {
						'message' : 'Probe name is already used or is similar to another probe name.  Please select a different probe name.  Note: Special characters and spaces are removed when checking names.',
						'type' : 'error'
					}
					alerts.append(alert)					
				elif found is not None and r['name'] != '':
					# Check virtual ports and fix up probe labels if they've changed 
					in_virtual_device = []
					for index, device in enumerate(wizardInstallInfo['probe_map']['probe_devices']):
						if 'virtual' in device['module']: 
							if r['name'] in device['config']['probes_list']:
								for item, value in enumerate(wizardInstallInfo['probe_map']['probe_devices'][index]['config']['probes_list']):
									if value == r['name']: 
										wizardInstallInfo['probe_map']['probe_devices'][index]['config']['probes_list'][item] = new_probe['label']
										in_virtual_device.append(device['device']) # 
										break 
					
					# If this is a virtual port, check to make sure this config entry comes after the probe input config entries for this port
					if 'VIRT' in new_probe['port']:
						for index, device in enumerate(wizardInstallInfo['probe_map']['probe_devices']):
							if 'virtual' in device['module'] and new_probe['device'] == device['device']:
								input_probes = device['config']['probes_list']
								for probe in range(len(wizardInstallInfo['probe_map']['probe_info']), 0, -1):
									if wizardInstallInfo['probe_map']['probe_info'][probe]['label'] == new_probe['label']:
										# Found the virtual probe first, current location is OK
										wizardInstallInfo['probe_map']['probe_info'][found] = new_probe
										break 
									elif wizardInstallInfo['probe_map']['probe_info'][probe]['label'] in input_probes:
										# Found one of the input probes first, fix by inserting edited probe config here
										wizardInstallInfo['probe_map']['probe_info'].insert(probe, new_probe)
										# Remove the previous config from the list
										wizardInstallInfo['probe_map']['probe_info'].pop(found)
										break 
								break 

					elif in_virtual_device != []:
						# If this probe is used by a virtual device, make sure its config entry comes before the config entry for the virtual port 
						for index, probe in enumerate(wizardInstallInfo['probe_map']['probe_info']):
							if wizardInstallInfo['probe_map']['probe_info'][index]['label'] == r['name']:
								# Found the probe config for the virtual device, current location is OK 
								wizardInstallInfo['probe_map']['probe_info'][index] = new_probe
								break
							elif wizardInstallInfo['probe_map']['probe_info'][index]['device'] in in_virtual_device:
								# Found this input probes first, fix by inserting edited probe config here
								wizardInstallInfo['probe_map']['probe_info'].insert(index, new_probe)
								# Remove the previous config from the list
								wizardInstallInfo['probe_map']['probe_info'].pop(found+1)
								break 
					else: 
						# Editing probe with new data
						wizardInstallInfo['probe_map']['probe_info'][found] = new_probe
					store_wizard_install_info(wizardInstallInfo)
				elif not found and r['name'] == '':
					# Adding new probe
					wizardInstallInfo['probe_map']['probe_info'].append(new_probe)
					store_wizard_install_info(wizardInstallInfo)
				else:
					# Other Error
					alert = {
						'message' : 'Error Adding/Editing Probe.  Please try again.',
						'type' : 'error'
					}
					alerts.append(alert)	
					
			render_string = "{% from '_macro_probes_config.html' import render_probe_devices, render_probe_ports %}{{ render_probe_ports(probe_map, modules, alerts) }}"
			return render_template_string(render_string, probe_map=wizardInstallInfo['probe_map'], modules=wizardData['modules']['probes'], alerts=alerts)
	else:
		render_string = "Error!"
		return render_template_string(render_string)


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
def check_update(action=None):
	global settings
	update_data = {}
	update_data['version'] = settings['versions']['server']

	avail_updates_struct = get_available_updates()

	if avail_updates_struct['success']:
		commits_behind = avail_updates_struct['commits_behind']
	else:
		event = avail_updates_struct['message']
		write_log(event)
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

	if settings['globals']['venv']:
		python_exec = 'bin/python'
	else:
		python_exec = 'python'

	if request.method == 'GET':
		if action is None:
			update_data = get_update_data(settings)
			return render_template('updater.html', alert=alert, settings=settings,
								   page_theme=settings['globals']['page_theme'],
								   grill_name=settings['globals']['grill_name'],
								   update_data=update_data)
		elif action=='updatestatus':
			percent, status, output = get_updater_install_status()
			return jsonify({'percent' : percent, 'status' : status, 'output' : output})
		
		elif action=='post-message':
			try:
				with open('./updater/post-update-message.html','r') as file:
					post_update_message_html = " ".join(line.rstrip() for line in file)
			except:
				post_update_message_html = 'An error has occurred fetching the post-update message.' 
			return render_template_string(post_update_message_html)

	if request.method == 'POST':
		r = request.form
		update_data = get_update_data(settings)

		if 'update_remote_branches' in r:
			if is_real_hardware():
				os.system(f'{python_exec} %s %s &' % ('updater.py', '-r'))	 # Update branches from remote 
				time.sleep(5)  # Artificial delay to avoid race condition
			return redirect('/update')

		if 'change_branch' in r:
			if update_data['branch_target'] in r['branch_target']:
				alert = {
					'type' : 'success',
					'text' : f'Current branch {update_data["branch_target"]} already set to {r["branch_target"]}'
				}
				return render_template('updater.html', alert=alert, settings=settings,
									   page_theme=settings['globals']['page_theme'], update_data=update_data,
									   grill_name=settings['globals']['grill_name'])
			else:
				set_updater_install_status(0, 'Starting Branch Change...', '')
				os.system(f'{python_exec} updater.py -b {r["branch_target"]} &')	# Kickoff Branch Change
				return render_template('updater-status.html', page_theme=settings['globals']['page_theme'],
									   grill_name=settings['globals']['grill_name'])

		if 'do_update' in r:
			control = read_control()
			if control['mode'] == 'Stop':
				set_updater_install_status(0, 'Starting Update...', '')
				os.system(f'{python_exec} updater.py -u {update_data["branch_target"]} &') # Kickoff Update
				return render_template('updater-status.html', page_theme=settings['globals']['page_theme'],
									grill_name=settings['globals']['grill_name'])
			else:
				alert = {
					'type' : 'error',
					'text' : f'PiFire System Update cannot be completed when the system is active.  Please shutdown/stop your smoker before retrying.'
				}
				update_data = get_update_data(settings)
				return render_template('updater.html', alert=alert, settings=settings,
									page_theme=settings['globals']['page_theme'],
									grill_name=settings['globals']['grill_name'],
									update_data=update_data)


		if 'show_log' in r:
			if r['show_log'].isnumeric():
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
			
			return render_template('updater_out.html', settings=settings, page_theme=settings['globals']['page_theme'],
								   action=action, output_html=output_html, grill_name=settings['globals']['grill_name'])

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
	control = read_control()

	metrics_data = process_metrics(read_metrics(all=True))

	if (request.method == 'GET') and (action == 'export'):
		filename = datetime.datetime.now().strftime('%Y%m%d-%H%M') + '-PiFire-Metrics-Export'
		csvfilename = _prepare_metrics_csv(metrics_data, filename)
		return send_file(csvfilename, as_attachment=True, max_age=0)

	return render_template('metrics.html', settings=settings, control=control, page_theme=settings['globals']['page_theme'], 
							grill_name=settings['globals']['grill_name'], metrics_data=metrics_data)

'''
==============================================================================
 Supporting Functions
==============================================================================
'''

def _create_safe_name(name): 
	return("".join([x for x in name if x.isalnum()]))

def _is_not_blank(response, setting):
	return setting in response and setting != ''

def _is_checked(response, setting):
	return setting in response and response[setting] == 'on'

def _allowed_file(filename):
	return '.' in filename and \
		   filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def _check_cpu_temp():
	temp = os.popen('vcgencmd measure_temp').readline()
	return temp.replace("temp=","")

def create_ui_hash():
	global settings 
	return hash(json.dumps(settings['probe_settings']['probe_map']['probe_info']))

def _prepare_annotations(displayed_starttime, metrics_data=[]):
	if(metrics_data == []):
		metrics_data = read_metrics(all=True)
	annotation_json = {}
	# Process Additional Metrics Information for Display
	for index in range(0, len(metrics_data)):
		# Check if metric falls in the displayed time window
		if metrics_data[index]['starttime'] > displayed_starttime:
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

def _prepare_metrics_csv(metrics_data, filename):
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

def _prepare_event_totals(events):
	auger_time = 0
	for index in range(0, len(events)):
		auger_time += events[index]['augerontime']
	auger_time = int(auger_time)

	event_totals = {}
	event_totals['augerontime'] = seconds_to_string(auger_time)

	grams = int(auger_time * settings['globals']['augerrate'])
	pounds = round(grams * 0.00220462, 2)
	ounces = round(grams * 0.03527392, 2)
	event_totals['estusage_m'] = f'{grams} grams'
	event_totals['estusage_i'] = f'{pounds} pounds ({ounces} ounces)'

	seconds = int((events[-1]['starttime']/1000) - (events[0]['starttime']/1000))
	
	event_totals['cooktime'] = seconds_to_string(seconds)

	event_totals['pellet_level_start'] = events[0]['pellet_level_start']
	event_totals['pellet_level_end'] = events[-2]['pellet_level_end']

	return(event_totals)

def _paginate_list(datalist, sortkey='', reversesortorder=False, itemsperpage=10, page=1):
	if sortkey != '':
		#  Sort list if key is specified
		tempdatalist = sorted(datalist, key=lambda d: d[sortkey], reverse=reversesortorder)
	else:
		#  If no key, reverse list if specified, or keep order 
		if reversesortorder:
			datalist.reverse()
		tempdatalist = datalist.copy()
	listlength = len(tempdatalist)
	if listlength <= itemsperpage:
		curpage = 1
		prevpage = 1 
		nextpage = 1 
		lastpage = 1
		displaydata = tempdatalist.copy()
	else: 
		lastpage = (listlength // itemsperpage) + ((listlength % itemsperpage) > 0)
		if (lastpage < page):
			curpage = lastpage
			prevpage = curpage - 1 if curpage > 1 else 1
			nextpage = curpage + 1 if curpage < lastpage else lastpage 
		else: 
			curpage = page if page > 0 else 1
			prevpage = curpage - 1 if curpage > 1 else 1
			nextpage = curpage + 1 if curpage < lastpage else lastpage 
		#  Calculate starting / ending position and create list with that data
		start = itemsperpage * (curpage - 1)  # Get starting position 
		end = start + itemsperpage # Get ending position 
		displaydata = tempdatalist.copy()[start:end]

	reverse = 'true' if reversesortorder else 'false'

	pagination = {
		'displaydata' : displaydata,
		'curpage' : curpage,
		'prevpage' : prevpage,
		'nextpage' : nextpage, 
		'lastpage' : lastpage,
		'reverse' : reverse,
		'itemspage' : itemsperpage
	}

	return (pagination)

def _get_cookfilelist(folder=HISTORY_FOLDER):
	# Grab list of Historical Cook Files
	if not os.path.exists(folder):
		os.mkdir(folder)
	dirfiles = os.listdir(folder)
	cookfiles = []
	for file in dirfiles:
		if file.endswith('.pifire'):
			cookfiles.append(file)
	return(cookfiles)

def _get_cookfilelist_details(cookfilelist):
	cookfiledetails = []
	for item in cookfilelist:
		filename = HISTORY_FOLDER + item['filename']
		cookfiledata, status = read_json_file_data(filename, 'metadata')
		if(status == 'OK'):
			thumbnail = unpack_thumb(cookfiledata['thumbnail'], filename) if ('thumbnail' in cookfiledata) else ''
			cookfiledetails.append({'filename' : item['filename'], 'title' : cookfiledata['title'], 'thumbnail' : thumbnail})
		else:
			cookfiledetails.append({'filename' : item['filename'], 'title' : 'ERROR', 'thumbnail' : ''})
	return(cookfiledetails)

def _get_recipefilelist(folder=RECIPE_FOLDER):
	# Grab list of Recipe Files
	if not os.path.exists(folder):
		os.mkdir(folder)
	dirfiles = os.listdir(folder)
	recipefiles = []
	for file in dirfiles:
		if file.endswith('.pfrecipe'):
			recipefiles.append(file)
	return(recipefiles)

def _get_recipefilelist_details(recipefilelist):
	recipefiledetails = []
	for item in recipefilelist:
		filename = RECIPE_FOLDER + item['filename']
		recipefiledata, status = read_json_file_data(filename, 'metadata')
		if(status == 'OK'):
			thumbnail = unpack_thumb(recipefiledata['thumbnail'], filename) if ('thumbnail' in recipefiledata) else ''
			recipefiledetails.append({'filename' : item['filename'], 'title' : recipefiledata['title'], 'thumbnail' : thumbnail})
		else:
			recipefiledetails.append({'filename' : item['filename'], 'title' : 'ERROR', 'thumbnail' : ''})
	return(recipefiledetails)

def _calc_shh_coefficients(t1, t2, t3, r1, r2, r3, units='F'):
	try: 
		if units=='F':
			# Convert Temps from Fahrenheit to Kelvin
			t1 = ((t1 - 32) * (5 / 9)) + 273.15
			t2 = ((t2 - 32) * (5 / 9)) + 273.15
			t3 = ((t3 - 32) * (5 / 9)) + 273.15
		else:
			# Convert Temps from Celsius to Kelvin
			t1 = t1 + 273.15
			t2 = t2 + 273.15
			t3 = t3 + 273.15

		# https://en.wikipedia.org/wiki/Steinhart%E2%80%93Hart_equation

		# Step 1: L1 = ln (R1), L2 = ln (R2), L3 = ln (R3)
		l1 = math.log(r1)
		l2 = math.log(r2)
		l3 = math.log(r3)

		# Step 2: Y1 = 1 / T1, Y2 = 1 / T2, Y3 = 1 / T3
		y1 = 1 / t1
		y2 = 1 / t2
		y3 = 1 / t3

		# Step 3: G2 = (Y2 - Y1) / (L2 - L1) , G3 = (Y3 - Y1) / (L3 - L1)
		g2 = (y2 - y1) / (l2 - l1)
		g3 = (y3 - y1) / (l3 - l1)

		# Step 4: C = ((G3 - G2) / (L3 - L2)) * (L1 + L2 + L3)^-1
		c = ((g3 - g2) / (l3 - l2)) * math.pow(l1 + l2 + l3, -1)

		# Step 5: B = G2 - C * (L1^2 + (L1*L2) + L2^2)
		b = g2 - c * (math.pow(l1, 2) + (l1 * l2) + math.pow(l2, 2))

		# Step 6: A = Y1 - (B + L1^2*C) * L1
		a = y1 - ((b + (math.pow(l1, 2) * c)) * l1)
	except:
		a = 0
		b = 0
		c = 0

	return(a, b, c)

def _temp_to_tr(temp, a, b, c, units='F'):
	'''
	# Not recommended for use, as it commonly produces a complex number
	'''

	try: 
		if units == 'F':
			temp_k = ((temp - 32) * (5 / 9)) + 273.15
		else:
			temp_k = temp + 273.15

		# https://en.wikipedia.org/wiki/Steinhart%E2%80%93Hart_equation
		# Inverse of the equation, to determine Tr = Resistance Value of the thermistor

		x = (a - (1 / temp_k)) / c
		y1 = math.pow((b/(3*c)), 3) 
		y2 = ((x*x)/4)
		y = math.sqrt(y1+y2)  # If the result of y1 + y2 is negative, this will throw an exception
		Tr = math.exp(math.pow(y - (x/2), (1/3)) - math.pow(y + (x/2), (1/3)))
	except: 
		Tr = 0

	return int(Tr)

def _tr_to_temp(tr, a, b, c, units='F'):
	try:
		#Steinhart Hart Equation
		# 1/T = A + B(ln(R)) + C(ln(R))^3
		# T = 1/(a + b[ln(ohm)] + c[ln(ohm)]^3)
		ln_ohm = math.log(tr) # ln(ohms)
		t1 = (b * ln_ohm) # b[ln(ohm)]
		t2 = c * math.pow(ln_ohm, 3) # c[ln(ohm)]^3
		temp_k = 1/(a + t1 + t2) # calculate temperature in Kelvin
		temp_c = temp_k - 273.15 # Kelvin to Celsius
		temp_f = temp_c * (9 / 5) + 32 # Celsius to Fahrenheit
	except:
		temp_c = 0.0
		temp_f = 0
	if units == 'F': 
		return int(temp_f) # Return Calculated Temperature and Thermistor Value in Ohms
	else:
		return temp_c

def _calc_shh_chart(a, b, c, units='F', temp_range=220, tr_points=[]):
	'''
	Based on SHH Coefficients determined during tuning, show Temp (x) vs. Tr (y) chart
	'''

	labels = []

	for label in range(0, temp_range, temp_range//20):
		labels.append(label)

	chart_data = []

	for T in labels:
		R = _temp_to_tr(T, a, b, c, units=units)
		if R != 0:
			chart_data.append({'x': int(T), 'y': int(R)})
		else:
			# Error/Exception occurred calculating the temperature, break and return
			chart_data = []
			break

	return labels, chart_data

def _str_td(td):
	s = str(td).split(", ", 1)
	a = s[-1]
	if a[1] == ':':
		a = "0" + a
	s2 = s[:-1] + [a]
	return ", ".join(s2)

def _zip_files_dir(dir_name):
	memory_file = BytesIO()
	with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
		for root, dirs, files in os.walk(dir_name):
			for file in files:
				zipf.write(os.path.join(root, file))
	memory_file.seek(0)
	return memory_file

def _zip_files_logs(dir_name):
	time_now = datetime.datetime.now()
	time_str = time_now.strftime('%m-%d-%y_%H%M%S') # Truncate the microseconds
	file_name = f'/tmp/PiFire_Logs_{time_str}.zip'
	directory = pathlib.Path(f'{dir_name}')
	with zipfile.ZipFile(file_name, "w", zipfile.ZIP_DEFLATED) as archive:
		for file_path in directory.rglob("*"):
			archive.write(file_path, arcname=file_path.relative_to(directory))
	return file_name

'''
==============================================================================
 SocketIO Section
==============================================================================
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
		control = read_control()
		pelletdb = read_pellet_db()
		probe_info = read_current()

		if control['timer']['end'] - time.time() > 0 or bool(control['timer']['paused']):
			timer_info = {
				'timer_paused' : bool(control['timer']['paused']),
				'timer_start_time' : math.trunc(control['timer']['start']),
				'timer_end_time' : math.trunc(control['timer']['end']),
				'timer_paused_time' : math.trunc(control['timer']['paused']),
				'timer_active' : 'true'
			}
		else:
			timer_info = {
				'timer_paused' : 'false',
				'timer_start_time' : '0',
				'timer_end_time' : '0',
				'timer_paused_time' : '0',
				'timer_active' : 'false'
			}

		current_data = {
			'probe_info' : probe_info,
			'notify_data' : control['notify_data'],
			'timer_info' : timer_info,
			'current_mode' : control['mode'],
			'smoke_plus' : control['s_plus'],
			'pwm_control' : control['pwm_control'],
			'hopper_level' : pelletdb['current']['hopper_level']
		}

		if force_refresh:
			socketio.emit('grill_control_data', current_data)
			force_refresh = False
			socketio.sleep(2)
		elif previous_data != current_data:
			socketio.emit('grill_control_data', current_data)
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
		return read_pellet_db()

	elif action == 'events_data':
		event_list, num_events = read_events()
		events_trim = []
		for x in range(min(num_events, 60)):
			events_trim.append(event_list[x])
		return { 'events_list' : events_trim }

	elif action == 'info_data':
		return {
			'uptime' : os.popen('uptime').readline(),
			'cpuinfo' : os.popen('cat /proc/cpuinfo').readlines(),
			'ifconfig' : os.popen('ifconfig').readlines(),
			'temp' : _check_cpu_temp(),
			'outpins' : settings['outpins'],
			'inpins' : settings['inpins'],
			'dev_pins' : settings['dev_pins'],
			'server_version' : settings['versions']['server'],
			'server_build' : settings['versions']['build'] }

	elif action == 'manual_data':
		control = read_control()
		return {
			'manual' : control['manual'],
			'mode' : control['mode'] }
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
					settings = deep_update(settings, request)
					write_settings(settings)
					return {'response': {'result':'success'}}
				else:
					return {'response': {'result':'error', 'message':'Error: Key not found in settings'}}
		elif type == 'control':
			control = read_control()
			for key in request.keys():
				if key in control.keys():
					'''
						Updating of control input data is now done in common.py > execute_commands() 
					'''
					write_control(request, origin='app-socketio')
					return {'response': {'result':'success'}}
				else:
					return {'response': {'result':'error', 'message':'Error: Key not found in control'}}
		else:
			return {'response': {'result':'error', 'message':'Error: Received request without valid type'}}

	elif action == 'admin_action':
		if type == 'clear_history':
			write_log('Clearing History Log.')
			read_history(0, flushhistory=True)
			return {'response': {'result':'success'}}
		elif type == 'clear_events':
			write_log('Clearing Events Log.')
			os.system('rm /tmp/events.log')
			return {'response': {'result':'success'}}
		elif type == 'clear_pelletdb':
			write_log('Clearing Pellet Database.')
			os.system('rm pelletdb.json')
			return {'response': {'result':'success'}}
		elif type == 'clear_pelletdb_log':
			pelletdb = read_pellet_db()
			pelletdb['log'].clear()
			write_pellet_db(pelletdb)
			write_log('Clearing Pellet Database Log.')
			return {'response': {'result':'success'}}
		elif type == 'factory_defaults':
			read_history(0, flushhistory=True)
			read_control(flush=True)
			os.system('rm settings.json')
			settings = default_settings()
			control = default_control()
			write_settings(settings)
			write_control(control, origin='app-socketio')
			write_log('Resetting Settings, Control, History to factory defaults.')
			return {'response': {'result':'success'}}
		elif type == 'reboot':
			write_log("Admin: Reboot")
			os.system("sleep 3 && sudo reboot &")
			return {'response': {'result':'success'}}
		elif type == 'shutdown':
			write_log("Admin: Shutdown")
			os.system("sleep 3 && sudo shutdown -h now &")
			return {'response': {'result':'success'}}
		elif type == 'restart':
			write_log("Admin: Restart Server")
			restart_scripts()
			return {'response': {'result':'success'}}
		else:
			return {'response': {'result':'error', 'message':'Error: Received request without valid type'}}

	elif action == 'units_action':
		if type == 'f_units' and settings['globals']['units'] == 'C':
			settings = convert_settings_units('F', settings)
			write_settings(settings)
			control = read_control()
			control['updated'] = True
			control['units_change'] = True
			write_control(control, origin='app-socketio')
			write_log("Changed units to Fahrenheit")
			return {'response': {'result':'success'}}
		elif type == 'c_units' and settings['globals']['units'] == 'F':
			settings = convert_settings_units('C', settings)
			write_settings(settings)
			control = read_control()
			control['updated'] = True
			control['units_change'] = True
			write_control(control, origin='app-socketio')
			write_log("Changed units to Celsius")
			return {'response': {'result':'success'}}
		else:
			return {'response': {'result':'error', 'message':'Error: Units could not be changed'}}

	elif action == 'remove_action':
		if type == 'onesignal_device':
			if 'onesignal_player_id' in request['onesignal_device']:
				device = request['onesignal_device']['onesignal_player_id']
				if device in settings['onesignal']['devices']:
					settings['onesignal']['devices'].pop(device)
				write_settings(settings)
				return {'response': {'result':'success'}}
			else:
				return {'response': {'result':'error', 'message':'Error: Device not specified'}}
		else:
			return {'response': {'result':'error', 'message':'Error: Remove type not found'}}

	elif action == 'pellets_action':
		pelletdb = read_pellet_db()
		if type == 'load_profile':
			if 'profile' in request['pellets_action']:
				pelletdb['current']['pelletid'] = request['pellets_action']['profile']
				now = str(datetime.datetime.now())
				now = now[0:19]
				pelletdb['current']['date_loaded'] = now
				pelletdb['current']['est_usage'] = 0
				pelletdb['log'][now] = request['pellets_action']['profile']
				control = read_control()
				control['hopper_check'] = True
				write_control(control, origin='app-socketio')
				write_pellet_db(pelletdb)
				return {'response': {'result':'success'}}
			else:
				return {'response': {'result':'error', 'message':'Error: Profile not included in request'}}
		elif type == 'hopper_check':
			control = read_control()
			control['hopper_check'] = True
			write_control(control, origin='app-socketio')
			return {'response': {'result':'success'}}
		elif type == 'edit_brands':
			if 'delete_brand' in request['pellets_action']:
				delBrand = request['pellets_action']['delete_brand']
				if delBrand in pelletdb['brands']:
					pelletdb['brands'].remove(delBrand)
				write_pellet_db(pelletdb)
				return {'response': {'result':'success'}}
			elif 'new_brand' in request['pellets_action']:
				newBrand = request['pellets_action']['new_brand']
				if newBrand not in pelletdb['brands']:
					pelletdb['brands'].append(newBrand)
				write_pellet_db(pelletdb)
				return {'response': {'result':'success'}}
			else:
				return {'response': {'result':'error', 'message':'Error: Function not specified'}}
		elif type == 'edit_woods':
			if 'delete_wood' in request['pellets_action']:
				delWood = request['pellets_action']['delete_wood']
				if delWood in pelletdb['woods']:
					pelletdb['woods'].remove(delWood)
				write_pellet_db(pelletdb)
				return {'response': {'result':'success'}}
			elif 'new_wood' in request['pellets_action']:
				newWood = request['pellets_action']['new_wood']
				if newWood not in pelletdb['woods']:
					pelletdb['woods'].append(newWood)
				write_pellet_db(pelletdb)
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
				control = read_control()
				control['hopper_check'] = True
				write_control(control, origin='app-socketio')
				now = str(datetime.datetime.now())
				now = now[0:19]
				pelletdb['current']['date_loaded'] = now
				pelletdb['current']['est_usage'] = 0
				pelletdb['log'][now] = profile_id
				write_pellet_db(pelletdb)
				return {'response': {'result':'success'}}
			else:
				write_pellet_db(pelletdb)
				return {'response': {'result':'success'}}
		if type == 'edit_profile':
			if 'profile' in request['pellets_action']:
				profile_id = request['pellets_action']['profile']
				pelletdb['archive'][profile_id]['brand'] = request['pellets_action']['brand_name']
				pelletdb['archive'][profile_id]['wood'] = request['pellets_action']['wood_type']
				pelletdb['archive'][profile_id]['rating'] = request['pellets_action']['rating']
				pelletdb['archive'][profile_id]['comments'] = request['pellets_action']['comments']
				write_pellet_db(pelletdb)
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
				write_pellet_db(pelletdb)
				return {'response': {'result':'success'}}
			else:
				return {'response': {'result':'error', 'message':'Error: Profile not included in request'}}
		elif type == 'delete_log':
			if 'log_item' in request['pellets_action']:
				delLog = request['pellets_action']['log_item']
				if delLog in pelletdb['log']:
					pelletdb['log'].pop(delLog)
				write_pellet_db(pelletdb)
				return {'response': {'result':'success'}}
			else:
				return {'response': {'result':'error', 'message':'Error: Function not specified'}}
		else:
			return {'response': {'result':'error', 'message':'Error: Received request without valid type'}}

	elif action == 'timer_action':
		control = read_control()
		for index, notify_obj in enumerate(control['notify_data']):
			if notify_obj['type'] == 'timer':
				break
		if type == 'start_timer':
			control['notify_data'][index]['req'] = True
			if control['timer']['paused'] == 0:
				now = time.time()
				control['timer']['start'] = now
				if 'hours_range' in request['timer_action'] and 'minutes_range' in request['timer_action']:
					seconds = request['timer_action']['hours_range'] * 60 * 60
					seconds = seconds + request['timer_action']['minutes_range'] * 60
					control['timer']['end'] = now + seconds
					control['notify_data'][index]['shutdown'] = request['timer_action']['timer_shutdown']
					control['notify_data'][index]['keep_warm'] = request['timer_action']['timer_keep_warm']
					write_log('Timer started.  Ends at: ' + epoch_to_time(control['timer']['end']))
					write_control(control, origin='app-socketio')
					return {'response': {'result':'success'}}
				else:
					return {'response': {'result':'error', 'message':'Error: Start time not specified'}}
			else:
				now = time.time()
				control['timer']['end'] = (control['timer']['end'] - control['timer']['paused']) + now
				control['timer']['paused'] = 0
				write_log('Timer unpaused.  Ends at: ' + epoch_to_time(control['timer']['end']))
				write_control(control, origin='app-socketio')
				return {'response': {'result':'success'}}
		elif type == 'pause_timer':
			control['notify_data'][index]['req'] = False
			now = time.time()
			control['timer']['paused'] = now
			write_log('Timer paused.')
			write_control(control, origin='app-socketio')
			return {'response': {'result':'success'}}
		elif type == 'stop_timer':
			control['notify_data'][index]['req'] = False
			control['timer']['start'] = 0
			control['timer']['end'] = 0
			control['timer']['paused'] = 0
			control['notify_data'][index]['shutdown'] = False
			control['notify_data'][index]['keep_warm'] = False
			write_log('Timer stopped.')
			write_control(control, origin='app-socketio')
			return {'response': {'result':'success'}}
		else:
			return {'response': {'result':'error', 'message':'Error: Received request without valid type'}}
	else:
		return {'response': {'result':'error', 'message':'Error: Received request without valid action'}}

'''
==============================================================================
 Main Program Start
==============================================================================
'''
settings = read_settings(init=True)

if __name__ == '__main__':
	if is_real_hardware():
		socketio.run(app, host='0.0.0.0')
	else:
		socketio.run(app, host='0.0.0.0', debug=True)
