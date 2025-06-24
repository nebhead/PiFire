#!/usr/bin/env python3

"""
==============================================================================
 PiFire SocketIO Module
==============================================================================

Description: This library provides socketio functions for app.py

==============================================================================
"""

'''
==============================================================================
 Imported Modules
==============================================================================
'''
import threading
from common import *
from flask import request, current_app
from app import socketio
from file_mgmt.recipes import read_recipefile, get_recipefilelist
from base64 import b64encode
from datetime import datetime
from threading import Event

thread_lock = threading.Lock()
thread_event = Event()
thread = None

'''
==============================================================================
 Flush Redis DB's and create Settings / PelletDB / Connected Users / Events
==============================================================================
'''
read_settings_redis(init=True)
read_pellets_redis(init=True)
read_connected_users(flush=True)
read_events_redis(flush=True)

'''
==============================================================================
 Functions
==============================================================================
'''

@socketio.on("connect")
def handle_connect():
    client_id = request.sid
    write_connected_user(client_id)
    connected_users = read_connected_users()
    listen_app_data(force=True)
    print(f"User {client_id} connected. Current connected users: {connected_users}")

@socketio.on("disconnect")
def handle_disconnect():
    global thread
    client_id = request.sid
    remove_connected_user(client_id)
    connected_users = read_connected_users()
    print(f"User {client_id} disconnected. Current connected users: {connected_users}")
    if len(connected_users) == 0:
        thread_event.clear()
        with thread_lock:
            if thread is not None:
                thread.join()
                thread = None

@socketio.on('listen_app_data')
def listen_app_data(force=False):
    global thread

    with thread_lock:
        if thread is None:
            thread_event.set()
            thread = socketio.start_background_task(_emit_app_data, thread_event, force)

    return _response(result='OK')

@socketio.on('get_app_data')
def get_app_data(action=None, arg01=None, arg02=None):
    return _get_app_data(action, arg01, arg02)

@socketio.on('post_app_data')
def post_app_data(action=None, type=None, json_data=None):
    return _post_app_data(action, type, json_data)


'''
==============================================================================
 Supporting Functions
==============================================================================
'''

def _emit_app_data(event, force_refresh):
    global thread

    previous_dash = ''
    previous_event = ''
    previous_pellet = ''

    try:
        while event.is_set():
            check_control_status()
            settings = read_settings_redis()
            pelletdb = read_pellets_redis()
            uuid = settings['server_info']['uuid']

            pellet_data = {
                'uuid' : uuid,
                'pellets' : pelletdb
            }

            event_data = {
                'uuid' : uuid,
                'events' : read_events_redis()
            }

            dash_data = _get_dash_data(settings, pelletdb)

            if force_refresh:
                socketio.emit('socket_event_data', event_data)
                socketio.emit('socket_pellet_data', pellet_data)
                socketio.emit('socket_dash_data', dash_data)
                force_refresh = False
            else:
                if previous_event != event_data:
                    socketio.emit('socket_event_data', event_data)
                    previous_event = event_data

                if previous_pellet != pellet_data:
                    socketio.emit('socket_pellet_data', pellet_data)
                    previous_pellet = pellet_data

                if previous_dash != dash_data:
                    socketio.emit('socket_dash_data', dash_data)
                    previous_dash = dash_data

            socketio.sleep(1)
    finally:
        event.clear()
        thread = None


