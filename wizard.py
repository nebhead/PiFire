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

'''
==============================================================================
 Main Program
==============================================================================
'''

print('PiFire Module Wizard')
print('Copyright 2022, MIT License, Ben Parmeter')

settings = read_settings()

WizardData = read_wizard()
WizardInstallInfo = load_wizard_install_info()

percent = 5
status = 'Setting Up Modules...'
output = ' - Adding selected modules to the settings.json file. '
set_wizard_install_status(percent, status, output)
time.sleep(2)

display_selected = WizardInstallInfo['modules']['display']['profile_selected'][0]
settings['modules']['display'] = WizardData['modules']['display'][display_selected]['filename']
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

		# Convert Number Strings to Int or Float
		if selected_setting.isdigit():
			selected_setting = int(selected_setting)
		elif selected_setting.isdecimal():
			selected_setting = float(selected_setting)

		# Convert Boolean String to Standard Boolean
		if selected_setting == 'True' or selected_setting == 'False':
			selected_setting = selected_setting == 'True'
		
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

# Install Py dependencies
if settings['globals']['venv']:
	python_exec = 'bin/python'
else:
	python_exec = 'python'

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
