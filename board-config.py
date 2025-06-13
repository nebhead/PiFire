'''
==============================================================================
 PiFire Board Configuration Tool 
==============================================================================

 Description: Tool to configure the board settings based on the settings.json
  configuration.  Currently supports only Raspberry Pi based platforms.

==============================================================================
'''

'''
==============================================================================
 Imported Modules
==============================================================================
'''

import argparse
import logging
import os 
import json
import subprocess

'''
==============================================================================
 Globals
==============================================================================
'''

log_level = logging.DEBUG

'''
==============================================================================
 Main Functions
==============================================================================
'''

def set_pwm_gpio():
	result = 'Setting the PWM pin: '
	try:
		settings = read_generic_json('settings.json')
		pin = settings['platform']['outputs']['pwm']
		system_type = settings['platform']['system_type']
	except:
		result += 'FAILED (error getting settings.json data) '
		return result 
	
	try:
		if system_type == 'raspberry_pi_all' or system_type == 'prototype':
			# "dtoverlay=pwm,pin=13,func=4"
			pin = int(pin) if pin != None else None
			result += rpi_config_write('dtoverlay', 'pwm', add_config={'func' : '4'}, pin=pin, pin_type='pin')
		else:
			result += 'NA - No system defined'
	except:
		result += 'FAILED (error making the configuration change) '
	
	return result 

def set_onewire_gpio():
	result = 'Setting the 1Wire pin: '
	try:
		settings = read_generic_json('settings.json')
		pin = settings['platform']['system']['1WIRE']
		system_type = settings['platform']['system_type']
	except:
		result += 'FAILED (error getting settings.json data) '
		return result 
	
	try:
		if system_type == 'raspberry_pi_all' or system_type == 'prototype':
			# "dtoverlay=w1-gpio,pin=6"
			pin = int(pin) if pin != None else None
			result += rpi_config_write('dtoverlay', 'w1-gpio', pin=pin, pin_type='gpiopin')
		else:
			result += 'NA - No system defined'
	except:
		result += 'FAILED (error making the configuration change) '
	
	return result 

def set_backlight():
	result = 'Enabling Backlight Control for DSI Touch Display: '
	try:
		settings = read_generic_json('settings.json')
		system_type = settings['platform']['system_type']
	except:
		result += 'FAILED (error getting settings.json data) '
		return result 
	
	try:
		if system_type == 'raspberry_pi_all':
			lines = [ 'SUBSYSTEM=="backlight",RUN+="/bin/chmod 666 /sys/class/backlight/%k/brightness /sys/class/backlight/%k/bl_power"\n' ] 
			file = '/etc/udev/rules.d/backlight-permissions.rules'
			result += create_file(file, lines)
	except:
		result += 'FAILED (error making the configuration change) '
	
	return result 

def enable_spi():
	result = 'Enabling SPI: '
	try:
		settings = read_generic_json('settings.json')
		system_type = settings['platform']['system_type']
	except:
		result += 'FAILED (error getting settings.json data) '
		return result 
	
	try:
		if system_type == 'raspberry_pi_all' or system_type == 'prototype':
			# "dtparam=spi=on"
			result += rpi_config_write('dtparam', 'spi')
		else:
			result += 'NA - No system defined'
	except:
		result += 'FAILED (error making the configuration change) '
	
	return result 

def enable_i2c():
	result = 'Enabling I2C: '
	try:
		settings = read_generic_json('settings.json')
		system_type = settings['platform']['system_type']
	except:
		result += 'FAILED (error getting settings.json data) '
		return result 
	
	try:
		if system_type == 'raspberry_pi_all':
			# dtparam=i2c_arm=on
			result += rpi_config_write('dtparam', 'i2c_arm')
			# To enable userspace access to I2C ensure that /etc/modules contains "12c-dev"
			# echo "i2c-dev" | $SUDO tee -a /etc/modules
			result += append_file('/etc/modules', 'i2c-dev\n')
		else:
			result += 'NA - No system defined'

	except:
		result += 'FAILED (error making the configuration change) '
	
	return result 

