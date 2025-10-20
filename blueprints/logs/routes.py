
import os
from flask import render_template, request, send_file, current_app
from common.common import read_settings, read_control, read_log_file, add_line_numbers
from common.app import paginate_list, allowed_file

from . import logs_bp

@logs_bp.route('/<action>', methods=['POST','GET'])
@logs_bp.route('/', methods=['POST','GET'])
def logs_page(action=None):
    settings = read_settings()
    control = read_control()
    LOGS_FOLDER = current_app.config['LOGS_FOLDER']

    # Get list of log files 
    if not os.path.exists(LOGS_FOLDER):
        os.mkdir(LOGS_FOLDER)
    log_file_list = os.listdir(LOGS_FOLDER)
    for file in log_file_list:
        if not allowed_file(file):
            log_file_list.remove(file)

    if(request.method == 'POST') and ('form' in request.content_type):
        requestform = request.form 

        if 'download' in requestform:
            log_file_name = LOGS_FOLDER + requestform['selectLog']
            return send_file(log_file_name, as_attachment=True, max_age=0)
        elif 'eventslist' in requestform:
            log_file_name = requestform['logfile']
            event_list = read_log_file(LOGS_FOLDER + log_file_name)
            event_list = add_line_numbers(event_list)
            page = int(requestform['page'])
            reverse = True if requestform['reverse'] == 'true' else False
            itemsperpage = int(requestform['itemsperpage'])
            pgntd_data = paginate_list(event_list, reversesortorder=reverse, itemsperpage=itemsperpage, page=page)
            return render_template('_log_list.html', pgntd_data = pgntd_data, log_file_name=log_file_name)
        else:
            return ('Error')

    return render_template('logs/index.html',
                            settings=settings,
                            control=control,
                            log_file_list=log_file_list,
                            page_theme=settings['globals'].get('page_theme', 'light'),
                            grill_name=settings['globals'].get('grill_name', '')
                            )
