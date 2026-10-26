#!/usr/bin/env python3

"""
==============================================================================
 PiFire Mobile API v2: Live stream (Server-Sent Events)
==============================================================================

Description: Replaces the Socket.IO emit loop. Each client gets a snapshot on
  connect, then an event whenever a payload changes (checked once a second),
  alerts as they fire, and a ping every 15 seconds.

==============================================================================
"""

import json
import logging
import time

from flask import Response, stream_with_context

from blueprints.mobile.app_data import check_control_status, get_dash_data
from common.common import read_events_redis, read_pellets_redis, read_settings_redis
from notify.mobile_push import alerts_after, latest_sequence
from . import mobile_v2_bp

POLL_SECONDS = 1
PING_SECONDS = 15
CONTROL_CHECK_SECONDS = 30
RETRY_MS = 5000

logger = logging.getLogger(__name__)

# Shared by all streams so the control process is checked once per server, not once per client.
last_control_check = 0.0


def event(name, payload):
    return f'event: {name}\ndata: {json.dumps(payload)}\n\n'


def snapshot():
    settings = read_settings_redis()
    pelletdb = read_pellets_redis()
    uuid = settings['server_info']['uuid']
    return {
        'dash': get_dash_data(settings, pelletdb),
        'pellets': {'uuid': uuid, 'pellets': pelletdb},
        'events': {'uuid': uuid, 'events': read_events_redis()},
        'settings': settings,
    }


def check_control():
    global last_control_check
    now = time.time()
    if now - last_control_check > CONTROL_CHECK_SECONDS:
        last_control_check = now
        check_control_status()


@mobile_v2_bp.route('/stream', methods=['GET'])
def stream():
    def generate():
        previous = {}
        alert_seq = latest_sequence()
        last_write = time.time()
        yield f'retry: {RETRY_MS}\n\n'
        while True:
            try:
                check_control()
                for name, payload in snapshot().items():
                    if previous.get(name) != payload:
                        previous[name] = payload
                        last_write = time.time()
                        yield event(name, payload)
                for item in alerts_after(alert_seq):
                    alert_seq = item['seq']
                    last_write = time.time()
                    yield event('alert', item['alert'])
            except GeneratorExit:
                raise
            except Exception:
                # Keep the stream up through a bad read; the next loop tries again.
                logger.exception('Mobile API v2: stream update failed')
            if time.time() - last_write >= PING_SECONDS:
                last_write = time.time()
                yield ': ping\n\n'
            # Cooperative under gunicorn's eventlet worker, which patches time.sleep.
            time.sleep(POLL_SECONDS)

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )
