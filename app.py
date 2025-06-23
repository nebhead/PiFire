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

from flask import Flask, request, render_template, jsonify, redirect, render_template_string
from flask_mobility import Mobility
from flask_socketio import SocketIO
from flask_qrcode import QRcode
from werkzeug.exceptions import InternalServerError
import threading

from threading import Thread
from datetime import datetime
from updater import *  # Library for doing project updates from GitHub

from common.app import get_system_command_output

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
from blueprints.probeconfig import probeconfig_bp
from blueprints.recipes import recipes_bp
from blueprints.settings import settings_bp
from blueprints.wizard import wizard_bp

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
app.register_blueprint(probeconfig_bp, url_prefix='/probeconfig')
app.register_blueprint(recipes_bp, url_prefix='/recipes')
app.register_blueprint(settings_bp, url_prefix='/settings')
app.register_blueprint(wizard_bp, url_prefix='/wizard')

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
	settings = read_settings()
	
	if settings['globals']['first_time_setup']:
		return redirect('/wizard/welcome')
	else: 
		return redirect('/dash')

'''
Updater Function Routes
'''
@app.route('/checkupdate', methods=['GET'])
def check_update(action=None):
	settings = read_settings()
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
	settings = read_settings()

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
# TODO: Move to socketIO section 
def _check_cpu_temp():
	process_command(action='sys', arglist=['check_cpu_temp'], origin='admin')  # Request supported commands 
	data = get_system_command_output(requested='check_cpu_temp')
	control = read_control()
	control['system']['cpu_temp'] = data['data'].get('cpu_temp', None)
	write_control(control)
	return f"{control['system']['cpu_temp']}C"

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
