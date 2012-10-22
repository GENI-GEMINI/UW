# -----------------------------------------------------------------------------
#
# Copyright (c) 2010 University of Kentucky
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and/or hardware specification (the "Work") to deal in the
# Work without restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Work, and to permit persons to whom the Work is furnished to do so,
# subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Work.

# THE WORK IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE WORK OR THE USE OR OTHER DEALINGS IN THE WORK.
#
# -----------------------------------------------------------------------------

#! /usr/bin/env python
#toolkit for uk proto-geni experiment setup
import subprocess
import re
import xmlrpclib
import urllib
import xml.sax
import string
import time
import socket
import tempfile
import getpass
from xml.dom.minidom import parse, parseString
from pprint import pprint
import os.path
import datetime
import sys
import crypt
import random
import multiprocessing

#globals 
ssh = 'ssh'
scp = 'scp'
Supported_CM_versions = ['2']
host_info = {}
INSTOOLS_LOCK='/var/emulab/lock/INSTOOLS_LOCK'
NOTSUPPORTED_FLAG='/var/emulab/lock/NOTSUPPORTED'
SUPPORTED_FLAG='/var/emulab/lock/SUPPORTED'
POLL_DATA='/etc/topology/POLL_DATA'
measure_scripts_path="/usr/testbed/bin/measure-scripts"
ARCHIVE_CMD_FILE=measure_scripts_path+"/archive_cmd.sh"
version="0.1"
mc_repo_rooturl="http://gemini.netlab.uky.edu/"
lampca = "https://unis.incntre.iu.edu/protogeni/xmlrpc/lampca"
INSTOOLS_repo_url = mc_repo_rooturl+"GEMINI/"+version+"/"
topology_file_on_mc = "/etc/topology/topology.xml"
EXP_NODE_tmppath = "/tmp"
TRUE = 1
FALSE = 0
ERROR = "ERROR"
printtoscreen=1
dontprinttoscreen=0
PID = str(os.getpid())

def print_timing(func):
    def wrapper(*arg):
        t1 = time.time()
        res = func(*arg)
        t2 = time.time()
        print '%s took %0.3f ms' % (func.func_name, (t2-t1)*1000.0)                                                                    
        return res
    return wrapper

