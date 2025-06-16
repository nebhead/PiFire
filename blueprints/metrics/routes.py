import datetime
from flask import render_template, request, send_file
from common.common import read_settings, read_control, read_metrics, process_metrics
from common.app import prepare_metrics_csv

from . import metrics_bp

@metrics_bp.route('/<action>', methods=['POST','GET'])
@metrics_bp.route('/', methods=['POST','GET'])
def metrics_page(action=None):
    settings = read_settings()
    control = read_control()

    metrics_data = process_metrics(read_metrics(all=True))

    if (request.method == 'GET') and (action == 'export'):
        filename = datetime.datetime.now().strftime('%Y%m%d-%H%M') + '-PiFire-Metrics-Export'
        csvfilename = prepare_metrics_csv(metrics_data, filename)
        return send_file(csvfilename, as_attachment=True, max_age=0)

    return render_template(
                            'metrics/index.html',
                            settings=settings,
                            control=control,
                            metrics_data=metrics_data,
                            page_theme=settings['globals'].get('page_theme', 'light'),
                            grill_name=settings['globals'].get('grill_name', '')
                        )
