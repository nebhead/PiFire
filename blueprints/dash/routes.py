
from flask import render_template, request, redirect, render_template_string
from common.common import read_settings, read_control, process_command, read_errors, read_warnings, read_probe_status, write_settings, read_generic_json
from common.app import get_system_command_output

from . import dash_bp

@dash_bp.route('/', methods=['POST','GET'])
def dash_page():
    settings = read_settings()
    control = read_control()
    errors = read_errors()
    warnings = read_warnings()

    current = settings['dashboard'].get('current', 'Default')
    dash_template = f"{current.lower()}/{settings['dashboard']['dashboards'][current].get('html_name', 'dash_default.html')}"
    dash_data = settings['dashboard']['dashboards'].get(current, {})
    probe_status = read_probe_status(settings['probe_settings']['probe_map']['probe_info'])

    ''' Check if control process is up and running. '''
    process_command(action='sys', arglist=['check_alive'], origin='dash')  # Request supported commands 
    data = get_system_command_output(requested='check_alive')
    if data['result'] != 'OK':
        errors.append('The control process did not respond to a request and may be stopped.  Try reloading the page or restarting the system.  Check logs for details.')

    return render_template(
                            dash_template,
                            settings=settings,
                            control=control,
                            dash_data=dash_data,
                            probe_status=probe_status,
                            errors=errors,
                            warnings=warnings,
                            page_theme=settings['globals'].get('page_theme', 'light'),
                            grill_name=settings['globals'].get('grill_name', '')
                            )

@dash_bp.route('/config', methods=['POST','GET'])
def dash_config():
	settings = read_settings()
	current = settings['dashboard']['current']
	dash_data = settings['dashboard']['dashboards'].get(current, {})
	meta_data_filename = dash_data.get('metadata', None)
	dash_metadata = read_generic_json(f'./dashboard/{meta_data_filename}')

	if request.method == 'GET':
		render_string = "{% from '_macro_generic_config.html' import render_dash_config_card %}{{ render_dash_config_card(dash_metadata, dash_data) }}"
		return render_template_string(
			                render_string, 
							dash_metadata=dash_metadata, 
							dash_data=dash_data
                          )
	elif request.method == 'POST':
		dash_config_request = request.form
		for key, value in dash_config_request.items():
			if 'dashConfig_' in key:
				dash_data['config'][key.replace('dashConfig_','')] = value
		settings['dashboard']['dashboards'][current]['config'] = dash_data['config']
		write_settings(settings)
		return redirect('/dash')
	
	return 'Bad Request'