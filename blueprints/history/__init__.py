from flask import Blueprint

history_bp = Blueprint('history_bp', __name__,
                     template_folder='templates',
                     static_folder='static',
                     url_prefix='/history')

from . import routes
