'''
==============================================================================
 PiFire Module Wizard
==============================================================================

 Description: This script used during install to configure modules and settings

==============================================================================
'''

'''
==============================================================================
 Imported Libraries
==============================================================================
'''

from common import * # Common Library for writing settings
import subprocess
import argparse

def _convert_value(value):
	"""
	Converts a given value to an appropriate data type based on its string representation.

	Parameters:
	- value (str): The string representation of the value to be converted.

	Returns:
	- int or float or bool or list or str or None: The converted value in the appropriate data type.

	The function checks if the value is a string representation of a number and converts it to an integer or float if possible. 
	If the value is the string representation of a boolean, it is converted to a boolean value. 
	If the value is the string representation of None, it is converted to None. 
	If the value is a string representation of a list, it is converted to a list. 
	Otherwise, the original value is returned.

	Note:
	- The function assumes that the value parameter is a string.
	- The function does not perform any validation on the input value.
	"""
	if value.isdigit():
		return int(value)
	
	if value.isdecimal():
		return float(value)

	# Convert Boolean String to Standard Boolean
	if value == 'True' or value == 'False':
		return value == 'True'
	
	# Convert 'None' to None 
	if value == 'None':
		return None 
	
	# Covert String List to List
	if type(value) == str:
		if value.startswith('[') and value.endswith(']'):
			value = value.replace('\'', '').replace('\"', '').replace(' ', '')
			return value[1:-1].split(',')

	return value 	

def wizardInstallInfoExisting(settings, wizardData):
	wizardInstallInfo = {
		'modules' : {
			'grillplatform' : {
				'profile_selected' : [settings['platform']['current']],
				'settings' : {},
				'config' : {}
			}, 
			'display' : {
				'profile_selected' : [settings['modules']['display']],
				'settings' : {},
				'config' : {}
			}, 
			'distance' : {
				'profile_selected' : [settings['modules']['dist']],
				'settings' : {},
				'config' : {}
			}, 
			'probes' : {
				'profile_selected' : [],
				'settings' : {
					'units' : settings['globals']['units']
				},
				'config' : {}
			}
		}, 
		'probe_map' : settings['probe_settings']['probe_map']
	} 
	''' Populate Probes Module List with all configured probe devices '''
	for device in wizardInstallInfo['probe_map']['probe_devices']:
		wizardInstallInfo['modules']['probes']['profile_selected'].append(device['module'])
	
	''' Populate Modules Info with current Settings '''
	for module in ['grillplatform', 'display', 'distance']:
		selected = wizardInstallInfo['modules'][module]['profile_selected'][0]
		''' Error condition if the item in settings doesn't match the wizard manifest '''
		if selected not in wizardData['modules'][module].keys():
			if module == 'grillplatform':
				selected = 'custom'
				settings['platform']['current'] = selected
			else:
				selected = 'none'
			wizardInstallInfo['modules'][module]['profile_selected'] = selected

		for setting in wizardData['modules'][module][selected]['settings_dependencies']:
			settingsLocation = wizardData['modules'][module][selected]['settings_dependencies'][setting]['settings']
			settingsValue = settings.copy() 
			for index in range(0, len(settingsLocation)):
				settingsValue = settingsValue[settingsLocation[index]]
			wizardInstallInfo['modules'][module]['settings'][setting] = str(settingsValue)
		if module == 'display':
			wizardInstallInfo['modules'][module]['config'] = settings['display']['config'][settings['modules']['display']]
	return wizardInstallInfo

