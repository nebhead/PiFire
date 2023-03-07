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

import curses
import time

class Display:

	def __init__(self, dev_pins, buttonslevel='HIGH', rotation=0, units='F'):
		self.units = units 
		curses.wrapper(self._curses_main)
		curses.curs_set(0)  # Invisible Cursor 
		curses.start_color()  # Init Color
		curses.init_pair(1, curses.COLOR_BLUE, curses.COLOR_BLACK)
		curses.init_pair(2, curses.COLOR_CYAN, curses.COLOR_BLACK)
		curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_BLACK)
		curses.init_pair(4, curses.COLOR_YELLOW, curses.COLOR_BLACK)
		curses.init_pair(5, curses.COLOR_RED, curses.COLOR_BLACK)
		curses.init_pair(6, curses.COLOR_GREEN, curses.COLOR_BLACK)

		self.display_splash()

	def _curses_main(self, screen):
		self.screen = screen

	def display_status(self, in_data, status_data):
		''' Screen Box '''
		self.screen.clear()
		num_rows, num_cols = self.screen.getmaxyx()
		self.screen.box()
		title = f"| Mode: {status_data['mode']} |"
		title_col = (num_cols // 2) - (len(title) // 2)
		title_color = curses.color_pair(2)
		self.screen.addstr(0, title_col, title, title_color)

		''' Temp Info '''
		line = 1
		display_color = curses.color_pair(1)
		for index, group in enumerate(in_data['probe_history']):
			for item in in_data['probe_history'][group]:
				if group != 'tr':
					display_text = f"{item}: {in_data['probe_history'][group][item]} {self.units}"
					self.screen.addstr(line, 3, display_text)
					if group == 'primary':
						display_text = f"{item} Setpoint: {in_data['primary_setpoint']} {self.units} Target: {in_data['notify_targets'][item]} {self.units}"
					else: 
						display_text = f"{item} Target: {in_data['notify_targets'][item]} {self.units}"
					self.screen.addstr(line, (num_cols // 2), display_text, display_color)
					line += 1

		''' Notification Info '''
		line += 1
		line_bak = line
		display_color = curses.color_pair(4)
		for index, item in enumerate(status_data['notify_data']):
			if item['req']:
				display_text = f" * {item['label']} Notify"
				self.screen.addstr(line, (num_cols // 2), display_text, display_color)
				line += 1

		''' Active Hardware Pins '''
		line = line_bak 
		for item in status_data['outpins']:
			if status_data['outpins'][item]:
				display_text = f"{item}: ON"
				self.screen.addstr(line, 3, display_text)
			else:
				display_text = f"{item}: OFF"
				self.screen.addstr(line, 3, display_text)
			line += 1

		''' Show Pellet Level '''
		line += 1
		if status_data["hopper_level"] >= 70:
			display_color = curses.color_pair(6)
		elif status_data["hopper_level"] >= 25:
			display_color = curses.color_pair(4)
		else:
			display_color = curses.color_pair(5)
			
		display_text = f'Pellet Level: {status_data["hopper_level"]}%'
		self.screen.addstr(line, 3, display_text, display_color)
		
		''' Show the screen '''
		self.screen.refresh()

	def display_splash(self):
		splash_str = []
		splash_str.append('  (        (')
		splash_str.append('  )\ )     )\ )')
		splash_str.append(' (()/( (  (()/(  (   (      (')
		splash_str.append('  /(_)))\  /(_)) )\  )(    ))\ ')
		splash_str.append(' (_)) ((_)(_))_|((_)(()\  /((_) ')
		splash_str.append(' | _ \ (_)| |_   (_) ((_)(_)) ')
		splash_str.append(' |  _/ | || __|  | || \'_|/ -_) ')
		splash_str.append(' |_|   |_||_|    |_||_|  \___|  ')
		self.screen.clear()
		num_rows, num_cols = self.screen.getmaxyx()
		self.screen.box()
		title = '| PiFire Display |'
		title_col = (num_cols // 2) - (len(title) // 2)
		title_color = curses.color_pair(2)
		self.screen.addstr(0, title_col, title, title_color)
		splash_str_start = (num_cols // 2) - (len(splash_str[7]) // 2)
		splash_color = curses.color_pair(2)
		for line in range(0, len(splash_str)):
			self.screen.addstr(line+3, splash_str_start, splash_str[line], splash_color)
		self.screen.refresh()
		time.sleep(1)

	def clear_display(self):
		''' Screen Box '''
		self.screen.clear()
		num_rows, num_cols = self.screen.getmaxyx()
		self.screen.box()
		title = '| PiFire Display |'
		title_col = (num_cols // 2) - (len(title) // 2)
		title_color = curses.color_pair(2)
		self.screen.addstr(0, title_col, title, title_color)

		self.screen.refresh()

	def display_text(self, text):
		self.screen.clear()
		num_rows, num_cols = self.screen.getmaxyx()
		self.screen.box()
		title = 'PiFire Display'
		title_col = (num_cols // 2) - (len(title) // 2)
		self.screen.addstr(0, title_col, title)
		text_str_start = (num_cols // 2) - (len(text) // 2)
		self.screen.addstr(3, text_str_start, text)
		self.screen.refresh()

	def display_network(self):
		pass
