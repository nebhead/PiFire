'''
==============================================================================
 PiFire Updater 
==============================================================================

 Description: Update support functions to utilize Git/GitHub for live system updates

==============================================================================
'''

'''
==============================================================================
 Imported Modules
==============================================================================
'''

from common import *
import pkg_resources
import subprocess
import argparse
import logging

'''
==============================================================================
 Supporting Functions
==============================================================================
'''

def get_available_branches():
	command = ['git', 'branch', '-a']
	branches = subprocess.run(command, capture_output=True, text=True)
	branch_list = []
	error_msg = ''
	if branches.returncode == 0:
		input_list = branches.stdout.split("\n")
		for line in input_list:
			line = line.strip(' *')
			if 'origin/main' in line:
				# Skip this line
				pass
			elif 'remotes/origin/' in line:
				line = line.replace('remotes/origin/', '')
				if line not in branch_list and line != '':
					branch_list.append(line)
			elif line != '':
				branch_list.append(line)
	else:
		error_msg = branches.stderr 
	return(branch_list, error_msg)

def update_remote_branches():
	# git remote set-branches origin '*'
	command = ['git', 'remote', 'set-branches', 'origin', '*']
	remote_branches = subprocess.run(command, capture_output=True, text=True)
	error_msg = ''
	if remote_branches.returncode != 0:
		error_msg = remote_branches.stderr 
	# Fetch Branch Information Locally
	command = ['git', 'fetch'] 
	fetch = subprocess.run(command, capture_output=True, text=True)
	if fetch.returncode != 0:
		error_msg += ' | ' + remote_branches.stderr 
	return(error_msg)

def get_branch():
	# --show-current is only in later versions of git, and unfortunately buster does not have this
	command = ['git', 'branch', '-a']
	branches = subprocess.run(command, capture_output=True, text=True)
	error_msg = ''
	result = ''
	if branches.returncode == 0:
		input_list = branches.stdout.split("\n")
		for line in input_list:
			if '*' in line:
				result = line.strip(' *')
				break
	else:
		result = 'ERROR Getting Current Branch'
		error_msg = branches.stderr 
	return(result, error_msg)

def set_branch(branch_target):
	command = ['git', 'checkout', '-f', branch_target]
	target = subprocess.run(command, capture_output=True, text=True)
	error_msg = ''
	result = ''
	if target.returncode == 0:
		result = target.stdout.replace('\n', '<br>') + target.stderr.replace('\n', '<br>')
	else: 
		result = 'ERROR Setting Branch'
		error_msg = target.stderr.replace('\n', '<br>')
	return(result, error_msg)

def get_remote_url():
	command = ['git', 'config', '--get', 'remote.origin.url']
	remote = subprocess.run(command, capture_output=True, text=True)
	error_msg = ''
	if remote.returncode == 0:
		result = remote.stdout.strip(' \n')
	else:
		result = 'ERROR Retrieving URL'
		error_msg = remote.stderr.replace(' \n', ' ')
	return(result, error_msg)

def get_available_updates(branch=''):
	result = {}
	remote, error_msg1 = get_remote_url()
	if branch == '':
		branch, error_msg2 = get_branch()

	if 'ERROR' not in remote and 'ERROR' not in branch:
		command = ['git', 'fetch']
		fetch = subprocess.run(command, capture_output=True, text=True)
		command = ['git', 'rev-list', '--left-only', '--count', f'origin/{branch}...@']
		rev_list = subprocess.run(command, capture_output=True, text=True)
		#print(f'rev_list.returncode = {rev_list.returncode}')
		#print(f'fetch.returncode = {fetch.returncode}')

		if rev_list.returncode == 0 and fetch.returncode == 0:
			rev_list = rev_list.stdout.strip(' \n')
			if rev_list.isnumeric():
				result['success'] = True 
				result['commits_behind'] = int(rev_list)
			else: 
				result['success'] = False 
				result['message'] = rev_list
		else: 
			result['success'] = False 
			result['message'] = 'ERROR Getting Revision List: ' + rev_list.stderr.replace('\n', ' ') + \
								rev_list.stdout.replace('\n', ' ')
	else:
		result['success'] = False 
		result['message'] = 'ERROR Getting Remote or Branch: ' + error_msg1.replace('\n', ' ') + ' ' + \
							error_msg2.replace('\n', ' ')
	return(result)

