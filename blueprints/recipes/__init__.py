from flask import Blueprint

recipes_bp = Blueprint('recipes_bp', __name__,
                     template_folder='templates',
                     static_folder='static',
                     url_prefix='/recipes')

from . import routes
