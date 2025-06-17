
import datetime
import os
from flask import render_template, request, current_app, jsonify, redirect, send_file
from werkzeug.utils import secure_filename
from common.common import read_settings, epoch_to_time, generate_uuid
from common.app import prepare_annotations, prepare_metrics_csv, allowed_file, prepare_csv, prepare_event_totals, paginate_list, create_safe_name
from file_mgmt.cookfile import read_cookfile, upgrade_cookfile
from file_mgmt.common import fixup_assets, read_json_file_data, update_json_file_data, remove_assets
from file_mgmt.media import add_asset, set_thumbnail, unpack_thumb

from . import cookfile_bp

@cookfile_bp.route('/', methods=['POST','GET'])
def cookfile_page():
    settings = read_settings()
    HISTORY_FOLDER = current_app.config['HISTORY_FOLDER']

    errors = []

    if(request.method == 'POST') and ('json' in request.content_type):
        requestjson = request.json
        if('full_graph' in requestjson):
            filename = requestjson['filename']
            cookfiledata, status = read_cookfile(filename)

            if(status == 'OK'):
                annotations = prepare_annotations(0, cookfiledata['events'])

                json_data = {
                    'chart_data' : cookfiledata['graph_data']['chart_data'],
                    'time_labels' : cookfiledata['graph_data']['time_labels'],
                    'probe_mapper' : cookfiledata['graph_data']['probe_mapper'],
                    'annotations' : annotations
                }
                return jsonify(json_data)

        if('getcommentassets' in requestjson):
            assetlist = []
            cookfilename = requestjson['cookfilename']
            commentid = requestjson['commentid']
            comments, status = read_json_file_data(cookfilename, 'comments')
            for comment in comments:
                if comment['id'] == commentid:
                    assetlist = comment['assets']
                    break
            return jsonify({'result' : 'OK', 'assetlist' : assetlist})

        if('managemediacomment' in requestjson):
            # Grab list of all assets in file, build assetlist
            assetlist = []
            cookfilename = requestjson['cookfilename']
            commentid = requestjson['commentid']
            
            assets, status = read_json_file_data(cookfilename, 'assets')
            metadata, status = read_json_file_data(cookfilename, 'metadata')
            for asset in assets:
                asset_object = {
                    'assetname' : asset['filename'],
                    'assetid' : asset['id'],
                    'selected' : False
                }
                assetlist.append(asset_object)

            # Grab list of selected assets in comment currently
            selectedassets = []
            comments, status = read_json_file_data(cookfilename, 'comments')
            for comment in comments:
                if comment['id'] == commentid:
                    selectedassets = comment['assets']
                    break 

            # For each item in asset list, if in comment, mark selected
            for object in assetlist:
                if object['assetname'] in selectedassets:
                    object['selected'] = True 

            return jsonify({'result' : 'OK', 'assetlist' : assetlist}) 

        if('getallmedia' in requestjson):
            # Grab list of all assets in file, build assetlist
            assetlist = []
            cookfilename = requestjson['cookfilename']
            assets, status = read_json_file_data(cookfilename, 'assets')

            for asset in assets:
                asset_object = {
                    'assetname' : asset['filename'],
                    'assetid' : asset['id'],
                }
                assetlist.append(asset_object)

            return jsonify({'result' : 'OK', 'assetlist' : assetlist}) 

        if('navimage' in requestjson):
            direction = requestjson['navimage']
            mediafilename = requestjson['mediafilename'] 
            commentid = requestjson['commentid']
            cookfilename = requestjson['cookfilename']

            comments, status = read_json_file_data(cookfilename, 'comments')
            if status == 'OK':
                assetlist = []
                for comment in comments:
                    if comment['id'] == commentid:
                        assetlist = comment['assets']
                        break 
                current = 0
                found = False 
                for index in range(0, len(assetlist)):
                    if assetlist[index] == mediafilename:
                        current = index
                        found = True 
                        break 
                
                if found and direction == 'next':
                    if current == len(assetlist)-1:
                        mediafilename = assetlist[0]
                    else:
                        mediafilename = assetlist[current+1]
                    return jsonify({'result' : 'OK', 'mediafilename' : mediafilename})
                elif found and direction == 'prev':
                    if current == 0:
                        mediafilename = assetlist[-1]
                    else:
                        mediafilename = assetlist[current-1]
                    return jsonify({'result' : 'OK', 'mediafilename' : mediafilename})

        errors.append('Something unexpected has happened.')
        return jsonify({'result' : 'ERROR', 'errors' : errors})

    if(request.method == 'POST') and ('form' in request.content_type):
        requestform = request.form 
        if('dl_cookfile' in requestform):
            # Download the full JSON Cook File Locally
            filename = requestform['dl_cookfile']
            return send_file(filename, as_attachment=True, max_age=0)

        if('dl_eventfile' in requestform):
            filename = requestform['dl_eventfile']
            cookfiledata, status = read_json_file_data(filename, 'events')
            if(status == 'OK'):
                csvfilename = prepare_metrics_csv(cookfiledata, filename)
                return send_file(csvfilename, as_attachment=True, max_age=0)

        if('dl_graphfile' in requestform):
            # Download CSV of the raw temperature data (and extended data)
            filename = requestform['dl_graphfile']
            cookfiledata, status = read_cookfile(filename)
            if(status == 'OK'):
                csvfilename = prepare_csv(cookfiledata['raw_data'], filename)
                return send_file(csvfilename, as_attachment=True, max_age=0)

        if('ulcookfilereq' in requestform):
            # Assume we have request.files and localfile in response
            remotefile = request.files['ulcookfile']
            
            if (remotefile.filename != ''):
                # If the user does not select a file, the browser submits an
                # empty file without a filename.
                if remotefile and allowed_file(remotefile.filename):
                    filename = secure_filename(remotefile.filename)
                    remotefile.save(os.path.join('HISTORY_FOLDER', filename))
                else:
                    errors.append('Disallowed File Upload.')
                return redirect('/history')

        if('thumbSelected' in requestform):
            thumbnail = requestform['thumbSelected']
            filename = requestform['filename']
            # Reload Cook File
            cookfilename = HISTORY_FOLDER + filename
            cookfilestruct, status = read_cookfile(cookfilename)
            if status=='OK':
                cookfilestruct['metadata']['thumbnail'] = thumbnail
                update_json_file_data(cookfilestruct['metadata'], HISTORY_FOLDER + filename, 'metadata')
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

                return render_template(
                            'cookfile/index.html',
                            settings=settings,
                            cookfilename=cookfilename, 
                            filenameonly=filename,
                            events=events, 
                            event_totals=event_totals,
                            comments=comments, 
                            metadata=metadata, 
                            labels=labels, 
                            assets=assets, 
                            errors=errors, 
                            page_theme=settings['globals'].get('page_theme', 'light'),
                            grill_name=settings['globals'].get('grill_name', '')
                            )

        if('ulmediafn' in requestform) or ('ulthumbfn' in requestform):
            # Assume we have request.files and localfile in response
            if 'ulmediafn' in requestform:
                #uploadedfile = request.files['ulmedia']
                uploadedfiles = request.files.getlist('ulmedia')
                cookfilename = HISTORY_FOLDER + requestform['ulmediafn']
                filenameonly = requestform['ulmediafn']
            else: 
                uploadedfile = request.files['ulthumbnail']
                cookfilename = HISTORY_FOLDER + requestform['ulthumbfn']
                filenameonly = requestform['ulthumbfn']
                uploadedfiles = [uploadedfile]

            status = 'ERROR'
            for remotefile in uploadedfiles:
                if (remotefile.filename != ''):
                    # Reload Cook File
                    cookfilestruct, status = read_cookfile(cookfilename)
                    parent_id = cookfilestruct['metadata']['id']
                    tmp_path = f'/tmp/pifire/{parent_id}'
                    if not os.path.exists(tmp_path):
                        os.mkdir(tmp_path)

                    if remotefile and allowed_file(remotefile.filename):
                        filename = secure_filename(remotefile.filename)
                        pathfile = os.path.join(tmp_path, filename)
                        remotefile.save(pathfile)
                        asset_id, asset_filetype = add_asset(cookfilename, tmp_path, filename)
                        if 'ulthumbfn' in requestform:
                            set_thumbnail(cookfilename, f'{asset_id}.{asset_filetype}')
                        #  Reload all of the data
                        cookfilestruct, status = read_cookfile(cookfilename)
                    else:
                        errors.append('Disallowed File Upload.')

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

                return render_template(
                            'cookfile/index.html',
                            settings=settings,
                            cookfilename=cookfilename, 
                            filenameonly=filename,
                            events=events, 
                            event_totals=event_totals,
                            comments=comments, 
                            metadata=metadata, 
                            labels=labels, 
                            assets=assets, 
                            errors=errors, 
                            page_theme=settings['globals'].get('page_theme', 'light'),
                            grill_name=settings['globals'].get('grill_name', '')
                            )

        if('cookfilelist' in requestform):
            page = int(requestform['page'])
            reverse = True if requestform['reverse'] == 'true' else False
            itemsperpage = int(requestform['itemsperpage'])
            filelist = _get_cookfilelist()
            cookfilelist = []
            for filename in filelist:
                cookfilelist.append({'filename' : filename, 'title' : '', 'thumbnail' : ''})
            paginated_cookfile = paginate_list(cookfilelist, 'filename', reverse, itemsperpage, page)
            paginated_cookfile['displaydata'] = _get_cookfilelist_details(paginated_cookfile['displaydata'])
            return render_template('cookfile/_cookfile_list.html', pgntdcf = paginated_cookfile)

        if('repairCF' in requestform):
            cookfilename = requestform['repairCF']
            filenameonly = requestform['repairCF'].replace(HISTORY_FOLDER, '')
            cookfilestruct, status = upgrade_cookfile(cookfilename, repair=True)
            if status != 'OK':
                errors.append(status)
                if 'version' in status:
                    errortype = 'version'
                elif 'asset' in status: 
                    errortype = 'asset'
                else: 
                    errortype = 'other'
                errors.append('Repair Failed.')
                return render_template(
                            'cookfile/cferror.html', 
                            settings=settings, 
                            cookfilename=cookfilename, 
                            errortype=errortype, 
                            errors=errors, 
                            page_theme=settings['globals'].get('page_theme', 'light'),
                            grill_name=settings['globals'].get('grill_name', '')
                        )

            # Fix issues with assets
            cookfilestruct, status = read_cookfile(cookfilename)
            cookfilestruct, status = fixup_assets(cookfilename, cookfilestruct)
            if status != 'OK':
                errors.append(status)
                if 'version' in status:
                    errortype = 'version'
                elif 'asset' in status: 
                    errortype = 'asset'
                else: 
                    errortype = 'other'
                errors.append('Repair Failed.')
                return render_template(
                            'cookfile/cferror.html', 
                            settings=settings, 
                            cookfilename=cookfilename, 
                            errortype=errortype, 
                            errors=errors, 
                            page_theme=settings['globals'].get('page_theme', 'light'),
                            grill_name=settings['globals'].get('grill_name', '')
                        )
            else: 
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

                return render_template(
                            'cookfile/index.html',
                            settings=settings,
                            cookfilename=cookfilename, 
                            filenameonly=filename,
                            events=events, 
                            event_totals=event_totals,
                            comments=comments, 
                            metadata=metadata, 
                            labels=labels, 
                            assets=assets, 
                            errors=errors, 
                            page_theme=settings['globals'].get('page_theme', 'light'),
                            grill_name=settings['globals'].get('grill_name', '')
                            )

        if('upgradeCF' in requestform):
            cookfilename = requestform['upgradeCF']
            filenameonly = requestform['upgradeCF'].replace(HISTORY_FOLDER, '')
            cookfilestruct, status = upgrade_cookfile(cookfilename)
            if status != 'OK':
                errors.append(status)
                if 'version' in status:
                    errortype = 'version'
                elif 'asset' in status: 
                    errortype = 'asset'
                else: 
                    errortype = 'other'
                return render_template(
                            'cookfile/cferror.html', 
                            settings=settings, 
                            cookfilename=cookfilename, 
                            errortype=errortype, 
                            errors=errors, 
                            page_theme=settings['globals'].get('page_theme', 'light'),
                            grill_name=settings['globals'].get('grill_name', '')
                        )
            else: 
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

                return render_template(
                            'cookfile/index.html',
                            settings=settings,
                            cookfilename=cookfilename, 
                            filenameonly=filename,
                            events=events, 
                            event_totals=event_totals,
                            comments=comments, 
                            metadata=metadata, 
                            labels=labels, 
                            assets=assets, 
                            errors=errors, 
                            page_theme=settings['globals'].get('page_theme', 'light'),
                            grill_name=settings['globals'].get('grill_name', '')
                            )

        if('delmedialist' in requestform):
            cookfilename = HISTORY_FOLDER + requestform['delmedialist']
            filenameonly = requestform['delmedialist']
            assetlist = requestform['delAssetlist'].split(',') if requestform['delAssetlist'] != '' else []
            status = remove_assets(cookfilename, assetlist)
            cookfilestruct, status = read_cookfile(cookfilename)
            if status != 'OK':
                errors.append(status)
                if 'version' in status:
                    errortype = 'version'
                elif 'asset' in status: 
                    errortype = 'asset'
                else: 
                    errortype = 'other'
                return render_template(
                            'cookfile/cferror.html', 
                            settings=settings, 
                            cookfilename=cookfilename, 
                            errortype=errortype, 
                            errors=errors, 
                            page_theme=settings['globals'].get('page_theme', 'light'),
                            grill_name=settings['globals'].get('grill_name', '')
                        )
            else: 
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

                return render_template(
                            'cookfile/index.html',
                            settings=settings,
                            cookfilename=cookfilename, 
                            filenameonly=filename,
                            events=events, 
                            event_totals=event_totals,
                            comments=comments, 
                            metadata=metadata, 
                            labels=labels, 
                            assets=assets, 
                            errors=errors, 
                            page_theme=settings['globals'].get('page_theme', 'light'),
                            grill_name=settings['globals'].get('grill_name', '')
                            )

    errors.append('Something unexpected has happened.')
    return jsonify({'result' : 'ERROR', 'errors' : errors})

