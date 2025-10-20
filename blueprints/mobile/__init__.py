from flask import Blueprint

mobile_bp = Blueprint('mobile', __name__)
# This will be set when registered with the app
socketio = None

from . import socket_io
