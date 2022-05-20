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

	def __init__(self, buttonslevel='HIGH', rotation=0, units='F'):
		self.display_splash()

	def display_status(self, in_data, status_data):
		pass 

	def display_splash(self):
		print('[Splash] PiFire Display Starting Up')

	def clear_display(self):
		print('[Display] Clear Display Command Sent')

	def display_text(self, text):
		print(f'[Display] {text}')

	def display_network(self):
		print(f'[Display] Network')