def set_i2c_speed(baud=100000):
	result = f'Setting I2C speed ({baud} Baud): '
	try:
		settings = read_generic_json('settings.json')
		system_type = settings['platform']['system_type']
	except:
		result += 'FAILED (error getting settings.json data) '
		return result 
	
	try:
		if system_type == 'raspberry_pi_all' or system_type == 'prototype':
			# dtparam=i2c_arm_baudrate=100000
			result += rpi_config_write('dtparam', 'i2c_arm_baudrate', param=baud)
		else:
			result += 'NA - No system defined'

	except:
		result += 'FAILED (error making the configuration change) '
	
	return result 

def enable_gpio_shutdown():
	result = 'Enabling the GPIO Shutdown pin: '
	try:
		settings = read_generic_json('settings.json')
		pin = settings['platform']['inputs']['shutdown']
		system_type = settings['platform']['system_type']
	except:
		result += 'FAILED (error getting settings.json data) '
		return result 
	
	try:
		if system_type == 'raspberry_pi_all' or system_type == 'prototype':
   			# dtoverlay=gpio-shutdown,gpio_pin=17,active_low=1,gpio_pull=up
			add_config = {
				'active_low' : '1',
				'gpio_pull' : 'up'
			}
			pin = int(pin) if pin != None else None
			result += rpi_config_write('dtoverlay', 'gpio-shutdown', add_config=add_config, pin=pin, pin_type='gpio_pin')
		else:
			result += 'NA - No system defined'
	except:
		result += 'FAILED (error making the configuration change) '
	
	return result 
'''
==============================================================================
 Supporting Functions
==============================================================================
'''

def rpi_config_write(config_type, feature, add_config={}, pin=0, param='', pin_type='gpio_pin'):
	result = 'SUCCESS'
	''' Check OS version, so we can get the correct location of config.txt '''
	os_info = get_os_info()
	version = os_info.get('VERSION_ID', None)
	if version == '12':
		''' Version 12 Bookworm '''
		config_filename = '/boot/firmware/config.txt'
	elif version == '11':
		''' Version 11 Bullseye '''
		config_filename = '/boot/config.txt'
	else:
		''' Test Mode '''
		config_filename = './local/config.txt'

	''' Modify the configuration file '''
	try:
		''' Open the configuration file '''
		with open(config_filename, 'r+') as config_txt:
			config_data = config_txt.readlines()
		''' Look for the configuration line if it exists already '''
		found = False
		for index in range(0, len(config_data)):
			if config_type in config_data[index] and feature in config_data[index]:
				found = True
				# Check for leading hashtag and remove 
				config_line = remove_hashtag(config_data[index])

				# If the pin is marked as disabled / None, then comment out the line
				if pin == None:
					config_data[index] = f'#{config_line}'
				else:
					# Remove the preceding configuration type
					config_line = config_line.replace(f'{config_type}=', '')

					# Get dictionary of the components 
					config_dict = parse_config_line(config_line)

					# For dtparams, turn on feature
					if config_type == 'dtparam':
						if param == '':
							config_dict[feature] = 'on'
						else:
							config_dict[feature] = param

					# For dtoverlay, edit gpio-pin and additional features 
					elif config_type == 'dtoverlay':
					# Modify pin number
						if pin > 0:
							for noun in ['gpio-pin', 'gpiopin', 'gpio_pin', 'pin']:
								if noun in config_dict[feature].keys():
									config_dict[feature].pop(noun, None)
									config_dict[feature][pin_type] = str(pin)

						# If function, add function number
						if add_config != {}:
							for key, value in add_config.items():
								config_dict[feature][key] = value

					''' Create the modified configuration line '''
					config_data[index] = build_config_line(config_type, config_dict)
					break 
		
		if not found and pin is not None:
			config_dict = {}
			if config_type == 'dtoverlay':
				config_dict[feature] = {}
				config_dict[feature][pin_type] = pin
				if add_config != {}:
					for key, value in add_config.items():
						config_dict[feature][key] = value 
			elif config_type == 'dtparam':
				config_dict[feature] = 'on'

			config_data.append(build_config_line(config_type, config_dict))


		''' Write all data back to the file '''
		with open(config_filename, 'w') as config_txt:
			config_txt.writelines(config_data)

	except:
		result = 'FAILED '

	return result 

