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

from flask import Flask, request, render_template, send_file, jsonify, redirect, render_template_string
from flask_mobility import Mobility
from flask_socketio import SocketIO
from flask_qrcode import QRcode
from werkzeug.utils import secure_filename
from werkzeug.exceptions import InternalServerError
import threading

from threading import Thread
from datetime import datetime
from updater import *  # Library for doing project updates from GitHub
from file_mgmt.common import read_json_file_data, update_json_file_data, remove_assets
from file_mgmt.media import add_asset, unpack_thumb
from file_mgmt.recipes import read_recipefile, create_recipefile
from common.app import allowed_file, get_supported_cmds, get_system_command_output

''' Flask Blueprints '''
from blueprints.admin import admin_bp
from blueprints.api import api_bp
from blueprints.events import events_bp
from blueprints.logs import logs_bp
from blueprints.manifest import manifest_bp
from blueprints.manual import manual_bp
from blueprints.history import history_bp
from blueprints.metrics import metrics_bp
from blueprints.dash import dash_bp
from blueprints.pellets import pellets_bp
from blueprints.cookfile import cookfile_bp
from blueprints.tuner import tuner_bp

'''
==============================================================================
 Constants & Globals 
==============================================================================
'''
from config import ProductionConfig  # ProductionConfig or DevelopmentConfig

BACKUP_PATH = './backups/'  # Path to backups of settings.json, pelletdb.json
UPLOAD_FOLDER = BACKUP_PATH  # Point uploads to the backup path
HISTORY_FOLDER = './history/'  # Path to historical cook files
RECIPE_FOLDER = './recipes/'  # Path to recipe files 
LOGS_FOLDER = './logs/'  # Path to log files 
ALLOWED_EXTENSIONS = {'json', 'pifire', 'pfrecipe', 'jpg', 'jpeg', 'png', 'gif', 'bmp', 'log'}

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
QRcode(app)
Mobility(app)

app.config.from_object(ProductionConfig)

''' Register Flask Blueprints '''
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(events_bp, url_prefix='/events')
app.register_blueprint(logs_bp, url_prefix='/logs')
app.register_blueprint(manifest_bp, url_prefix='/manifest')
app.register_blueprint(manual_bp, url_prefix='/manual')
app.register_blueprint(history_bp, url_prefix='/history')
app.register_blueprint(metrics_bp, url_prefix='/metrics')
app.register_blueprint(dash_bp, url_prefix='/dash')
app.register_blueprint(pellets_bp, url_prefix='/pellets')
app.register_blueprint(cookfile_bp, url_prefix='/cookfile')
app.register_blueprint(tuner_bp, url_prefix='/tuner')

'''
==============================================================================
 App Routes
==============================================================================
'''

@app.errorhandler(InternalServerError)
def handle_500(e):
	''' Handle 500 Server Error '''
	return render_template('server_error.html'), 500

