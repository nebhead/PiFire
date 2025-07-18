
from flask import render_template, request, render_template_string, jsonify
from common.common import read_settings, read_control, write_settings, write_control, read_generic_json, generate_uuid, convert_settings_units
from common.app import is_not_blank, is_checked

from . import settings_bp

@settings_bp.route('/<action>', methods=['POST','GET'])
@settings_bp.route('/', methods=['POST','GET'])
def settings_page(action=None):
    settings = read_settings()
    control = read_control()

    controller = read_generic_json('./controller/controllers.json')

    event = {
        'type' : 'none',
        'text' : ''
    }

    if request.method == 'POST' and action == 'dashboard_config':
        response = request.form
        selected = response.get('selected', '')
        if selected == '':
            selected = settings['dashboard']['selected']
        elif selected not in settings['dashboard']['dashboards']:
            selected = list(settings['dashboard']['dashboards'].keys())[0]
        render_string = "{% from 'settings/_macro_settings.html' import render_dash_settings %}{{ render_dash_settings(selected, settings) }}"
        return render_template_string(render_string, selected=selected, settings=settings)

    if request.method == 'POST' and action == 'probe_select':
        response = request.form

        if response['selected'] == '':
            selected = settings['probe_settings']['probe_map']['probe_info'][0]['label']
            probe_info = settings['probe_settings']['probe_map']['probe_info']
        else:
            selected = response['selected']
            probe_info = settings['probe_settings']['probe_map']['probe_info']

        render_string = "{% from 'settings/_macro_probes.html' import render_probe_select %}{{ render_probe_select(selected, probe_info, settings) }}"
        return render_template_string(render_string, selected=selected, probe_info=probe_info, settings=settings)

    if request.method == 'POST' and action == 'probe_config':
        response = request.form
        probe_info = None

        if request.form['selected'] == '':
            selected = settings['probe_settings']['probe_map']['probe_info'][0]['label']
            probe_info = settings['probe_settings']['probe_map']['probe_info'][0]
        else:
            selected = request.form['selected']
            for probe in settings['probe_settings']['probe_map']['probe_info']:
                if probe['label'] == selected:
                    probe_info = probe
                    break 

        if probe_info == None:
            probe_info = settings['probe_settings']['probe_map']['probe_info'][0]

        render_string = "{% from 'settings/_macro_probes.html' import render_probe_config %}{{ render_probe_config(probe_info, settings) }}"
        return render_template_string(render_string, probe_info=probe_info, settings=settings)

    if request.method == 'POST' and action == 'probe_config_save':
        probe_config = request.json
        label = probe_config.get('label', '')
        probe_edited = {}

        for index, probe in enumerate(settings['probe_settings']['probe_map']['probe_info']):
            if probe['label'] == label:
                probe_edited['label'] = probe['label']
                probe_edited['name'] = probe_config.get('name', settings['probe_settings']['probe_map']['probe_info'][index]['name'])
                probe_edited['type'] = probe_config.get('type', settings['probe_settings']['probe_map']['probe_info'][index]['type'])
                probe_edited['port'] = probe_config.get('port', settings['probe_settings']['probe_map']['probe_info'][index]['port'])
                probe_edited['device'] = probe_config.get('device', settings['probe_settings']['probe_map']['probe_info'][index]['device'])
                probe_edited['enabled'] = True if probe_config.get('enabled', False) == 'true' else False
                profile_id = probe_config.get('profile_id', settings['probe_settings']['probe_map']['probe_info'][index]['profile']['id'])
                if profile_id != probe['profile']['id']:
                    probe_edited['profile'] = settings['probe_settings']['probe_profiles'].get(profile_id, settings['probe_settings']['probe_map']['probe_info'][index]['profile'])
                else:
                    probe_edited['profile'] = settings['probe_settings']['probe_map']['probe_info'][index]['profile']
                break

        if probe_edited:
            settings['probe_settings']['probe_map']['probe_info'][index] = probe_edited
            settings['history_page']['probe_config'][label]['name'] = probe_edited['name']
            control['probe_profile_update'] = True
            # Take all settings and write them
            write_settings(settings)
            write_control(control, origin='app')

            return jsonify({'result' : 'success'})
        else:
            return jsonify({'result' : 'label_not_found'})

    if request.method == 'POST' and action == 'notify':
        response = request.form

        if is_checked(response, 'apprise_enabled'):
            settings['notify_services']['apprise']['enabled'] = True
        else:
            settings['notify_services']['apprise']['enabled'] = False
        if 'appriselocations' in response:
            locations = []
            for location in response.getlist('appriselocations'):
                if(len(location)):
                    locations.append(location)
            settings['notify_services']['apprise']['locations'] = locations
        else:
            settings['notify_services']['apprise']['locations'] = []
        if is_checked(response, 'ifttt_enabled'):
            settings['notify_services']['ifttt']['enabled'] = True
        else:
            settings['notify_services']['ifttt']['enabled'] = False
        if 'iftttapi' in response:
            settings['notify_services']['ifttt']['APIKey'] = response['iftttapi']
        if is_checked(response, 'pushbullet_enabled'):
            settings['notify_services']['pushbullet']['enabled'] = True
        else:
            settings['notify_services']['pushbullet']['enabled'] = False
        if 'pushbullet_apikey' in response:
            settings['notify_services']['pushbullet']['APIKey'] = response['pushbullet_apikey']
        if 'pushbullet_publicurl' in response:
            settings['notify_services']['pushbullet']['PublicURL'] = response['pushbullet_publicurl']
        if is_checked(response, 'pushover_enabled'):
            settings['notify_services']['pushover']['enabled'] = True
        else:
            settings['notify_services']['pushover']['enabled'] = False
        if 'pushover_apikey' in response:
            settings['notify_services']['pushover']['APIKey'] = response['pushover_apikey']
        if 'pushover_userkeys' in response:
            settings['notify_services']['pushover']['UserKeys'] = response['pushover_userkeys']
        if 'pushover_publicurl' in response:
            settings['notify_services']['pushover']['PublicURL'] = response['pushover_publicurl']
        if is_checked(response, 'onesignal_enabled'):
            settings['notify_services']['onesignal']['enabled'] = True
        else:
            settings['notify_services']['onesignal']['enabled'] = False

        if is_checked(response, 'influxdb_enabled'):
            settings['notify_services']['influxdb']['enabled'] = True
        else:
            settings['notify_services']['influxdb']['enabled'] = False
        if 'influxdb_url' in response:
            settings['notify_services']['influxdb']['url'] = response['influxdb_url']
        if 'influxdb_token' in response:
            settings['notify_services']['influxdb']['token'] = response['influxdb_token']
        if 'influxdb_org' in response:
            settings['notify_services']['influxdb']['org'] = response['influxdb_org']
        if 'influxdb_bucket' in response:
            settings['notify_services']['influxdb']['bucket'] = response['influxdb_bucket']

        if is_checked(response, 'mqtt_enabled'):
            settings['notify_services']['mqtt']['enabled'] = True
        else:
            settings['notify_services']['mqtt']['enabled'] = False
        if 'mqtt_id' in response:
            settings['notify_services']['mqtt']['id'] = response['mqtt_id']
        if 'mqtt_broker' in response:
            settings['notify_services']['mqtt']['broker'] = response['mqtt_broker']
        if 'mqtt_port' in response:
            settings['notify_services']['mqtt']['port'] = response['mqtt_port']
        if 'mqtt_user' in response:
            settings['notify_services']['mqtt']['username'] = response['mqtt_user']
        if 'mqtt_pw' in response:
            settings['notify_services']['mqtt']['password'] = response['mqtt_pw']
        if 'mqtt_auto_d' in response:
            settings['notify_services']['mqtt']['homeassistant_autodiscovery_topic'] = response['mqtt_auto_d']
        if 'mqtt_freq' in response:
            settings['notify_services']['mqtt']['update_sec'] = response['mqtt_freq']

        if 'delete_device' in response:
            DeviceID = response['delete_device']
            settings['notify_services']['onesignal']['devices'].pop(DeviceID)

        if 'edit_device' in response:
            if response['edit_device'] != '':
                DeviceID = response['edit_device']
                settings['notify_services']['onesignal']['devices'][DeviceID] = {
                    'friendly_name' : response['FriendlyName_' + DeviceID],
                    'device_name' : response['DeviceName_' + DeviceID],
                    'app_version' : response['AppVersion_' + DeviceID]
                }

        control['settings_update'] = True

        event['type'] = 'updated'
        event['text'] = 'Successfully updated notification settings.'

        # Take all settings and write them
        write_settings(settings)
        write_control(control, origin='app')

    if request.method == 'POST' and action == 'editprofile':
        response = request.form

        if 'delete' in response:
            UniqueID = response['delete'] # Get the string of the UniqueID
            try:
                # Check if this profile is in use
                for item in settings['probe_settings']['probe_map']['probe_info']:
                    if item['profile']['id'] == UniqueID:
                        event['type'] = 'error'
                        event['text'] = f'Error: Cannot delete this profile, as it is selected for a probe.  Go to the probe settings tab and select a different profile for {item["name"]}.  Then try to delete this profile again.'
                if event['type'] != 'error':
                    # Attempt to remove the profile 
                    settings['probe_settings']['probe_profiles'].pop(UniqueID)
                    write_settings(settings)
                    event['type'] = 'updated'
                    event['text'] = 'Successfully removed ' + response['Name_' + UniqueID] + ' profile.'
            except:
                event['type'] = 'error'
                event['text'] = 'Error: Failed to remove ' + response['Name_' + UniqueID] + ' profile.'

        if 'editprofile' in response:
            if response['editprofile'] != '':
                # Try to convert input values
                try:
                    UniqueID = response['editprofile'] # Get the string of the UniqueID
                    settings['probe_settings']['probe_profiles'][UniqueID] = {
                        'A' : float(response['A_' + UniqueID]),
                        'B' : float(response['B_' + UniqueID]),
                        'C' : float(response['C_' + UniqueID]),
                        'name' : response['Name_' + UniqueID], 
                        'id' : UniqueID
                    }
                    # Update profile info in probe map 
                    profile_in_use = False 
                    for index, probe in enumerate(settings['probe_settings']['probe_map']['probe_info']):
                        if probe['profile']['id'] == UniqueID:
                            settings['probe_settings']['probe_map']['probe_info'][index]['profile'] = settings['probe_settings']['probe_profiles'][UniqueID]
                            profile_in_use = True

                    event['type'] = 'updated'
                    event['text'] = 'Successfully edited ' + response['Name_' + UniqueID] + ' profile.'
                    # Write the new probe profile to disk
                    write_settings(settings)
                    # If this profile is currently in use, update the profile in the control script as well 
                    if profile_in_use:					
                        control['probe_profile_update'] = True
                        write_control(control, origin='app')
                except:
                    event['type'] = 'error'
                    event['text'] = 'Something bad happened when trying to format your inputs.  Try again.'
            else:
                event['type'] = 'error'
                event['text'] = 'Error. Profile NOT saved.'

    if request.method == 'POST' and action == 'addprofile':
        response = request.form

        if (response['Name'] != '' and response['A'] != '' and response['B'] != '' and response['C'] != ''):
            # Try to convert input values
            try:
                UniqueID = generate_uuid()
                settings['probe_settings']['probe_profiles'][UniqueID] = {
                    'A' : float(response['A']),
                    'B' : float(response['B']),
                    'C' : float(response['C']),
                    'name' : response['Name'], 
                    'id' : UniqueID
                }
                if response.get('apply_profile', False):
                    probe_selected = response['apply_profile']
                    for index, probe in enumerate(settings['probe_settings']['probe_map']['probe_info']):
                        if probe['label'] == probe_selected:
                            settings['probe_settings']['probe_map']['probe_info'][index]['profile'] = settings['probe_settings']['probe_profiles'][UniqueID]

                # Write the new probe profile to disk
                write_settings(settings)
                event['type'] = 'updated'
                event['text'] = 'Successfully added ' + response['Name'] + ' profile.'

            except:
                event['type'] = 'error'
                event['text'] = 'Something bad happened when trying to format your inputs.  Try again.'
        else:
            event['type'] = 'error'
            event['text'] = 'All fields must be completed before submitting. Profile NOT saved.'

    if request.method == 'POST' and action == 'controller_card':
        response = request.form
        render_string = "{% from 'settings/_macro_settings.html' import render_controller_config %}{{ render_controller_config(selected, metadata, settings, cycle_data) }}"
        return render_template_string(render_string, 
                selected=response['selected'], 
                metadata=controller['metadata'], 
                settings=settings['controller'],
                cycle_data=settings['cycle_data'])

    if request.method == 'POST' and action == 'cycle':
        response = request.form

        if is_not_blank(response, 'pmode'):
            settings['cycle_data']['PMode'] = int(response['pmode'])
        if is_not_blank(response, 'holdcycletime'):
            settings['cycle_data']['HoldCycleTime'] = int(response['holdcycletime'])
        if is_not_blank(response, 'SmokeOnCycleTime'):
            settings['cycle_data']['SmokeOnCycleTime'] = int(response['SmokeOnCycleTime'])
        if is_not_blank(response, 'SmokeOffCycleTime'):
            settings['cycle_data']['SmokeOffCycleTime'] = int(response['SmokeOffCycleTime'])

        if is_not_blank(response, 'u_min'):
            settings['cycle_data']['u_min'] = float(response['u_min'])
        if is_not_blank(response, 'u_max'):
            settings['cycle_data']['u_max'] = float(response['u_max'])

        if is_checked(response, 'lid_open_detect_enable'):
            settings['cycle_data']['LidOpenDetectEnabled'] = True
        else:
            settings['cycle_data']['LidOpenDetectEnabled'] = False
        if is_not_blank(response, 'lid_open_threshold'):
            settings['cycle_data']['LidOpenThreshold'] = int(response['lid_open_threshold'])
        if is_not_blank(response, 'lid_open_pausetime'):
            settings['cycle_data']['LidOpenPauseTime'] = int(response['lid_open_pausetime'])
        if is_not_blank(response, 'sp_on_time'):
            settings['smoke_plus']['on_time'] = int(response['sp_on_time'])
        if is_not_blank(response, 'sp_off_time'):
            settings['smoke_plus']['off_time'] = int(response['sp_off_time'])
        if is_checked(response, 'sp_fan_ramp'):
            settings['smoke_plus']['fan_ramp'] = True
        else:
            settings['smoke_plus']['fan_ramp'] = False
        if is_not_blank(response, 'sp_duty_cycle'):
            settings['smoke_plus']['duty_cycle'] = int(response['sp_duty_cycle'])
        if is_not_blank(response, 'sp_min_temp'):
            settings['smoke_plus']['min_temp'] = int(response['sp_min_temp'])
        if is_not_blank(response, 'sp_max_temp'):
            settings['smoke_plus']['max_temp'] = int(response['sp_max_temp'])
        if is_checked(response, 'default_smoke_plus'):
            settings['smoke_plus']['enabled'] = True
        else:
            settings['smoke_plus']['enabled'] = False
        if is_not_blank(response, 'keep_warm_temp'):
            settings['keep_warm']['temp'] = int(response['keep_warm_temp'])
        if is_checked(response, 'keep_warm_s_plus'):
            settings['keep_warm']['s_plus'] = True
        else:
            settings['keep_warm']['s_plus'] = False

        if is_not_blank(response, 'selectController'):
            # Select Controller Type
            selected = response['selectController']
            settings['controller']['selected'] = selected
            settings['controller']['config'][selected] = {}
            # Save Controller Configuration 
            for item, value in response.items(): 
                if item.startswith('controller_config_'):
                    option_name = item.replace('controller_config_', '')
                    for option in controller['metadata'][selected]['config']:
                        if option_name == option['option_name']: 
                            if option['option_type'] == 'float':
                                settings['controller']['config'][selected][option_name] = float(value) 
                            elif option['option_type'] == 'int':
                                settings['controller']['config'][selected][option_name] = int(value)
                            elif option['option_type'] == 'bool':
                                settings['controller']['config'][selected][option_name] = True if value == 'true' else False 
                            elif option['option_type'] == 'numlist':
                                settings['controller']['config'][selected][option_name] = float(value)
                            else: 
                                settings['controller']['config'][selected][option_name] = value
            control['controller_update'] = True
            #print(f'Controller Settings: {settings["controller"]["config"]}')

        event['type'] = 'updated'
        event['text'] = 'Successfully updated cycle settings.'

        control['settings_update'] = True

        write_settings(settings)
        write_control(control, origin='app')

    if request.method == 'POST' and action == 'pwm':
        response = request.form

        if is_checked(response, 'pwm_control'):
            settings['pwm']['pwm_control'] = True
        else:
            settings['pwm']['pwm_control'] = False
        if is_not_blank(response, 'pwm_update'):
            settings['pwm']['update_time'] = int(response['pwm_update'])
        if is_not_blank(response, 'min_duty_cycle'):
            settings['pwm']['min_duty_cycle'] = int(response['min_duty_cycle'])
        if is_not_blank(response, 'max_duty_cycle'):
            settings['pwm']['max_duty_cycle'] = int(response['max_duty_cycle'])
        if is_not_blank(response, 'frequency'):
            settings['pwm']['frequency'] = int(response['frequency'])

        event['type'] = 'updated'
        event['text'] = 'Successfully updated PWM settings.'

        control['settings_update'] = True

        write_settings(settings)
        write_control(control, origin='app')

    if request.method == 'POST' and action == 'startup':
        response = request.form

        if is_not_blank(response, 'shutdown_duration'):
            settings['shutdown']['shutdown_duration'] = int(response['shutdown_duration'])
        if is_not_blank(response, 'startup_duration'):
            settings['startup']['duration'] = int(response['startup_duration'])
        if is_checked(response, 'auto_power_off'):
            settings['shutdown']['auto_power_off'] = True
        else:
            settings['shutdown']['auto_power_off'] = False
        if is_checked(response, 'smartstart_enable'):
            settings['startup']['smartstart']['enabled'] = True
        else:
            settings['startup']['smartstart']['enabled'] = False
        if is_not_blank(response, 'smartstart_exit_temp'):
            settings['startup']['smartstart']['exit_temp'] = int(response['smartstart_exit_temp'])
        if is_not_blank(response, 'startup_exit_temp'):
            settings['startup']['startup_exit_temp'] = int(response['startup_exit_temp'])
        if is_not_blank(response, 'prime_on_startup'):
            prime_amount = int(response['prime_on_startup'])
            if prime_amount < 0 or prime_amount > 200:
                prime_amount = 0  # Validate input, set to disabled if exceeding limits.  
            settings['startup']['prime_on_startup'] = int(response['prime_on_startup'])

        settings['startup']['start_to_mode']['after_startup_mode'] = response['after_startup_mode']
        settings['startup']['start_to_mode']['primary_setpoint'] = int(response['startup_mode_setpoint'])
        
        if is_checked(response, 'startup_start_to_hold_prompt'):
            settings['startup']['start_to_mode']['start_to_hold_prompt'] = True
        else:
            settings['startup']['start_to_mode']['start_to_hold_prompt'] = False

        event['type'] = 'updated'
        event['text'] = 'Successfully updated startup/shutdown settings.'

        control['settings_update'] = True

        write_settings(settings)
        write_control(control, origin='app')

    if request.method == 'POST' and action == 'history':
        response = request.form

        if is_not_blank(response, 'historymins'):
            settings['history_page']['minutes'] = int(response['historymins'])
        if is_checked(response, 'clearhistorystartup'):
            settings['history_page']['clearhistoryonstart'] = True
        else:
            settings['history_page']['clearhistoryonstart'] = False
        if is_checked(response, 'historyautorefresh'):
            settings['history_page']['autorefresh'] = 'on'
        else:
            settings['history_page']['autorefresh'] = 'off'
        if is_not_blank(response, 'datapoints'):
            settings['history_page']['datapoints'] = int(response['datapoints'])

        # This check should be the last in this group
        if control['mode'] != 'Stop' and is_checked(response, 'ext_data') != settings['globals']['ext_data']:
            event['type'] = 'error'
            event['text'] = 'This setting cannot be changed in any active mode.  Stop the grill and try again.'
        else: 
            if is_checked(response, 'ext_data'):
                settings['globals']['ext_data'] = True
            else:
                settings['globals']['ext_data'] = False 

            event['type'] = 'updated'
            event['text'] = 'Successfully updated history settings.'

        # Edit Graph Color Config
        for item in response:
            if 'clr_temp_' in item: 
                probe_label = item.replace('clr_temp_', '')
                settings['history_page']['probe_config'][probe_label]['line_color'] = response[item]
            if 'clrbg_temp_' in item: 
                probe_label = item.replace('clrbg_temp_', '')
                settings['history_page']['probe_config'][probe_label]['bg_color'] = response[item]
            if 'clr_setpoint_' in item: 
                probe_label = item.replace('clr_setpoint_', '')
                settings['history_page']['probe_config'][probe_label]['line_color_setpoint'] = response[item]
            if 'clrbg_setpoint_' in item: 
                probe_label = item.replace('clrbg_setpoint_', '')
                settings['history_page']['probe_config'][probe_label]['bg_color_setpoint'] = response[item]
            if 'clr_target_' in item: 
                probe_label = item.replace('clr_target_', '')
                settings['history_page']['probe_config'][probe_label]['line_color_target'] = response[item]
            if 'clrbg_target_' in item: 
                probe_label = item.replace('clrbg_target_', '')
                settings['history_page']['probe_config'][probe_label]['bg_color_target'] = response[item]

        write_settings(settings)

    if request.method == 'POST' and action == 'safety':
        response = request.form

        if is_not_blank(response, 'minstartuptemp'):
            settings['safety']['minstartuptemp'] = int(response['minstartuptemp'])
        if is_not_blank(response, 'maxstartuptemp'):
            settings['safety']['maxstartuptemp'] = int(response['maxstartuptemp'])
        if is_not_blank(response, 'reigniteretries'):
            settings['safety']['reigniteretries'] = int(response['reigniteretries'])
        if is_not_blank(response, 'maxtemp'):
            settings['safety']['maxtemp'] = int(response['maxtemp'])
        if is_checked(response, 'startup_check'):
            settings['safety']['startup_check'] = True
        else:
            settings['safety']['startup_check'] = False
        if is_checked(response, 'allow_manual_changes'):
            settings['safety']['allow_manual_changes'] = True
        else:
            settings['safety']['allow_manual_changes'] = False
        if is_not_blank(response, 'manual_override_time'):
            settings['safety']['manual_override_time'] = int(response['manual_override_time'])

        event['type'] = 'updated'
        event['text'] = 'Successfully updated safety settings.'

        write_settings(settings)

    if request.method == 'POST' and action == 'pellets':
        response = request.form

        if is_checked(response, 'pellet_warning'):
            settings['pelletlevel']['warning_enabled'] = True
        else:
            settings['pelletlevel']['warning_enabled'] = False
        if is_not_blank(response, 'warning_time'):
            settings['pelletlevel']['warning_time'] = int(response['warning_time'])
        if is_not_blank(response, 'warning_level'):
            settings['pelletlevel']['warning_level'] = int(response['warning_level'])
        if is_not_blank(response, 'empty'):
            settings['pelletlevel']['empty'] = int(response['empty'])
            control['distance_update'] = True
        if is_not_blank(response, 'full'):
            settings['pelletlevel']['full'] = int(response['full'])
            control['distance_update'] = True
        if is_not_blank(response, 'auger_rate'):
            settings['globals']['augerrate'] = float(response['auger_rate'])

        if is_checked(response, 'prime_ignition'):
            settings['globals']['prime_ignition'] = True
        else:
            settings['globals']['prime_ignition'] = False

        event['type'] = 'updated'
        event['text'] = 'Successfully updated pellet settings.'

        control['settings_update'] = True

        write_settings(settings)
        write_control(control, origin='app')

    '''
    Smart Start Settings
    '''
    if request.method == 'GET' and action == 'smartstart':
        temps = settings['startup']['smartstart']['temp_range_list']
        profiles = settings['startup']['smartstart']['profiles']
        return(jsonify({'temps_list' : temps, 'profiles' : profiles}))

    if request.method == 'POST' and action == 'smartstart':
        response = request.json 
        settings['startup']['smartstart']['temp_range_list'] = response['temps_list']
        settings['startup']['smartstart']['profiles'] = response['profiles']
        write_settings(settings)
        return(jsonify({'result' : 'success'}))

    '''
    PWM Duty Cycle
    '''
    if request.method == 'GET' and action == 'pwm_duty_cycle':
        temps = settings['pwm']['temp_range_list']
        profiles = settings['pwm']['profiles']
        return(jsonify({'dc_temps_list' : temps, 'dc_profiles' : profiles}))

    if request.method == 'POST' and action == 'pwm_duty_cycle':
        response = request.json
        settings['pwm']['temp_range_list'] = response['dc_temps_list']
        settings['pwm']['profiles'] = response['dc_profiles']
        write_settings(settings)
        return(jsonify({'result' : 'success'}))

    return render_template(
                            'settings/index.html',
                            alert=event,
                            settings=settings,
                            control=control,
                            controller_metadata=controller['metadata'],
                            page_theme=settings['globals'].get('page_theme', 'light'),
                            grill_name=settings['globals'].get('grill_name', '')
                            )