def parse_config_line(config_line):
    """
    (Format of the configuration line adheres to the Raspberry Pi config.txt formatting rules)
    This function parses a configuration line into component options. 
    This function assumes that the preceding configuration option has been removed (i.e. dtparam=, dtoverlay=, etc.).
    This function removes comments.

    Args:
        config_line: The configuration line to be parsed

    Returns:
        Dictionary of configuration keys and values, sub-keys/values 
    """
    if '#' in config_line:
        config_line = config_line.split('#')[0]

    split_line = config_line.split(',')
    config_dict = {}
    feature = None

    for item in split_line:
        item_split = item.split('=')
        item_dict = {}
        if len(item_split) > 1:
            if feature is not None:
                config_dict[feature][item_split[0]] = item_split[1]
            else:
                config_dict[item_split[0]] = item_split[1]
        else:
            config_dict[item_split[0]] = {}
            feature = item_split[0]
    return config_dict

def build_config_line(config_type, config_dict):
    """
    (Format of the configuration line adheres to the Raspberry Pi config.txt formatting rules)
    This function parses a configuration dictionary into a configuration string/line. 

    Args:
        config_type: String of the type 'dtparam', 'dtoverlay', etc.
        config_dict: The configuration dictionary to be parsed

    Returns:
        String of the configuration line
    """

    config_line = f'{config_type}='
    comma = False
    for key, value in config_dict.items():
        if comma:
            config_line += ','
        if isinstance(value, dict):
            config_line += f'{key}'
            for subkey, subvalue in value.items():
                if subvalue is not None:
                    config_line += f',{subkey}={subvalue}'
                else:
                    config_line += f',{subkey}'
        else:
            config_line += f'{key}={value}'
        comma = True

    config_line += '  # Modified by PiFire Board Configuration Utility'
    config_line += '\n'

    return config_line

def get_os_info():
	"""Get operating system information"""
	os_info = {}

	try:
		# Get OS release info
		with open('/etc/os-release', 'r') as f:
			for line in f:
				if '=' in line:
					key, value = line.strip().split('=', 1)
					# Remove quotes if present
					value = value.strip('"')
					os_info[key] = value
		
		# Get architecture using uname -m
		arch = subprocess.check_output(['/bin/uname', '-m']).decode().strip()
		os_info['ARCHITECTURE'] = arch
		
		# Save to JSON file
		write_generic_json(os_info, 'os_info.json')
		return os_info
		
	except Exception as e:
		event = f"Error getting OS info: {str(e)}"
		logger.error(event)
		return os_info

def create_file(filename, lines):
	result = f'\n - Attempting to write data to {filename}: '
	try:
		with open(filename, "w") as file:
			for line in lines:
				file.write(line)
		result += f' SUCCESS (creating file {filename}) '
	except:
		result += f' FAILED (creating file {filename}) '
	return result 

def append_file(filename, lines):
	result = f'\n - Attempting to append data to {filename}: '
	try:
		with open(filename, "a+") as file:
			for line in lines:
				file.write(line)
		result += f' SUCCESS (appending file {filename}) '
	except:
		result += f' FAILED (appending file {filename}) '
	return result 

def remove_hashtag(text):
  """Removes a preceding hashtag character from a string if it exists,
  including any leading spaces.

  Args:
      text: The string to process.

  Returns:
      The string with the hashtag and leading spaces removed if it existed, 
      otherwise the original string.
  """
  if text:
    # Strip leading spaces
    stripped_text = text.lstrip()
    if stripped_text and stripped_text[0] == "#":
      return stripped_text[1:]
    else:
      return text
  else:
    return text

