#!/usr/bin/env python3

'''
Update support functions to utilize Git/GitHub for live system updates
'''

import os
import time

def get_available_branches():
	command = "sudo git branch -a"
	branches = os.popen(command).readlines()
	branch_list = []
	for line in branches:
		line = line.strip(' \n *')
		if('origin/main' in line):
			# Skip this line
			pass
		elif('remotes/origin/' in line):
			line = line.replace('remotes/origin/', '')
			if (line not in branch_list):
				branch_list.append(line)
		else:
			branch_list.append(line)
	return(branch_list)

def get_branch():
#	--show-current is only in later versions of git, and unfortunatly buster does not have this
#	command = "git branch --show-current"
#	branch = os.popen(command).readline()
	command = "sudo git branch -a"
	branches = os.popen(command).readlines()
	branch = ''
	for line in branches:
		if('*' in line):
			branch = line.strip(' \n *')
			break
	return(branch)

def set_branch(branch_target):
	command = f'sudo git checkout -f {branch_target}'
	result = os.popen(command).readlines() 
	time.sleep(1)
	return(result)

def get_remote_url():
	command = "sudo git config --get remote.origin.url"
	remote = os.popen(command).readline()
	if(remote):
		return(remote.strip(' \n'))
	else:
		return('ERROR: Remote URL not specified in git config.')

def get_available_updates(branch=''):
	result = {}
	remote = get_remote_url()
	if('ERROR' not in remote):
		if(branch == ''):
			branch = get_branch()
		command = "sudo git fetch"
		os.popen(command)
		command = f"sudo git rev-list --left-only --count origin/{branch}...@"
		response = os.popen(command).readline()
		time.sleep(1)
		response = response.strip(' \n')
		if(response.isnumeric()):
			result['success'] = True 
			result['commits_behind'] = int(response)
		else: 
			result['success'] = False 
			result['message'] = response 
	else: 
		result['success'] = False 
		result['message'] = 'ERROR: No remote repository defined.  You may need to re-install from the remote repository.' 
	return(result)

def do_update():
	'''
	Forced Update
	git fetch
	git reset --hard HEAD
	git merge '@{u}'
	'''
	remote = get_remote_url()
	if('ERROR' not in remote):
		command = "sudo git fetch"
		os.popen(command)
		command = "sudo git reset --hard HEAD"
		os.popen(command)
		command = "sudo git merge \'@{u}\'"
		output = os.popen(command).readlines()
		time.sleep(1)
	else:
		output = ['ERROR: No remote configured.']
	return(output)

def get_log(num_commits=10):
	branch = get_branch()
	command = f'git log origin/{branch} -{num_commits} --pretty="%h - %cr : %s"'
	output = os.popen(command).readlines()
	return(output)

def get_remote_version():
	remote_url = get_remote_url()
	# Reference command: git ls-remote --tags --sort="v:refname" git://github.com/nebhead/test-update.git | tail -n1 | sed "s/.*\\///;"
	# Gets a list of the remote hashes/tags sorted by version, then takes the last (tail) and processes the output to remove the hash and ref/tags/
	command = f'git ls-remote --tags --sort="v:refname" {remote_url} | tail -n1 | sed "s/.*\\///;"'
	output = os.popen(command).readline()
	return(output)