def _get_dash_data(settings, pelletdb):
    control = read_control()
    status = read_status()
    current = read_current()
    errors = read_errors()
    warnings = read_warnings()
    notify_data = control['notify_data']
    probe_device_info = read_generic_key('probe_device_info')
    RECIPE_FOLDER = current_app.config['RECIPE_FOLDER']

    timer_notify_data = _get_timer_notify_data(notify_data)
    food_probes = _get_probe_data('Food', settings, current, probe_device_info, notify_data)
    primary_probe = _get_probe_data('Primary', settings, current, probe_device_info, notify_data)[0]

    dash_data = {
        'uuid': settings['server_info']['uuid'],
        'errors': errors,
        'warnings': warnings,
        'status': control['status'],
        'criticalError': control['critical_error'],
        'grillName': settings['globals']['grill_name'],
        'currentMode': control['mode'],
        'nextMode': control['next_mode'],
        'displayMode': status['mode'],
        'smokePlus': control['s_plus'],
        'pwmControl': control['pwm_control'],
        'pMode': settings['cycle_data']['PMode'],
        'hopperLevel': pelletdb['current']['hopper_level'],
        'startupTimestamp': math.trunc(control['startup_timestamp']),
        'modeStartTime': math.trunc(status['start_time']),
        'lidOpenDetectEnabled': settings['cycle_data']['LidOpenDetectEnabled'],
        'lidOpenDetected': status['lid_open_detected'],
        'lidOpenEndTime': math.trunc(status['lid_open_endtime']),
        'startDuration': status['start_duration'],
        'shutdownDuration': status['shutdown_duration'],
        'primeDuration': status['prime_duration'],
        'primeAmount': status['prime_amount'],
        'tempUnits': settings['globals']['units'],
        'hasDcFan': settings['platform']['dc_fan'],
        'startupCheck': settings['safety']['startup_check'],
        'allowManualOutputs': settings['safety']['allow_manual_changes'],
        'timer': {
            'start': math.trunc(control['timer']['start']),
            'paused': math.trunc(control['timer']['paused']),
            'end': math.trunc(control['timer']['end']),
            'keepWarm': timer_notify_data['keep_warm'],
            'shutdown': timer_notify_data['shutdown'],
        },
        'outputs': {
            'fan': status['outpins']['fan'],
            'auger': status['outpins']['auger'],
            'igniter': status['outpins']['igniter']
        },
        'recipeStatus': {
            'recipeMode': status['recipe'],
            'filename': control['recipe']['filename'].split('/')[-1],
            'mode': status['mode'],
            'paused': status['recipe_paused'],
            'step': control['recipe']['step']
        },
        'foodProbes': food_probes,
        'primaryProbe': primary_probe
    }
    return dash_data

def _get_app_data(action=None, arg01=None, arg02=None):
    settings = read_settings_redis()
    RECIPE_FOLDER = current_app.config['RECIPE_FOLDER']

    if action == 'settings_data':
        return _response(
            result='OK',
            data=settings
        )

    elif action == 'dash_data':
        pelletdb = read_pellets_redis()
        return _response(
            result='OK',
            data=_get_dash_data(settings, pelletdb)
        )

    elif action == 'pellets_data':
        return _response(
            result='OK',
            data={
                'uuid': settings['server_info']['uuid'],
                'pellets': read_pellets_redis()
            }
        )

    elif action == 'events_data':
        return _response(
            result='OK',
            data={
                'uuid': settings['server_info']['uuid'],
                'events': read_events_redis()
            }
        )

    elif action == 'hopper_level':
        return _response(
            result='OK',
            data=read_pellets_redis()['current']['hopper_level']
        )

    elif action == 'info_data':
        return _response(
            result='OK',
            data={
                'uuid': settings['server_info']['uuid'],
                'upTime': os.popen('uptime').readline(),
                'cpuInfo': os.popen('cat /proc/cpuinfo').readlines(),
                'ifConfig': os.popen('ifconfig').readlines(),
                'cpuTemp': check_cpu_temp(),
                'outPins': settings['platform']['outputs'],
                'inPins': settings['platform']['inputs'],
                'devPins': settings['platform']['devices'],
                'serverVersion': settings['versions']['server'],
                'serverBuild': settings['versions']['build'],
                'platform': settings['modules']['grillplat'],
                'display': settings['modules']['display'],
                'distance': settings['modules']['dist'],
                'dcFan': settings['platform']['dc_fan']
            }
        )

    elif action == 'manual_data':
        control = read_control()
        return _response(
            result='OK',
            data={
                'manual': read_status()['outpins'],
                'active': control['mode'] == 'Manual',
                'dcFan': settings['platform']['dc_fan']
            }
        )
    elif action == 'recipe_data':
        if arg01 is not None:
            if arg01 == 'details':
                filelist = get_recipefilelist()
                recipedetailslist = []
                for filename in filelist:
                    filepath = f'{RECIPE_FOLDER}{filename}'
                    recipe_data, status = read_recipefile(filepath)
                    if status == 'OK':
                        recipe_data = _encode_assets(recipe_data)
                        recipedetailslist.append({'filename': filename, 'details': recipe_data})
                if recipedetailslist:
                    return _response(
                        result='OK',
                        data={
                            'uuid': settings['server_info']['uuid'],
                            'recipe_details': recipedetailslist
                        }
                    )
                else:
                    return _response(result='Error', message='Error: Recipes details not found')
    else:
        return _response(result='Error', message='Error: Received request without valid action')


