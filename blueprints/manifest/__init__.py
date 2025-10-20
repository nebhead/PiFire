from flask import Blueprint

manifest_bp = Blueprint('manifest_bp', __name__,
                     template_folder='templates',
                     static_folder='static',
                     url_prefix='/manifest')

from . import routes