def do_update():
	branch, error_msg1 = get_branch()
	remote, error_msg2 = get_remote_url()
	if error_msg1 == '' and error_msg2 == '':
		command = ['git', 'fetch', '--all']
		fetch = subprocess.run(command, capture_output=True, text=True)
		command = ['git', 'reset', '--hard', f'origin/{branch}']
		reset = subprocess.run(command, capture_output=True, text=True)

		'''
		command = ['git', 'reset', '--hard', 'HEAD']
		reset = subprocess.run(command, capture_output=True, text=True)
		command = ['git', 'merge', f'origin/{branch}']
		merge = subprocess.run(command, capture_output=True, text=True)
		'''
		error_msg = ''
		if fetch.returncode == 0 and reset.returncode == 0:
			result = fetch.stdout.replace('\n', '<br>') + '<br>' + reset.stdout.replace('\n', '<br>') # + '<br>' + merge.stdout.replace('\n', '<br>')
		else: 
			result = 'ERROR Performing Update.'
			error_msg = fetch.stderr.replace('\n', '<br>') + '<br>' + reset.stderr.replace('\n', '<br>') # + '<br>' + merge.stderr.replace('\n', '<br>')
	else: 
		result = 'ERROR Getting Remote URL.'
	return(result, error_msg)

def get_log(num_commits=10):
	branch, error_msg = get_branch()
	if error_msg == '':
		command = ['git', 'log', f'origin/{branch}', f'-{num_commits}', '--pretty="%h - %cr : %s"']
		log = subprocess.run(command, capture_output=True, text=True)
		if log.returncode == 0:
			result = log.stdout.replace('\n', '<br>').replace('"', '')
		else: 
			result = 'ERROR Getting Log.'
			error_msg = log.stderr.replace('\n', '<br>')
	else: 
		result = 'ERROR Getting Branch Name.'
	return(result, error_msg)

def get_remote_version():
	remote_url, error_msg = get_remote_url()
	if error_msg == '':
		# Reference command: git ls-remote --tags --sort="v:refname" git://github.com/nebhead/test-update.git
		# 	| tail -n1 | sed "s/.*\\///;"
		# Gets a list of the remote hashes/tags sorted by version, then takes the last (tail) and processes the
		# 	output to remove the hash and ref/tags/
		command = ['git', 'ls-remote', '--tags', '--sort=v:refname', remote_url]
		versions = subprocess.run(command, capture_output=True, text=True)
		if versions.returncode == 0:
			version_list = versions.stdout.split('\n')  # Make a list of versions from the output
			if version_list != ['']:
				# Get the last version from the sorted version list (-1 is actually an empty string, so go -2 to
				# 	get the last item)
				result = version_list[-2]
				# Trickery to split the string after "refs/tags/" to get the version suffix
				result = result.split("refs/tags/",1)[1]
			else: 
				result = "No versions found"
		else: 
			result = "ERROR Getting Remote Version."
			error_msg = versions.stderr.replace('\n', ' | ')
	else: 
		result = 'ERROR Getting Remote URL.'
	return(result, error_msg)

def get_current_tag():
	error_msg = ''
	command = ['git', 'describe', '--tags']
	tag = subprocess.run(command, capture_output=True, text=True)
	if tag.returncode == 0:
		result = tag.stdout.replace('\n', '')
	else: 
		result = 'ERROR Getting Log.'
		error_msg = tag.stderr.replace('\n', '<br>')
	return(result, error_msg)

def get_update_data(settings):
	# Populate Update Data Structure
	update_data = {}
	tag, error_msg = get_current_tag()
	if error_msg != '':
		write_log(error_msg)
	update_data['version'] = f'v{settings["versions"]["server"]} ({tag})'
	update_data['branch_target'], error_msg = get_branch()
	if error_msg != '':
		write_log(error_msg)
	update_data['branches'], error_msg = get_available_branches()
	if error_msg != '':
		write_log(error_msg)
	update_data['remote_url'], error_msg = get_remote_url()
	if error_msg != '':
		write_log(error_msg)
	update_data['remote_version'], error_msg = get_remote_version()
	if error_msg != '':
		write_log(error_msg)

	return update_data

def change_branch(branch_target):
	command = ['git', 'checkout', '-f', branch_target]
	target = subprocess.run(command, capture_output=True, text=True)
	if target.returncode == 0:
		status = 'Branch Changed Successfully'
		output = ' - ' + target.stdout + target.stderr
		success = True
	else:
		status = 'ERROR Changing Branch'
		output = ' - ' + target.stderr
		success = False
	return(success, status, output)

