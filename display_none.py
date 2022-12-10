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

	def __init__(self, dev_pins, buttonslevel='HIGH', rotation=0, units='F'):
		self.display_splash()

	def display_status(self, in_data, status_data):
		pass 

	def display_splash(self):
		pass

	def clear_display(self):
		pass

	def display_text(self, text):
		pass

	def display_network(self):
		pass 