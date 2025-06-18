from flask import Blueprint

probeconfig_bp = Blueprint('probeconfig_bp', __name__,
                     template_folder='templates',
                     static_folder='static',
                     url_prefix='/probeconfig')

from . import routes
