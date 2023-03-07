#!/usr/bin/env python3

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
		if fetch.returncode == 0 and reset.returncode == 0 and merge.returncode == 0:
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

def install_dependencies():
	result = 0
	percent = 30
	status = 'Calculating Python/Package Dependencies...'
	output = ' - Calculating Python & Package Dependencies'
	set_updater_install_status(percent, status, output)
	time.sleep(2)

	updaterInfo = read_dependencies()

	# Get PyPi & Apt dependencies
	py_dependencies = []
	apt_dependencies = []
	for section in updaterInfo['dependencies']:
		for module in updaterInfo['dependencies'][section]['py_dependencies']:
			try:
				dist = pkg_resources.get_distribution(module)
				print('{} ({}) is installed'.format(dist.key, dist.version))
			except pkg_resources.DistributionNotFound:
				print('{} is NOT installed'.format(module))
				py_dependencies.append(module)

		for package in updaterInfo['dependencies'][section]['apt_dependencies']:
			if subprocess.call(["which", package]) != 0:
				apt_dependencies.append(package)

	# Calculate the percent done from remaining items to install
	items_remaining = len(py_dependencies) + len(apt_dependencies)
	if items_remaining == 0:
		increment = 70
	else:
		increment = 70 / items_remaining

	# Install Py dependencies
	launch_pip = ['pip3', 'install']
	status = 'Installing Python Dependencies...'
	output = ' - Installing Python Dependencies'
	set_updater_install_status(percent, status, output)

	for py_item in py_dependencies:
		command = []
		command.extend(launch_pip)
		command.append(py_item)

		process = subprocess.Popen(command, stdout=subprocess.PIPE, encoding='utf-8')
		while True:
			output = process.stdout.readline()
			if process.poll() is not None:
				break
			if output:
				set_wizard_install_status(percent, status, output.strip())
				print(output.strip())
		return_code = process.poll()
		result += return_code
		print(f'Return Code: {return_code}')

		percent += increment
		output = f' - Completed Install of {py_item}'
		set_updater_install_status(percent, status, output)

	time.sleep(4)

	# Install Apt dependencies
	launch_apt = ['apt', 'install']
	status = 'Installing Package Dependencies...'
	output = ' - Installing APT Package Dependencies'
	set_updater_install_status(percent, status, output)

	for apt_item in apt_dependencies:
		command = []
		command.extend(launch_apt)
		command.append(apt_item)
		command.append('-y')

		process = subprocess.Popen(command, stdout=subprocess.PIPE, encoding='utf-8')
		while True:
			output = process.stdout.readline()
			if process.poll() is not None:
				break
			if output:
				set_updater_install_status(percent, status, output.strip())
				print(output.strip())
		return_code = process.poll()
		result += return_code
		print(f'Return Code: {return_code}')

		percent += increment
		output = f' - Completed Install of {apt_item}'
		set_updater_install_status(percent, status, output)

	time.sleep(4)

	percent = 100
	status = 'Finished!'
	output = ' - Finished!  Restarting Server...'
	set_updater_install_status(percent, status, output)

	time.sleep(4)

	percent = 101
	set_updater_install_status(percent, status, output)

	return result

if __name__ == "__main__":
	parser = argparse.ArgumentParser(description='Updater Script')
	parser.add_argument('-b', '--branch', metavar='BRANCH', type=str, required=False, help="Change Branches")
	parser.add_argument('-u', '--update', metavar='BRANCH', type=str, required=False, help="Update Current Branch")
	parser.add_argument('-r', '--remote', action='store_true', required=False, help="Update Remote Branches")

	args = parser.parse_args()

	if args.update:
		percent = 10
		status = f'Attempting Update on {args.update}...'
		output = f' - Attempting an update on branch {args.update}'
		set_updater_install_status(percent, status, output)
		time.sleep(2)

		success, status, output = install_update()

		percent = 20
		set_updater_install_status(percent, status, output)
		time.sleep(4)

		install_dependencies()

	elif args.branch:
		percent = 10
		status = f'Changing Branch to {args.branch}...'
		output = f' - Changing to selected branch {args.branch}'
		set_updater_install_status(percent, status, output)
		time.sleep(2)

		success, status, output = change_branch(args.branch)

		percent = 20
		set_updater_install_status(percent, status, output)
		time.sleep(4)

		install_dependencies()

	elif args.remote:
		error_msg = update_remote_branches()
		if error_msg != '':
			print(f'Error updating remote branches: {error_msg}')

	else:
		print('No Arguments Found. Use --help to see available arguments')

