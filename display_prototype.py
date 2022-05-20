#!/usr/bin/env python3

# *****************************************
# PiFire Display Prototype Interface Library
# *****************************************
#
# Description: This library simulates a display.
#
# *****************************************

# *****************************************
# Imported Libraries
# *****************************************

class Display:

	def __init__(self, buttonslevel='HIGH', rotation=0, units='F'):
		self.display_splash()
		self.units = units 

	def display_status(self, in_data, status_data):
		units = status_data['units']
		print('====[Display]=====')
		print('* Grill Temp: ' + str(in_data['GrillTemp'])[:5] + units)
		print('* Grill SetPoint: ' + str(in_data['GrillSetPoint']) + units)
		print('* Probe1 Temp: ' + str(in_data['Probe1Temp'])[:5] + units)
		print('* Probe1 SetPoint: ' + str(in_data['Probe1SetPoint']) + units)
		print('* Probe2 Temp: ' + str(in_data['Probe2Temp'])[:5] + units)
		print('* Probe2 SetPoint: ' + str(in_data['Probe2SetPoint']) + units)
		print('* Mode: ' + str(status_data['mode']))
		notification = False 
		for item in status_data['notify_req']:
			if status_data['notify_req'][item] == True:
				notification = True
		if notification == True:
			print('* Notifications: True')
		for item in status_data['outpins']:
			if status_data['outpins'][item] == 0:
				print('* ' + str(item) + ' ON')
		print('==================')

	def display_splash(self):
		print('  (        (')
		print('  )\ )     )\ )')
		print(' (()/( (  (()/(  (   (      (')
		print('  /(_)))\  /(_)) )\  )(    ))\ ')
		print(' (_)) ((_)(_))_|((_)(()\  /((_) ')
		print(' | _ \ (_)| |_   (_) ((_)(_)) ')
		print(' |  _/ | || __|  | || \'_|/ -_)  ')
		print(' |_|   |_||_|    |_||_|  \___|  ')

	def clear_display(self):
		print('[Display] Clear Display Command Sent')

	def display_text(self, text):
		print('====[Display]=====')
		print('* Text: ' + str(text))
		print('==================')

	def display_network(self):
		pass