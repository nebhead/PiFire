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
import zipfile
import pathlib
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

def update_global_settings(updated_settings):
	global settings
	settings = updated_settings

def _create_safe_name(name): 
	return("".join([x for x in name if x.isalnum()]))

def _is_not_blank(response, setting):
	return setting in response and setting != ''

def _is_checked(response, setting):
	return setting in response and response[setting] == 'on'

def _allowed_file(filename):
	return '.' in filename and \
		   filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
			thumbnail = unpack_thumb(cookfiledata['thumbnail'], filename, cookfiledata["id"]) if ('thumbnail' in cookfiledata) else ''
			cookfiledetails.append({'filename' : item['filename'], 'title' : cookfiledata['title'], 'thumbnail' : thumbnail})
		else:
			cookfiledetails.append({'filename' : item['filename'], 'title' : 'ERROR', 'thumbnail' : ''})
	return(cookfiledetails)

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
		event = 'ERROR: Failed to calculate Steinhart-Hart coefficients.'
		write_log(event)
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
		for file_path in directory.rglob("*.log"):
			archive.write(file_path, arcname=file_path.relative_to(directory))
	return file_name

def _get_supported_cmds():
	process_command(action='sys', arglist=['supported_commands'], origin='admin')  # Request supported commands 
	data = _get_system_command_output(requested='supported_commands')
	if data['result'] != 'ERROR':
		return data['data']['supported_cmds']
	else:
		return data

def _get_system_command_output(requested='supported_commands', timeout=1):
	system_output = RedisQueue('control:systemo')
	endtime = timeout + time.time()
	while time.time() < endtime:
		while system_output.length() > 0:
			data = system_output.pop()
			if data['command'][0] == requested:
				return data

	return {
		'command' : [requested, None, None, None],
		'result' : 'ERROR',
		'message' : 'The requested command output could not be found.',
		'data' : {'Response_Was' : 'To_Fast'}
	}


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

'''
==============================================================================
 SocketIO Section
==============================================================================
'''
import mobile.socket_io