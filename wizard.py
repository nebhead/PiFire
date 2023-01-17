#!/usr/bin/env python3

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

settings['modules']['grillplat'] = WizardInstallInfo['modules']['grillplatform']['module_selected'][0]
#settings['modules']['adc'] = WizardInstallInfo['modules']['probes']['module_selected']		
settings['modules']['display'] = WizardInstallInfo['modules']['display']['module_selected'][0]
settings['modules']['dist'] = WizardInstallInfo['modules']['distance']['module_selected'][0]		

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
		selected = WizardInstallInfo['modules'][module]['module_selected'][0]
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
		elif len(settingsLocation) == 1:
			settings[settingsLocation[0]] = selected_setting
		elif len(settingsLocation) == 2:
			settings[settingsLocation[0]][settingsLocation[1]] = selected_setting
		elif len(settingsLocation) == 3:
			settings[settingsLocation[0]][settingsLocation[1]][settingsLocation[2]] = selected_setting

		output = f'   + Set {setting} in settings.json'
		set_wizard_install_status(percent, status, output)

# Commit Settings to JSON
write_settings(settings)

percent = 20
status = 'Calculating Python/Package Dependencies...'
output = ' - Calculating Python & Package Dependencies'
set_wizard_install_status(percent, status, output)
time.sleep(2)
# Get PyPi & Apt dependencies
py_dependencies = []
apt_dependencies = []
for module in WizardInstallInfo['modules']:
	for selected in WizardInstallInfo['modules'][module]['module_selected']:
		for py_dependency in WizardData['modules'][module][selected]['py_dependencies']:
			py_dependencies.append(py_dependency)
		for apt_dependency in WizardData['modules'][module][selected]['apt_dependencies']:
			apt_dependencies.append(apt_dependency)

# Calculate the percent done from remaining items to install 
items_remaining = len(py_dependencies) + len(apt_dependencies)
if items_remaining == 0:
	increment = 80
else:
	increment = 80 / items_remaining 

# Install Py dependencies
launch_pip = ['pip3', 'install']
status = 'Installing Python Dependencies...'
output = ' - Installing Python Dependencies'
set_wizard_install_status(percent, status, output)

for py_item in py_dependencies:
	command = []
	command.extend(launch_pip)
	command.append(py_item)

	if is_raspberry_pi():
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
launch_apt = ['apt', 'install']
status = 'Installing Package Dependencies...'
output = ' - Installing APT Package Dependencies'
set_wizard_install_status(percent, status, output)

for apt_item in apt_dependencies:
	command = []
	command.extend(launch_apt)
	command.append(apt_item)
	command.append('-y')
	
	if is_raspberry_pi():
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

percent = 100
status = 'Finished!'
output = ' - Finished!  Restarting Server...'
set_wizard_install_status(percent, status, output)

time.sleep(4)

percent = 101
set_wizard_install_status(percent, status, output)

# Clear First Time Setup Flag
settings['globals']['first_time_setup'] = False 
# Commit Setting to JSON
write_settings(settings)