def _post_app_data(action=None, type=None, json_data=None):
    settings = read_settings_redis()
    RECIPE_FOLDER = current_app.config['RECIPE_FOLDER']

    if json_data is not None:
        request = json.loads(json_data)
    else:
        request = {''}

    if action == 'update_action':
        if type == 'settings':
            control = read_control()
            for key in request.keys():
                if key in settings.keys():
                    settings = deep_update(settings, request)
                    _write_settings(settings, control)
                    control['settings_update'] = True
                    write_control(control, origin='app-socketio')
                    return _response(result='OK', data=settings)
                else:
                    return _response(result='Error', message='Error: Key not found in settings')
        elif type == 'control':
            control = read_control()
            for key in request.keys():
                if key in control.keys():
                    '''
                        Updating of control input data is now done in common.py > execute_commands() 
                    '''
                    write_control(request, origin='app-socketio')
                    return _response(result='OK', data=control)
                else:
                    return _response(result='Error', message='Error: Key not found in control')
        else:
            return _response(result='Error', message='Error: Received request without valid type')

    elif action == 'admin_action':
        if type == 'clear_history':
            write_log('Clearing History Log.')
            read_history(0, flushhistory=True)
            return _response(result='OK')
        elif type == 'clear_events':
            write_log('Clearing Events Log.')
            os.system('rm /tmp/events.log')
            return _response(result='OK')
        elif type == 'clear_pelletdb':
            write_log('Clearing Pellet Database.')
            os.system('rm pelletdb.json')
            return _response(result='OK')
        elif type == 'clear_pelletdb_log':
            pelletdb = read_pellets_redis()
            pelletdb['log'].clear()
            write_pellet_db(pelletdb)
            write_log('Clearing Pellet Database Log.')
            return _response(result='OK')
        elif type == 'factory_defaults':
            read_history(0, flushhistory=True)
            read_control(flush=True)
            os.system('rm settings.json')
            settings = default_settings()
            control = default_control()
            _write_settings(settings, control)
            write_control(control, origin='app-socketio')
            write_log('Resetting Settings, Control, History to factory defaults.')
            return _response(result='OK')
        elif type == 'reboot':
            write_log("Admin: Reboot")
            os.system("sleep 3 && sudo reboot &")
            return _response(result='OK')
        elif type == 'shutdown':
            write_log("Admin: Shutdown")
            os.system("sleep 3 && sudo shutdown -h now &")
            return _response(result='OK')
        elif type == 'restart':
            write_log("Admin: Restart Server")
            restart_scripts()
            return _response(result='OK')
        else:
            return _response(result='Error', message='Error: Received request without valid type')

    elif action == 'units_action':
        if type == 'f_units' and settings['globals']['units'] == 'C':
            settings = convert_settings_units('F', settings)
            control = read_control()
            _write_settings(settings, control)
            control['updated'] = True
            control['units_change'] = True
            write_control(control, origin='app-socketio')
            write_log("Changed units to Fahrenheit")
            return _response(result='OK')
        elif type == 'c_units' and settings['globals']['units'] == 'F':
            settings = convert_settings_units('C', settings)
            control = read_control()
            _write_settings(settings, control)
            control['updated'] = True
            control['units_change'] = True
            write_control(control, origin='app-socketio')
            write_log("Changed units to Celsius")
            return _response(result='OK')
        else:
            return _response(result='Error', message='Error: Units could not be changed')

    elif action == 'pellets_action':
        pelletdb = read_pellets_redis()
        if type == 'load_profile':
            if 'profile' in request['pellets_action']:
                pelletdb['current']['pelletid'] = request['pellets_action']['profile']
                now = str(datetime.now())
                now = now[0:19]
                pelletdb['current']['date_loaded'] = now
                pelletdb['current']['est_usage'] = 0
                pelletdb['log'][now] = request['pellets_action']['profile']
                control = read_control()
                control['hopper_check'] = True
                write_control(control, origin='app-socketio')
                write_pellet_db(pelletdb)
                return _response(result='OK')
            else:
                return _response(result='Error', message='Error: Profile not included in request')
        elif type == 'hopper_check':
            control = read_control()
            control['hopper_check'] = True
            write_control(control, origin='app-socketio')
            return _response(result='OK')
        elif type == 'edit_brands':
            if 'delete_brand' in request['pellets_action']:
                delBrand = request['pellets_action']['delete_brand']
                if delBrand in pelletdb['brands']:
                    pelletdb['brands'].remove(delBrand)
                write_pellet_db(pelletdb)
                return _response(result='OK')
            elif 'new_brand' in request['pellets_action']:
                newBrand = request['pellets_action']['new_brand']
                if newBrand not in pelletdb['brands']:
                    pelletdb['brands'].append(newBrand)
                write_pellet_db(pelletdb)
                return _response(result='OK')
            else:
                return _response(result='Error', message='Error: Function not specified')
        elif type == 'edit_woods':
            if 'delete_wood' in request['pellets_action']:
                delWood = request['pellets_action']['delete_wood']
                if delWood in pelletdb['woods']:
                    pelletdb['woods'].remove(delWood)
                write_pellet_db(pelletdb)
                return _response(result='OK')
            elif 'new_wood' in request['pellets_action']:
                newWood = request['pellets_action']['new_wood']
                if newWood not in pelletdb['woods']:
                    pelletdb['woods'].append(newWood)
                write_pellet_db(pelletdb)
                return _response(result='OK')
            else:
                return _response(result='Error', message='Error: Function not specified')
        elif type == 'add_profile':
            profile_id = ''.join(filter(str.isalnum, str(datetime.now())))
            pelletdb['archive'][profile_id] = {
                'id': profile_id,
                'brand': request['pellets_action']['brand_name'],
                'wood': request['pellets_action']['wood_type'],
                'rating': request['pellets_action']['rating'],
                'comments': request['pellets_action']['comments']}
            if request['pellets_action']['add_and_load']:
                pelletdb['current']['pelletid'] = profile_id
                control = read_control()
                control['hopper_check'] = True
                write_control(control, origin='app-socketio')
                now = str(datetime.now())
                now = now[0:19]
                pelletdb['current']['date_loaded'] = now
                pelletdb['current']['est_usage'] = 0
                pelletdb['log'][now] = profile_id
                write_pellet_db(pelletdb)
                return _response(result='OK')
            else:
                write_pellet_db(pelletdb)
                return _response(result='OK')
        if type == 'edit_profile':
            if 'profile' in request['pellets_action']:
                profile_id = request['pellets_action']['profile']
                pelletdb['archive'][profile_id]['brand'] = request['pellets_action']['brand_name']
                pelletdb['archive'][profile_id]['wood'] = request['pellets_action']['wood_type']
                pelletdb['archive'][profile_id]['rating'] = request['pellets_action']['rating']
                pelletdb['archive'][profile_id]['comments'] = request['pellets_action']['comments']
                write_pellet_db(pelletdb)
                return _response(result='OK')
            else:
                return _response(result='Error', message='Error: Profile not included in request')
        if type == 'delete_profile':
            if 'profile' in request['pellets_action']:
                profile_id = request['pellets_action']['profile']
                if pelletdb['current']['pelletid'] == profile_id:
                    return _response(result='Error', message='Error: Cannot delete current profile')
                else:
                    pelletdb['archive'].pop(profile_id)
                    for index in pelletdb['log']:
                        if pelletdb['log'][index] == profile_id:
                            pelletdb['log'][index] = 'deleted'
                write_pellet_db(pelletdb)
                return _response(result='OK')
            else:
                return _response(result='Error', message='Error: Profile not included in request')
        elif type == 'delete_log':
            if 'log_item' in request['pellets_action']:
                delLog = request['pellets_action']['log_item']
                if delLog in pelletdb['log']:
                    pelletdb['log'].pop(delLog)
                write_pellet_db(pelletdb)
                return _response(result='OK')
            else:
                return _response(result='Error', message='Error: Function not specified')
        else:
            return _response(result='Error', message='Error: Received request without valid type')

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
                    return _response(result='OK')
                else:
                    return _response(result='Error', message='Error: Start time not specified')
            else:
                now = time.time()
                control['timer']['end'] = (control['timer']['end'] - control['timer']['paused']) + now
                control['timer']['paused'] = 0
                write_log('Timer unpaused.  Ends at: ' + epoch_to_time(control['timer']['end']))
                write_control(control, origin='app-socketio')
                return _response(result='OK')
        elif type == 'pause_timer':
            control['notify_data'][index]['req'] = False
            now = time.time()
            control['timer']['paused'] = now
            write_log('Timer paused.')
            write_control(control, origin='app-socketio')
            return _response(result='OK')
        elif type == 'stop_timer':
            control['notify_data'][index]['req'] = False
            control['timer']['start'] = 0
            control['timer']['end'] = 0
            control['timer']['paused'] = 0
            control['notify_data'][index]['shutdown'] = False
            control['notify_data'][index]['keep_warm'] = False
            write_log('Timer stopped.')
            write_control(control, origin='app-socketio')
            return _response(result='OK')
        else:
            return _response(result='Error', message='Error: Received request without valid type')
    elif action == 'recipes_action':
        if type == 'recipe_delete':
            if request['recipes_action']['filename']:
                filename = request['recipes_action']['filename']
                filepath = f'{RECIPE_FOLDER}{filename}'
                os.system(f'rm {filepath}')
                return _response(result='OK')
        elif type == 'recipe_start':
            if request['recipes_action']['filename']:
                control = read_control()
                filename = request['recipes_action']['filename']
                control['updated'] = True
                control['mode'] = 'Recipe'
                control['recipe']['filename'] = RECIPE_FOLDER + filename
                write_control(control, origin='app-socketio')
                return _response(result='OK')
        else:
            return _response(result='Error', message='Error: Received request without valid type')
    elif action == 'probes_action':
        if type == 'probe_update':
            if all(v in ('name', 'label', 'profile_id', 'enabled') for v in request['probes_action'].keys()):
                control = read_control()
                return _update_probe_config(settings, control, request)
            else:
                return _response(result='Error', message='Error: Missing required argument, probe cannot be updated')
        else:
            return _response(result='Error', message='Error: Received request without valid type')
    elif action == 'notify_action':
        if type == 'notify_update':
            if 'label' in request['notify_action'].keys():
                control = read_control()
                return _update_notify_data(control, request)
            else:
                return _response(result='Error', message='Error: Request missing probe label')
        else:
            return _response(result='Error', message='Error: Received request without valid type')
    else:
        return _response(result='Error', message='Error: Received request without valid action')


