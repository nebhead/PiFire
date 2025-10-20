from flask import Blueprint

logs_bp = Blueprint('logs_bp', __name__,
                     template_folder='templates',
                     static_folder='static',
                     url_prefix='/logs')

from . import routes
