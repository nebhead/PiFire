'''
==============================================================================
 PiFire Web UI (Flask App) Process
==============================================================================

Description: 
  This script will start at boot, and start up the web user
  interface.
  
  This script runs as a separate process from the control program
  implementation which handles interfacing the hardware directly.

==============================================================================
'''

'''
==============================================================================
 Imported Modules
==============================================================================
'''

from flask import Flask, render_template, redirect
from flask_mobility import Mobility
from flask_socketio import SocketIO
from flask_qrcode import QRcode
from werkzeug.exceptions import InternalServerError
from common.common import read_settings, is_real_hardware

'''
==============================================================================
 Constants & Globals 
==============================================================================
'''
from config import ProductionConfig  # ProductionConfig or DevelopmentConfig

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
QRcode(app)
Mobility(app)

''' Load Configuration Settings '''
# Use ProductionConfig for production environment, DevelopmentConfig for development
# Uncomment the line below to switch to DevelopmentConfig
# app.config.from_object(DevelopmentConfig)
app.config.from_object(ProductionConfig)

''' Flask Blueprints '''
from blueprints.admin import admin_bp
from blueprints.api import api_bp
from blueprints.events import events_bp
from blueprints.logs import logs_bp
from blueprints.manifest import manifest_bp
from blueprints.manual import manual_bp
from blueprints.history import history_bp
from blueprints.metrics import metrics_bp
from blueprints.dash import dash_bp
from blueprints.pellets import pellets_bp
from blueprints.cookfile import cookfile_bp
from blueprints.tuner import tuner_bp
from blueprints.probeconfig import probeconfig_bp
from blueprints.recipes import recipes_bp
from blueprints.settings import settings_bp
from blueprints.wizard import wizard_bp
from blueprints.update import update_bp

''' Register Flask Blueprints '''
app.register_blueprint(admin_bp, url_prefix='/admin')
app.register_blueprint(api_bp, url_prefix='/api')
app.register_blueprint(events_bp, url_prefix='/events')
app.register_blueprint(logs_bp, url_prefix='/logs')
app.register_blueprint(manifest_bp, url_prefix='/manifest')
app.register_blueprint(manual_bp, url_prefix='/manual')
app.register_blueprint(history_bp, url_prefix='/history')
app.register_blueprint(metrics_bp, url_prefix='/metrics')
app.register_blueprint(dash_bp, url_prefix='/dash')
app.register_blueprint(pellets_bp, url_prefix='/pellets')
app.register_blueprint(cookfile_bp, url_prefix='/cookfile')
app.register_blueprint(tuner_bp, url_prefix='/tuner')
app.register_blueprint(probeconfig_bp, url_prefix='/probeconfig')
app.register_blueprint(recipes_bp, url_prefix='/recipes')
app.register_blueprint(settings_bp, url_prefix='/settings')
app.register_blueprint(wizard_bp, url_prefix='/wizard')
app.register_blueprint(update_bp, url_prefix='/update')

'''
==============================================================================
 App Routes
==============================================================================
'''

@app.errorhandler(InternalServerError)
def handle_500(e):
	''' Handle 500 Server Error '''
	return render_template('server_error.html'), 500

@app.route('/')
def index():
	settings = read_settings()
	
	if settings['globals']['first_time_setup']:
		return redirect('/wizard/welcome')
	else: 
		return redirect('/dash')

'''
==============================================================================
 SocketIO Section
==============================================================================
'''
import mobile.socket_io

'''
==============================================================================
 Main Program Start
==============================================================================
'''

if __name__ == '__main__':
	if is_real_hardware():
		socketio.run(app, host='0.0.0.0')
	else:
		socketio.run(app, host='0.0.0.0', debug=True)