def _get_probe_data(probe_type, settings, current, probe_device_info, notify_data):
    probe_list = []

    # Determine section based on probe type
    if probe_type == 'Primary':
        section = 'P'
    elif probe_type == 'Food':
        section = 'F'
    else:
        section = 'AUX'

    for probe in settings['probe_settings']['probe_map']['probe_info']:
        if probe['type'] == probe_type and probe['enabled'] == True:
            probe_data = _get_probe_structure(probe_type, settings)
            probe_data['title'] = probe['name']
            probe_data['label'] = probe['label']
            probe_data['temp'] = current[section][probe['label']]
            probe_data['device'] = probe['device']
            if probe_type == 'Primary':
                probe_data['setTemp'] = current['PSP']
            probe_list.append(probe_data)
    for probe in probe_list:
        for index, notify_obj in enumerate(notify_data):
            if notify_data[index]['label'] == probe['label']:
                if notify_obj['type'] == 'probe':
                    probe['eta'] = notify_obj['eta']
                    probe['target'] = notify_obj['target']
                    probe['targetShutdown'] = notify_obj['shutdown']
                    probe['targetKeepWarm'] = notify_obj['keep_warm']
                    probe['targetReq'] = notify_obj['req']
                    if notify_obj['req']:
                        probe['hasNotifications'] = True
                if notify_obj['type'] == 'probe_limit_high':
                    probe['highLimitTemp'] = notify_obj['target']
                    probe['highLimitReq'] = notify_obj['req']
                    probe['highLimitShutdown'] = notify_obj['shutdown']
                    probe['highLimitTriggered'] = notify_obj['triggered']
                    if notify_obj['req']:
                        probe['hasNotifications'] = True
                if notify_obj['type'] == 'probe_limit_low':
                    probe['lowLimitTemp'] = notify_obj['target']
                    probe['lowLimitReq'] = notify_obj['req']
                    probe['lowLimitShutdown'] = notify_obj['shutdown']
                    probe['lowLimitReignite'] = notify_obj['reignite']
                    probe['lowLimitTriggered'] = notify_obj['triggered']
                    if notify_obj['req']:
                        probe['hasNotifications'] = True
        for device in probe_device_info:
            if device['device'] == probe['device']:
                status = device.get('status', {})
                if 'battery_charging' in status:
                    probe['status']['batteryCharging'] = status['battery_charging']
                if 'battery_percentage' in status:
                    probe['status']['batteryPercentage'] = status['battery_percentage']
                if 'battery_voltage' in status:
                    probe['status']['batteryVoltage'] = status['battery_voltage']
                if 'connected' in status:
                    probe['status']['connected'] = status['connected']
                if 'error' in status:
                    probe['status']['error'] = status['error']

    return probe_list


