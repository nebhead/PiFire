#!/usr/bin/env python3

'''
Update support functions to utilize Git/GitHub for live system updates
'''

import subprocess

def get_available_branches():
	command = ['git', 'branch', '-a']
	branches = subprocess.run(command, capture_output=True, text=True)
	branch_list = []
	error_msg = ''
	if(branches.returncode == 0):
		input_list = branches.stdout.split("\n")
		for line in input_list:
			line = line.strip(' *')
			if('origin/main' in line):
				# Skip this line
				pass
			elif('remotes/origin/' in line):
				line = line.replace('remotes/origin/', '')
				if (line not in branch_list) and (line != ''):
					branch_list.append(line)
			elif(line != ''):
				branch_list.append(line)
	else:
		error_msg = branches.stderr 
	return(branch_list, error_msg)

def get_branch():
#	--show-current is only in later versions of git, and unfortunatly buster does not have this
	command = ['git', 'branch', '-a']
	branches = subprocess.run(command, capture_output=True, text=True)
	error_msg = ''
	result = ''
	if(branches.returncode == 0):
		input_list = branches.stdout.split("\n")
		for line in input_list:
			if('*' in line):
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
	if(target.returncode == 0):
		result = target.stdout.replace('\n', '<br>') + target.stderr.replace('\n', '<br>')
	else: 
		result = 'ERROR Setting Branch'
		error_msg = target.stderr.replace('\n', '<br>')
	return(result, error_msg)

def get_remote_url():
	command = ['git', 'config', '--get', 'remote.origin.url']
	remote = subprocess.run(command, capture_output=True, text=True)
	error_msg = ''
	result = ''
	if(remote.returncode == 0):
		result = remote.stdout.strip(' \n')
	else:
		result = 'ERROR Retrieving URL'
		error_msg = remote.stderr.replace(' \n', ' ')
	return(result, error_msg)

def get_available_updates(branch=''):
	result = {}
	remote, error_msg1 = get_remote_url()
	if(branch == ''):
		branch, error_msg2 = get_branch()

	if('ERROR' not in remote) and ('ERROR' not in branch):
		command = ['git', 'fetch']
		fetch = subprocess.run(command, capture_output=True, text=True)
		command = ['git', 'rev-list', '--left-only', '--count', f'origin/{branch}...@']
		revlist = subprocess.run(command, capture_output=True, text=True)
		#print(f'revlist.returncode = {revlist.returncode}')
		#print(f'fetch.returncode = {fetch.returncode}')

		if (revlist.returncode == 0) and (fetch.returncode == 0):
			revlist = revlist.stdout.strip(' \n')
			if(revlist.isnumeric()):
				result['success'] = True 
				result['commits_behind'] = int(revlist)
			else: 
				result['success'] = False 
				result['message'] = revlist 
		else: 
			result['success'] = False 
			result['message'] = 'ERROR Getting Revision List: ' + revlist.stderr.replace('\n', ' ') + revlist.stdout.replace('\n', ' ')
	else:
		result['success'] = False 
		result['message'] = 'ERROR Getting Remote or Branch: ' + error_msg1 + ' ' + error_msg2
	return(result)

def do_update():
	branch, error_msg1 = get_branch()
	remote, error_msg2 = get_remote_url()
	if (error_msg1 == '') and (error_msg2 == ''):
		command = ['git', 'fetch']
		fetch = subprocess.run(command, capture_output=True, text=True)
		command = ['git', 'reset', '--hard', 'HEAD']
		reset = subprocess.run(command, capture_output=True, text=True)
		command = ['git', 'merge', f'origin/{branch}']
		merge = subprocess.run(command, capture_output=True, text=True)
		error_msg = ''
		result = ''
		if(fetch.returncode == 0) and (reset.returncode == 0) and (merge.returncode == 0):
			result = fetch.stdout.replace('\n', '<br>') + '<br>' + reset.stdout.replace('\n', '<br>') + '<br>' + merge.stdout.replace('\n', '<br>')
		else: 
			result = 'ERROR Performing Update.'
			error_msg = fetch.stderr.replace('\n', '<br>') + '<br>' + reset.stderr.replace('\n', '<br>') + '<br>' + merge.stderr.replace('\n', '<br>')
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
		# Reference command: git ls-remote --tags --sort="v:refname" git://github.com/nebhead/test-update.git | tail -n1 | sed "s/.*\\///;"
		# Gets a list of the remote hashes/tags sorted by version, then takes the last (tail) and processes the output to remove the hash and ref/tags/
		command = ['git', 'ls-remote', '--tags', '--sort=v:refname', remote_url]
		versions = subprocess.run(command, capture_output=True, text=True)
		if versions.returncode == 0:
			versionlist = versions.stdout.split('\n')  # Make a list of versions from the output
			if versionlist != ['']:
				result = versionlist[-2]  # Get the last version from the sorted version list (-1 is actually an empty string, so go -2 to get the last item)
				result = result.split("refs/tags/",1)[1]  # Trickery to split the string after "refs/tags/" to get the version suffix
			else: 
				result = "No versions found"
		else: 
			result = "ERROR Getting Remote Version."
			error_msg = versions.stderr.replace('\n', ' | ')
	else: 
		result = 'ERROR Getting Remote URL.'
	return(result, error_msg)
