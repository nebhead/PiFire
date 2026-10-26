#!/usr/bin/env python3

"""
==============================================================================
 PiFire Mobile Push
==============================================================================

Description: Alerts for the mobile app (API v2).

  - Alert feed: notifications are sent by the control process while the live
    stream runs in the web app, so alerts pass through Redis: a numbered list
    of the most recent alerts that each stream reads past its last seen number.
  - Devices: phones register their push relay key here (push_devices.json).
    Keys never leave this file: not in settings, logs or API responses.
  - Relay sends: each alert goes to every device's push relay in a background
    thread, so a slow relay never holds up the caller.

  Lives in notify/ so the control process can use it without importing the
  web app. Payloads are a contract with the app: see the app repo's
  docs/V2_API.md and docs/PUSH.md.

==============================================================================
"""

import fcntl
import hashlib
import json
import logging
import os
import re
import threading
import time
import uuid

import requests

from common.common import cmdsts, read_pellets_redis

ALERTS_KEY = 'mobile:v2:alerts'
SEQUENCE_KEY = 'mobile:v2:alert_seq'
MAX_KEPT = 50

DEVICES_FILE = 'push_devices.json'
MAX_DEVICES = 20
PUSH_KEY = re.compile(r'^pfk_[A-Za-z0-9_-]{43}$')
MAX_URL_LENGTH = 200
MAX_NAME_LENGTH = 64

SEND_TIMEOUT_SECONDS = 5
SEND_TRIES = 3
# The relay may not know a brand-new key for about a minute (KV is eventually consistent), so a
# device is only dropped after it has been unknown for a day.
NOT_FOUND_GRACE_SECONDS = 24 * 60 * 60

logger = logging.getLogger(__name__)

'''
==============================================================================
 Alert feed
==============================================================================
'''


def publish_alert(alert):
    """Adds an alert (the relay send body without push_key) for every open stream. Never raises."""
    try:
        seq = cmdsts.incr(SEQUENCE_KEY)
        if seq is None:
            return  # Redis unavailable; the push still goes out through the relay
        cmdsts.lpush(ALERTS_KEY, json.dumps({'seq': seq, 'alert': alert}))
        cmdsts.ltrim(ALERTS_KEY, 0, MAX_KEPT - 1)
    except Exception:
        logger.exception('Mobile push: could not publish alert to the stream')


def latest_sequence():
    return int(cmdsts.get(SEQUENCE_KEY) or 0)


def alerts_after(seq):
    """Alerts newer than seq, oldest first."""
    newer = []
    for raw in cmdsts.lrange(ALERTS_KEY, 0, MAX_KEPT - 1) or []:
        try:
            item = json.loads(raw)
        except (TypeError, ValueError):
            continue
        if item.get('seq', 0) > seq:
            newer.append(item)
    return sorted(newer, key=lambda item: item['seq'])


'''
==============================================================================
 Devices
==============================================================================
'''


class DeviceError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def device_id(push_key):
    return hashlib.sha256(push_key.encode('utf-8')).hexdigest()[:16]


