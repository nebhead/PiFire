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

settings = ReadSettings()

WizardData = ReadWizard()
WizardInstallInfo = LoadWizardInstallInfo()

percent = 5
status = 'Setting Up Modules...'
output = ' - Adding selected modules to the settings.json file. '
SetWizardInstallStatus(percent, status, output)
time.sleep(2)

settings['modules']['grill_plat'] = WizardInstallInfo['modules']['grillplatform']['module_selected']		
settings['modules']['adc'] = WizardInstallInfo['modules']['probes']['module_selected']		
settings['modules']['display'] = WizardInstallInfo['modules']['display']['module_selected']		
settings['modules']['dist'] = WizardInstallInfo['modules']['distance']['module_selected']		

percent = 10
status = 'Updating Settings...'
output = ' - Adding selected settings to the settings.json file.'
SetWizardInstallStatus(percent, status, output)
time.sleep(2)

for module in WizardInstallInfo['modules']:
	for setting in WizardInstallInfo['modules'][module]['settings']:
		selected = WizardInstallInfo['modules'][module]['module_selected']
		settingsLocation = WizardData['modules'][module][selected]['settings_dependencies'][setting]['settings']
		
		# Special Handling for Units
		if(setting == 'units'):
			units = WizardInstallInfo['modules'][module]['settings'][setting]
			if(units == 'C') and (settings['globals']['units'] == 'F'):
				settings = convert_settings_units('C', settings)
			elif(units == 'F') and (settings['globals']['units'] == 'C'):
				settings = convert_settings_units('F', settings)
		elif(len(settingsLocation) == 1):
			settings[settingsLocation[0]] = WizardInstallInfo['modules'][module]['settings'][setting]
		elif(len(settingsLocation) == 2):
			settings[settingsLocation[0]][settingsLocation[1]] = WizardInstallInfo['modules'][module]['settings'][setting]
		elif(len(settingsLocation) == 3):
			settings[settingsLocation[0]][settingsLocation[1]][settingsLocation[2]] = WizardInstallInfo['modules'][module]['settings'][setting]

		output = f'   + Set {setting} in settings.json'
		SetWizardInstallStatus(percent, status, output)

# Commit Settings to JSON
WriteSettings(settings)

percent = 20
status = 'Calculating Python/Package Dependencies...'
output = ' - Calculating Python & Package Dependencies'
SetWizardInstallStatus(percent, status, output)
time.sleep(2)
# Get PyPi & Apt dependencies
py_dependencies = []
apt_dependencies = []
for module in WizardInstallInfo['modules']:
	selected = WizardInstallInfo['modules'][module]['module_selected']
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
launchpip = ['pip3', 'install']
status = 'Installing Python Dependencies...'
output = ' - Installing Python Dependencies'
SetWizardInstallStatus(percent, status, output)

for py_item in py_dependencies:
	command = []
	command.extend(launchpip)
	command.append(py_item)

	if(isRaspberryPi()):
		process = subprocess.Popen(command, stdout=subprocess.PIPE, encoding='utf-8')
		while True:
			output = process.stdout.readline()
			if process.poll() is not None:
				break
			if output:
				SetWizardInstallStatus(percent, status, output.strip())
				print(output.strip())
		returncode = process.poll()
		print(f'Return Code: {returncode}')
	else:
		# This path is for development/testing
		time.sleep(2)

	percent += increment
	output = f' - Completed Install of {py_item}'
	SetWizardInstallStatus(percent, status, output)

# Install Apt dependencies
launchapt = ['apt', 'install']
status = 'Installing Package Dependencies...'
output = ' - Installing APT Package Dependencies'
SetWizardInstallStatus(percent, status, output)

for apt_item in apt_dependencies:
	command = []
	command.extend(launchapt)
	command.append(apt_item)
	command.append('-y')
	
	if(isRaspberryPi()):
		process = subprocess.Popen(command, stdout=subprocess.PIPE, encoding='utf-8')
		while True:
			output = process.stdout.readline()
			if process.poll() is not None:
				break
			if output:
				SetWizardInstallStatus(percent, status, output.strip())
				print(output.strip())
		returncode = process.poll()
		print(f'Return Code: {returncode}')
	else:
		# This path is for development/testing
		time.sleep(2)
	
	percent += increment
	output = f' - Completed Install of {apt_item}'
	SetWizardInstallStatus(percent, status, output)

percent = 100
status = 'Finished!'
output = ' - Finished!  Restarting Server...'
SetWizardInstallStatus(percent, status, output)

time.sleep(4)

percent = 101
SetWizardInstallStatus(percent, status, output)

# Clear First Time Setup Flag
settings['globals']['first_time_setup'] = False 
# Commit Setting to JSON
WriteSettings(settings)
