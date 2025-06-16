from flask import Blueprint

pellets_bp = Blueprint('pellets_bp', __name__,
                     template_folder='templates',
                     static_folder='static',
                     url_prefix='/pellets')

from . import routes
