from flask import render_template
from common.common import read_settings, read_control

from . import manual_bp

@manual_bp.route('/', methods=['POST','GET'])
def manual_page(action=None):
    settings = read_settings()
    control = read_control()
    return render_template('manual/index.html',
                            settings=settings,
                            control=control,
                            page_theme=settings['globals'].get('page_theme', 'light'),
                            grill_name=settings['globals'].get('grill_name', '')
                            )