def install_update():
	branch, error_msg1 = get_branch()
	remote, error_msg2 = get_remote_url()
	if error_msg1 == '' and error_msg2 == '':
		command = ['git', 'fetch']
		fetch = subprocess.run(command, capture_output=True, text=True)
		command = ['git', 'reset', '--hard', 'HEAD']
		reset = subprocess.run(command, capture_output=True, text=True)
		command = ['git', 'merge', f'origin/{branch}']
		merge = subprocess.run(command, capture_output=True, text=True)
		if fetch.returncode == 0 and reset.returncode == 0 and merge.returncode == 0:
			status = 'Update Completed Successfully'
			output = ' - ' + fetch.stdout + reset.stdout + merge.stdout
			success = True
		else:
			status = 'ERROR Performing Update.'
			output = ' - ' + fetch.stdout + reset.stdout + merge.stdout
			success = False
	else:
		status = 'ERROR Getting Remote URL.'
		output = ' - ERROR Getting Remote URL. Please check your git install'
		success = False
	return(success, status, output)

def read_output(command):
	process = subprocess.Popen(command, stdout=subprocess.PIPE, encoding='utf-8')
	while True:
		output = process.stdout.readline()
		if process.poll() is not None:
			break
		if output:
			set_updater_install_status(percent, status, output.strip())
			print(output.strip())

	return_code = process.poll()
	print(f'Return Code: {return_code}')

