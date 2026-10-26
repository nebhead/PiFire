from flask import Blueprint

# Mobile app API v2: HTTP + Server-Sent Events, mounted at /mobile/v2 in app.py.
mobile_v2_bp = Blueprint('mobile_v2', __name__)

from . import routes, stream, push