def _get_probe_structure(probe_type, settings):
    return {
        'title': 'Probe',
        'label': 'probe',
        'eta': 0,
        'temp': 0,
        'setTemp': 0,
        'maxTemp': _get_probe_max_temp(probe_type, settings),
        'target': 0,
        'lowLimitTemp': 0,
        'highLimitTemp': 0,
        'targetReq': False,
        'hasNotifications': False,
        'lowLimitReq': False,
        'highLimitReq': False,
        'highLimitShutdown': False,
        'highLimitTriggered': False,
        'lowLimitShutdown': False,
        'lowLimitReignite': False,
        'lowLimitTriggered': False,
        'targetShutdown': False,
        'targetKeepWarm': False,
        'status': {}
    }


def _get_probe_max_temp(probe_type, settings):
    config = settings['dashboard']['dashboards']['Default']['config']
    units = settings['globals']['units']
    if units == 'F':
        if probe_type == 'Primary':
            return config['max_primary_temp_F']
        else:
            return config['max_food_temp_F']
    else:
        if probe_type == 'Primary':
            return config['max_primary_temp_C']
        else:
            return config['max_food_temp_C']


def _get_timer_notify_data(notify_data):
    timer_info = {
        'keep_warm': False,
        'shutdown': False,
    }
    for index, notify_obj in enumerate(notify_data):
        if notify_obj['type'] == 'timer':
            timer_info['keep_warm'] = notify_obj['keep_warm']
            timer_info['shutdown'] = notify_obj['shutdown']
    return timer_info

