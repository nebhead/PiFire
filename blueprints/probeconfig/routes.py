
from flask import request, render_template_string
from common.common import read_settings, read_wizard, load_wizard_install_info, store_wizard_install_info

from . import probeconfig_bp


@probeconfig_bp.route('/', methods=['POST','GET'])
def probeconfig_page():
    settings = read_settings()

    wizardData = read_wizard()
    wizardInstallInfo = load_wizard_install_info()
    alerts = []
    errors = 0

    if request.method == 'GET':
        render_string = "{% from 'probeconfig/_macro_probes_config.html' import render_probe_devices, render_probe_ports %}{{ render_probe_devices(probe_map, modules, alerts) }}{{ render_probe_ports(probe_map, modules) }}"
        return render_template_string(render_string, probe_map=wizardInstallInfo['probe_map'], modules=wizardData['modules']['probes'], alerts=alerts)
    elif request.method == 'POST':
        r = request.form
        if r['section'] == 'devices':
            if r['action'] == 'delete_device':
                for index, device in enumerate(wizardInstallInfo['probe_map']['probe_devices']):
                    if device['device'] == r['name']:
                        # Remove the device from the device list
                        wizardInstallInfo['probe_map']['probe_devices'].pop(index)
                        # Remove probes associated with device from the probe list
                        probe_info = []
                        for index, probe in enumerate(wizardInstallInfo['probe_map']['probe_info']):
                            # to maintain consistency while iterating, create a new list of probes
                            if probe['device'] != r['name']:
                                probe_info.append(probe)
                        wizardInstallInfo['probe_map']['probe_info'] = probe_info
                        store_wizard_install_info(wizardInstallInfo)
                        break 
            if r['action'] == 'add_config':
                ''' Populate Configuration Settings into Modal '''
                moduleData = wizardData['modules']['probes'][r['module']]
                friendlyName = wizardData['modules']['probes'][r['module']]['friendly_name']
                deviceName = "".join([x for x in friendlyName if x.isalnum()])
                available_probes = []
                ''' Get a list of port-labels that can be used by the virtual port '''
                for index, probe in enumerate(wizardInstallInfo['probe_map']['probe_info']):
                    available_probes.append(probe['label'])
                ''' Set default configuration data '''
                defaultConfig = {}
                for config_setting in moduleData['device_specific']['config']:
                    if config_setting['label'] == 'probes_list':
                        defaultConfig[config_setting['label']] = []
                    else:
                        defaultConfig[config_setting['label']] = config_setting['default']
                render_string = "{% from 'probeconfig/_macro_probes_config.html' import render_probe_device_settings %}{{ render_probe_device_settings(moduleData, moduleSection, defaultName, defaultConfig, available_probes, mode) }}"
                return render_template_string(render_string, moduleData=moduleData, moduleSection='probes', defaultName=deviceName, defaultConfig=defaultConfig, available_probes=available_probes, mode='Add')
            if r['action'] == 'add_device':
                ''' Add device to the Wizard Install Info Probe Map Devices '''
                device_name = "".join([x for x in r['name'] if x.isalnum()])
                # Check if any other devices are using that name
                for index, device in enumerate(wizardInstallInfo['probe_map']['probe_devices']):
                    if device['device'] == device_name: 
                        alert = {
                            'message' : 'Device name already exists.  Please select a unique device name.',
                            'type' : 'error'
                        }
                        alerts.append(alert)
                        errors += 1
                        break 
                
                if r['name'] == '': 
                    alert = {
                        'message' : 'Device name is blank.  Please select a unique device name.',
                        'type' : 'error'
                    }
                    alerts.append(alert)
                    errors += 1

                if errors == 0:
                    # Configure new device entry
                    new_device = {
                        "config": {},
                        "device": device_name,
                        "module": r['module'],
                        "module_filename": wizardData['modules']['probes'][r['module']]['filename'],
                        "ports": wizardData['modules']['probes'][r['module']]['device_specific']['ports']
                    }
                    # If any device specific configuration settings, set them here
                    for key, config_value in r.items():
                        if 'probes_devspec_' in key:
                            if '[]' in key:
                                config_item = key.replace('probes_devspec_', '').replace('[]', '')
                                new_device['config'][config_item] = request.form.getlist(key)
                            else:
                                config_item = key.replace('probes_devspec_', '')
                                new_device['config'][config_item] = config_value 
                    
                    wizardInstallInfo['probe_map']['probe_devices'].append(new_device)
                    store_wizard_install_info(wizardInstallInfo)
            if r['action'] == 'edit_config':
                ''' Populate Configuration Settings into Modal '''
                device_name = r['name']
                for index, device in enumerate(wizardInstallInfo['probe_map']['probe_devices']):
                    if device['device'] == device_name: 
                        #wizardInstallInfo['probe_map']['probe_devices'][index]
                        moduleData = wizardData['modules']['probes'][device['module']]
                        defaultConfig = device['config']
                        break 
                    
                ''' Get a list of port-labels that can be used by the virtual port '''
                available_probes = []
                for index, probe in enumerate(wizardInstallInfo['probe_map']['probe_info']):
                    available_probes.append(probe['label'])

                render_string = "{% from 'probeconfig/_macro_probes_config.html' import render_probe_device_settings %}{{ render_probe_device_settings(moduleData, moduleSection, defaultName, defaultConfig, available_probes, mode) }}"
                return render_template_string(render_string, moduleData=moduleData, moduleSection='probes', defaultName=device_name, defaultConfig=defaultConfig, available_probes=available_probes, mode='Edit')
            if r['action'] == 'edit_device':
                ''' Save changes from edited device to WizardInstallInfo structure '''
                if r['newname'] == '': 
                    alert = {
                        'message' : 'Device name is blank.  Please select a unique device name.',
                        'type' : 'error'
                    }
                    alerts.append(alert)
                    errors += 1
                
                if not errors: 
                    # Configure new device entry
                    new_device = {
                        "config": {},
                        "device": r['newname'],
                        "module": "",
                        "module_filename": "",
                        "ports": []
                    }
                    # If any device specific configuration settings, set them here
                    for key, config_value in r.items():
                        if 'probes_devspec_' in key:
                            if '[]' in key:
                                config_item = key.replace('probes_devspec_', '').replace('[]', '')
                                new_device['config'][config_item] = request.form.getlist(key)
                            else:
                                config_item = key.replace('probes_devspec_', '')
                                new_device['config'][config_item] = config_value 
                    for index, probe in enumerate(wizardInstallInfo['probe_map']['probe_devices']):
                        if probe['device'] == r['name']:
                            new_device['ports'] = probe['ports']
                            new_device['module'] = probe['module']
                            new_device['module_filename'] = probe.get('module_filename', probe['module'])
                            wizardInstallInfo['probe_map']['probe_devices'][index] = new_device
                            store_wizard_install_info(wizardInstallInfo)
                            break
            render_string = "{% from 'probeconfig/_macro_probes_config.html' import render_probe_devices, render_probe_ports %}{{ render_probe_devices(probe_map, modules, alerts) }}"
            return render_template_string(render_string, probe_map=wizardInstallInfo['probe_map'], modules=wizardData['modules']['probes'], alerts=alerts)
        elif r['section'] == 'ports':
            if r['action'] == 'delete_probe':
                for probe_index, probe in enumerate(wizardInstallInfo['probe_map']['probe_info']):
                    if probe['label'] == r['label']:
                        # Check if probe is being used in a virtual device, and delete it from there. 
                        for index, device in enumerate(wizardInstallInfo['probe_map']['probe_devices']):
                            if 'virtual' in device['module']:
                                if probe['label'] in device['config']['probes_list']: 
                                    wizardInstallInfo['probe_map']['probe_devices'][index]['config']['probes_list'].remove(probe['label'])
                        wizardInstallInfo['probe_map']['probe_info'].pop(probe_index)
                        store_wizard_install_info(wizardInstallInfo)
                        break

            if r['action'] == 'config':
                defaultLabel = r['label']
                defaultConfig = {
                    'name' : '', 
                    'device_port' : '',
                    'type' : '',
                    'profile_id' : '',
                    'enabled' : 'true'
                }

                if r['label'] != '':
                    for index, probe in enumerate(wizardInstallInfo['probe_map']['probe_info']):
                        if probe['label'] == r['label']:
                            defaultConfig['name'] = probe['name']
                            defaultConfig['device_port'] = f'{probe["device"]}:{probe["port"]}'
                            defaultConfig['type'] = probe['type']
                            defaultConfig['profile_id'] = probe['profile']['id']
                            defaultConfig['enabled'] = 'true' if probe['enabled'] else 'false'
                            break
                
                configOptions = wizardData['probe_config_options']

                # Populate Device & Port Options
                for index, device in enumerate(wizardInstallInfo['probe_map']['probe_devices']):
                    device_name = device['device']
                    for port in device['ports']:
                        option_id = f'{device_name}:{port}'
                        option_name = f'{device_name} -> {port}'
                        configOptions['device_port']['options'][option_id] = option_name 

                # Populate Probe Profiles
                for profile in settings['probe_settings']['probe_profiles']:
                    configOptions['profile_id']['options'][profile] = settings['probe_settings']['probe_profiles'][profile]['name']

                render_string = "{% from 'probeconfig/_macro_probes_config.html' import render_probe_port_settings %}{{ render_probe_port_settings(defaultLabel, defaultConfig, configOptions) }}"
                return render_template_string(render_string, defaultLabel=defaultLabel, defaultConfig=defaultConfig, configOptions=configOptions)

            if r['action'] == 'add_probe' or r['action'] == 'edit_probe':
                new_probe = {} 
                for key, config_value in r.items():
                    if 'probe_config_' in key:
                        config_item = key.replace('probe_config_', '')
                        new_probe[config_item] = config_value 

                if new_probe['name'] == '':
                    errors += 1
                    # Error: Probe Name is empty. 
                    alert = {
                        'message' : 'Probe name is empty.  Please select a probe name.',
                        'type' : 'error'
                    }
                    alerts.append(alert)					

                new_probe['enabled'] = True if new_probe['enabled'] == 'true' else False 
                new_probe['label'] = "".join([x for x in new_probe['name'] if x.isalnum()])
                new_probe['device'] = new_probe['device_port'].split(':')[0]
                new_probe['port'] = new_probe['device_port'].split(':')[1]
                new_probe.pop('device_port')

                for profile in settings['probe_settings']['probe_profiles']:
                    if profile == new_probe['profile_id']:
                        new_probe['profile'] = settings['probe_settings']['probe_profiles'][profile].copy()
                        break 
                new_probe.pop('profile_id') 

                # Look for existing probe with the same name
                found = None
                for index, probe in enumerate(wizardInstallInfo['probe_map']['probe_info']):
                    if r['name'] != '' and probe['label'] == r['name']:
                        found = index
                        break 
                    elif probe['label'] == new_probe['label']:
                        found = index 
                        break 
                
                # Check for primary probe conflict
                if new_probe['type'] == 'Primary': 
                    for index, probe in enumerate(wizardInstallInfo['probe_map']['probe_info']):
                        if probe['label'] == r['name']:
                            pass
                        elif probe['type'] == 'Primary':
                            # Found a conflict, report error  
                            errors += 1
                            # Error: Probe Name is empty. 
                            alert = {
                                'message' : f'There must only be one Primary probe defined. The probe named {probe["name"]} is already set to primary.  Delete or edit that probe to a different type, before setting a new primary probbe.',
                                'type' : 'error'
                            }
                            alerts.append(alert)
                            break

                if errors: 
                    pass 
                elif found is not None and r['name'] == '':
                    # Error Adding New Probe: There is already a probe with the same name
                    alert = {
                        'message' : 'Probe name is already used or is similar to another probe name.  Please select a different probe name.  Note: Special characters and spaces are removed when checking names.',
                        'type' : 'error'
                    }
                    alerts.append(alert)					
                elif found is not None and r['name'] != '':
                    # Check virtual ports and fix up probe labels if they've changed 
                    in_virtual_device = []
                    for index, device in enumerate(wizardInstallInfo['probe_map']['probe_devices']):
                        if 'virtual' in device['module']: 
                            if r['name'] in device['config']['probes_list']:
                                for item, value in enumerate(wizardInstallInfo['probe_map']['probe_devices'][index]['config']['probes_list']):
                                    if value == r['name']: 
                                        wizardInstallInfo['probe_map']['probe_devices'][index]['config']['probes_list'][item] = new_probe['label']
                                        in_virtual_device.append(device['device']) # 
                                        break 
                    
                    # If this is a virtual port, check to make sure this config entry comes after the probe input config entries for this port
                    if 'VIRT' in new_probe['port']:
                        for index, device in enumerate(wizardInstallInfo['probe_map']['probe_devices']):
                            if 'virtual' in device['module'] and new_probe['device'] == device['device']:
                                input_probes = device['config']['probes_list']
                                for probe in range(len(wizardInstallInfo['probe_map']['probe_info']), 0, -1):
                                    if wizardInstallInfo['probe_map']['probe_info'][probe]['label'] == new_probe['label']:
                                        # Found the virtual probe first, current location is OK
                                        wizardInstallInfo['probe_map']['probe_info'][found] = new_probe
                                        break 
                                    elif wizardInstallInfo['probe_map']['probe_info'][probe]['label'] in input_probes:
                                        # Found one of the input probes first, fix by inserting edited probe config here
                                        wizardInstallInfo['probe_map']['probe_info'].insert(probe, new_probe)
                                        # Remove the previous config from the list
                                        wizardInstallInfo['probe_map']['probe_info'].pop(found)
                                        break 
                                break 

                    elif in_virtual_device != []:
                        # If this probe is used by a virtual device, make sure its config entry comes before the config entry for the virtual port 
                        for index, probe in enumerate(wizardInstallInfo['probe_map']['probe_info']):
                            if wizardInstallInfo['probe_map']['probe_info'][index]['label'] == r['name']:
                                # Found the probe config for the virtual device, current location is OK 
                                wizardInstallInfo['probe_map']['probe_info'][index] = new_probe
                                break
                            elif wizardInstallInfo['probe_map']['probe_info'][index]['device'] in in_virtual_device:
                                # Found this input probes first, fix by inserting edited probe config here
                                wizardInstallInfo['probe_map']['probe_info'].insert(index, new_probe)
                                # Remove the previous config from the list
                                wizardInstallInfo['probe_map']['probe_info'].pop(found+1)
                                break 
                    else: 
                        # Editing probe with new data
                        wizardInstallInfo['probe_map']['probe_info'][found] = new_probe
                    store_wizard_install_info(wizardInstallInfo)
                elif not found and r['name'] == '':
                    # Adding new probe
                    wizardInstallInfo['probe_map']['probe_info'].append(new_probe)
                    store_wizard_install_info(wizardInstallInfo)
                else:
                    # Other Error
                    alert = {
                        'message' : 'Error Adding/Editing Probe.  Please try again.',
                        'type' : 'error'
                    }
                    alerts.append(alert)	
                    
            render_string = "{% from 'probeconfig/_macro_probes_config.html' import render_probe_devices, render_probe_ports %}{{ render_probe_ports(probe_map, modules, alerts) }}"
            return render_template_string(render_string, probe_map=wizardInstallInfo['probe_map'], modules=wizardData['modules']['probes'], alerts=alerts)
    else:
        render_string = "Error!"
        return render_template_string(render_string)

