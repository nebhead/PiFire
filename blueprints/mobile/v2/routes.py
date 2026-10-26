#!/usr/bin/env python3

"""
==============================================================================
 PiFire Mobile API v2
==============================================================================

Description: HTTP replacement for the Socket.IO transport used by the mobile
  app. The same reads and writes as socket_io.py (see app_data.py), wrapped in
  an {ok, code, message, data} envelope.

==============================================================================
"""

import functools
import json
import logging
from urllib.parse import urlsplit

from flask import jsonify, request

from blueprints.mobile.app_data import get_app_data, post_app_data
from common.common import read_settings_redis
from . import mobile_v2_bp

API_VERSION = 1
CAPABILITIES = ['stream', 'push']

logger = logging.getLogger(__name__)

# /data/<name> -> get_app_data arguments
DATA = {
    'settings': ('settings_data',),
    'dash': ('dash_data',),
    'pellets': ('pellets_data',),
    'events': ('events_data',),
    'info': ('info_data',),
    'manual': ('manual_data',),
    'recipes': ('recipe_data', 'details'),
}

# /action/<action>/<type> -> post_app_data('<action>_action', '<type>', body)
ACTIONS = {
    'update': {'settings', 'control'},
    'admin': {'clear_history', 'clear_events', 'clear_pelletdb', 'clear_pelletdb_log', 'factory_defaults',
              'reboot', 'shutdown', 'restart_control', 'restart_webapp', 'restart_supervisor'},
    'units': {'f_units', 'c_units'},
    'pellets': {'load_profile', 'hopper_check', 'edit_brands', 'edit_woods', 'add_profile', 'edit_profile',
                'delete_profile', 'delete_log'},
    'timer': {'start_timer', 'pause_timer', 'stop_timer'},
    'recipes': {'recipe_delete', 'recipe_start'},
    'probes': {'probe_update'},
    'notify': {'notify_update'},
}

'''
==============================================================================
 Responses
==============================================================================
'''


def ok(data=None):
    return jsonify({'ok': True, 'data': data}), 200


def fail(code, status, message=None):
    body = {'ok': False, 'code': code}
    if message:
        body['message'] = message
    return jsonify(body), status


def from_app_data(response):
    """Wraps an app_data {'data', 'result', 'message'} response in the v2 envelope."""
    if isinstance(response, dict) and response.get('result') == 'OK':
        return ok(response.get('data'))
    message = response.get('message') if isinstance(response, dict) else None
    return fail('action_failed', 422, message or 'Error: Request could not be completed')


def handle_errors(view):
    """Any exception becomes a 500 with no details; the traceback stays in the log."""
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except Exception:
            logger.exception('Mobile API v2: unhandled error in %s', request.path)
            return fail('internal_error', 500)
    return wrapper


'''
==============================================================================
 Browser protection
==============================================================================
'''


@mobile_v2_bp.before_request
def check_request():
    # The app sends no Origin. A browser does on cross-site requests: refuse anything from another
    # site, so a web page can't drive the grill (Socket.IO allows any origin).
    origin = request.headers.get('Origin')
    if origin is not None and urlsplit(origin).netloc != request.host:
        return fail('forbidden_origin', 403)
    # A JSON content type forces a CORS preflight in browsers, which this API never answers.
    if request.method == 'POST' and not request.is_json:
        return fail('invalid_request', 400, 'Content-Type must be application/json')
    return None


'''
==============================================================================
 Routes
==============================================================================
'''


@mobile_v2_bp.route('/hello', methods=['GET'])
@handle_errors
def hello():
    settings = read_settings_redis()
    return ok({
        'api_version': API_VERSION,
        'uuid': settings['server_info']['uuid'],
        'server_version': settings['versions']['server'],
        'server_build': settings['versions']['build'],
        'capabilities': CAPABILITIES,
    })


@mobile_v2_bp.route('/data/<name>', methods=['GET'])
@handle_errors
def data(name):
    args = DATA.get(name)
    if args is None:
        return fail('unknown_action', 404, f'Unknown data: {name}')
    return from_app_data(get_app_data(*args))


@mobile_v2_bp.route('/action/<action>/<type>', methods=['POST'])
@handle_errors
def action(action, type):
    if type not in ACTIONS.get(action, ()):
        return fail('unknown_action', 404, f'Unknown action: {action}/{type}')
    body = request.get_json(silent=True)
    if body is None:
        body = {}
    if not isinstance(body, dict):
        return fail('invalid_request', 400, 'Body must be a JSON object')
    return from_app_data(post_app_data(f'{action}_action', type, json.dumps(body)))
