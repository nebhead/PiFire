'''
Common PiFire WebApp Functions Shared Between Blueprints
'''

from common.common import process_command, read_settings
from flask import current_app
from common.redis_queue import RedisQueue
import time
import json


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