def install_dependencies(current_version_string='0.0.0', current_build=None):
	result = 0
	percent = 30
	status = 'Calculating Python/Package Dependencies...'
	output = ' - Calculating Python & Package Dependencies'
	if DEBUG:
		print(f'Percent: {percent}')
		print(f'Status:  {status}')
		print(f'Output:  {output}')
	logger.debug(f'Percent: {percent}')
	logger.info(f'Status:  {status}')
	logger.debug(f'Output:  {output}')
	# Update the status bar with the current status
	set_updater_install_status(percent, status, output)
	time.sleep(2)

	updaterInfo = read_updater_manifest()

	# Get ALL PyPi & Apt dependencies and commands to install / update 
	py_dependencies = []
	apt_dependencies = []
	command_list = []
	reboot = False

	for version_info in updaterInfo['versions']:
		''' Walk list of versions in updater_manifest, check for dependencies '''	
		if (semantic_ver_is_lower(current_version_string, version_info['version'])) or \
			((current_version_string == version_info['version']) and \
			(current_build < version_info['build'])):
			
			# If the current version (pre-update) is less than this version information, install dependencies, etc.
			for section in version_info['dependencies']:
				for module in version_info['dependencies'][section]['py_dependencies']:
					try:
						dist = pkg_resources.get_distribution(module)
						print('{} ({}) is installed'.format(dist.key, dist.version))
						logger.debug('{} ({}) is installed'.format(dist.key, dist.version))
					except pkg_resources.DistributionNotFound:
						print('{} is NOT installed'.format(module))
						logger.debug('{} is NOT installed'.format(module))
						py_dependencies.append(module)

				for package in version_info['dependencies'][section]['apt_dependencies']:
					if subprocess.call(["which", package]) != 0:
						apt_dependencies.append(package)

				for command in version_info['dependencies'][section]['command_list']:
					command_list.append(command)
				
				if version_info['reboot_required']:
					reboot = True 

	if DEBUG:
		print(f'py_dep: {py_dependencies}')
		print(f'apt_dep:  {apt_dependencies}')
		print(f'command:  {command_list}')
	logger.debug(f'py_dep: {py_dependencies}')
	logger.debug(f'apt_dep:  {apt_dependencies}')
	logger.debug(f'command:  {command_list}')

	# Calculate the percent done from remaining items to install
	items_remaining = len(py_dependencies) + len(apt_dependencies) + len(command_list)
	if items_remaining == 0:
		increment = 70
	else:
		increment = 70 / items_remaining

	# Install Py dependencies
	settings = read_settings(init=True)
	python_exec = settings['globals'].get('python_exec', 'python')

	if settings['globals'].get('uv', False):
		launch_pip = ['uv', 'pip', 'install']
	else:
		launch_pip = [python_exec, '-m', 'pip', 'install']

	status = 'Installing Python Dependencies...'
	output = ' - Installing Python Dependencies'
	set_updater_install_status(percent, status, output)
	if DEBUG:
		print(f'Percent: {percent}')
		print(f'Status:  {status}')
		print(f'Output:  {output}')
	logger.debug(f'Percent: {percent}')
	logger.info(f'Status:  {status}')
	logger.debug(f'Output:  {output}')

	for py_item in py_dependencies:
		command = []
		command.extend(launch_pip)
		command.append(py_item)
		if not DEBUG:
			process = subprocess.Popen(command, stdout=subprocess.PIPE, encoding='utf-8')
			while True:
				output = process.stdout.readline()
				if process.poll() is not None:
					break
				if output:
					set_wizard_install_status(percent, status, output.strip())
					print(output.strip())
					logger.info(output.strip())
			return_code = process.poll()
			result += return_code
			print(f'Return Code: {return_code}')
		
		percent += increment
		output = f' - Completed Install of {py_item}'
		set_updater_install_status(percent, status, output)
		if DEBUG:
			print(f'Percent: {percent}')
			print(f'Status:  {status}')
			print(f'Output:  {output}')
		logger.debug(f'Percent: {percent}')
		logger.debug(f'Status:  {status}')
		logger.info(f'Output:  {output}')

	time.sleep(4)

	# Install Apt dependencies
	launch_apt = ['sudo', 'apt', 'install']
	status = 'Installing Package Dependencies...'
	output = ' - Installing APT Package Dependencies'
	set_updater_install_status(percent, status, output)

	for apt_item in apt_dependencies:
		command = []
		command.extend(launch_apt)
		command.append(apt_item)
		command.append('-y')
		if not DEBUG:
			process = subprocess.Popen(command, stdout=subprocess.PIPE, encoding='utf-8')
			while True:
				output = process.stdout.readline()
				if process.poll() is not None:
					break
				if output:
					set_updater_install_status(percent, status, output.strip())
					print(output.strip())
					logger.info(output.strip())
			return_code = process.poll()
			result += return_code
			print(f'Return Code: {return_code}')
		
		percent += increment
		output = f' - Completed Install of {apt_item}'
		set_updater_install_status(percent, status, output)
		if DEBUG:
			print(f'Percent: {percent}')
			print(f'Status:  {status}')
			print(f'Output:  {output}')
		logger.debug(f'Percent: {percent}')
		logger.debug(f'Status:  {status}')
		logger.info(f'Output:  {output}')

	time.sleep(4)

	# Run system commands dependencies
	status = 'Installing General Dependencies...'
	output = ' - Installing General Dependencies'
	set_updater_install_status(percent, status, output)
	if DEBUG:
		print(f'Percent: {percent}')
		print(f'Status:  {status}')
		print(f'Output:  {output}')
	logger.debug(f'Percent: {percent}')
	logger.info(f'Status:  {status}')
	logger.debug(f'Output:  {output}')

	for command in command_list:
		process = subprocess.Popen(command, stdout=subprocess.PIPE, encoding='utf-8')
		while True:
			output = process.stdout.readline()
			if process.poll() is not None:
				break
			if output:
				set_updater_install_status(percent, status, output.strip())
				print(f'{output.strip()}')
				logger.info(output.strip())
		return_code = process.poll()
		result += return_code
		print(f'Return Code: {return_code}')

		percent += increment
		output = f' - Completed General Dependency Item'
		set_updater_install_status(percent, status, output)
		if DEBUG:
			print(f'Percent: {percent}')
			print(f'Status:  {status}')
			print(f'Output:  {output}')
		logger.debug(f'Percent: {percent}')
		logger.debug(f'Status:  {status}')
		logger.debug(f'Output:  {output}')

	time.sleep(4)

	percent = 100
	status = 'Finished!'
	output = ' - Finished!  Restarting Server...'
	set_updater_install_status(percent, status, output)
	if DEBUG:
		print(f'Percent: {percent}')
		print(f'Status:  {status}')
		print(f'Output:  {output}')

	time.sleep(4)

	percent = 142 if reboot else 101
	set_updater_install_status(percent, status, output)

	return result

