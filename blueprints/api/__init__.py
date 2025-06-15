from flask import Blueprint

api_bp = Blueprint('api_bp', __name__,
                     template_folder='templates',
                     static_folder='static',
                     url_prefix='/api')

from . import routes
