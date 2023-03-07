#!/usr/bin/env python3

# *****************************************
# PiFire None Distance Interface Library
# *****************************************
#
# Description: This library supports getting
# 	the hopper level from stored value
#
# *****************************************

from common import write_log

class HopperLevel:

	def __init__(self, dev_pins, empty=22, full=4, debug=False, random=False):
		self.empty = empty # Empty is greater than distance measured for empty
		self.full = full # Full is less than or equal to the minimum full distance.
		if self.empty <= self.full:
			event = 'ERROR: Invalid Hopper Level Configuration Empty Level <= Full Level (forcing defaults)'
			write_log(event)
			# Set defaults that are valid
			self.empty = 22
			self.full = 4
		self.set_level()
	
	def set_level(self, level=100):
		# Do nothing
		return()

	def update_distances(self, empty=22, full=4):
		self.empty = empty
		self.full = full

	def get_distances(self):
		levels = {}
		levels['empty'] = self.empty
		levels['full'] = self.full
		return (levels)

	def get_level(self):
		return 100
