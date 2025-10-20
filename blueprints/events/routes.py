
from flask import render_template, request
from common.common import read_settings, read_control, read_events
from common.app import paginate_list

from . import events_bp

@events_bp.route('/<action>', methods=['POST','GET'])
@events_bp.route('/', methods=['POST','GET'])
def events_page(action=None):
    settings = read_settings()
    control = read_control()

    if(request.method == 'POST') and ('form' in request.content_type):
        requestform = request.form 
        if 'eventslist' in requestform:
            event_list = read_events(legacy=False)
            page = int(requestform['page'])
            reverse = True if requestform['reverse'] == 'true' else False
            itemsperpage = int(requestform['itemsperpage'])
            pgntd_data = paginate_list(event_list, reversesortorder=reverse, itemsperpage=itemsperpage, page=page)
            return render_template('events/_events_list.html', pgntd_data = pgntd_data)
        else:
            return ('Error')

    return render_template('events/index.html',
                            settings=settings,
                            control=control,
                            page_theme=settings['globals'].get('page_theme', 'light'),
                            grill_name=settings['globals'].get('grill_name', '')
                            )
