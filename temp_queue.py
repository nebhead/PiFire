#!/usr/bin/env python3

'''
	Class to track temperature averages coming from the probes and 
	handle errors gracefully (hopefully).  
'''

import statistics

class TempQueue():
	def __init__(self, qlength=10, units='F'):
		self.queue = []
		self.units = units

		if qlength < 2:
			self.qlength = 2 # Set minimum qlength to 2
		else: 
			self.qlength = qlength
		
		if units == 'F':
			self.stdev_max = 4.75  # Standard Deviation Maximum for degrees F
		else:
			self.stdev_max = 2.25  # Standard Deviation Maximum for degrees C
		self.last_average = 0

	def enqueue(self, value):
		while len(self.queue) < (self.qlength + 1):
			self.queue.insert(0, value)
		self.queue.pop()
		return(self.average())

	def average(self):
		if len(self.queue) < self.qlength:
			# Handle case if queue isn't full 
			self.last_average = 0
			return(0)
		elif self.last_average == 0:
			# Handle case if lastaverage isn't initialized
			average = (sum(self.queue) / self.qlength)
			self.last_average = average
			if self.units == 'F':
				return(int(average))  # Give integer for F units
			else: 
				return(round(average, 1))  # Give one digit of decimal for C units
		else:
			# Handle normal case
			# Get standard deviation from temperatures in the queue
			stdev = statistics.stdev(self.queue)
			if stdev < self.stdev_max:
				# If the standard deviation is less than the max deviation, calculate the average temperature as normal
				average = (sum(self.queue) / self.qlength)
				self.last_average = average
			else:
				# If the standard deviation exceeds the max deviation, keep the last average value
				average = self.last_average

			if self.units == 'F':
				return(int(average))  # Give integer for F units
			else: 
				return(round(average, 1))  # Give one digit of decimal for C units