def run_wizard(settings, WizardData, WizardInstallInfo):
	settings = read_settings()

	percent = 5
	status = 'Setting Up Modules...'
	output = ' - Adding selected modules to the settings.json file. '
	set_wizard_install_status(percent, status, output)
	time.sleep(2)

	display_selected = WizardInstallInfo['modules']['display']['profile_selected'][0]
	settings['modules']['display'] = WizardData['modules']['display'][display_selected]['filename']
	settings['display']['selected'] = display_selected
	distance_selected = WizardInstallInfo['modules']['distance']['profile_selected'][0]
	settings['modules']['dist'] = WizardData['modules']['distance'][distance_selected]['filename']

	''' Configuring Probes Data '''
	settings['probe_settings']['probe_map'] = WizardInstallInfo['probe_map']

	''' Update History Page Config with Latest Probe Config '''
	settings['history_page']['probe_config'] = default_probe_config(settings)

	percent = 10
	status = 'Updating Settings...'
	output = ' - Adding selected settings to the settings.json file.'
	set_wizard_install_status(percent, status, output)
	time.sleep(2)

	for module in WizardInstallInfo['modules']:
		for setting in WizardInstallInfo['modules'][module]['settings']:
			selected = WizardInstallInfo['modules'][module]['profile_selected'][0]
			settingsLocation = WizardData['modules'][module][selected]['settings_dependencies'][setting]['settings']
			selected_setting = WizardInstallInfo['modules'][module]['settings'][setting]

			# Convert Strings to the correct type 
			selected_setting = _convert_value(selected_setting)

			# Special Handling for Units
			if setting == 'units':
				units = WizardInstallInfo['modules'][module]['settings'][setting]
				if units == 'C' and settings['globals']['units'] == 'F':
					settings = convert_settings_units('C', settings)
				elif(units == 'F') and (settings['globals']['units'] == 'C'):
					settings = convert_settings_units('F', settings)
			else:
				settings = set_nested_key_value(settings, settingsLocation, selected_setting)
			output = f'   + Set {setting} in settings.json'
			set_wizard_install_status(percent, status, output)
		if module == 'display':
			selected = WizardInstallInfo['modules'][module]['profile_selected'][0]
			settings['display']['config'][selected] = WizardInstallInfo['modules']['display']['config']
			for key in settings['display']['config'][selected]:
				# Convert Strings to the correct type
				settings['display']['config'][selected][key] = _convert_value(settings['display']['config'][selected][key])

	percent = 15
	status = 'Installing Dependencies...'
	output = ' - Installing Dependencies'
	set_wizard_install_status(percent, status, output)
	time.sleep(2)

	''' Set the grillplatform module per the system_type '''
	settings['modules']['grillplat'] = 'prototype'
	if settings['platform']['system_type'] == 'raspberry_pi_all':
		settings['modules']['grillplat'] = 'raspberry_pi_all'

	# Commit Settings to JSON
	write_settings(settings)

	percent = 20
	status = 'Calculating Python/Package Dependencies...'
	output = ' - Calculating Python, APT Package, and General Dependencies'
	set_wizard_install_status(percent, status, output)
	time.sleep(2)
	# Get PyPi & Apt dependencies
	py_dependencies = []
	apt_dependencies = []
	command_list = []
	reboot_required = False 

	for module in WizardInstallInfo['modules']:
		for selected in WizardInstallInfo['modules'][module]['profile_selected']:
			if module == 'grillplatform':
				selected = WizardInstallInfo['modules'][module]['settings']['current']
			for py_dependency in WizardData['modules'][module][selected]['py_dependencies']:
				py_dependencies.append(py_dependency)
			for apt_dependency in WizardData['modules'][module][selected]['apt_dependencies']:
				apt_dependencies.append(apt_dependency)
			for command in WizardData['modules'][module][selected]['command_list']:
				command_list.append(command)
			if WizardData['modules'][module][selected]['reboot_required']:
				reboot_required = True

	# Calculate the percent done from remaining items to install 
	items_remaining = len(py_dependencies) + len(apt_dependencies) + len(command_list)
	if items_remaining == 0:
		increment = 80
	else:
		increment = 80 / items_remaining 

	# Install Apt dependencies
	launch_apt = ['sudo', 'apt', 'install']
	status = 'Installing Package Dependencies...'
	output = ' - Installing APT Package Dependencies'
	set_wizard_install_status(percent, status, output)

	for apt_item in apt_dependencies:
		command = []
		command.extend(launch_apt)
		command.append(apt_item)
		command.append('-y')
		
		if is_real_hardware():
			process = subprocess.Popen(command, stdout=subprocess.PIPE, encoding='utf-8')
			while True:
				output = process.stdout.readline()
				if process.poll() is not None:
					break
				if output:
					set_wizard_install_status(percent, status, output.strip())
					print(output.strip())
			return_code = process.poll()
			print(f'Return Code: {return_code}')
		else:
			# This path is for development/testing
			time.sleep(2)
		
		percent += increment
		output = f' - Completed Install of {apt_item}'
		set_wizard_install_status(percent, status, output)

	# Install Py dependencies
	python_exec = settings['globals'].get('python_exec', 'python')

	if settings['globals'].get('uv', False):
		launch_pip = ['uv', 'pip', 'install']
	else:
		launch_pip = [python_exec, '-m', 'pip', 'install']

	status = 'Installing Python Dependencies...'
	output = ' - Installing Python Dependencies'
	set_wizard_install_status(percent, status, output)

	for py_item in py_dependencies:
		command = []
		command.extend(launch_pip)
		command.append(py_item)

		if is_real_hardware():
			process = subprocess.Popen(command, stdout=subprocess.PIPE, encoding='utf-8')
			while True:
				output = process.stdout.readline()
				if process.poll() is not None:
					break
				if output:
					set_wizard_install_status(percent, status, output.strip())
					print(output.strip())
			return_code = process.poll()
			print(f'Return Code: {return_code}')
		else:
			# This path is for development/testing
			time.sleep(2)

		percent += increment
		output = f' - Completed Install of {py_item}'
		set_wizard_install_status(percent, status, output)

	# Get PIP List 
	command = [python_exec, 'updater.py', '-p']

	pip_list = subprocess.run(command, capture_output=True, text=True)
	if pip_list.returncode == 0:
		print(f'PIP List Command Success.')

	# Run system commands dependencies
	status = 'Installing General Dependencies...'
	output = ' - Installing General Dependencies'
	set_wizard_install_status(percent, status, output)

	for command in command_list:
		if is_real_hardware():
			process = subprocess.Popen(command, stdout=subprocess.PIPE, encoding='utf-8')
			while True:
				output = process.stdout.readline()
				if process.poll() is not None:
					break
				if output:
					set_wizard_install_status(percent, status, output.strip())
					print(f'command output: {output.strip()}')
			#return_code = process.poll()
		else:
			# This path is for development/testing
			time.sleep(2)
			
		percent += increment
		output = f' - Completed General Dependency Item'
		set_updater_install_status(percent, status, output)

	percent = 100
	status = 'Finished!'
	if reboot_required:
		output = ' - Finished!  Rebooting Server...'
	else: 
		output = ' - Finished!  Restarting Server...'

	set_wizard_install_status(percent, status, output)

	time.sleep(4)

	percent = 142 if reboot_required else 101
	set_wizard_install_status(percent, status, output)

	# Clear First Time Setup Flag
	settings['globals']['first_time_setup'] = False 
	# Commit Setting to JSON
	write_settings(settings)



'''
==============================================================================
 Main Program
==============================================================================
'''

print('PiFire Module Wizard')
print('Copyright 2022-2025, MIT License, Ben Parmeter')

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description='PiFire Module Wizard')
	parser.add_argument('-e','--existing', action='store_true', help='Run the wizard to install modules and settings for an existing PiFire installation.')
	
	args = parser.parse_args()

	# Load Settings
	settings = read_settings()
	# Load Wizard Data
	WizardData = read_wizard()

	if args.existing:
		print('Running Wizard for Existing PiFire Installation...')
		WizardInstallInfo = wizardInstallInfoExisting(settings, WizardData)
		if not WizardInstallInfo:
			print('No existing wizard install info found. Exiting.')
			exit(1)
		else:
			print('Found existing wizard install info.')
			run_wizard(settings, WizardData, WizardInstallInfo)
			exit(0)
	else:		
		WizardInstallInfo = load_wizard_install_info()
		if WizardInstallInfo is None:
			print('No wizard install info found.  Exiting...')
			exit(1)
		else:
			print('Found existing wizard install info.')
			run_wizard(settings, WizardData, WizardInstallInfo)
			exit(0)
