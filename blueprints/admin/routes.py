import os
import datetime
import pathlib
import zipfile
from flask import render_template, current_app, request, send_file
from werkzeug.utils import secure_filename
from common.common import process_command, read_settings, write_settings, read_control, write_control, read_pellet_db, \
            write_pellet_db, read_history, write_log, read_generic_json, write_generic_json, reboot_system, shutdown_system, \
            restart_scripts, default_settings, default_control, backup_settings, backup_pellet_db, get_os_info
from common.app import allowed_file, get_supported_cmds, get_system_command_output
from . import admin_bp

@admin_bp.route('/<action>', methods=['POST','GET'])
@admin_bp.route('/', methods=['POST','GET'])
def admin_page(action=None):
    server_status = 'available'
    settings = read_settings()
    control = read_control()
    pelletdb = read_pellet_db()

    errors = []
    warnings = []
    success = []

    BACKUP_PATH = current_app.config['BACKUP_PATH']

    if not os.path.exists(BACKUP_PATH):
        os.mkdir(BACKUP_PATH)
    files = os.listdir(BACKUP_PATH)
    for file in files:
        if not allowed_file(file):
            files.remove(file)

    if action == 'reboot':
        event = "Admin: Reboot"
        write_log(event)
        server_status = 'rebooting'
        reboot_system()
        return render_template('shutdown.html', action=action, page_theme=settings['globals']['page_theme'],
                                grill_name=settings['globals']['grill_name'])

    elif action == 'shutdown':
        event = "Admin: Shutdown"
        write_log(event)
        server_status = 'shutdown'
        shutdown_system()
        return render_template('shutdown.html', action=action, page_theme=settings['globals']['page_theme'],
                                grill_name=settings['globals']['grill_name'])

    elif action == 'restart':
        event = "Admin: Restart Server"
        write_log(event)
        server_status = 'restarting'
        restart_scripts()
        return render_template('shutdown.html', action=action, page_theme=settings['globals']['page_theme'],
                                grill_name=settings['globals']['grill_name'])

    if request.method == 'POST' and action == 'setting':
        response = request.form

        if 'debugenabled' in response:
            control['settings_update'] = True
            if response['debugenabled'] == 'disabled':
                write_log('Debug Mode Disabled.')
                settings['globals']['debug_mode'] = False
                write_settings(settings)
                write_control(control, origin='app')
            else:
                settings['globals']['debug_mode'] = True
                write_settings(settings)
                write_control(control, origin='app')
                write_log('Debug Mode Enabled.')

        if 'clearhistory' in response:
            if response['clearhistory'] == 'true':
                write_log('Clearing History Log.')
                read_history(0, flushhistory=True)

        if 'clearevents' in response:
            if response['clearevents'] == 'true':
                write_log('Clearing Events Log.')
                os.system('rm /tmp/events.log')

        if 'clearpelletdb' in response:
            if response['clearpelletdb'] == 'true':
                write_log('Clearing Pellet Database.')
                os.system('rm pelletdb.json')

        if 'clearpelletdblog' in response:
            if response['clearpelletdblog'] == 'true':
                write_log('Clearing Pellet Database Log.')
                pelletdb['log'].clear()
                write_pellet_db(pelletdb)

        if 'factorydefaults' in response:
            if response['factorydefaults'] == 'true':
                write_log('Resetting Settings, Control and History to factory defaults.')
                read_history(0, flushhistory=True)
                read_control(flush=True)
                os.system('rm settings.json')
                os.system('rm pelletdb.json')
                settings = default_settings()
                control = default_control()
                write_settings(settings)
                write_control(control, origin='app')
                server_status = 'restarting'
                restart_scripts()
                return render_template('shutdown.html', action='restart', page_theme=settings['globals']['page_theme'],
                                        grill_name=settings['globals']['grill_name'])

        if 'download_logs' in response:
            zip_file = _zip_files_logs('logs')
            return send_file(zip_file, as_attachment=True, max_age=0)
        
        if 'delete_logs' in response:
            # Delete *.log files in logs/
            try:
                os.system('rm logs/*.log')
                success.append('Log files deleted.')
            except:
                errors.append('There was an error restoring pellet database.  Restore file wasn\'t specified or found')

        if 'download_settings' in response: 
            return send_file('settings.json', as_attachment=True, max_age=0)

        if 'download_control' in response:
            filename = '/tmp/control_general.json'
            write_generic_json(control, filename)
            return send_file(filename, as_attachment=True, max_age=0)
        
        if 'download_pip_list' in response:
            filename = 'pip_list.json'
            return send_file(filename, as_attachment=True, max_age=0)
        
        if 'backupsettings' in response:
            backup_file = backup_settings()
            return send_file(backup_file, as_attachment=True, max_age=0)

        if 'restoresettings' in response:
            # Assume we have request.files and local file in response
            remote_file = request.files['uploadfile']
            local_file = request.form['localfile']
            
            if local_file != 'none':
                new_settings = read_settings(filename=BACKUP_PATH+local_file)
                write_settings(new_settings)
                server_status = 'restarting'
                restart_scripts()
                return render_template('shutdown.html', action='restart', page_theme=settings['globals']['page_theme'],
                                        grill_name=settings['globals']['grill_name'])
            elif remote_file.filename != '':
                # If the user does not select a file, the browser submits an
                # empty file without a filename.
                if remote_file and allowed_file(remote_file.filename):
                    filename = secure_filename(remote_file.filename)
                    remote_file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
                    success.append('Successfully restored settings.')
                    new_settings = read_settings(filename=BACKUP_PATH+filename)
                    write_settings(new_settings)
                    server_status = 'restarting'
                    restart_scripts()
                    return render_template('shutdown.html', action='restart', page_theme=settings['globals']['page_theme'],
                                            grill_name=settings['globals']['grill_name'])
                else:
                    errors.append('There was an error restoring settings.  File either is a disallowed type or was not found.')
            else:
                errors.append('There was an error restoring settings.  Restore file wasn\'t specified or found')

        if 'backuppelletdb' in response:
            backup_file = backup_pellet_db(action='backup')
            return send_file(backup_file, as_attachment=True, max_age=0)

        if 'restorepelletdb' in response:
            # Assume we have request.files and local file in response
            remote_file = request.files['uploadfile']
            local_file = request.form['localfile']
            
            if local_file != 'none':
                pelletdb = read_pellet_db(filename=BACKUP_PATH+local_file)
                write_pellet_db(pelletdb)
                success.append('Successfully restored pellet database.')
            elif remote_file.filename != '':
                # If the user does not select a file, the browser submits an
                # empty file without a filename.
                if remote_file and allowed_file(remote_file.filename):
                    filename = secure_filename(remote_file.filename)
                    remote_file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
                    success.append('Successfully restored pellet database.')
                    pelletdb = read_pellet_db(filename=BACKUP_PATH+filename)
                    write_pellet_db(pelletdb)
                else:
                    errors.append('There was an error restoring the pellet database.  File either is a disallowed type or was not found.')
            else:
                errors.append('There was an error restoring pellet database.  Restore file wasn\'t specified or found')

    if request.method == 'POST' and action == 'boot':
        response = request.form

        if 'boot_to_monitor' in response:
            settings['globals']['boot_to_monitor'] = True 
        else:
            settings['globals']['boot_to_monitor'] = False 
        
        write_settings(settings)

    ''' 
        Get System Information 
    '''

    system_info = {}

    system_info['uptime'] = os.popen('uptime').readline()

    system_info['os_info'] = _get_os_info()

    system_info['network_info'] = {
            'Unknown': {
                'ip_address': '0.0.0.0',
                'mac_address': '00:00:00:00:00:00'
            }
        }

    system_info['hardware_info'] = {
            'total_ram': 'Unknown',
            'available_ram': 'Unknown',
            'cpu_info': {
                'hardware': 'Unknown',
                'model': 'Unknown',
                'model_name': 'Unknown',
                'cores': 'Unknown',
                'frequency': 'Unknown'
            }
        }

    supported_cmds = get_supported_cmds()

    if 'check_wifi_quality' in supported_cmds:
        process_command(action='sys', arglist=['check_wifi_quality'], origin='admin')  # Request supported commands 
        data = get_system_command_output(requested='check_wifi_quality')
        if data['result'] != 'OK':
            event = data['message']
            errors.append(event)
        control['system']['wifi_quality_value'] = data['data'].get('wifi_quality_value', None)
        control['system']['wifi_quality_max'] = data['data'].get('wifi_quality_max', None)
        control['system']['wifi_quality_percentage'] = data['data'].get('wifi_quality_percentage', None)

    if 'check_throttled' in supported_cmds:
        process_command(action='sys', arglist=['check_throttled'], origin='admin')  # Request supported commands 
        data = get_system_command_output(requested='check_throttled')
        if data['result'] != 'OK':
            event = data['message']
            errors.append(event)
        control['system']['cpu_throttled'] = data['data'].get('cpu_throttled', None)
        control['system']['cpu_under_voltage'] = data['data'].get('cpu_under_voltage', None)

        if control['system']['cpu_throttled'] or control['system']['cpu_under_voltage']: 
            event = "CPU Throttled / Undervoltage event has occurred.  Check your power supply for proper voltage."
            errors.append(event)

    if 'check_cpu_temp' in supported_cmds:
        process_command(action='sys', arglist=['check_cpu_temp'], origin='admin')  # Request supported commands 
        data = get_system_command_output(requested='check_cpu_temp')
        if data['result'] != 'OK':
            event = data['message']
            errors.append(event)
        control['system']['cpu_temp'] = data['data'].get('cpu_temp', None)

    if 'network_info' in supported_cmds:
        process_command(action='sys', arglist=['network_info'], origin='admin')
        data = get_system_command_output(requested='network_info')
        if data['result'] != 'OK':
            event = data['message']
            errors.append(event)
        else:
            network_info = data.get('data', None)
            if network_info:
                system_info['network_info'] = network_info

    if 'hardware_info' in supported_cmds:
        process_command(action='sys', arglist=['hardware_info'], origin='admin')
        data = get_system_command_output(requested='hardware_info')
        if data['result'] != 'OK':
            event = data['message']
            errors.append(event)
        else:
            system_info['hardware_info'] = data.get('data', {})

    write_control(control)

    url = request.url_root

    pip_list = read_generic_json('pip_list.json')
    if pip_list == {}:
        event = 'Pip list is empty. Run \'updater.py -p\' to generate pip list.'
        errors.append(event)
        pip_list = []

    return render_template('admin/index.html', settings=settings, control=control,
                            system_info=system_info, 
                            qr_content=url,
                            pip_list=pip_list,
                            page_theme=settings['globals'].get('page_theme', 'light'),
                            grill_name=settings['globals'].get('grill_name', ''),
                            files=files, errors=errors, warnings=warnings, success=success)

