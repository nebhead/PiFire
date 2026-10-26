#!/usr/bin/env python3

"""
==============================================================================
 PiFire Mobile API v2: Push devices
==============================================================================

Description: Phones register their push relay key so alerts reach them with
  the app closed. Storage and sending live in notify/mobile_push.py.

==============================================================================
"""

from flask import request

from common.common import read_settings, write_settings
from notify.mobile_push import DeviceError, list_devices, register_device, remove_device
from . import mobile_v2_bp
from .routes import fail, handle_errors, ok

DEVICE_ERROR_STATUS = {'invalid_request': 400, 'too_many_devices': 409}


@mobile_v2_bp.route('/push/devices', methods=['POST'])
@handle_errors
def add_device():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return fail('invalid_request', 400, 'Body must be a JSON object')
    try:
        device_id = register_device(
            push_key=body.get('push_key'),
            relay_url=body.get('relay_url'),
            device_name=body.get('device_name'),
            app_version=body.get('app_version'),
        )
    except DeviceError as error:
        return fail(error.code, DEVICE_ERROR_STATUS.get(error.code, 400), error.message)
    return ok({'id': device_id})


@mobile_v2_bp.route('/push/devices', methods=['GET'])
@handle_errors
def get_devices():
    return ok(list_devices())


@mobile_v2_bp.route('/push/devices/<device_id>', methods=['DELETE'])
@handle_errors
def delete_device(device_id):
    if not remove_device(device_id):
        return fail('unknown_device', 404)
    return ok()


@mobile_v2_bp.route('/push/onesignal/<player_id>', methods=['DELETE'])
@handle_errors
def delete_onesignal_device(player_id):
    """An app moving to app push removes its old OneSignal entry, so the phone doesn't get every alert twice."""
    settings = read_settings()
    devices = settings['notify_services']['onesignal']['devices']
    if player_id not in devices:
        return fail('unknown_device', 404)
    devices.pop(player_id)
    write_settings(settings)
    return ok()
