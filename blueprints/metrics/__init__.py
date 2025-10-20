from flask import Blueprint

metrics_bp = Blueprint('metrics_bp', __name__,
                     template_folder='templates',
                     static_folder='static',
                     url_prefix='/metrics')

from . import routes