@cookfile_bp.route('/update', methods=['POST','GET'])
def cookfile_update():
    settings = read_settings()
    HISTORY_FOLDER = current_app.config['HISTORY_FOLDER']

    if(request.method == 'POST'):
        requestjson = request.json 
        if('comments' in requestjson):
            filename = requestjson['filename']
            cookfiledata, status = read_json_file_data(filename, 'comments')

            if('commentnew' in requestjson):
                now = datetime.datetime.now()
                comment_struct = {}
                comment_struct['text'] = requestjson['commentnew']
                comment_struct['id'] = generate_uuid()
                comment_struct['edited'] = ''
                comment_struct['date'] = now.strftime('%Y-%m-%d')
                comment_struct['time'] = now.strftime('%H:%M')
                comment_struct['assets'] = []
                cookfiledata.append(comment_struct)
                result = update_json_file_data(cookfiledata, filename, 'comments')
                if(result == 'OK'):
                    return jsonify({'result' : 'OK', 'newcommentid' : comment_struct['id'], 'newcommentdt': comment_struct['date'] + ' ' + comment_struct['time']})
            if('delcomment' in requestjson):
                for item in cookfiledata:
                    if item['id'] == requestjson['delcomment']:
                        cookfiledata.remove(item)
                        result = update_json_file_data(cookfiledata, filename, 'comments')
                        if(result == 'OK'):
                            return jsonify({'result' : 'OK'})
            if('editcomment' in requestjson):
                for item in cookfiledata:
                    if item['id'] == requestjson['editcomment']:
                        return jsonify({'result' : 'OK', 'text' : item['text']})
            if('savecomment' in requestjson):
                for item in cookfiledata:
                    if item['id'] == requestjson['savecomment']:
                        now = datetime.datetime.now()
                        item['text'] = requestjson['text']
                        item['edited'] = now.strftime('%Y-%m-%d %H:%M')
                        result = update_json_file_data(cookfiledata, filename, 'comments')
                        if(result == 'OK'):
                            return jsonify({'result' : 'OK', 'text' : item['text'].replace('\n', '<br>'), 'edited' : item['edited'], 'datetime' : item['date'] + ' ' + item['time']})
        
        if('metadata' in requestjson):
            filename = requestjson['filename']
            cookfiledata, status = read_json_file_data(filename, 'metadata')
            if(status == 'OK'):
                if('editTitle' in requestjson):
                    cookfiledata['title'] = requestjson['editTitle']
                    result = update_json_file_data(cookfiledata, filename, 'metadata')
                    if(result == 'OK'):
                        return jsonify({'result' : 'OK'})
                    else: 
                        return jsonify({'result' : 'ERROR'})
        
        if('graph_labels' in requestjson):
            filename = requestjson['filename']
            
            ''' Update graph_labels.json '''
            cookfiledata, result = read_json_file_data(filename, 'graph_labels')
            if(result != 'OK'):
                return jsonify({'result' : 'ERROR'})

            old_label = requestjson['old_label']
            new_label = requestjson['new_label']
            new_label_safe = create_safe_name(new_label)

            for category in cookfiledata:
                if new_label_safe in cookfiledata[category].keys():
                    result = 'Label already exists!'
                    break
                if old_label in cookfiledata[category].keys():
                    cookfiledata[category].pop(old_label)
                    cookfiledata[category][new_label_safe] = new_label 
            
            if(result != 'OK'):
                return jsonify({'result' : 'ERROR'})

            result = update_json_file_data(cookfiledata, filename, 'graph_labels')
            if(result != 'OK'):
                return jsonify({'result' : 'ERROR'})

            ''' Update graph_data.json '''
            cookfiledata, result = read_json_file_data(filename, 'graph_data')
            if(result != 'OK'):
                return jsonify({'result' : 'ERROR'})

            for category in cookfiledata['probe_mapper']:
                if old_label in cookfiledata['probe_mapper'][category].keys():
                    cookfiledata['probe_mapper'][category][new_label_safe] = cookfiledata['probe_mapper'][category][old_label]
                    cookfiledata['probe_mapper'][category].pop(old_label)
                    list_position = cookfiledata['probe_mapper'][category][new_label_safe]
                    if category == 'targets': 
                        addendum = ' Target'
                    elif category == 'primarysp':
                        addendum = ' Set Point'
                    else:
                        addendum = ''
                    cookfiledata['chart_data'][list_position]['label'] = new_label + addendum 

            result = update_json_file_data(cookfiledata, filename, 'graph_data')
            if(result != 'OK'):
                return jsonify({'result' : 'ERROR'})

            return jsonify({'result' : 'OK', 'new_label_safe' : new_label_safe})

        if('media' in requestjson):
            filename = requestjson['filename']
            assetfilename = requestjson['assetfilename']
            commentid = requestjson['commentid']
            state = requestjson['state']
            comments, status = read_json_file_data(filename, 'comments')
            result = 'OK'
            for index in range(0, len(comments)):
                if comments[index]['id'] == commentid:
                    if assetfilename in comments[index]['assets'] and state == 'selected':
                        comments[index]['assets'].remove(assetfilename)
                        result = update_json_file_data(comments, filename, 'comments')
                    elif assetfilename not in comments[index]['assets'] and state == 'unselected':
                        comments[index]['assets'].append(assetfilename)
                        result = update_json_file_data(comments, filename, 'comments')
                    break

            return jsonify({'result' : result})

    return jsonify({'result' : 'ERROR'})

def _get_cookfilelist(folder=None):
    if folder is None:
        folder = current_app.config['HISTORY_FOLDER']

    # Grab list of Historical Cook Files
    if not os.path.exists(folder):
        os.mkdir(folder)
    dirfiles = os.listdir(folder)
    cookfiles = []
    for file in dirfiles:
        if file.endswith('.pifire'):
            cookfiles.append(file)
    return(cookfiles)

def _get_cookfilelist_details(cookfilelist):
    HISTORY_FOLDER = current_app.config['HISTORY_FOLDER']
    cookfiledetails = []
    for item in cookfilelist:
        filename = HISTORY_FOLDER + item['filename']
        cookfiledata, status = read_json_file_data(filename, 'metadata')
        if(status == 'OK'):
            thumbnail = unpack_thumb(cookfiledata['thumbnail'], filename) if ('thumbnail' in cookfiledata) else ''
            cookfiledetails.append({'filename' : item['filename'], 'title' : cookfiledata['title'], 'thumbnail' : thumbnail})
        else:
            cookfiledetails.append({'filename' : item['filename'], 'title' : 'ERROR', 'thumbnail' : ''})
    return(cookfiledetails)