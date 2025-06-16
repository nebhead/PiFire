
from flask import render_template, request, current_app, jsonify, send_file, redirect
import os
import time
from common.common import read_settings, read_control, read_current, write_settings, epoch_to_time, prepare_csv
from common.app import create_ui_hash, prepare_annotations, prepare_event_totals
from file_mgmt.cookfile import read_cookfile, prepare_chartdata

from . import history_bp

@history_bp.route('/<action>', methods=['POST','GET'])
@history_bp.route('/', methods=['POST','GET'])
def history_page(action=None):
    settings = read_settings()
    control = read_control()
    HISTORY_FOLDER = current_app.config['HISTORY_FOLDER']
    errors = []

    if action == 'stream':
        # GET - Read current temperatures and set points for history streaming 
        control = read_control()
        json_response = {}
        if control['mode'] in ['Stop', 'Error']:
            json_response['current'] = read_current(zero_out=True) # Probe Temps Zero'd Out
        else:
            json_response['current'] = read_current() # Probe Temps Zero'd Out

        # Calculate Displayed Start Time
        displayed_starttime = time.time() - (settings['history_page']['minutes'] * 20)
        json_response['annotations'] = prepare_annotations(displayed_starttime)
        json_response['mode'] = control['mode']
        json_response['ui_hash'] = create_ui_hash()
        json_response['timestamp'] = int(time.time() * 1000)
        
        return jsonify(json_response)

    elif action == 'refresh':
        # POST - Get number of minutes into the history to refresh the history chart
        control = read_control()
        request_json = request.json
        if 'num_mins' in request_json:
            num_items = int(request_json['num_mins']) * 20 if int(request_json['num_mins']) > 0 else 20 # Calculate number of items requested
            settings['history_page']['minutes'] = int(request_json['num_mins']) if int(request_json['num_mins']) > 0 else 1
            write_settings(settings)
        elif 'zoom' in request_json:
            num_items = int(request_json['zoom']) * 20
        else: 
            num_items = int(settings['history_page']['minutes'] * 20)

        # Get Chart Data Structures
        json_response = prepare_chartdata(settings['history_page']['probe_config'], num_items=num_items, reduce=True, data_points=settings['history_page']['datapoints'])
        json_response['ui_hash'] = create_ui_hash()
        # Calculate Displayed Start Time
        displayed_starttime = time.time() - (int(num_items / 20) * 60)
        json_response['annotations'] = prepare_annotations(displayed_starttime)
        '''
        json_response = {
            'annotations' : [], 
            'time_labels' : time_labels,
            'probe_mapper' : probe_mapper, 
            'chart_data' : chart_data
        }		
        '''
        return jsonify(json_response)

    if request.method == 'POST':
        response = request.form
        if(action == 'cookfile'):
            if('delcookfile' in response):
                filename = './history/' + response["delcookfile"]
                os.remove(filename)
                return redirect('/history')
            if('opencookfile' in response):
                cookfilename = HISTORY_FOLDER + response['opencookfile']
                cookfilestruct, status = read_cookfile(cookfilename)
                if(status == 'OK'):
                    events = cookfilestruct['events']
                    event_totals = prepare_event_totals(events)
                    comments = cookfilestruct['comments']
                    for comment in comments:
                        comment['text'] = comment['text'].replace('\n', '<br>')
                    metadata = cookfilestruct['metadata']
                    metadata['starttime'] = epoch_to_time(metadata['starttime'] / 1000)
                    metadata['endtime'] = epoch_to_time(metadata['endtime'] / 1000)
                    labels = cookfilestruct['graph_labels']
                    assets = cookfilestruct['assets']
                    filenameonly = response['opencookfile']
                    return render_template('cookfile.html', settings=settings, cookfilename=cookfilename, 
                        filenameonly=filenameonly, events=events, event_totals=event_totals, comments=comments, 
                        metadata=metadata, labels=labels, assets=assets, errors=errors, 
                        page_theme=settings['globals']['page_theme'], grill_name=settings['globals']['grill_name'])
                else:
                    errors.append(status)
                    if 'version' in status:
                        errortype = 'version'
                    elif 'asset' in status: 
                        errortype = 'asset'
                    else: 
                        errortype = 'other'
                    return render_template('cferror.html', settings=settings, cookfilename=cookfilename, errortype=errortype, errors=errors, page_theme=settings['globals']['page_theme'], grill_name=settings['globals']['grill_name'])
            if('dlcookfile' in response):
                filename = './history/' + response['dlcookfile']
                return send_file(filename, as_attachment=True, max_age=0)

        if(action == 'setmins'):
            if('minutes' in response):
                if(response['minutes'] != ''):
                    num_items = int(response['minutes']) * 20
                    settings['history_page']['minutes'] = int(response['minutes'])
                    write_settings(settings)

    elif (request.method == 'GET') and (action == 'export'):
        exportfilename = prepare_csv()
        return send_file(exportfilename, as_attachment=True, max_age=0)

    return render_template(
                            'history/index.html',
                            settings=settings,
                            control=control,
                            page_theme=settings['globals'].get('page_theme', 'light'),
                            grill_name=settings['globals'].get('grill_name', '')
                            )