@app.route('/')
def index():
	global settings
	
	if settings['globals']['first_time_setup']:
		return redirect('/wizard/welcome')
	else: 
		return redirect('/dash')

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
				if remote_file and allowed_file(remote_file.filename):
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

					if remotefile and allowed_file(remotefile.filename):
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

	if request.method == 'POST' and action == 'probe_select':
		response = request.form

		if response['selected'] == '':
			selected = settings['probe_settings']['probe_map']['probe_info'][0]['label']
			probe_info = settings['probe_settings']['probe_map']['probe_info']
		else:
			selected = response['selected']
			probe_info = settings['probe_settings']['probe_map']['probe_info']

		render_string = "{% from '/settings/_macro_probes.html' import render_probe_select %}{{ render_probe_select(selected, probe_info, settings) }}"
		return render_template_string(render_string, selected=selected, probe_info=probe_info, settings=settings)

	if request.method == 'POST' and action == 'probe_config':
		response = request.form
		probe_info = None

		if request.form['selected'] == '':
			selected = settings['probe_settings']['probe_map']['probe_info'][0]['label']
			probe_info = settings['probe_settings']['probe_map']['probe_info'][0]
		else:
			selected = request.form['selected']
			for probe in settings['probe_settings']['probe_map']['probe_info']:
				if probe['label'] == selected:
					probe_info = probe
					break 

		if probe_info == None:
			probe_info = settings['probe_settings']['probe_map']['probe_info'][0]

		render_string = "{% from '/settings/_macro_probes.html' import render_probe_config %}{{ render_probe_config(probe_info, settings) }}"
		return render_template_string(render_string, probe_info=probe_info, settings=settings)

	if request.method == 'POST' and action == 'probe_config_save':
		probe_config = request.json
		label = probe_config.get('label', '')
		probe_edited = {}

		for index, probe in enumerate(settings['probe_settings']['probe_map']['probe_info']):
			if probe['label'] == label:
				probe_edited['label'] = probe['label']
				probe_edited['name'] = probe_config.get('name', settings['probe_settings']['probe_map']['probe_info'][index]['name'])
				probe_edited['type'] = probe_config.get('type', settings['probe_settings']['probe_map']['probe_info'][index]['type'])
				probe_edited['port'] = probe_config.get('port', settings['probe_settings']['probe_map']['probe_info'][index]['port'])
				probe_edited['device'] = probe_config.get('device', settings['probe_settings']['probe_map']['probe_info'][index]['device'])
				probe_edited['enabled'] = True if probe_config.get('enabled', False) == 'true' else False
				profile_id = probe_config.get('profile_id', settings['probe_settings']['probe_map']['probe_info'][index]['profile']['id'])
				if profile_id != probe['profile']['id']:
					probe_edited['profile'] = settings['probe_settings']['probe_profiles'].get(profile_id, settings['probe_settings']['probe_map']['probe_info'][index]['profile'])
				else:
					probe_edited['profile'] = settings['probe_settings']['probe_map']['probe_info'][index]['profile']
				break

		if probe_edited:
			settings['probe_settings']['probe_map']['probe_info'][index] = probe_edited
			settings['history_page']['probe_config'][label]['name'] = probe_edited['name']
			control['probe_profile_update'] = True
			# Take all settings and write them
			write_settings(settings)
			write_control(control, origin='app')

			return jsonify({'result' : 'success'})
		else:
			return jsonify({'result' : 'label_not_found'})

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
			control['controller_update'] = True
			print(f'Controller Settings: {settings["controller"]["config"]}')
 
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
		if _is_checked(response, 'allow_manual_changes'):
			settings['safety']['allow_manual_changes'] = True
		else:
			settings['safety']['allow_manual_changes'] = False
		if _is_not_blank(response, 'manual_override_time'):
			settings['safety']['manual_override_time'] = int(response['manual_override_time'])

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

	python_exec = settings['globals'].get('python_exec', 'python')

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
				moduleSettings = {}
				moduleSettings['settings'] = get_settings_dependencies_values(settings, moduleData)
				moduleSettings['config'] = {} if section != 'display' else settings['display']['config'][module]
				render_string = "{% from '_macro_wizard_card.html' import render_wizard_card %}{{ render_wizard_card(moduleData, moduleSection, moduleSettings) }}"
				return render_template_string(render_string, moduleData=moduleData, moduleSection=section, moduleSettings=moduleSettings)
			else:
				return '<strong color="red">No Data</strong>'

		if action=='bt_scan':
			itemID=r['itemID']
			bt_data = []
			error = None

			try: 
				supported_cmds = get_supported_cmds()

				if 'scan_bluetooth' in supported_cmds:
					process_command(action='sys', arglist=['scan_bluetooth'], origin='admin')  # Request supported commands 
					data = get_system_command_output(requested='scan_bluetooth', timeout=6)
					#print('[DEBUG] BT Scan Data:', data)
					if data['result'] != 'OK':
						error = data['message']
					else:
						bt_data = parse_bt_device_info(data['data']['bt_devices'])
						if bt_data == []:
							error = 'No bluetooth devices found.'
				else:
					error = 'No support for bluetooth scan command.'

			except Exception as e: 
				error = f'Something bad happened: {e}'
				#print(f'[DEBUG] {error}')

			render_string = "{% from '_macro_probes_config.html' import render_bt_scan_table %}{{ render_bt_scan_table(itemID, bt_data, error) }}"
			return render_template_string(render_string, itemID=itemID, bt_data=bt_data, error=error)

	''' Create Temporary Probe Device/Port Structure for Setup, Use Existing unless First Time Setup '''
	if settings['globals']['first_time_setup']: 
		wizardInstallInfo = wizardInstallInfoDefaults(wizardData, settings)
	else:
		wizardInstallInfo = wizardInstallInfoExisting(wizardData, settings)

	store_wizard_install_info(wizardInstallInfo)

	if control['mode'] != 'Stop':
		errors.append('PiFire configuration wizard cannot be run while the system is active.  Please stop the current cook before continuing.')

	return render_template('wizard.html', settings=settings, page_theme=settings['globals']['page_theme'],
						   grill_name=settings['globals']['grill_name'], wizardData=wizardData, wizardInstallInfo=wizardInstallInfo, control=control, errors=errors)