'''
==============================================================================
 Main
==============================================================================
'''
if __name__ == "__main__":
	parser = argparse.ArgumentParser(description='Updater Script')
	parser.add_argument('-b', '--branch', metavar='BRANCH', type=str, required=False, help="Change Branches")
	parser.add_argument('-u', '--update', metavar='BRANCH', type=str, required=False, help="Update Current Branch")
	parser.add_argument('-r', '--remote', action='store_true', required=False, help="Update Remote Branches")
	parser.add_argument('-p', '--piplist', action='store_true', required=False, help="Output PIP List packages to JSON file.")
	parser.add_argument('-v', '--uv', action='store_true', required=False, help="Set uv flag and clear venv flag in settings.json")
	parser.add_argument('-l', '--legacyvenv', action='store_true', required=False, help="Set venv flag in settings.json")
	parser.add_argument('-d', '--debug', action='store_true', required=False, help="Enable Debug Mode")
	parser.add_argument('-i', '--installdependencies', action='store_true', required=False, help="Install Dependencies for current version")

	args = parser.parse_args()

	''' Setup Logger '''
	if args.debug:
		log_level = logging.DEBUG
		DEBUG = True
	else:
		log_level = logging.INFO
		DEBUG = False

	logger = create_logger('updater', filename='./logs/update.log', messageformat='%(asctime)s | %(levelname)s | %(message)s', level=log_level)

	# num_args = number of arguments passed to the script
	num_args = 0

	if args.update:
		num_args += 1
		settings = read_generic_json('settings.json')
		current_version = settings['versions']['server']
		current_build = settings['versions'].get('build', 0)

		percent = 10
		status = f'Attempting Update on {args.update}...'
		output = f' - Attempting an update on branch {args.update}'
		set_updater_install_status(percent, status, output)
		time.sleep(2)

		success, status, output = install_update()

		percent = 20
		set_updater_install_status(percent, status, output)
		time.sleep(4)

		install_dependencies(current_version, current_build)

	elif args.branch:
		num_args += 1
		settings = read_generic_json('settings.json')
		current_version = settings['versions']['server']
		current_build = settings['versions'].get('build', 0)

		percent = 10
		status = f'Changing Branch to {args.branch}...'
		output = f' - Changing to selected branch {args.branch}'
		set_updater_install_status(percent, status, output)
		time.sleep(2)

		success, status, output = change_branch(args.branch)

		percent = 20
		set_updater_install_status(percent, status, output)
		time.sleep(4)

		install_dependencies(current_version, current_build)

	elif args.remote:
		num_args += 1
		error_msg = update_remote_branches()
		if error_msg != '':
			print(f'Error updating remote branches: {error_msg}')

	elif args.installdependencies:
		num_args += 1
		settings = read_generic_json('settings.json')
		current_version = settings['versions']['server']
		current_build = settings['versions'].get('build', 0)

		percent = 10
		status = f'Installing Dependencies for Current Version...'
		output = f' - APT, Python and Command Dependencies for version {current_version} ({current_build})'
		set_updater_install_status(percent, status, output)

		install_dependencies(current_version, current_build)

	if args.piplist:
		num_args += 1
		settings = read_settings(init=True)

		# Get python executable
		python_exec = settings['globals'].get('python_exec', 'python')

		if settings['globals'].get('uv', False):
			command = ['uv', 'pip', 'list', '--format=json']
		else:
			command = [python_exec, '-m', 'pip', 'list', '--format=json']

		pip_list = subprocess.run(command, capture_output=True, text=True)
		if pip_list.returncode == 0:
			write_generic_json(json.loads(pip_list.stdout), 'pip_list.json')
			#print(f'PIP List: {pip_list.stdout}')
		else:
			print(f'Error creating PIP List: {pip_list.stderr}')
			pip_list = []
			write_generic_json(pip_list, 'pip_list.json')
	
	if args.uv:
		num_args += 1
		settings = read_settings()
		settings['globals']['uv'] = True
		settings['globals']['venv'] = True
		settings['globals']['python_exec'] = '.venv/bin/python'
		write_generic_json(settings, 'settings.json')
		print('Updated settings.json to set uv flag and set venv flag')
	
	if args.legacyvenv:
		num_args += 1
		settings = read_settings()
		settings['globals']['uv'] = False
		settings['globals']['venv'] = True
		settings['globals']['python_exec'] = 'bin/python'
		write_generic_json(settings, 'settings.json')
		print('Updated settings.json to set venv flag and clear uv flag')

	''' If no valid arguments are passed, print help message '''
	if num_args == 0:
		print('No valid arguments provided. Use -h for help.')