#
# Put user credentials  onto MC and setup ssh keys for communication
# between MC and other node
#
def setupkeys ( nodes_sliver_urns , username, MC_sliver_urn,isVirtualMC, debug, LOGFILE,keyfile):

	MC_NODE_keypath = "/tmp"
	LOCAL_tmppath = "/tmp"
	global EXP_NODE_tmppath
	global INSTOOLS_repo_url
	public_key = "id_rsa.pub"
	public_key_dest = "/var/emulab/boot/mc_ssh_pubkey"
	rc_startup="/etc/rc.local"
	root_authorized_keys="/root/.ssh/authorized_keys"
	global ssh
	global scp
	global host_info
		
	f = tempfile.NamedTemporaryFile(delete=False)
        my_mckeyfile = f.name
	nodes_sliver_urn = nodes_sliver_urns.keys()
	#This get the public key of the measurement node to put on other nodes in your experiement
	msg = "Fetching Measurement controller Public key"
	write_to_log(LOGFILE,msg,dontprinttoscreen,debug)
	(MC,hostname_from_urn,port,auth_type,vid) = host_info[MC_sliver_urn].split(" ")
	ssh_options = getSSH_options(keyfile,port)
	process = subprocess.Popen(scp+ssh_options+" -r "+username+"@"+MC+":"+MC_NODE_keypath+"/"+public_key+" "+my_mckeyfile, shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	process.wait()
	write_to_processlog(process, LOGFILE)
	

	mc_ip = socket.gethostbyname(MC)
	msg = "MC IP = "+mc_ip+"\n"
	write_to_log(LOGFILE,msg,dontprinttoscreen,debug)

	node_cmd ="sudo mv "+my_mckeyfile+" "+public_key_dest+";cd "+EXP_NODE_tmppath+";sudo rm -rf INSTOOLS_SETUP.*;wget "+INSTOOLS_repo_url+"tarballs/INSTOOLS_SETUP.tgz;tar xzfv INSTOOLS_SETUP.tgz;sudo ./INSTOOLS_SETUP.sh Node INSTALL "+mc_ip
	
        # Put the measurement node public key into the other nodes by appending to the authorized keys file     
	proclist = []
	for node_sliver_urn in nodes_sliver_urn:
#		if (nodes_sliver_urns[node_sliver_urn]["active"]["enable"] != 'yes'):
#			continue

	        p = multiprocessing.Process(target=NodeInstall,args=(host_info[node_sliver_urn],node_cmd,my_mckeyfile,LOGFILE,debug,keyfile,username,))
		proclist.append(p)
		p.start()                                                                                                                      
        
	for i in proclist:
		i.join()

	os.remove(my_mckeyfile)
	
	return

def NodeInstall(host_info,node_cmd,my_mckeyfile,LOGFILE,debug,keyfile,username):

	LOCAL_tmppath = "/tmp"
	global EXP_NODE_tmppath
	global INSTOOLS_repo_url
	rc_startup="/etc/rc.local"
	root_authorized_keys="/root/.ssh/authorized_keys"
	global ssh
	global scp
	
	(node,hostname_from_urn,port,auth_type,vid) = host_info.split(" ")
	ssh_options = getSSH_options(keyfile,port)

	msg = "Placing the Measurement controller's public key on Node:\""+vid+"\" to allow it to complete setup"
	write_to_log(LOGFILE,msg,dontprinttoscreen,debug)
	process = subprocess.Popen(scp+ssh_options+" -qr "+my_mckeyfile+" "+username+"@"+node+":"+EXP_NODE_tmppath, shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	process.wait()
	write_to_processlog(process, LOGFILE)
	
	msg = "Running Node Configuration Scripts on Node: \""+vid+"\""
	write_to_log(LOGFILE,msg,printtoscreen,debug)

	
	process = subprocess.Popen(ssh+ssh_options+username+"@"+node+' "'+node_cmd+' "', shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	process.wait()
	write_to_processlog(process, LOGFILE)

	msg = "Node Configuration Scripts on Node: \""+vid+"\" completed."
	write_to_log(LOGFILE,msg,printtoscreen,debug)


#
# Check to see if Node is up and ready
#
def check_if_ready(sliver_urn, username,LOGFILE,keyfile,debug):

	global ssh
	global INSTOOLS_LOCK
	global host_info
	
	cmd = 'sudo ls '
	filename = INSTOOLS_LOCK
	
	(hostname,hostname_from_urn,port,auth_type,vid) = host_info[sliver_urn].split(" ")
	ssh_options = getSSH_options(keyfile,port)
	msg = "Checking if Node :\""+vid+"\" is configured and ready"
	write_to_log(LOGFILE,msg,dontprinttoscreen,debug)
	process = subprocess.Popen(ssh+ssh_options+username+'@'+hostname+' "'+cmd+filename+'"', shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	process.wait()
	ret_code = process.returncode
	write_to_processlog(process, LOGFILE)
	if (ret_code == 0): # Means file exists
		cmd = 'sudo cat '
		process = subprocess.Popen(ssh+ssh_options+username+'@'+hostname+' "'+cmd+filename+'"', shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
		process.wait()
		(out,err) = process.communicate()
		out = out.strip()
		if (out == "INSTALLATION_COMPLETE"): 
	   		return TRUE
		elif(out == "INSTALLATION_IN_PROGRESS"):
			return FALSE
		else:
			pass
	else:
		return ERROR
	return TRUE

#
# Check for Supported OS
#
def isOSSupported(sliver_urn,isMC, username, LOGFILE,keyfile,debug):

	global ssh
	global NOTSUPPORTED_FLAG
	global SUPPORTED_FLAG
	global EXP_NODE_tmppath
	global INSTOOLS_repo_url
	global host_info

	cmd = 'sudo ls '

	(hostname,hostname_from_urn,port,auth_type,vid) = host_info[sliver_urn].split(" ")
	ssh_options = getSSH_options(keyfile,port)

	msg = "Checking if OS on Node : \""+vid+"\" is supported"
	write_to_log(LOGFILE,msg,dontprinttoscreen,debug)

	if (not isMC):
		pre_cmd ="sudo rm -rf "+measure_scripts_path+"/INSTALL_DEFS.sh "+EXP_NODE_tmppath+"/INSTALL_DEFS.tgz;sudo mkdir -p "+measure_scripts_path+";sudo wget -P "+EXP_NODE_tmppath+" "+INSTOOLS_repo_url+"tarballs/INSTALL_DEFS.tgz;sudo tar xzf "+EXP_NODE_tmppath+"/INSTALL_DEFS.tgz -C "+measure_scripts_path+";"
		additional_cmd ="sudo rm -rf /tmp/version_check.sh;wget -P /tmp "+INSTOOLS_repo_url+"scripts/version_check.sh;chmod +x "+EXP_NODE_tmppath+"/version_check.sh;sudo "+EXP_NODE_tmppath+"/version_check.sh "
		process = subprocess.Popen(ssh+ssh_options+username+'@'+hostname+' "'+pre_cmd+additional_cmd+'"', shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
		process.wait()
		write_to_processlog(process, LOGFILE)
	
	process = subprocess.Popen(ssh+ssh_options+username+'@'+hostname+' "'+cmd+SUPPORTED_FLAG+'"', shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	process.wait()
	ret_code = process.returncode
	write_to_processlog(process, LOGFILE)
	if (ret_code == 2):
	   return FALSE
   	elif(ret_code == 0):
	   return TRUE

	return

#
# Check if machine is reachable and then perform OS support version check
# This is usually done before instrumentizing
#
def precheckNodes(rspec_dom,version,cm_urn_to_look,username,keyfile,LOGFILE,debug):

	global ssh
	global EXP_NODE_tmppath
	global INSTOOLS_repo_url
	nodes_sliver_urns = {}
	possibleGMnode = []
	gemini_service_on_node = []
	isGNVirtual = FALSE
	GN_sliverurn = ""
	msg = ""
	isGN = FALSE
	
	cmd = 'ls '
	nodes = rspec_dom.getElementsByTagName('node')
	for i in range(0,nodes.length):
		isMP = FALSE
		my_cmurn = get_cm_urn_value(version,nodes[i])
		sliver_urn = get_sliv_urn_value(version,nodes[i])
		possibleGMnode = nodes[i].getElementsByTagName('gemini:node')
		if (len(possibleGMnode) > 1):
			msg = "Cannot have more than one GEMINI node_type in one node\n"
			return FALSE,GN_sliverurn,isGNVirtual,nodes_sliver_urns,msg
		elif(len(possibleGMnode) == 0):
			continue
		if ( possibleGMnode and possibleGMnode[0].hasAttribute('type')):
			if(possibleGMnode[0].getAttribute('type') == "mp_node"):
				gemini_services = possibleGMnode[0].getElementsByTagName('gemini:services')
				if (len(gemini_services) > 1):
					msg = "Cannot have more than one Gemini Services tag in a <node>\n"
					return FALSE,GN_sliverurn,isGNVirtual,nodes_sliver_urns,msg
				elif(len(gemini_services) == 0):
					continue
				isMP = TRUE
			elif(possibleGMnode[0].getAttribute('type') == "global_node"):
				whichAM = possibleGMnode[0].getElementsByTagName('gemini:monitor_urn')
				if (len(whichAM) > 1):
					msg = "This Global Node cannot monitor slivers at more than one AM\n"
					return FALSE,GN_sliverurn,isGNVirtual,nodes_sliver_urns,msg
				if (whichAM and whichAM[0].hasAttribute('name')):
					my_amurn = whichAM[0].getAttribute('name')
					# Verify if AM value is correct
					# and is same as the cm_urn in this node tag
					if(my_cmurn != my_amurn):
						msg = "This Global Node cannot monitor slivers at a REMOTE AM\n"
						return FALSE,GN_sliverurn,isGNVirtual,nodes_sliver_urns,msg
				if(my_cmurn == cm_urn_to_look):
					if(isGN):
						msg = "This AM cannot have more than one Global Node\n"
						return FALSE,GN_sliverurn,isGNVirtual,nodes_sliver_urns,msg
					isGN = TRUE
					(vtype,vsubtype) = get_virtualization_type(version,nodes[i])
					if (vtype == "emulab-openvz" or vsubtype == "emulab-openvz"):
						isGNVirtual = TRUE
					GN_sliverurn = sliver_urn
					# Add attributes for old INSTOOLS Compatibility
					nodes[i].setAttribute("MC","1")
					nodes[i].setAttribute("mc_type","pc")

			else:
				msg = "Unrecognized GEMINI Node TYPE\n"
				return FALSE,GN_sliverurn,isGNVirtual,nodes_sliver_urns,msg
			pass

			if(my_cmurn == cm_urn_to_look):
	
				(hostname,hostname_from_urn,port,auth_type,vid) = getSSHD_port_number(version,nodes[i],LOGFILE,debug).split(" ")
				ssh_options = getSSH_options(keyfile,port)
				pre_cmd ="rm -rf "+EXP_NODE_tmppath+"/sudoers.tgz;wget -P "+EXP_NODE_tmppath+" "+INSTOOLS_repo_url+"tarballs/sudoers.tgz;";
				cmd = "sudo tar xzf "+EXP_NODE_tmppath+"/sudoers.tgz -C /"
	
				# To fix sudo requiretty problem on fc10
				process = subprocess.Popen(ssh+' -t '+ssh_options+username+"@"+hostname+' "'+pre_cmd+' "', shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
				process.wait()
				write_to_processlog(process, LOGFILE)
				
				process = subprocess.Popen(ssh+' -tt '+ssh_options+username+'@'+hostname+' "'+cmd+'"', shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
				process.wait()
				(out,err) = process.communicate()
				ret_code = process.returncode
				if (ret_code != 0):
					msg =  hostname+" at port "+port+" (Node : "+vid+") is not responding\nInstrumentization will terminate. Please make sure your experiment is running"+"\n"+err
					return FALSE,GN_sliverurn,isGNVirtual,nodes_sliver_urns,msg
				if (not isOSSupported(sliver_urn,FALSE, username, LOGFILE, keyfile,debug)):
					msg = "The Operating System on the Node \""+vid+"\" is not compatible with GEMINI"
					return FALSE,GN_sliverurn,isGNVirtual,nodes_sliver_urns,msg
				msg = "Node : \""+vid+"\" passed pre-check test"
				write_to_log(LOGFILE,msg,dontprinttoscreen,debug)
				if(isMP):
					nodes_sliver_urns[sliver_urn] = get_gservices_from_node(gemini_services[0])
					#pprint(get_gservices_from_node(gemini_services[0]))
					pass
				pass
			pass
		pass
	
	return TRUE,GN_sliverurn,isGNVirtual,nodes_sliver_urns,msg

#
# Collect GEMINI SERVICES info from node
#

def get_gservices_from_node(node):

	my_services = {}
	my_services['active'] = {}
	my_services['passive'] = {}
	my_services['active']['install'] = {}
	my_services['active']['enable'] = {}
	my_services['passive']['install'] = {}
	my_services['passive']['enable'] = {}
	active = node.getElementsByTagName('gemini:active')
	passive = node.getElementsByTagName('gemini:passive')

	if(len(active) > 0):
		if (active[0].hasAttribute('install')):
			my_services['active']['install'] = active[0].getAttribute('install')
			pass

		if (active[0].hasAttribute('enable') and my_services['active']['install'] == 'yes'):
			my_services['active']['enable'] = active[0].getAttribute('enable')
			pass

	if(len(passive) > 0):
		if (passive[0].hasAttribute('install')):
			my_services['passive']['install'] = passive[0].getAttribute('install')
			pass

		if (passive[0].hasAttribute('enable') and my_services['passive']['install'] == 'yes' ):
			my_services['passive']['enable'] = passive[0].getAttribute('enable')
			pass

	return my_services

#
# Ask user if he/she want to instrumentize all the CM's in the topology
#
def CM_Choices(my_managers,choice):
	
	managers = []
	while True:
		if (choice == "add"):
			msg1 = 'Do you want to Instrumentize your nodes at all the Component Managers (Y / N)? [DEFAULT: Y]  : '
		else:
			msg1 = 'Do you want to de-instrumentize your nodes at all the Component Managers (Y / N)? [DEFAULT: Y]  : '

		user_input = raw_input(msg1)
		if user_input in ['Y','y','']:
			managers = my_managers
			break
		elif user_input in ['N','n']:
			for my_manager in my_managers:
				CM_HRN = my_manager["hrn"]
				if (choice == "add"):
					msg2 = 'Do you want to Instrumentize your nodes at '+CM_HRN+' (Y / N)? [DEFAULT: N]  : '
				else:
					msg2 = 'Do you want to de-Instrumentize your nodes at '+CM_HRN+' (Y / N)? [DEFAULT: N]  : '

				cm_allow = raw_input(msg2)
				if cm_allow in ['Y','y']:
					managers.append(my_manager)
				elif cm_allow in ['N','n','']:
					continue
				else:
					print "Incorrect Choice.\n"
			break
		else:
			print "Incorrect Choice.\n"

	return managers

# Install packages and other softare for INSTOOLS

def InstallGN(MC_sliver_urn, username, LOGFILE,keyfile,debug ):

	global ssh
	global scp
	global host_info

	(MC,hostname_from_urn,port,auth_type,vid) =  host_info[MC_sliver_urn].split(" ")
	ssh_options = getSSH_options(keyfile,port)

	cmd ="cd /tmp/;sudo rm -rf /tmp/INSTOOLS_SETUP.*;wget "+INSTOOLS_repo_url+"tarballs/INSTOOLS_SETUP.tgz;tar xzf /tmp/INSTOOLS_SETUP.tgz;nohup sudo /tmp/INSTOOLS_SETUP.sh MC INSTALL &"

	msg = "Starting the Global Node Software Intallation..."
	write_to_log(LOGFILE,msg,printtoscreen,debug)
	process = subprocess.Popen(ssh+ssh_options+username+'@'+MC+' "'+cmd+'"', shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	post_cmd = "sudo touch /var/emulab/boot/isGemini;"
	process = subprocess.Popen(ssh+ssh_options+username+'@'+MC+' "'+post_cmd+'"', shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
#	process.wait()
#	write_to_processlog(process, LOGFILE)
	
	return


#
# start data collection routines 
#
def copy_manifest_to_MC(manifest,MC_sliver_urn, username, LOGFILE,keyfile,debug ):

	global ssh
	global scp
	global topology_file_on_mc
	global host_info

	f = tempfile.NamedTemporaryFile()
	manifest_file = f.name
	manifest.replace("<emulab:vnode", "<rs:vnode")
	f.write(manifest)
	f.flush()
	
	(MC,hostname_from_urn,port,auth_type,vid) =  host_info[MC_sliver_urn].split(" ")
	ssh_options = getSSH_options(keyfile,port)
	#This places your Manifest file on the Measurement node
	msg = "Placing your Manifest file on the Measurement controller"
	write_to_log(LOGFILE,msg,dontprinttoscreen,debug)
	process = process = subprocess.Popen(scp+ssh_options+" -qr "+manifest_file+" "+username+"@"+MC+":"+topology_file_on_mc, shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	process.wait()
	write_to_processlog(process, LOGFILE)
	
	cmd = 'chmod +r '+topology_file_on_mc+';'
	process = subprocess.Popen(ssh+ssh_options+username+'@'+MC+' "'+cmd+'"', shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	process.wait()
	write_to_processlog(process, LOGFILE)
	
	f.close()
	return
#
# start data collection routines 
#
def startStatscollection(cmurn,cmhrn, sliceurn,userurn,MC_sliver_urn, username, LOGFILE,keyfile,debug ):

	global ssh
	global scp
	global host_info

	(MC,hostname_from_urn,port,auth_type,vid) =  host_info[MC_sliver_urn].split(" ")
	ssh_options = getSSH_options(keyfile,port)
	
	cmd = 'sudo '+measure_scripts_path+'/initiate_stat_collection_without_credentials.sh '+userurn+' '+cmurn+' '+cmhrn+' '+sliceurn
	msg = "Starting the Data collection routines on the Measurement controller"
	write_to_log(LOGFILE,msg,dontprinttoscreen,debug)
	process = subprocess.Popen(ssh+ssh_options+username+'@'+MC+' "'+cmd+'"', shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	process.wait()
	write_to_processlog(process, LOGFILE)
	
	return

#
# Initialize Drupal menus for this topology
#
def initialize_Drupal_menu( MC_sliver_urn, username,SLICENAME,dp_username,dp_passwd,LOGFILE ,keyfile,debug):

	global ssh
	global host_info

	(MC,hostname_from_urn,port,auth_type,vid) =  host_info[MC_sliver_urn].split(" ")
	ssh_options = getSSH_options(keyfile,port)
	
	cmd = '/usr/bin/wget -b --no-check-certificate -a /var/emulab/logs/INSTOOLS.log -O /tmp/instools_pt.log --user='+dp_username+' --password='+dp_passwd+' "http://'+hostname_from_urn+'/drupal/parseTopology.php?SLICENAME='+SLICENAME+'"'
	msg = "Initializing Drupal Menu creation for this Topology"
	write_to_log(LOGFILE,msg,printtoscreen,debug)
	process = subprocess.Popen(ssh+ssh_options+username+'@'+MC+' \''+cmd+' \'', shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	write_to_processlog(process, LOGFILE)
	
	return

#
# Create md5 crypt from user input passwd
#
def generate_crypt_passwd(passwd,LOGFILE,debug):

	seq = ('./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')
	salt = ""
	for k in range (0, 2):
		salt  += random.choice(seq)
		pass
	mycrypt =  crypt.crypt(passwd,salt)
#	msg = "Your passwd crypt = "+mycrypt
#	write_to_log(LOGFILE,msg,dontprinttoscreen,debug)
	return mycrypt

#
# Push POLL_DATA file to MC
#
def send_polldata_file(MC_sliver_urn,username,password,LOGFILE,keyfile,debug):

	global ssh
	global host_info
	global POLL_DATA
	global EXP_NODE_tmppath
	
	(MC,hostname_from_urn,port,auth_type,vid) =  host_info[MC_sliver_urn].split(" ")
	ssh_options = getSSH_options(keyfile,port)
	
	f = tempfile.NamedTemporaryFile()
	pdata = f.name
	f.write(password)
	f.flush()
	
	process = subprocess.Popen(scp+ssh_options+" -qr "+pdata+" "+username+"@"+MC+":"+POLL_DATA, shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	process.wait()
	write_to_processlog(process, LOGFILE)
	f.close()
	
	cmd = 'sudo chmod 444 '+POLL_DATA
	msg = "Sending POLL_DATA file to MC"
	write_to_log(LOGFILE,msg,printtoscreen,debug)
	process = subprocess.Popen(ssh+ssh_options+username+'@'+MC+' \''+cmd+'\'', shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	write_to_processlog(process, LOGFILE)

	return

def getLockStatus(MC_sliver_urn,username,LOGFILE,keyfile,debug):

	global ssh
	global host_info
	global EXP_NODE_tmppath
	global INSTOOLS_LOCK
	
	(MC,hostname_from_urn,port,auth_type,vid) =  host_info[MC_sliver_urn].split(" ")
	ssh_options = getSSH_options(keyfile,port)
	sendcmd = 'cat '+INSTOOLS_LOCK+';'
	process = subprocess.Popen(ssh+ssh_options+username+'@'+MC+' \''+sendcmd+'\'', shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	(out,err) = process.communicate()

	return out.rstrip()

#
# Lock/unlock MC during setup
#
def lock_unlock_MC(MC_sliver_urn,what_to_do,username,LOGFILE,keyfile,debug):

	global ssh
	global host_info
	global EXP_NODE_tmppath
	global INSTOOLS_LOCK
	msg = ""

	while(1):
		lockstatus = getLockStatus(MC_sliver_urn,username,LOGFILE,keyfile,debug)
		if(lockstatus == "INSTALLATION_COMPLETE"):
			msg = "Gemini Configuration setup is starting..\n"
			break
		elif(lockstatus == "INSTALLATION_IN_PROGRESS"):
			msg = "Global Node software Installation is in progress\nWill check again in 15 seconds....\n"
			write_to_log(LOGFILE,msg,printtoscreen,debug)
			time.sleep(15)
			continue
		elif(lockstatus == "INSTRUMENTIZE_IN_PROGRESS"):
			if (what_to_do == "lock"):
				msg = "Gemini Configuration setup is running..\nWill not proceed for this AM\n"
				return FALSE,msg
			else:
				msg = "Gemini Configuration setup is complete..\n"
				break
		elif(lockstatus == "INSTRUMENTIZE_COMPLETE"):
			msg = "Gemini Configuration setup is already complete..\nWill not proceed for this AM\n"
			return FALSE,msg
		elif(lockstatus == ""):
			msg = "Global Node Software Installation starting...\n"
			InstallGN(MC_sliver_urn,username,LOGFILE,keyfile,debug)
			time.sleep(15)
			continue

        if (what_to_do == "lock"):
                lock_flag = "INSTRUMENTIZE_IN_PROGRESS"
        elif(what_to_do == "unlock"):
                lock_flag = "INSTRUMENTIZE_COMPLETE"
        else:
                lock_flag = ""
	

	(MC,hostname_from_urn,port,auth_type,vid) =  host_info[MC_sliver_urn].split(" ")
	ssh_options = getSSH_options(keyfile,port)
	f = tempfile.NamedTemporaryFile()
	adata = f.name
	f.write(lock_flag)
	f.flush()
	process = subprocess.Popen(scp+ssh_options+" -qr "+adata+" "+username+"@"+MC+":"+EXP_NODE_tmppath, shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	process.wait()
	write_to_processlog(process, LOGFILE)
	f.close()
	
	sendcmd = 'sudo mv '+adata+' '+INSTOOLS_LOCK+';'
	process = subprocess.Popen(ssh+ssh_options+username+'@'+MC+' \''+sendcmd+'\'', shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	write_to_processlog(process, LOGFILE)
	
	return TRUE,msg





#
# Push the needed info to the portal site
#
def send_to_instools_portal(MC_sliver_urn,username,password,op,emailid,cmurn,cmhrn,slicename,cert_issuer,LOGFILE,keyfile,debug):

	global ssh
	global host_info
	global ARCHIVE_CMD_FILE
	global EXP_NODE_tmppath
	
	(MC,hostname_from_urn,port,auth_type,vid) =  host_info[MC_sliver_urn].split(" ")
	ssh_options = getSSH_options(keyfile,port)
	
	archive_cmd = '/usr/bin/lynx -dump "https://instools-archive.uky.emulab.net/drupal/archive.php?VM_MC='+hostname_from_urn+'&MC='+MC+'&sshd_port='+port+'&username='+username+'&password='+password+'&HRN='+cmhrn+'&slicename='+slicename+'&cert_issuer='+cert_issuer+'&urn='+urllib.quote_plus(MC_sliver_urn)+'&email='+emailid+'";'

	f = tempfile.NamedTemporaryFile()
	adata = f.name
	f.write(archive_cmd)
	f.flush()
	
	process = subprocess.Popen(scp+ssh_options+" -qr "+adata+" "+username+"@"+MC+":"+EXP_NODE_tmppath, shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	process.wait()
	write_to_processlog(process, LOGFILE)
	f.close()
	

	precmd = 'sudo  mv '+adata+' '+ARCHIVE_CMD_FILE+';sudo chmod 555 '+ARCHIVE_CMD_FILE+';'
	#cmd = '/usr/bin/lynx -dump "https://geminiportal.netlab.uky.edu/getTopinfo.php?VM_MC='+hostname_from_urn+'&MC='+MC+'&sshd_port='+port+'&username='+username+'&password='+password+'&HRN='+cmhrn+'&CMURN='+urllib.quote_plus(cmurn)+'&slicename='+slicename+'&cert_issuer='+cert_issuer+'&urn='+urllib.quote_plus(MC_sliver_urn)+'&op='+op+'";'
	cmd = '/usr/bin/wget --no-check-certificate -a /var/emulab/logs/INSTOOLS.log -O /tmp/gm-portal.log "https://geminiportal.netlab.uky.edu/getTopinfo.php?VM_MC='+hostname_from_urn+'&MC='+MC+'&sshd_port='+port+'&username='+username+'&password='+password+'&HRN='+cmhrn+'&CMURN='+urllib.quote_plus(cmurn)+'&slicename='+slicename+'&cert_issuer='+cert_issuer+'&urn='+urllib.quote_plus(MC_sliver_urn)+'&op='+op+'";'
	msg = "Sending this MC's info to INSTOOLS portal site"
	write_to_log(LOGFILE,msg,printtoscreen,debug)
	process = subprocess.Popen(ssh+ssh_options+username+'@'+MC+' \''+precmd+cmd+'\'', shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	write_to_processlog(process, LOGFILE)

	return

#
# Initialize/Start/Stop Netflow data collection 
#
def do_netflow_stuff(MC_sliver_urn,action, username, LOGFILE,keyfile ,debug):
	global ssh
	global host_info
	
	(MC,hostname_from_urn,port,auth_type,vid) = host_info[MC_sliver_urn].split(" ")
	ssh_options = getSSH_options(keyfile,port)
	
	cmd = '/usr/bin/perl /usr/testbed/bin/netflow-scripts/geni_netflow.pl'
	
	msg = action+" Netflow Setup for this Topology"
	write_to_log(LOGFILE,msg,dontprinttoscreen,debug)
	process = subprocess.Popen(ssh+ssh_options+username+'@'+MC+' "'+cmd+" "+action+'"', shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	process.wait()
	write_to_processlog(process, LOGFILE)
	
	return

#
# Check if netflow data was generated
#
def check_netflow_data_generated(MC_sliver_urn, username, LOGFILE,keyfile ,debug):
	global ssh
	global host_info
	ret_code = 1

	(MC,hostname_from_urn,port,auth_type,vid) = host_info[MC_sliver_urn].split(" ")
	ssh_options = getSSH_options(keyfile,port)
	
	cmd = 'ls /etc/netflow/output/*.rrd'

	while TRUE:
		msg = "Checking if Netflow data collection started for this Topology"
		write_to_log(LOGFILE,msg,printtoscreen,debug)
		process = subprocess.Popen(ssh+ssh_options+username+'@'+MC+' "'+cmd+'"', shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
		process.wait()

		ret_code = process.returncode
		write_to_processlog(process, LOGFILE)
		if (ret_code != 0):
			msg = "Netflow Data collection not started yet.. Will check again after 30 seconds "
			if(debug):
				msg = msg+"retcode ="+str(ret_code)
			write_to_log(LOGFILE,msg,printtoscreen,debug)
			time.sleep(30)
		else:
			msg = "Netflow Data collection has started .. Continuing Intrumentize.... "
			if(debug):
				msg = msg+"retcode ="+str(ret_code)
			write_to_log(LOGFILE,msg,printtoscreen,debug)
			break
	
	return
#
# Check if the topology is already has an MC at this CM
# And while we are at it we can collect all Nodes to monitor
#
def is_GN_present(rspec_dom,version,cm_urn_to_look,LOGFILE,debug):

	nodes = rspec_dom.getElementsByTagName('node')
	isPresent = FALSE
	isMCVirtual = FALSE
	msg = ""
	sliver_urn = ""
	for i in range(0,nodes.length):
		possibleGNnode = nodes[i].getElementsByTagName('gemini:node_type')
		if (len(possibleGNnode) > 1):
			msg = "Cannot have more than one GEMINI node_type in one node\n"
			write_to_log(LOGFILE,msg,printtoscreen,debug)
			sys.exit()
		elif(len(possibleGNnode) == 0):
			continue
		if (possibleGNnode[0].hasAttribute('name') and possibleGNnode[0].getAttribute('name') == "global_node"):
			whichAM = possibleGNnode[0].getElementsByTagName('gemini:monitor_urn')
			if (len(whichAM) > 1):
				msg = "This Global Node cannot monitor slivers at more than one AM\n"
				break
				pass
			my_cmurn = get_cm_urn_value(version,nodes[i])
			if (whichAM[0].hasAttribute('name')):
				my_amurn = whichAM[0].getAttribute('name')
				# Verify if AM value is correct
				# and is same as the cm_urn in this node tag
				if(my_cmurn != my_amurn):
					msg = "This Global Node cannot monitor slivers at a REMOTE AM\n"
					break
					pass
			if(my_cmurn == cm_urn_to_look):
				if(isPresent):
					msg = "This AM cannot have more than one Global Node\n"
					break
					pass
				isPresent = TRUE
				if(get_component_urn_value(version,nodes[i]) != ""):
					(hostname,hostname_from_urn,port,auth_type,vid) = getSSHD_port_number(version,nodes[i],LOGFILE,debug).split(" ")
					sliver_urn = get_sliv_urn_value(version,nodes[i])
					(vtype,vsubtype) = get_virtualization_type(version,nodes[i])
					if (vtype == "emulab-openvz" or vsubtype == "emulab-openvz"):
						isMCVirtual = TRUE
				break
				pass
			elif(my_cmurn == ""):
				msg = "Your MC Node defination is missing a component_manager_id attribute.\nCannot proceed"
				break
				pass
		
		
	return (isPresent,sliver_urn,isMCVirtual,msg)
#
# Check if the topology is already Instrumentized at this CM
# Return MC hostname if instrumentized and FALSE if not
#
def is_instrumentized(rspec_dom,version,cm_urn,debug):

	nodes = rspec_dom.getElementsByTagName('node')
	instrumentized = FALSE
	isMCVirtual = FALSE
	for i in range(0,nodes.length):
		if (nodes[i].hasAttribute('MC')):
			instrumentized = TRUE
			break
			pass
	if (instrumentized):
		(hostname,hostname_from_urn,port,auth_type,vid) = getSSHD_port_number(version,nodes[i],LOGFILE,debug).split(" ")
		(vtype,vsubtype) = get_virtualization_type(version,nodes[i])
		if (vtype == "emulab-openvz" or vsubtype == "emulab-openvz"):
			isMCVirtual = TRUE
		return get_sliv_urn_value(version,nodes[i]),isMCVirtual
	else:
		return "",isMCVirtual
#
# get hostname and sshd port number for the node
# and save it in a data-structure with sliver_urn as key
#
def getSSHD_port_number(rspec_version,xml_node,LOGFILE,debug):

	global host_info
	sliver_urn = get_sliv_urn_value(rspec_version,xml_node)
	vid = get_vid_value(rspec_version,xml_node)
	hostname_from_urn = getHostnameFromExt(xml_node,get_component_urn_value(rspec_version,xml_node),rspec_version)

	try:
		host_login_details = host_info[sliver_urn]
		msg = "\nHost info for Node : \""+vid+"\" exists already. \nThis info is "+host_info[sliver_urn]+"\n"
		write_to_log(LOGFILE,msg,dontprinttoscreen,debug)

	except KeyError:
		msg = "\nHost info for Node : \""+vid+"\" does not exist. Will search for it and save for later use\n"
		write_to_log(LOGFILE,msg,dontprinttoscreen,debug)
		services_node = xml_node.getElementsByTagName('services')
		for i in range(0,services_node.length):
			login_node = services_node[i].getElementsByTagName('login')
			for j in range(0,login_node.length):
				if (login_node[j].hasAttribute('hostname') and login_node[j].hasAttribute('port')):
					phys_hostname = login_node[j].getAttribute('hostname')
					sshd_port = login_node[j].getAttribute('port')
					auth_type = login_node[j].getAttribute('authentication')
					host_info[sliver_urn] = phys_hostname +" "+hostname_from_urn+" "+sshd_port+" "+auth_type+" "+vid
	return host_info[sliver_urn]


#
# Performs some uninstalls to de-intrumentize and experiment
#
def deInstrumentize(nodes_sliver_urn,username, debug, LOGFILE,keyfile):
		
	ssl_dir = "~/.ssl "
	global EXP_NODE_tmppath
	global ssh
	global INSTOOLS_repo_url
	global host_info

	pre_cmd =";"
	node_cmd ="cd "+EXP_NODE_tmppath+";sudo rm -rf INSTOOLS_SETUP.*;wget "+INSTOOLS_repo_url+"tarballs/INSTOOLS_SETUP.tgz;tar xzfv INSTOOLS_SETUP.tgz;sudo ./INSTOOLS_SETUP.sh Node REMOVE;"
	post_cmd ="cd "+EXP_NODE_tmppath+";sudo rm -rf INSTOOLS_*.*;sudo rm -rf Node-pkg_*.sh sudoers.tgz version_check.sh INSTALL_DEFS.*;sudo rm -rf /etc/vnc /etc/snmp/snmpd.conf.rpmsave;"
	
	proclist = []
	for node_sliver_urn in nodes_sliver_urn:

		p = multiprocessing.Process(target=Node_deInstall,args=(host_info[node_sliver_urn],pre_cmd+node_cmd+post_cmd,LOGFILE,debug,keyfile,username,))
		proclist.append(p)
		p.start()                                                                                                                      
        
	for i in proclist:
		i.join()

	return



#	for node_sliver_urn in nodes_sliver_urn:
#		(node,hostname_from_urn,port,auth_type,vid) = host_info[node_sliver_urn].split(" ")
#		ssh_options = getSSH_options(keyfile,port)
#		process = subprocess.Popen(ssh+ssh_options+username+'@'+node+' "'+pre_cmd+post_cmd+node_cmd+scripts_cleanup+'"', shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
#		process.wait()
#		write_to_processlog(process, LOGFILE)
	
#	return

def Node_deInstall(host_info,node_cmd,LOGFILE,debug,keyfile,username):

	global EXP_NODE_tmppath
	global ssh
	global INSTOOLS_repo_url

	(node,hostname_from_urn,port,auth_type,vid) = host_info.split(" ")
	msg = "Running Node de-Configuration Scripts on Node: \""+vid+"\""
	write_to_log(LOGFILE,msg,printtoscreen,debug)
	ssh_options = getSSH_options(keyfile,port)
	process = subprocess.Popen(ssh+ssh_options+username+'@'+node+' "'+node_cmd+'"', shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	process.wait()
	write_to_processlog(process, LOGFILE)

	msg = "De-Configuring Node: \""+vid+"\" Complete"
	write_to_log(LOGFILE,msg,printtoscreen,debug)
	return 

# SSH/SCP option string
def getSSH_options(kf,port):
	opt = ' -o StrictHostKeyChecking=no '
	if(kf):
		if ( os.path.isfile(kf) ):
			opt = opt+ '-i '+kf+' ' 
	if(port):
			opt = opt+'-o Port='+port+' ' 
	
	return opt

#
# Get MDA Account details from user
#
def getMDA_Account_Details():

	
	MDA_username = ""
	MDA_password = ""

	u = raw_input("Please enter your MDA Archive Service Username : ")
	MDA_username = u.strip()
	a = getpass.getpass("Please enter your MDA Archive Service Password : ")
	MDA_password = a.strip()

	return MDA_username,MDA_password

#
# Setup MDA archive mount
#
def	setup_mda_archive_mount(MC_sliver_urn,username,keyfile,LOGFILE,debug):
		
	global ssh
	global host_info

	MDA_username = ""
	MDA_password = ""

	(MC,hostname_from_urn,port,auth_type,vid) = host_info[MC_sliver_urn].split(" ")
	ssh_options = getSSH_options(keyfile,port)
	precmd = 'sudo /usr/testbed/bin/measure-scripts/setup_mda.sh;'
	process = subprocess.Popen(ssh+ssh_options+username+'@'+MC+' \''+precmd+'\'',shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	process.wait()
	ret_code = process.returncode
	(out,err) = process.communicate()

	if (ret_code == 6 ):
		msg = "MDA Achive service had been previously setup. Using it now ..."
		write_to_log(LOGFILE,msg,printtoscreen,debug)
		return TRUE
	msg = "MDA Achive service setup starts now ..."
	write_to_log(LOGFILE,msg,printtoscreen,debug)
	(MDA_username,MDA_password) = getMDA_Account_Details()
	cmd = 'sudo /usr/testbed/bin/measure-scripts/setup_mda.sh '+MDA_username+' '+MDA_password+';'
	process = subprocess.Popen(ssh+ssh_options+username+'@'+MC+' \''+cmd+'\'',shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	process.wait()
	ret_code = process.returncode
	(out,err) = process.communicate()
	if (ret_code != 0):
		write_to_log(LOGFILE,err,printtoscreen,debug)
		return FALSE
	else:
		return TRUE

	return TRUE
	
	
#
# Create  MDA archive
#
def	archive_my_data_using_mda(MC_sliver_urn,username,keyfile,LOGFILE,debug):
		
	global ssh
	global host_info

	(MC,hostname_from_urn,port,auth_type,vid) = host_info[MC_sliver_urn].split(" ")
	ssh_options = getSSH_options(keyfile,port)
	cmd = 'sudo /usr/testbed/bin/measure-scripts/archive_using_mda.sh;'

	msg = "\nStarting archive process ...\n"
	write_to_log(LOGFILE,msg,printtoscreen,debug)
	process = subprocess.Popen(ssh+ssh_options+username+'@'+MC+' \''+cmd+'\'',shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	process.wait()
	ret_code = process.returncode
	(out,err) = process.communicate()
	while TRUE:
		if (ret_code != 0 ):
			write_to_log(LOGFILE,err,printtoscreen,debug)
			msg = "\nTrying to archive again...\n"
			write_to_log(LOGFILE,msg,printtoscreen,debug)
		else:
			write_to_log(LOGFILE,out,printtoscreen,debug)
			break

	return TRUE
	



#
# Call php script on MC to create the drupal account
#
def	drupal_account_create(MC_sliver_urn,username,password,email_id,dp_username,dp_passwd,LOGFILE,keyfile,debug):
		
	global INSTOOLS_repo_url
	global ssh
	global host_info

	(MC,hostname_from_urn,port,auth_type,vid) = host_info[MC_sliver_urn].split(" ")
	ssh_options = getSSH_options(keyfile,port)
	pre_cmd = 'sudo wget -P /var/www/html/drupal "'+INSTOOLS_repo_url+'scripts/createUser.php.txt";sudo mv /var/www/html/drupal/createUser.php.txt /var/www/html/drupal/createUser.php ;sudo chmod +x /var/www/html/drupal/createUser.php;sudo chgrp nobody /var/www/html/drupal/createUser.php;'
	cmd = '/usr/bin/wget --no-check-certificate -a /var/emulab/logs/INSTOOLS.log -O /tmp/instools_createuser.log --user='+dp_username+' --password='+dp_passwd+' "https://'+hostname_from_urn+'/drupal/createUser.php?uname='+username+'&pswd='+password+'&email='+email_id+'&debug=1";'
	post_cmd = 'sudo rm -rf /var/www/html/drupal/createUser.php;'

	process = subprocess.Popen(ssh+ssh_options+username+'@'+MC+' \''+pre_cmd+cmd+post_cmd+'\'',shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	process.wait()
	write_to_processlog(process, LOGFILE)
	return


#
# Update the drupal Admin info
#
def	update_Drupaladmin_acctinfo(MC_sliver_urn,username,dp_username,dp_passwd,LOGFILE,keyfile,debug):
		
	global ssh
	global host_info

	(MC,hostname_from_urn,port,auth_type,vid) = host_info[MC_sliver_urn].split(" ")
	ssh_options = getSSH_options(keyfile,port)
	
	cmd = 'sudo '+measure_scripts_path+'/change_drupal_accinfo.sh '+dp_passwd+';'

	msg = "Updating the drupal Admin account info"
	write_to_log(LOGFILE,msg,printtoscreen,debug)
	process = subprocess.Popen(ssh+ssh_options+username+'@'+MC+' \''+cmd+'\'',shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	process.wait()
	write_to_processlog(process, LOGFILE)
	
	return


	
#
# Create VNC password on MC and  copy the same to Experimental machines
#
def	vnc_passwd_create(nodes_sliver_urns,MC_sliver_urn,username,LOGFILE,keyfile,debug):
		
	global ssh
	global host_info
	
	node_list = ""
	nodes_sliver_urn = nodes_sliver_urns.keys()
	for node_sliver_urn in nodes_sliver_urn:
#		if (nodes_sliver_urns[node_sliver_urn]["active"]["enable"] != 'yes'):
#			continue
		(node,hostname_from_urn,port,auth_type,vid) = host_info[node_sliver_urn].split(" ")
		#node_list = node_list+" "+node+":"+port
		node_list = node_list+" "+hostname_from_urn

	(MC,hostname_from_urn,port,auth_type,vid) = host_info[MC_sliver_urn].split(" ")
	ssh_options = getSSH_options(keyfile,port)
	mc_cmd = 'sudo '+measure_scripts_path+'/configure_vnc.sh "'+node_list+'";'

	msg = "Setting up VNC Passwd file from MC and Experimental machines"
	write_to_log(LOGFILE,msg,dontprinttoscreen,debug)
	process = subprocess.Popen(ssh+ssh_options+username+'@'+MC+' \''+mc_cmd+'\'',shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	process.wait()
	write_to_processlog(process, LOGFILE)
	
	return

#
# Obtain username and password for drupal account creation
#
def getpasswd_for_drupal(LOGFILE,debug):
	
	passwd = ""
	confirm_passwd = ""
	email_id = ""

	# Loop to get password
	while (TRUE):
		print "Please enter a password to access the Webinterface on the Measurement Controller\nChoose a password with atleast SIX characters\n"
		a = getpass.getpass("Password : ")
		passwd = a.strip()
		if (len(passwd) < 6):
			print "Choose a password with atleast SIX characters\n"
		else:
			a = getpass.getpass("Confirm Password : ")
			confirm_passwd = a.strip()
			if (passwd != confirm_passwd ):
				print "Passwords entered do not match. Please try again\n"
			else:
				break
	return passwd

#
# Grab STDOUT and STDERR  and write it to MC Log
#
def write_to_processlog(process, LOGFILE):

	fh = open(LOGFILE, 'a')
	(out,err) = process.communicate()
	log_date = time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(time.time()))
	if out != "":
		fh.write(log_date+" :\n******** STDOUT ************* \n"+out+"*****************************\n")
	if err != "":
		fh.write(log_date+" :\n******** STDERR ************* \n"+err+"*****************************\n")
	
	fh.close()

	return
		
def write_to_log(LOGFILE, message,print_also,debug):

	if ((print_also == 1) or debug):
		print message+"\n"
	fh = open(LOGFILE, 'a')
	log_date = time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(time.time()))
	fh.write(log_date +" :\t"+ message+"\n")
	fh.close()
	return

# Check if directory exists and create it if it does not
def ensure_dir(f):
	d = os.path.dirname(f)
	if not os.path.exists(d):
		os.makedirs(d)

# Add node location to the manifest
def addNodeLocation(manifest_dom,version,CM_URN,CM_Resources_location,LOGFILE,debug):


#	manifest_dom = parseString(manifest)
	Manifest_Nodes = manifest_dom.getElementsByTagName('node')
	manifest_node_count = Manifest_Nodes.length
	for i in range(0,manifest_node_count):
		cm_urn = get_cm_urn_value(version,Manifest_Nodes.item(i))
		if (cm_urn == CM_URN):
			urn = get_component_urn_value(version,Manifest_Nodes.item(i))
			location_tag = Manifest_Nodes.item(i).getElementsByTagName('node')
			if(len(location_tag) == 0):
				try:
					Clone = CM_Resources_location[urn].cloneNode(True)
					Manifest_Nodes.item(i).appendChild(Clone)
				except KeyError:
					(node_urn,pcvm) = urn.rsplit("+",1)
					(pcname,junk) = pcvm.replace('pcvm','pc').split('-',1)
					Clone = CM_Resources_location[node_urn+"+"+pcname].cloneNode(True)
					Manifest_Nodes.item(i).appendChild(Clone)
				pass
			pass
		pass
	return manifest_dom.toxml()

# Get Expiry time from rspec if one exists
def getUserDefinedRspecExpiry(rspec_dom,slice_expiry,LOGFILE,debug):
	requested_minutes=180       # Default Slice/Sliver renewal time
	requested_expiration = None
	try:
		valid_until_tags = rspec_dom.getElementsByTagName('valid_until')
		rspec_tag = rspec_dom.getElementsByTagName('rspec')
		valid_until_attribute = rspec_tag[0].getAttribute('valid_until')
		if (valid_until_tags.length > 1 or (valid_until_tags.length == 1 and valid_until_attribute != "")):
			msg = "Only one <valid_until> tag or \"valid_until\" attribute in <rspec> tag permitted"
			write_to_log(LOGFILE,msg,printtoscreen,debug)
			sys.exit(1)
		elif (valid_until_tags.length == 0 and valid_until_attribute == ""):
			moretime = datetime.datetime.utcnow() + datetime.timedelta(minutes=requested_minutes)
			if (slice_expiry < moretime ):
				requested_expiration = moretime
			else:
				requested_expiration = None
		else:
			if(valid_until_attribute == ""):
				valid_until = valid_until_tags[0].firstChild
				reqtime_struct = time.strptime(valid_until.nodeValue,"%Y-%m-%dT%H:%M:%S")
			else:
				reqtime_struct = time.strptime(valid_until_attribute,"%Y-%m-%dT%H:%M:%S")
			requested_expiration = datetime.datetime(reqtime_struct.tm_year,reqtime_struct.tm_mon,reqtime_struct.tm_mday,reqtime_struct.tm_hour,reqtime_struct.tm_min,reqtime_struct.tm_sec)
	except ValueError:
		msg = "Syntax Error in valid_until tag in the supplied rspec"
		write_to_log(LOGFILE,msg,printtoscreen,debug)
		sys.exit(1)
		pass
	except TypeError:
		moretime = datetime.datetime.utcnow() + datetime.timedelta(minutes=requested_minutes)
		if (slice_expiry < moretime ):
			requested_expiration = moretime
		else:
			requested_expiration = None

	return requested_expiration


# Get the version of Rspec being userd
def getRspecVersion(rspec_dom):
		
	rspec_tag = rspec_dom.getElementsByTagName("rspec").item(0)
	(junk,rspec_version) = rspec_tag.getAttribute("xmlns").rsplit("/",1)
	if (float(rspec_version) < 2):
		rspec_version = 1
	return int(rspec_version)

# Get CM URN attribute value from node based on rspec version
def get_cm_urn_value(version,node):

	if (version < 2):
		return node.getAttribute("component_manager_urn")
		pass
	elif(version >= 2):
		return node.getAttribute("component_manager_id")
	else:
		sys.exit(1)
	return

# Get Component URN attribute value from node based on rspec version
def get_component_urn_value(version,node):

	if (version < 2):
		if (node.hasAttribute("component_urn")):
			return node.getAttribute("component_urn")
		elif (node.hasAttribute("component_uuid")):
			return node.getAttribute("component_uuid")
		else:
			return ""
		pass
	elif(version >= 2):
		return node.getAttribute("component_id")
	else:
		sys.exit(1)

	return

# Get Sliver URN attribute value from node based on rspec version
def get_sliv_urn_value(version,node):

	if (version < 2):
		return node.getAttribute("sliver_urn")
		pass
	elif(version >= 2):
		return node.getAttribute("sliver_id")
	else:
		sys.exit(1)

	return

# Get Virtual ID attribute value from node based on rspec version
def get_vid_value(version,node):

	if (version < 2):
		return node.getAttribute("virtual_id")
		pass
	elif(version >= 2):
		return node.getAttribute("client_id")
	else:
		sys.exit(1)

	return


# Get Sliver URN attribute value from node based on rspec version
def get_virtualization_type(version,node):
	
	from xml.dom.minidom import Node
	vtype = vsubtype = ""
	if (version < 2 ):
		vtype = node.getAttribute("virtualization_type")
		if (node.hasAttribute("virtualization_subtype")):
			vsubtype = node.getAttribute("virtualization_subtype")
	elif(version >= 2):
		Children = node.childNodes
		for childnode in Children:
			if (childnode.nodeType == Node.ELEMENT_NODE and childnode.nodeName == "sliver_type" and childnode.hasAttribute("name")):
				vsubtype = vtype = childnode.getAttribute("name")
		pass
	else:
		sys.exit(1)
	return vtype,vsubtype

# Form the virtualHostname from the Component URN
def getHostnameFromExt(node,urn,rspec_version):
	
	breaks = urn.split("+")
	if (rspec_version < 2):
		hostname = breaks.pop()
	elif(rspec_version >= 2):
		vnode_ext = node.getElementsByTagName('rs:vnode')
		if not (vnode_ext):
			vnode_ext = node.getElementsByTagName('emulab:vnode')
                if not (vnode_ext):
                    vnode_ext = node.getElementsByTagName('vnode')
		hostname = vnode_ext.item(0).getAttribute('name')
		breaks.pop()
	else:
		hostname = ""
		domain = ""

	domain = breaks.pop(len(breaks)-2) # Second last 

	return hostname+"."+domain

 
# The characters to make up the random password
chars = string.ascii_letters + string.digits
def random_password():
# Create a password of random length between 8 and 16
#   characters long, made up of numbers and letters.
	return "".join(random.choice(chars) for x in range(random.randint(8, 16)))


# Find the list of CM URNs from the rspec dom
# We do this by scanning each <node> tag and look for the 
# "component_manager_urn" attribute. If none is present 
# then the local CM URN is returned
def getCMs_from_rspec(rspec_dom,rspec_version):

	nodes = rspec_dom.getElementsByTagName('node')
	cms_in_rspec = []
	for i in range(0,nodes.length):
		cm_urn = get_cm_urn_value(rspec_version,nodes[i])
		if (cm_urn):
			if (cm_urn not in cms_in_rspec):
				cms_in_rspec.append(cm_urn)
			pass
		else:
			print "Missing Component Manager attribute in\n\n"+nodes[i].toxml()+"\n\n"
			print "Will not proceed\n"
			sys.exit()
		pass
	return cms_in_rspec

# Translate CM URI to generic URI
def get_AM_URI(CM_URI):

	if CM_URI[-2:] == "cm":
		AM_URI = CM_URI[:-3]
	elif CM_URI[-4:] == "cmv2":
		AM_URI = CM_URI[:-5]
	pass

	return AM_URI


# CALL LAMP python script to send MANIFEST
def LAMP_sendmanifest(SLICEURN,manifest,LAMPCERT,SLICECRED_FOR_LAMP,LOGFILE,debug):

	state = TRUE
	cred_file = ""
	manifest_file = ""
	lpcert_file = ""
	old_HTTPS_CERT_FILE = ""
	old_HTTPS_KEY_FILE = ""

	f = tempfile.NamedTemporaryFile()
	manifest_file = f.name
	f.write(manifest)
	f.flush()
	if(LAMPCERT):
		lp = tempfile.NamedTemporaryFile()
		lpcert_file = lp.name
		lp.write(LAMPCERT)
		lp.flush()
	
		#Backup environ variables
		if "HTTPS_CERT_FILE" in os.environ:
			old_HTTPS_CERT_FILE = os.environ["HTTPS_CERT_FILE"]
		if "HTTPS_KEY_FILE" in os.environ:
			old_HTTPS_KEY_FILE = os.environ["HTTPS_KEY_FILE"]
		# LAMP Workaround
		os.environ["HTTPS_CERT_FILE"] = lpcert_file
		os.environ["HTTPS_KEY_FILE"] = lpcert_file
	else:
		cred = tempfile.NamedTemporaryFile()
		cred_file = cred.name
		cred.write(SLICECRED_FOR_LAMP)
		cred.flush()

	msg = ""

	process = subprocess.Popen("./lamp-sendmanifest.py "+manifest_file+" "+SLICEURN+" "+cred_file, shell=True,stdout=subprocess.PIPE,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
	(out,err) = process.communicate()
	process.wait()
	write_to_log(LOGFILE,out+"\n"+err,dontprinttoscreen,debug)
	try:
		check = out.index("data element(s) successfully replaced")
		state = TRUE
		write_to_log(LOGFILE,out,dontprinttoscreen,debug)
		msg = "Sent Manifest to the LAMP CA Successfully\n"
	except ValueError:
		state = FALSE
		msg = ""

	f.close
	if(LAMPCERT):
		lp.close

		# Restore old variables
		if(old_HTTPS_CERT_FILE != ""):
			os.environ["HTTPS_CERT_FILE"] = old_HTTPS_CERT_FILE
		if(old_HTTPS_KEY_FILE != ""):
			os.environ["HTTPS_KEY_FILE"] = old_HTTPS_KEY_FILE
	else:
		cred.close

	return state,msg

def install_Active_measurements(nodes_sliver_urns,GN_sliver_urn,username,USERURN,SLICEURN,LAMPCERT,LOGFILE,keyfile,debug):

	global EXP_NODE_tmppath
	global INSTOOLS_repo_url

	nodes_sliver_urn = nodes_sliver_urns.keys()
	state = TRUE
	# Place LAMP CERT on all nodes regardless in case we need it later
	lpc = tempfile.NamedTemporaryFile()
	cert_file = lpc.name
	lpc.write(LAMPCERT)
	lpc.flush()
	proclist = []
	#sudo install -D -g geniuser -o root -m 440 /tmp/lampcert.pem  /usr/local/etc/protogeni/ssl/

        #Get the GN hostname for the active install scripts
        (GNHOST,hostname_from_urn,port,auth_type,vid)=host_info[GN_sliver_urn].split(" ")

	#Install software on GN Node regardless
	NODE_TYPE = "GN"
	cmd = "cd "+EXP_NODE_tmppath+";sudo rm -rf ACTIVE_SETUP.*;wget "+INSTOOLS_repo_url+"tarballs/ACTIVE_SETUP.tgz;tar xzf ACTIVE_SETUP.tgz;sudo ./ACTIVE_SETUP.sh "+NODE_TYPE+" INSTALL "+SLICEURN+" "+USERURN+" "+GNHOST 
	p = multiprocessing.Process(target=ActiveInstall,args=(host_info[GN_sliver_urn],cmd,cert_file,LOGFILE,debug,keyfile,username,))
	proclist.append(p)
	p.start()                                                                                                                      
	
        # Put the measurement node public key into the other nodes by appending to the authorized keys file     
	for node_sliver_urn in nodes_sliver_urn:
		mygservice = nodes_sliver_urns[node_sliver_urn]
		if (mygservice["active"]["enable"] != 'yes'):
			continue

		NODE_TYPE = "MP"
		cmd = "cd "+EXP_NODE_tmppath+";sudo rm -rf ACTIVE_SETUP.*;wget "+INSTOOLS_repo_url+"tarballs/ACTIVE_SETUP.tgz;tar xzf ACTIVE_SETUP.tgz;sudo ./ACTIVE_SETUP.sh "+NODE_TYPE+" INSTALL "+SLICEURN+" "+USERURN+" "+GNHOST
		#Install software on MP Nodes
	        p = multiprocessing.Process(target=ActiveInstall,args=(host_info[node_sliver_urn],cmd,cert_file,LOGFILE,debug,keyfile,username,))
		proclist.append(p)
		p.start()                                                                                                                      
        
	for i in proclist:
		i.join()

	lpc.close
#	os.remove(cert_file)
	return state

def ActiveInstall(host_info,node_cmd,cert_file,LOGFILE,debug,keyfile,username):

	cert_dest = "/var/emulab/boot/lampcert.pem"
	global EXP_NODE_tmppath
	global ssh
	global scp
	
	(node,hostname_from_urn,port,auth_type,vid) = host_info.split(" ")
	ssh_options = getSSH_options(keyfile,port)

	msg = "Placing the LAMP Cert on Node:\""+vid+"\" to allow it to complete setup"
	write_to_log(LOGFILE,msg,printtoscreen,debug)
	process = subprocess.Popen(scp+ssh_options+" -qr "+cert_file+" "+username+"@"+node+":"+EXP_NODE_tmppath+"/", shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	process.wait()
	write_to_processlog(process, LOGFILE)
	pre_cmd = "sudo mv "+EXP_NODE_tmppath+"/"+os.path.basename(cert_file)+" "+cert_dest+";"
	
	msg = "Running Active Services Install Scripts on Node: \""+vid+"\""
	write_to_log(LOGFILE,msg,printtoscreen,debug)
	
	process = subprocess.Popen(ssh+ssh_options+username+"@"+node+' "'+pre_cmd+node_cmd+' "', shell=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,)
	process.wait()
	write_to_processlog(process, LOGFILE)

	msg = "Active Services Scripts on Node: \""+vid+"\" completed."
	write_to_log(LOGFILE,msg,printtoscreen,debug)


	return