def parse_bt_device_info(bt_devices):
	global settings 
	# Check if this hardware id is already in use
	for index, peripheral in enumerate(bt_devices):
		for device in settings['probe_settings']['probe_map']['probe_devices']:
			#print(f'[DEBUG] Comparing {device["name"]} ({device["config"].get('hardware_id', None)}) to {name} ({hw_id})')
			if device['config'].get('hardware_id', None) == peripheral['hw_id']:
				bt_devices[index]['info'] += f'This hardware ID is already in use by {device["device"]}'
				return bt_devices
	return bt_devices

	return {'name':name, 'hw_id':hw_id, 'info':info}

def get_settings_dependencies_values(settings, moduleData):
	moduleSettings = {}
	for setting, data in moduleData['settings_dependencies'].items():
		setting_location = data['settings']
		setting_value = settings
		for setting_name in setting_location:
			setting_value = setting_value[setting_name]
		moduleSettings[setting] = setting_value 
	return moduleSettings 

def wizardInstallInfoDefaults(wizardData, settings):
	
	wizardInstallInfo = {
		'modules' : {
			'grillplatform' : {
				'profile_selected' : [],  # Reference the profile in wizardData > wizard_manifest.json
				'settings' : {},
				'config' : {}
			}, 
			'display' : {
				'profile_selected' : [],
				'settings' : {},
				'config' : {}
			}, 
			'distance' : {
				'profile_selected' : [],
				'settings' : {},
				'config' : {}
			}, 
			'probes' : {
				'profile_selected' : [],
				'settings' : {
					'units' : 'F'
				},
				'config' : {}
			}
		},
		'probe_map' : {}
	}
	''' Populate Modules Info with Defaults from Wizard Data including Settings '''
	for component in ['grillplatform', 'display', 'distance']:
		for module in wizardData['modules'][component]:
			if wizardData['modules'][component][module]['default']:
				''' Populate Module Filename'''
				wizardInstallInfo['modules'][component]['profile_selected'].append(module) #TODO: Change wizard.py to reference the module filename instead, or in grill_platform use platform>system_type
				for setting in wizardData['modules'][component][module]['settings_dependencies']: 
					''' Populate all settings with default value '''
					wizardInstallInfo['modules'][component]['settings'][setting] = list(wizardData['modules'][component][module]['settings_dependencies'][setting]['options'].keys())[0]
				if module == 'display':
					wizardInstallInfo['modules'][component]['config'] = settings['display']['config'][module]

	''' Populate the default probe device / probe map from the default PCB Board '''
	wizardInstallInfo['probe_map'] = wizardData['boards'][wizardInstallInfo['modules']['grillplatform']['profile_selected'][0]]['probe_map']

	''' Populate Probes Module List with all configured probe devices '''
	for device in wizardInstallInfo['probe_map']['probe_devices']:
		wizardInstallInfo['modules']['probes']['profile_selected'].append(device['module'])

	return wizardInstallInfo

def wizardInstallInfoExisting(wizardData, settings):
	wizardInstallInfo = {
		'modules' : {
			'grillplatform' : {
				'profile_selected' : [settings['platform']['current']],
				'settings' : {},
				'config' : {}
			}, 
			'display' : {
				'profile_selected' : [settings['modules']['display']],
				'settings' : {},
				'config' : {}
			}, 
			'distance' : {
				'profile_selected' : [settings['modules']['dist']],
				'settings' : {},
				'config' : {}
			}, 
			'probes' : {
				'profile_selected' : [],
				'settings' : {
					'units' : settings['globals']['units']
				},
				'config' : {}
			}
		}, 
		'probe_map' : settings['probe_settings']['probe_map']
	} 
	''' Populate Probes Module List with all configured probe devices '''
	for device in wizardInstallInfo['probe_map']['probe_devices']:
		wizardInstallInfo['modules']['probes']['profile_selected'].append(device['module'])
	
	''' Populate Modules Info with current Settings '''
	for module in ['grillplatform', 'display', 'distance']:
		selected = wizardInstallInfo['modules'][module]['profile_selected'][0]
		''' Error condition if the item in settings doesn't match the wizard manifest '''
		if selected not in wizardData['modules'][module].keys():
			if module == 'grillplatform':
				selected = 'custom'
				settings['platform']['current'] = selected
			else:
				selected = 'none'
			wizardInstallInfo['modules'][module]['profile_selected'] = selected

		for setting in wizardData['modules'][module][selected]['settings_dependencies']:
			settingsLocation = wizardData['modules'][module][selected]['settings_dependencies'][setting]['settings']
			settingsValue = settings.copy() 
			for index in range(0, len(settingsLocation)):
				settingsValue = settingsValue[settingsLocation[index]]
			wizardInstallInfo['modules'][module]['settings'][setting] = str(settingsValue)
		if module == 'display':
			wizardInstallInfo['modules'][module]['config'] = settings['display']['config'][settings['modules']['display']]
	return wizardInstallInfo

