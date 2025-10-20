from flask import Blueprint

update_bp = Blueprint('update_bp', __name__,
                     template_folder='templates',
                     static_folder='static',
                     url_prefix='/update')

from . import routes
