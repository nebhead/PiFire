
from flask import render_template, request, current_app, render_template_string, jsonify
from common.common import read_settings, read_control, write_control, read_tr, read_autotune, write_autotune, read_current
from common.app import paginate_list
from .tuner import *

from . import tuner_bp

@tuner_bp.route('/', methods=['POST','GET'])
def tuner_page():
    settings = read_settings()
    control = read_control()
    LOGS_FOLDER = current_app.config['LOGS_FOLDER']

    # This POST path will load/render portions of the tuner page
    if request.method == 'POST' and ('form' in request.content_type):
        requestform = request.form
        if 'command' in requestform.keys():
            if 'render' in requestform['command']:
                render_string = "{% from 'tuner/_macro_tuner.html' import render_" + requestform["value"] + " %}{{ render_" + requestform["value"] + "(settings, control) }}"
                return render_template_string(render_string, settings=settings, control=control)

    # This POST path provides data back to the page
    if request.method == 'POST' and 'json' in request.content_type:
        requestjson = request.json 
        command = requestjson.get('command', None)
        if command == 'stop_tuning':
            if control['tuning_mode']:
                control['tuning_mode'] = False  # Disable tuning mode
                write_control(control, origin='app')
            if control['mode'] == 'Monitor':
                # If in Monitor Mode, stop
                control['mode'] = 'Stop'  # Go to Stop mode
                control['updated'] = True
                write_control(control, origin='app')	
        if command == 'read_tr':
            if not control['tuning_mode']:
                control['tuning_mode'] = True  # Enable tuning mode
                write_control(control, origin='app')

            if control['mode'] == 'Stop':
                # Turn on Monitor Mode if the system is stopped
                control['mode'] = 'Monitor'  # Enable monitor mode
                control['updated'] = True
                write_control(control, origin='app')

            cur_probe_tr = read_tr()
            if requestjson['probe_selected'] in cur_probe_tr.keys():
                return jsonify({ 'trohms' : cur_probe_tr[requestjson['probe_selected']]})
            else:
                return jsonify({ 'trohms' : 0 })
        if command == 'manual_finish' or command == 'auto_finish':
            if control['tuning_mode']:
                control['tuning_mode'] = False  # Disable tuning mode
                write_control(control, origin='app')
            if control['mode'] == 'Monitor':
                # If in Monitor Mode, stop
                control['mode'] = 'Stop'  # Go to Stop mode
                control['updated'] = True
                write_control(control, origin='app')
            
            tunerManualHighTemp = requestjson.get('tunerManualHighTemp', 0.1)
            tunerManualHighTemp = 0 if tunerManualHighTemp == '' else float(tunerManualHighTemp)
            tunerManualHighTr = requestjson.get('tunerManualHighTr', 0.1)
            tunerManualHighTr = 0 if tunerManualHighTr == '' else int(float(tunerManualHighTr))

            tunerManualMediumTemp = requestjson.get('tunerManualMediumTemp', 0.1)
            tunerManualMediumTemp = 0 if tunerManualMediumTemp == '' else float(tunerManualMediumTemp)
            tunerManualMediumTr = requestjson.get('tunerManualMediumTr', 0.1)
            tunerManualMediumTr = 0 if tunerManualMediumTr == '' else int(float(tunerManualMediumTr))

            tunerManualLowTemp = requestjson.get('tunerManualLowTemp', 0.1)
            tunerManualLowTemp = 0 if tunerManualLowTemp == '' else float(tunerManualLowTemp)
            tunerManualLowTr = requestjson.get('tunerManualLowTr', 0.1)
            tunerManualLowTr = 0 if tunerManualLowTr == '' else int(float(tunerManualLowTr))

            a, b, c = calc_shh_coefficients(tunerManualLowTemp, tunerManualMediumTemp,
                                            tunerManualHighTemp, tunerManualLowTr,
                                            tunerManualMediumTr, tunerManualHighTr,
                                            units=settings['globals']['units'])
            tr_points = [int(tunerManualHighTr), int(tunerManualMediumTr), int(tunerManualLowTr)]
            labels, chart_data = calc_shh_chart(a, b, c, units=settings['globals']['units'], temp_range=220, tr_points=tr_points)
            return jsonify({'labels' : labels, 'chart_data' : chart_data, 'coefficients' : {'a' : a, 'b': b, 'c': c}})
        if command == 'read_auto_status':
            first_run = False 
            if not control['tuning_mode']:
                control['tuning_mode'] = True  # Enable tuning mode
                write_control(control, origin='app')
                read_autotune(flush=True)  # Flush autotune data
                first_run = True

            if control['mode'] == 'Stop':
                # Turn on Monitor Mode if the system is stopped
                control['mode'] = 'Monitor'  # Enable monitor mode
                control['updated'] = True
                write_control(control, origin='app')

            status_data = {
                'current_tr' : 0,
                'current_temp' : 0,
                'high_tr' : 0,
                'high_temp' : 0, 
                'medium_tr' : 0,
                'medium_temp' : 0,
                'low_tr' : 0,
                'low_temp' : 0,
                'ready' : False
            }
            
            # Get Tr Data from all probes 
            cur_probe_tr = read_tr()
            if requestjson['probe_selected'] in cur_probe_tr.keys():
                status_data['current_tr'] = cur_probe_tr[requestjson['probe_selected']]
            else:
                status_data['current_tr'] = -1
            
            # Get Temp Data from all probes 
            cur_probe_temps = read_current()
            if requestjson['probe_reference'] in cur_probe_temps['P'].keys():
                status_data['current_temp'] = cur_probe_temps['P'][requestjson['probe_reference']]
            elif requestjson['probe_reference'] in cur_probe_temps['F'].keys():
                status_data['current_temp'] = cur_probe_temps['F'][requestjson['probe_reference']]
            elif requestjson['probe_reference'] in cur_probe_temps['AUX'].keys():
                status_data['current_temp'] = cur_probe_temps['AUX'][requestjson['probe_reference']]
            else:
                status_data['current_temp'] = -1

            # Some probes (i.e. the DS18B20) may be slow to respond when Monitor mode starts, and may report 0 degrees
            # Thus we should ignore these first few data points if they are 0
            autotune_data_size = read_autotune(size_only=True)
            if (autotune_data_size > 4 or status_data['current_temp'] > 0) and \
                    status_data['current_tr'] >= 0 and \
                    status_data['current_temp'] >= 0 and \
                    not first_run:
                # Record Temperature / Tr Values in Auto-Tune Record
                data = {
                    'ref_T' : status_data['current_temp'],
                    'probe_Tr' : status_data['current_tr']
                }
                write_autotune(data)

            data = read_autotune()
            if len(data) > 10:
                # If more than 10 datapoints, then calculate high / low / medium
                temp_list = []
                tr_list = []
                for datapoint in data:
                    '''
                    Check if the ref_T value is already in the list and overwrite if so.
                    This assumes that the last temperature is the most recent and is likely 
                    the most accurate resistance value to take.
                    '''
                    if datapoint['ref_T'] in temp_list:
                        index = temp_list.index(datapoint['ref_T'])
                        tr_list[index] = datapoint['probe_Tr']
                    else:
                        temp_list.append(datapoint['ref_T'])
                        tr_list.append(datapoint['probe_Tr'])

                # Determine High Temp / Tr
                status_data['high_temp'] = max(temp_list)
                index = temp_list.index(max(temp_list))
                status_data['high_tr'] = tr_list[index]

                # Determine Low Temp / Tr 
                status_data['low_temp'] = min(temp_list)
                index = temp_list.index(min(temp_list))
                status_data['low_tr'] = tr_list[index]

                # Determine Medium Temp / Tr
                # Find best fit to Medium Temp
                medium_temp = ((status_data['high_temp'] - status_data['low_temp']) // 2) + status_data['low_temp']
                delta_temp = 1000  # Initial value is outside of any normal expected bounds
                for index, temp in enumerate(temp_list):
                    if abs(temp - medium_temp) < delta_temp:
                        delta_temp = abs(temp - medium_temp)
                        delta_index = index
                status_data['medium_temp'] = temp_list[delta_index]
                status_data['medium_tr'] = tr_list[delta_index]
                # Minimum range to be able to calculate temp
                if settings['globals']['units'] == 'F':
                    min_range = 50
                else:
                    min_range = 25

                if (status_data['high_temp'] - status_data['low_temp']) >= min_range:
                    status_data['ready'] = True

            return jsonify(status_data)

    return render_template(
                            'tuner/index.html',
                            settings=settings,
                            control=control,
                            page_theme=settings['globals'].get('page_theme', 'light'),
                            grill_name=settings['globals'].get('grill_name', '')
                            )
