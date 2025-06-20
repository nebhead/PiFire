from flask import Blueprint

settings_bp = Blueprint('settings_bp', __name__,
                     template_folder='templates',
                     static_folder='static',
                     url_prefix='/settings')

from . import routes