def _update_devices(change):
    """Read-modify-write of the device file under a lock: the web app and control process both write it."""
    fd = os.open(DEVICES_FILE, os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(fd, 'r+', encoding='utf-8') as file:
        fcntl.flock(file, fcntl.LOCK_EX)
        try:
            devices = json.loads(file.read() or '[]')
        except ValueError:
            logger.warning('Mobile push: %s unreadable, starting empty', DEVICES_FILE)
            devices = []
        result = change(devices)
        file.seek(0)
        file.truncate()
        json.dump(devices, file)
        return result


def _read_devices():
    try:
        with open(DEVICES_FILE, encoding='utf-8') as file:
            fcntl.flock(file, fcntl.LOCK_SH)
            return json.loads(file.read() or '[]')
    except (OSError, ValueError):
        return []


def _public(device):
    return {key: device.get(key) for key in ('id', 'device_name', 'app_version', 'registered')}


def register_device(push_key, relay_url, device_name, app_version):
    """Adds or refreshes a device; returns its id."""
    if not isinstance(push_key, str) or not PUSH_KEY.match(push_key):
        raise DeviceError('invalid_request', 'push_key is not a valid push key')
    if not isinstance(relay_url, str) or not relay_url.startswith('https://') or len(relay_url) > MAX_URL_LENGTH:
        raise DeviceError('invalid_request', 'relay_url must be an https URL')
    record = {
        'id': device_id(push_key),
        'key': push_key,
        'relay_url': relay_url.rstrip('/'),
        'device_name': str(device_name or '')[:MAX_NAME_LENGTH],
        'app_version': str(app_version or '')[:MAX_NAME_LENGTH],
        'registered': int(time.time()),
        'not_found_since': None,
    }

    def change(devices):
        for index, device in enumerate(devices):
            if device.get('id') == record['id']:
                devices[index] = record
                return record['id']
        if len(devices) >= MAX_DEVICES:
            raise DeviceError('too_many_devices', f'At most {MAX_DEVICES} devices can be registered')
        devices.append(record)
        return record['id']

    return _update_devices(change)


def list_devices():
    return [_public(device) for device in _read_devices()]


def remove_device(target_id):
    """Removes a device; True if it existed."""
    def change(devices):
        before = len(devices)
        devices[:] = [device for device in devices if device.get('id') != target_id]
        return len(devices) != before

    return _update_devices(change)


def _mark_not_found(target_id):
    """Starts or checks a device's not-found grace period; removes it once that has passed."""
    now = int(time.time())

    def change(devices):
        for device in devices:
            if device.get('id') == target_id:
                since = device.get('not_found_since') or now
                device['not_found_since'] = since
                if now - since > NOT_FOUND_GRACE_SECONDS:
                    devices.remove(device)
                    return True
        return False

    return _update_devices(change)


def _clear_not_found(target_id):
    def change(devices):
        for device in devices:
            if device.get('id') == target_id and device.get('not_found_since'):
                device['not_found_since'] = None

    _update_devices(change)


'''
==============================================================================
 Alerts
==============================================================================
'''


def _probe_name(settings, label):
    for probe in settings['probe_settings']['probe_map']['probe_info']:
        if probe['label'] == label:
            return probe.get('name') or label
    return label


def build_alert(notify_event, settings, control, label='Probe', target=0, error_grill_temp=0, limit_type=None,
                title='', body=''):
    """
    The alert for a send_notifications event, or None for an event the app has no type for.
    Never raises: a push problem must not break the notification path or the control loop.
    """
    try:
        return _build_alert(notify_event, settings, control, label, target, error_grill_temp, limit_type, title, body)
    except Exception:
        logger.exception('Mobile push: could not build alert for %s', notify_event)
        return None


def _build_alert(notify_event, settings, control, label, target, error_grill_temp, limit_type, title, body):
    units = settings['globals']['units']
    probe = {'probe_label': label, 'probe_name': _probe_name(settings, label), 'units': units}
    startup = {'temp': error_grill_temp, 'startup_temp': control['safety']['startuptemp'], 'units': units}

    if 'Probe_Temp_Achieved' in notify_event:
        alert_type, data = 'probe_target', {**probe, 'target': target}
    elif 'Probe_Temp_Limit_Alarm' in notify_event:
        alert_type, data = 'probe_limit', {**probe, 'limit': target}
        if limit_type in ('probe_limit_high', 'probe_limit_low'):
            data['direction'] = 'high' if limit_type == 'probe_limit_high' else 'low'
    elif 'Timer_Expired' in notify_event:
        alert_type, data = 'timer_expired', None
    elif 'Pellet_Level_Low' in notify_event:
        alert_type, data = 'pellet_level_low', {'level': _hopper_level()}
    elif 'Grill_Error_00' in notify_event:
        alert_type, data = 'grill_error', None
    elif 'Grill_Error_01' in notify_event:
        alert_type = 'grill_error_max_temp'
        data = {'temp': error_grill_temp, 'max_temp': settings['safety']['maxtemp'], 'units': units}
    elif 'Grill_Error_02' in notify_event:
        alert_type, data = 'grill_error_startup_temp', startup
    elif 'Grill_Error_03' in notify_event:
        alert_type, data = 'grill_reignite', startup
    elif 'Grill_Warning' in notify_event:
        alert_type, data = 'grill_warning', None
    elif 'Recipe_Step_Message' in notify_event:
        alert_type, data = 'recipe_message', {'message': str(control['recipe']['step_data']['message'])[:500]}
    elif 'Test_Notify' in notify_event:
        alert_type, data = 'test', None
    elif 'Control_Process_Stopped' in notify_event:
        alert_type, data = 'control_stopped', None
    else:
        return None

    alert = {
        'alert_id': str(uuid.uuid4()),
        'type': alert_type,
        'server_uuid': settings['server_info']['uuid'],
        'time': int(time.time()),
        'fallback': {'title': str(title)[:100], 'body': str(body)[:500]},
    }
    if data is not None:
        alert['data'] = data
    return alert


def _hopper_level():
    try:
        return read_pellets_redis()['current']['hopper_level']
    except (KeyError, TypeError):
        return None


def send_mobile_push(alert):
    """Sends an alert to every phone registered for app push, in a background thread. Never raises."""
    try:
        devices = _read_devices()
        if devices:
            threading.Thread(target=_send_to_devices, args=(alert, devices), daemon=True).start()
    except Exception:
        logger.exception('Mobile push: could not start sending alert %s', alert.get('alert_id'))


def _send_to_devices(alert, devices):
    for device in devices:
        try:
            _send_to_device(alert, device)
        except Exception:
            logger.exception('Mobile push: send to device %s failed', device.get('id'))


def _send_to_device(alert, device):
    body = {'push_key': device['key'], **alert}
    url = f"{device['relay_url']}/v1/send"
    for attempt in range(SEND_TRIES):
        if attempt:
            time.sleep(2 ** attempt)
        try:
            response = requests.post(url, json=body, timeout=SEND_TIMEOUT_SECONDS)
        except requests.RequestException as error:
            logger.warning('Mobile push: relay unreachable for device %s: %s', device['id'], type(error).__name__)
            continue
        if response.status_code == 200:
            if device.get('not_found_since'):
                _clear_not_found(device['id'])
            return
        if response.status_code == 410:
            remove_device(device['id'])
            logger.info('Mobile push: device %s is no longer registered with the relay, removed', device['id'])
            return
        if response.status_code == 404:
            if _mark_not_found(device['id']):
                logger.info('Mobile push: device %s unknown to the relay for a day, removed', device['id'])
            return
        if response.status_code == 429 or response.status_code >= 500:
            logger.warning('Mobile push: relay returned %s for device %s', response.status_code, device['id'])
            continue
        logger.warning('Mobile push: relay rejected alert for device %s with %s', device['id'], response.status_code)
        return
