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

	def DisplayTemp(self, temp):
		print('====[Display]=====')
		print('* Temp: ' + str(temp) + 'F')
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
		print('Clear Display Command Sent')

	def DisplayText(self, text):
		print('====[Display]=====')
		print('* Text: ' + str(text))
		print('==================')