def read_generic_json(filename):
	try:
		json_file = os.fdopen(os.open(filename, os.O_RDONLY))
		json_data = json_file.read()
		dictionary = json.loads(json_data)
		json_file.close()
	except: 
		dictionary = {}
		event = f'An error occurred loading {filename} '
		logger.error(event)
	return dictionary

def write_generic_json(dictionary, filename):
	try: 
		json_data_string = json.dumps(dictionary, indent=2, sort_keys=True)
		with open(filename, 'w') as json_file:
			json_file.write(json_data_string)
	except:
		event = f'Error writing generic json file ({filename})'
		logger.error(event)

def create_logger(name, filename='./logs/pifire.log', messageformat='%(asctime)s | %(levelname)s | %(message)s', level=logging.INFO):
	'''Create or Get Existing Logger'''
	logger = logging.getLogger(name)
	''' 
		If the logger does not exist, create one. Else return the logger. 
		Note: If the a log-level change is needed, the developer should directly set the log level on the logger, instead of using 
		this function.  
	'''
	if not logger.hasHandlers():
		logger.setLevel(level)
		formatter = logging.Formatter(fmt=messageformat, datefmt='%Y-%m-%d %H:%M:%S')
		# datefmt='%Y-%m-%d %H:%M:%S'
		handler = logging.FileHandler(filename)        
		handler.setFormatter(formatter)
		logger.addHandler(handler)
	return logger


'''
==============================================================================
 Main
==============================================================================
'''
if __name__ == "__main__":
	logger = create_logger('board_config', filename='./logs/board_config.log', level=log_level)
	
	print('PiFire Board Configuration Tool v1.0.1')
	print('Ben Parmeter - 2025 - MIT License')
	print(' --help, -h for command details\n')
	
	parser = argparse.ArgumentParser(description='This tool performs board specific configuration for certain system level features.  Use the below options to enable/disable and configure these features.  System settings are read from the settings.json file.')
	parser.add_argument('-pwm', '--pwm', action='store_true', required=False, help="Set PWM GPIO.")
	parser.add_argument('-ow', '--onewire', action='store_true', required=False, help="Set 1Wire GPIO.")
	parser.add_argument('-bl', '--backlight', action='store_true', required=False, help="Enable backlight permissions.")
	parser.add_argument('-ov', '--osversion', action='store_true', required=False, help="Get OS Version. Saves to os_info.json.")
	parser.add_argument('-s', '--spi', action='store_true', required=False, help="Enable SPI.")
	parser.add_argument('-i', '--i2c', action='store_true', required=False, help="Enable I2C.")
	parser.add_argument('-is', '--i2cspeed', metavar='BAUD', type=int, required=False, help="Set the I2C baud rate. BAUD should be an integer, i.e. 100000")
	parser.add_argument('-gs', '--gpioshutdown', action='store_true', required=False, help="Enable GPIO shutdown.")

	args = parser.parse_args()

	results = []

	if args.pwm:
		results.append(set_pwm_gpio())

	if args.onewire:
		results.append(set_onewire_gpio())

	if args.backlight:
		results.append(set_backlight())

	if args.spi:
		results.append(enable_spi())

	if args.i2c:
		results.append(enable_i2c())

	if args.i2cspeed:
		results.append(set_i2c_speed(baud=args.i2cspeed))

	if args.gpioshutdown:
		results.append(enable_gpio_shutdown())

	if args.osversion:
		os_info = get_os_info()
		version = os_info.get('VERSION_ID', 'Unknown')
		event = f'Detected OS version_id: {version}.'
		results.append(event)

	if len(results) == 0:
		print('No Arguments Found. Use --help to see available arguments')
	else:
		print('Results:')
		for item in results:
			print(f' - {item}')
			logger.info(f'{item}')

