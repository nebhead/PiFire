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
from flask import request
from app import socketio
from threading import Event
from blueprints.mobile.app_data import (
    get_app_data as _get_app_data,
    post_app_data as _post_app_data,
    get_dash_data as _get_dash_data,
    check_control_status as _check_control_status,
    _response,
)

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


from flask_socketio import emit

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

    check_control_time = time.time()

    previous_dash = ''
    previous_event = ''
    previous_pellet = ''

    try:
        while event.is_set():
            now = time.time()
            if (now - check_control_time) > 30:
                check_control_time = now
                _check_control_status()

            settings = read_settings_redis()
            pelletdb = read_pellets_redis()
            uuid = settings['server_info']['uuid']

            pellet_data = {
                'uuid': uuid,
                'pellets': pelletdb
            }

            event_data = {
                'uuid': uuid,
                'events': read_events_redis()
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
