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

	def __init__(self):
		self.DisplaySplash()

	def DisplayStatus(self, in_data, status_data):
		print('====[Display]=====')
		print('* Grill Temp: ' + str(in_data['GrillTemp'])[:5] + 'F')
		print('* Grill SetPoint: ' + str(in_data['GrillSetPoint']) + 'F')
		print('* Probe1 Temp: ' + str(in_data['Probe1Temp'])[:5] + 'F')
		print('* Probe1 SetPoint: ' + str(in_data['Probe1SetPoint']) + 'F')
		print('* Probe2 Temp: ' + str(in_data['Probe2Temp'])[:5] + 'F')
		print('* Probe2 SetPoint: ' + str(in_data['Probe2SetPoint']) + 'F')
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

	def DisplaySplash(self):
		print('  (        (')
		print('  )\ )     )\ )')
		print(' (()/( (  (()/(  (   (      (')
		print('  /(_)))\  /(_)) )\  )(    ))\ ')
		print(' (_)) ((_)(_))_|((_)(()\  /((_) ')
		print(' | _ \ (_)| |_   (_) ((_)(_)) ')
		print(' |  _/ | || __|  | || \'_|/ -_)  ')
		print(' |_|   |_||_|    |_||_|  \___|  ')

	def ClearDisplay(self):
		print('[Display] Clear Display Command Sent')

	def DisplayText(self, text):
		print('====[Display]=====')
		print('* Text: ' + str(text))
		print('==================')