def _encode_assets(recipe_data):
    img_size = ['full', 'thumb']
    recipe_id = recipe_data['metadata']['id']
    for size in img_size:
        try:
            for asset in recipe_data['assets']:
                if size == 'full':
                    asset['encoded_image'] = _encode_img(recipe_id, asset['filename'])
                else:
                    asset['encoded_thumb'] = _encode_img(recipe_id, asset['filename'], True)
        except KeyError:
            continue
    return recipe_data

def _encode_img(recipe_id, asset_filename, thumb=False):
    filepath = f'./static/img/tmp/{recipe_id}/thumbs/' if thumb else f'./static/img/tmp/{recipe_id}/'
    try:
        with open(filepath + asset_filename, 'rb') as img:
            buffer = img.read()
            asset_img = b64encode(buffer).decode("utf-8")
    except:
        asset_img = ''
    return asset_img

def _update_probe_config(settings, control, request):
    probe_config = request['probes_action']
    label = probe_config.get('label', '')
    probe_edited = {}

    for index, probe in enumerate(settings['probe_settings']['probe_map']['probe_info']):
        if probe['label'] == label:
            probe_edited['label'] = probe['label']
            probe_edited['name'] = probe_config.get('name', settings['probe_settings']['probe_map']['probe_info'][index]['name'])
            probe_edited['type'] = probe_config.get('type', settings['probe_settings']['probe_map']['probe_info'][index]['type'])
            probe_edited['port'] = probe_config.get('port', settings['probe_settings']['probe_map']['probe_info'][index]['port'])
            probe_edited['device'] = probe_config.get('device', settings['probe_settings']['probe_map']['probe_info'][index]['device'])
            probe_edited['enabled'] = probe_config.get('enabled', settings['probe_settings']['probe_map']['probe_info'][index]['enabled'])
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
        control['settings_update'] = True
        # Take all settings and write them
        _write_settings(settings, control)

        return _response(result='OK', data=settings)
    else:
        return _response(result='Error', message='Error: Probe was not found')