def _zip_files_logs(dir_name):
	time_now = datetime.datetime.now()
	time_str = time_now.strftime('%m-%d-%y_%H%M%S') # Truncate the microseconds
	file_name = f'/tmp/PiFire_Logs_{time_str}.zip'
	directory = pathlib.Path(f'{dir_name}')
	with zipfile.ZipFile(file_name, "w", zipfile.ZIP_DEFLATED) as archive:
		for file_path in directory.rglob("*.log"):
			archive.write(file_path, arcname=file_path.relative_to(directory))
	return file_name

def _get_os_info():
    try:
        os_info = read_generic_json('os_info.json')
        if not os_info:
            os_info = get_os_info()

    except Exception as e:
        current_app.logger.error(f"Error reading OS info: {e}")

    finally:
        if not os_info:
            os_info = {
            "PRETTY_NAME" : 'Unknown.',
            "NAME" : 'Unknown.',
            "VERSION_ID" : 'Unknown.',
            "VERSION" : 'Unknown.',
            "VERSION_CODENAME" : 'Unknown.',
            "ARCHITECTURE" : 'Unknown.',
            "BITS" : 'Unknown.'
            }
        else:
            # Ensure the os_info has all expected keys
            os_info.setdefault("PRETTY_NAME", 'Unknown.')
            os_info.setdefault("NAME", 'Unknown.')
            os_info.setdefault("VERSION_ID", 'Unknown.')
            os_info.setdefault("VERSION", 'Unknown.')
            os_info.setdefault("VERSION_CODENAME", 'Unknown.')
            os_info.setdefault("ARCHITECTURE", 'Unknown.')
            if os_info['ARCHITECTURE'] in ['armv7l', 'armv6l', 'armv5l', 'arm', 'i386', 'i486', 'i586', 'i686']:
                os_info['BITS'] = '32-Bit'
            elif os_info['ARCHITECTURE'] in ['aarch64', 'x86_64']:
                os_info['BITS'] = '64-Bit'
            else:
                os_info['BITS'] = 'Unknown'

        return os_info