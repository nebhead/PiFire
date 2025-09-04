from flask import current_app, request, jsonify, abort
from common.common import (
	process_command, 
	read_settings, 
	write_settings, 
	read_control, 
	write_control, 
	read_pellet_db, 
	write_log, 
	read_current, 
	read_status, 
	read_probe_status, 
	deep_update
	)
from common.app import get_system_command_output, create_ui_hash
from common.server_status import get_server_status
from . import api_bp

@api_bp.route('/', methods=['POST','GET'])
@api_bp.route('/<action>', methods=['POST','GET'])
@api_bp.route('/<action>/<arg0>', methods=['POST','GET'])
@api_bp.route('/<action>/<arg0>/<arg1>', methods=['POST','GET'])
@api_bp.route('/<action>/<arg0>/<arg1>/<arg2>', methods=['POST','GET'])
@api_bp.route('/<action>/<arg0>/<arg1>/<arg2>/<arg3>', methods=['POST','GET'])
def api_page(action=None, arg0=None, arg1=None, arg2=None, arg3=None):
	settings = read_settings()
    # Get current server status
	server_status = get_server_status()

	if action in ['get', 'set', 'cmd', 'sys']:
		#print(f'action={action}\narg0={arg0}\narg1={arg1}\narg2={arg2}\narg3={arg3}')
		arglist = []
		arglist.extend([arg0, arg1, arg2, arg3])

		data = process_command(action=action, arglist=arglist, origin='api')

		if action == 'sys':
			''' If system command, wait for output from control '''
			data = get_system_command_output(requested=arg0)
		
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
			current_temps = read_current()  # Get current temperatures
			control = read_control()  # Get status of control
			display = read_status()  # Get status of display items
			probe_status = read_probe_status(settings['probe_settings']['probe_map']['probe_info'])

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
			status['probe_status'] = probe_status
			status['critical_error'] = control.get('critical_error', False)
			return jsonify({'current':current_temps, 'notify_data':notify_data, 'status':status}), 201
		elif action == 'hopper':
			pelletdb = read_pellet_db()
			pelletlevel = pelletdb['current']['hopper_level']
			pelletid = pelletdb['current']['pelletid']
			pellets = f'{pelletdb["archive"][pelletid]["brand"]} {pelletdb["archive"][pelletid]["wood"]}'
			return jsonify({'hopper_level': pelletlevel, 'hopper_pellets': pellets})
		elif action == 'wled_discover':
			''' Discover WLED devices on the network '''
			try:
				import subprocess
				import json
				import sys
				import os
				
				# Get timeout from query parameter, default to 10 seconds
				timeout = request.args.get('timeout', 10, type=int)
				timeout = max(5, min(30, timeout))  # Clamp between 5-30 seconds
				
				# Use standalone script to avoid threading conflicts with eventlet/gunicorn
				script_path = '/usr/local/bin/pifire/wled_discover_standalone.py'
				python_path = '/usr/local/bin/pifire/bin/python3'
				
				# Run discovery in a separate process
				process = subprocess.Popen(
					[python_path, script_path, str(timeout)],
					stdout=subprocess.PIPE,
					stderr=subprocess.PIPE,
					cwd='/usr/local/bin/pifire'
				)
				
				stdout, stderr = process.communicate(timeout=timeout + 15)
				
				if process.returncode == 0 and stdout:
					try:
						result = json.loads(stdout.decode())
						if result.get('success', False):
							return jsonify({
								'result': 'success',
								'message': f'Found {result["count"]} WLED devices',
								'devices': result['devices']
							}), 200
						else:
							return jsonify({
								'result': 'error',
								'message': f'Discovery failed: {result.get("error", "Unknown error")}',
								'devices': []
							}), 500
					except json.JSONDecodeError as e:
						return jsonify({
							'result': 'error',
							'message': f'Failed to parse discovery result: {e}',
							'devices': []
						}), 500
				else:
					error_msg = stderr.decode() if stderr else 'Discovery process failed'
					return jsonify({
						'result': 'error',
						'message': f'Discovery process error: {error_msg}',
						'devices': []
					}), 500
					
			except Exception as e:
				return jsonify({
					'result': 'error', 
					'message': f'WLED discovery failed: {str(e)}',
					'devices': []
				}), 500 
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
				try:
					settings = deep_update(settings, request_json)
					write_settings(settings)
					return jsonify(
							{
							'settings' : 'success',  # Keeping for compatibility
							'result' : 'success',
							'message': 'Settings updated successfully.'
							}
						), 201
				except:
					return jsonify(
							{
							'settings' : 'error',  # Keeping for compatibility
							'result' : 'error',
							'message': 'Settings update failed.'
							}
						), 201

			elif(action == 'control'):
				'''
					Updating of control input data is now done in common.py > execute_commands() 
				'''
				try:
					# Update control data with request JSON
					write_control(request_json, origin='app')
					return jsonify(
							{
								'control': 'success',
								'result' : 'success',
								'message': 'Settings updated successfully.'
							}
						), 201
				except:
					return jsonify(
							{
								'control': 'error',
								'result' : 'error',
								'message': 'Settings update failed.'
							}
						), 201
			else:
				return jsonify({'Error':'Received POST request no valid action.'}), 404
	else:
		return jsonify({'Error':'Received undefined/unsupported request.'}), 404