def _update_notify_data(control, request):
    notify_dto = request['notify_action']
    updated_notify_data = control['notify_data']

    for index, item in enumerate(updated_notify_data):
        if item['type'] == 'probe' and item['label'] == notify_dto['label']:
            if 'target_temp' in notify_dto.keys():
                target_temp = notify_dto['target_temp']
                updated_notify_data[index]['target'] = int(target_temp)
                updated_notify_data[index]['shutdown'] = notify_dto['target_shutdown']
                updated_notify_data[index]['keep_warm'] = notify_dto['target_keep_warm']
                updated_notify_data[index]['req'] = notify_dto['target_req']
            else:
                updated_notify_data[index]['target'] = 0
                updated_notify_data[index]['shutdown'] = False
                updated_notify_data[index]['keep_warm'] = False
                updated_notify_data[index]['req'] = False

        if item['type'] == 'probe_limit_high' and item['label'] == notify_dto['label']:
            if 'high_limit_temp' in notify_dto.keys():
                high_limit_temp = notify_dto['high_limit_temp']
                updated_notify_data[index]['target'] = int(high_limit_temp)
                updated_notify_data[index]['shutdown'] = notify_dto['high_limit_shutdown']
                updated_notify_data[index]['req'] = notify_dto['high_limit_req']
            else:
                updated_notify_data[index]['target'] = 0
                updated_notify_data[index]['shutdown'] = False
                updated_notify_data[index]['req'] = False

        if item['type'] == 'probe_limit_low' and item['label'] == notify_dto['label']:
            if 'low_limit_temp' in notify_dto.keys():
                low_limit_temp = notify_dto['low_limit_temp']
                updated_notify_data[index]['target'] = int(low_limit_temp)
                updated_notify_data[index]['shutdown'] = notify_dto['low_limit_shutdown']
                updated_notify_data[index]['reignite'] = notify_dto['low_limit_reignite']
                updated_notify_data[index]['req'] = notify_dto['low_limit_req']
            else:
                updated_notify_data[index]['target'] = 0
                updated_notify_data[index]['shutdown'] = False
                updated_notify_data[index]['reignite'] = False
                updated_notify_data[index]['req'] = False

    control['notify_data'] = updated_notify_data
    write_control(control, origin='app-socketio')
    return _response(result="OK")

def _write_settings(settings, control):
    control['settings_update'] = True
    write_settings(settings)
    write_control(control, origin='app-socketio')

def check_control_status():
    errors = read_errors()
    ''' Check if control process is up and running. '''
    process_command(action='sys', arglist=['check_alive'], origin='app-socketio')
    data = get_system_command_output(requested='check_alive')
    if data['result'] != 'OK':
        error = 'The control process did not respond to a request and may be stopped. Check logs for details.'
        if error not in errors:
            errors.append(error)
            write_errors(errors)

def _response(result: str, message: str = None, data: dict = None):
    return {'data': data, 'result': result, 'message': message}

