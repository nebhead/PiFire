
import os
import time
from flask import render_template, request, jsonify, redirect, render_template_string
from common.common import read_settings, read_control, write_log, is_real_hardware
from updater import get_available_updates, get_update_data, get_updater_install_status, set_updater_install_status, get_log

from . import update_bp

@update_bp.route('/<action>', methods=['POST','GET'])
@update_bp.route('/', methods=['POST','GET'])
def update_page(action=None):
    settings = read_settings()
    control = read_control()

    # Create Alert Structure for Alert Notification
    alert = {
        'type' : '',
        'text' : ''
    }

    python_exec = settings['globals'].get('python_exec', 'python')

    if request.method == 'GET':
        if action is None:
            update_data = get_update_data(settings)
            return render_template(
                            'update/updater.html', 
                            alert=alert, 
                            settings=settings,
                            update_data=update_data,
                            page_theme=settings['globals'].get('page_theme', 'light'),
                            grill_name=settings['globals'].get('grill_name', '')
                            )
        elif action=='updatestatus':
            percent, status, output = get_updater_install_status()
            return jsonify({'percent' : percent, 'status' : status, 'output' : output})
        
        elif action=='post-message':
            try:
                with open('./updater/post-update-message.html','r') as file:
                    post_update_message_html = " ".join(line.rstrip() for line in file)
            except:
                post_update_message_html = 'An error has occurred fetching the post-update message.' 
            return render_template_string(post_update_message_html)
        elif action=='check':
            update_data = {}
            update_data['version'] = settings['versions']['server']

            avail_updates_struct = get_available_updates()

            if avail_updates_struct['success']:
                commits_behind = avail_updates_struct['commits_behind']
            else:
                event = avail_updates_struct['message']
                write_log(event)
                return jsonify({'result' : 'failure', 'message' : avail_updates_struct['message'] })

            return jsonify({'result' : 'success', 'current' : update_data['version'], 'behind' : commits_behind})

    if request.method == 'POST':
        r = request.form
        update_data = get_update_data(settings)

        if 'update_remote_branches' in r:
            if is_real_hardware():
                os.system(f'{python_exec} updater.py -r &')	 # Update branches from remote 
                time.sleep(5)  # Artificial delay to avoid race condition
            return redirect('/update')

        if 'change_branch' in r:
            if update_data['branch_target'] in r['branch_target']:
                alert = {
                    'type' : 'success',
                    'text' : f'Current branch {update_data["branch_target"]} already set to {r["branch_target"]}'
                }
                return render_template(
                                    'update/updater.html', 
                                    alert=alert, 
                                    settings=settings,
                                    update_data=update_data,
                                    page_theme=settings['globals'].get('page_theme', 'light'),
                                    grill_name=settings['globals'].get('grill_name', '')
                                    )
            else:
                set_updater_install_status(0, 'Starting Branch Change...', '')
                os.system(f'{python_exec} updater.py -b {r["branch_target"]} &')	# Kickoff Branch Change
                return render_template(
                                    'update/updater-status.html', 
                                    page_theme=settings['globals'].get('page_theme', 'light'),
                                    grill_name=settings['globals'].get('grill_name', '')
                                    )
        if 'do_update' in r:
            control = read_control()
            if control['mode'] == 'Stop':
                set_updater_install_status(0, 'Starting Update...', '')
                os.system(f'{python_exec} updater.py -u {update_data["branch_target"]} -p &') # Kickoff Update
                return render_template(
                                    'update/updater-status.html', 
                                    page_theme=settings['globals'].get('page_theme', 'light'),
                                    grill_name=settings['globals'].get('grill_name', '')
                                    )
            else:
                alert = {
                    'type' : 'error',
                    'text' : f'PiFire System Update cannot be completed when the system is active.  Please shutdown/stop your smoker before retrying.'
                }
                update_data = get_update_data(settings)
                return render_template(
                                    'update/updater.html', 
                                    alert=alert, 
                                    settings=settings,
                                    update_data=update_data,
                                    page_theme=settings['globals'].get('page_theme', 'light'),
                                    grill_name=settings['globals'].get('grill_name', '')
                                    )

        if 'do_upgrade' in r:
            control = read_control()
            if control['mode'] == 'Stop':
                set_updater_install_status(0, 'Starting Upgrade...', '')
                os.system(f'{python_exec} updater.py -i &')
                return render_template(
                                    'update/updater-status.html', 
                                    page_theme=settings['globals'].get('page_theme', 'light'),
                                    grill_name=settings['globals'].get('grill_name', '')
                                    )
            else:
                alert = {
                    'type' : 'error',
                    'text' : f'PiFire System Upgrade cannot be completed when the system is active.  Please shutdown/stop your smoker before retrying.'
                }
                update_data = get_update_data(settings)
                return render_template(
                                    'update/updater.html', 
                                    alert=alert, 
                                    settings=settings,
                                    update_data=update_data,
                                    page_theme=settings['globals'].get('page_theme', 'light'),
                                    grill_name=settings['globals'].get('grill_name', '')
                                    )

        if 'show_log' in r:
            if r['show_log'].isnumeric():
                action='log'
                result, error_msg = get_log(num_commits=int(r['show_log']))
                if error_msg == '':
                    output_html = f'*** Getting latest updates from origin/{update_data["branch_target"]} ***<br><br>' 
                    output_html += result
                else: 
                    output_html = f'*** Getting latest updates from origin/{update_data["branch_target"]} ERROR Occurred ***<br><br>' 
                    output_html += error_msg
            else:
                output_html = '*** Error, Number of Commits Not Defined! ***<br><br>'
            
            return render_template(
                                'update/updater_out.html', 
                                settings=settings, 
                                action=action, 
                                output_html=output_html,
                                page_theme=settings['globals'].get('page_theme', 'light'),
                                grill_name=settings['globals'].get('grill_name', '')
                                )
                                