'''
Common PiFire WebApp Functions Shared Between Blueprints
'''

from common.common import process_command, read_settings, read_metrics, seconds_to_string, metrics_items
from flask import current_app
from common.redis_queue import RedisQueue
import time
import json
import datetime


def allowed_file(filename):
    ALLOWED_EXTENSIONS = current_app.config['ALLOWED_EXTENSIONS']
    return '.' in filename and \
            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_supported_cmds():
	process_command(action='sys', arglist=['supported_commands'], origin='admin')  # Request supported commands 
	data = get_system_command_output(requested='supported_commands')
	if data['result'] != 'ERROR':
		return data['data']['supported_cmds']
	else:
		return data


def get_system_command_output(requested='supported_commands', timeout=1):
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

def create_ui_hash():
	settings = read_settings()
	return hash(json.dumps(settings['probe_settings']['probe_map']['probe_info']))

def paginate_list(datalist, sortkey='', reversesortorder=False, itemsperpage=10, page=1):
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

def prepare_annotations(displayed_starttime, metrics_data=[]):
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

def prepare_event_totals(events):
	settings = read_settings()
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

def prepare_csv(data=[], filename=''):
	# Create filename if no name specified
	if(filename == ''):
		now = datetime.datetime.now()
		filename = now.strftime('%Y%m%d-%H%M') + '-PiFire-Export'
	else:
		filename = filename.replace('.json', '')
		filename = filename.replace('./history/', '')
		filename += '-Pifire-Export'
	
	exportfilename = '/tmp/' + filename + ".csv"
	
	# Open CSV File for editing
	csvfile = open(exportfilename, "w")

	if(data == []):
		data = read_history()

	exd_data = True if 'EXD' in data[0].keys() else False 

	# Set Standard Labels 
	labels = 'Time, '
	primary_key = list(data[0]['P'].keys())[0]
	labels += f'{primary_key} Temp, {primary_key} Set Point, {primary_key} Notify Target' 
	for key in data[0]['F']:
		labels += f', {key} Temp, {key} Notify Target'
	for key in data[0]['AUX']:
		labels += f', {key} Temp'
	if exd_data: 
		for key in data[0]['EXD']:
			labels += f', {key}'

	# End the labels line
	labels += '\n'

	# Get the length of the data (number of captured events)
	list_length = len(data)

	if(list_length > 0):
		writeline = labels
		csvfile.write(writeline)

		for index in range(0, list_length):
			converted_dt = datetime.datetime.fromtimestamp(int(data[index]['T']) / 1000)
			timestr = converted_dt.strftime('%Y-%m-%d %H:%M:%S')
			writeline = f"{timestr}, {data[index]['P'][primary_key]}, {data[index]['PSP']}, {data[index]['NT'][primary_key]}"
			for key in data[index]['F']:
				writeline += f", {data[index]['F'][key]}, {data[index]['NT'][key]}"
			for key in data[index]['AUX']:
				writeline += f", {data[index]['AUX'][key]}"
			# Add any additional data if keys exist
			if exd_data: 
				for key in data[index]['EXD']:
					writeline += f", {data[index]['EXD'][key]}"
			# Write line to file
			csvfile.write(writeline + '\n')
	else:
		writeline = 'No Data\n'
		csvfile.write(writeline)

	csvfile.close()

	return(exportfilename)

def create_safe_name(name): 
	return("".join([x for x in name if x.isalnum()]))