def prepare_wizard_data(form_data):
	wizardData = read_wizard()
	
	wizardInstallInfo = load_wizard_install_info()

	wizardInstallInfo['modules'] = {
		'grillplatform' : {
			'profile_selected' : [form_data['grillplatformSelect']],
			'settings' : {},
			'config' : {}
		}, 
		'display' : {
			'profile_selected' : [form_data['displaySelect']],
			'settings' : {},
			'config' : {}
		}, 
		'distance' : {
			'profile_selected' : [form_data['distanceSelect']],
			'settings' : {},
			'config' : {}
		}, 
		'probes' : {
			'profile_selected' : [],
			'settings' : {
				'units' : form_data['probes_units']
			},
			'config' : {}
		}
	}

	for device in wizardInstallInfo['probe_map']['probe_devices']:
		wizardInstallInfo['modules']['probes']['profile_selected'].append(device['module'])

	for module in ['grillplatform', 'display', 'distance']:
		module_ = module + '_'
		moduleSelect = module + 'Select'
		selected = form_data[moduleSelect]
		for setting in wizardData['modules'][module][selected]['settings_dependencies']:
			settingName = module_ + setting
			if(settingName in form_data):
				wizardInstallInfo['modules'][module]['settings'][setting] = form_data[settingName]
		for config, value in form_data.items():
			if config.startswith(module_ + 'config_'):
				wizardInstallInfo['modules'][module]['config'][config.replace(module_ + 'config_', '')] = value

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

	python_exec = settings['globals'].get('python_exec', 'python')

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
				os.system(f'{python_exec} updater.py -r &')	 # Update branches from remote 
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
				os.system(f'{python_exec} updater.py -u {update_data["branch_target"]} -p &') # Kickoff Update
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

		if 'do_upgrade' in r:
			control = read_control()
			if control['mode'] == 'Stop':
				set_updater_install_status(0, 'Starting Upgrade...', '')
				os.system(f'{python_exec} updater.py -i &')
				return render_template('updater-status.html', page_theme=settings['globals']['page_theme'],
									grill_name=settings['globals']['grill_name'])
			else:
				alert = {
					'type' : 'error',
					'text' : f'PiFire System Upgrade cannot be completed when the system is active.  Please shutdown/stop your smoker before retrying.'
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
==============================================================================
 Supporting Functions
==============================================================================
'''

def _is_not_blank(response, setting):
	return setting in response and setting != ''

def _is_checked(response, setting):
	return setting in response and response[setting] == 'on'

def _check_cpu_temp():
	process_command(action='sys', arglist=['check_cpu_temp'], origin='admin')  # Request supported commands 
	data = get_system_command_output(requested='check_cpu_temp')
	control = read_control()
	control['system']['cpu_temp'] = data['data'].get('cpu_temp', None)
	write_control(control)
	return f"{control['system']['cpu_temp']}C"

# TODO Remove this function when other dependent functions are updated to use common/app.py
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
			'outpins' : settings['platform']['outputs'],
			'inpins' : settings['platform']['inputs'],
			'dev_pins' : settings['platform']['devices'],
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
# TODO remove this line when other dependent functions are updated to use common/app.py
settings = read_settings(init=True)

if __name__ == '__main__':
	if is_real_hardware():
		socketio.run(app, host='0.0.0.0')
	else:
		socketio.run(app, host='0.0.0.0', debug=True)
