#!/usr/bin/env python3

# *****************************************
# PiFire Prototype Distance Interface Library
# *****************************************
#
# Description: This library supports getting the hopper level from stored value
#
# *****************************************

class HopperLevel:

	def __init__(self, empty=30):
		self.empty = empty # Empty is greater than 30cm distance measured
		self.SetLevel()
	
	def SetLevel(self, level=100):
		self.level = int(level) 

	def GetLevel(self):
		return(self.level)