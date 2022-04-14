#!/usr/bin/env python3

# *****************************************
# PiFire Display None Interface Library
# *****************************************
#
# Description: This library can be used on 
# systems with no display present.  
#
# *****************************************

# *****************************************
# Imported Libraries
# *****************************************

class Display:

	def __init__(self, units='F'):
		self.DisplaySplash()

	def DisplayStatus(self, in_data, status_data):
		pass 

	def DisplaySplash(self):
		print('[Splash] PiFire Display Starting Up')

	def ClearDisplay(self):
		print('[Display] Clear Display Command Sent')

	def DisplayText(self, text):
		print(f'[Display] {text}')

	def EventDetect(self):
		return()