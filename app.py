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

from updater import *  # Library for doing project updates from GitHub

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
 SocketIO Section
==============================================================================
'''
import mobile.socket_io

'''
==============================================================================
 Main Program Start
==============================================================================
'''

if __name__ == '__main__':
	if is_real_hardware():
		socketio.run(app, host='0.0.0.0')
	else:
		socketio.run(app, host='0.0.0.0', debug=True)

