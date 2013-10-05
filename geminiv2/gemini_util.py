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
import M2Crypto
from urlparse import urlsplit, urlunsplit
import re
import xmlrpclib
import urlparse
import urllib
import urllib2
import httplib
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
import paramiko
#from OpenSSL import SSL
import json
import genproxy         # Import certificate generation routines

UNIS_SCHEMAS = {
    'networkresource': 'http://unis.incntre.iu.edu/schema/20120709/networkresource#',
    'node': 'http://unis.incntre.iu.edu/schema/20120709/node#',
    'domain': 'http://unis.incntre.iu.edu/schema/20120709/domain#',
    'port': 'http://unis.incntre.iu.edu/schema/20120709/port#',
    'link': 'http://unis.incntre.iu.edu/schema/20120709/link#',
    'path': 'http://unis.incntre.iu.edu/schema/20120709/path#',
    'network': 'http://unis.incntre.iu.edu/schema/20120709/network#',
    'topology': 'http://unis.incntre.iu.edu/schema/20120709/topology#',
    'service': 'http://unis.incntre.iu.edu/schema/20120709/service#',
    'blipp': 'http://unis.incntre.iu.edu/schema/20120709/blipp#',
    'metadata': 'http://unis.incntre.iu.edu/schema/20120709/metadata#',
    'datum': 'http://unis.incntre.iu.edu/schema/20120709/datum#',
    'data': 'http://unis.incntre.iu.edu/schema/20120709/data#'
}

#globals 
ssh = 'ssh'
scp = 'scp'
Supported_CM_versions = ['2']
INSTOOLS_LOCK='/var/emulab/lock/INSTOOLS_LOCK'
NOTSUPPORTED_FLAG='/var/emulab/lock/NOTSUPPORTED'
SUPPORTED_FLAG='/var/emulab/lock/SUPPORTED'
measure_scripts_path="/usr/testbed/bin/measure-scripts"
ARCHIVE_CMD_FILE=measure_scripts_path+"/archive_cmd.sh"
version="0.3"
devel_version="0.3"
mc_repo_rooturl="http://gemini.netlab.uky.edu/"
lampca = "https://unis.incntre.iu.edu/protogeni/xmlrpc/lampca"
UNIS_URL = "https://unis.incntre.iu.edu:8443"
INSTOOLS_repo_url = mc_repo_rooturl+"GEMINI/"+version+"/"
EXP_NODE_tmppath = "/tmp"
EXP_TMP_PATH = "/tmp"
debug = 0
DISABLE_ACTIVE = False
ERROR = "ERROR"
printtoscreen=1
dontprinttoscreen=0
SSH_pKey = None
CERT_pKey = None
SLICENAME = None
project = None
cache_expiry = 60 * 10 # 10 minutes
try:
	HOME            = os.environ["HOME"]
	CERTIFICATE     = HOME + "/.ssl/encrypted.pem"
	PASSPHRASEFILE  = HOME + "/.ssl/password"
except KeyError:
	HOME 		= None
	CERTIFICATE     = None
	PASSPHRASEFILE  = None
passphrase = ''
PID = str(os.getpid())
PROXY_CERT      = None
PROXY_KEY       = None
PROXY_ATTR      = None
LOGFILE_HANDLE	= None

BASE_CERT_DIR   = "/usr/local/etc/certs"
GN_PROXY_CERT   = BASE_CERT_DIR+'/gn_cert.pem'
GN_PROXY_KEY    = BASE_CERT_DIR+'/gn_key.pem'
GN_IRODS_CERT   = BASE_CERT_DIR+'/irods-proxy.pem'
GN_UNIS_CERT    = BASE_CERT_DIR+'/unis-proxy.pem'
MP_PROXY_CERT   = BASE_CERT_DIR+'/mp_cert.pem'
MP_PROXY_KEY    = BASE_CERT_DIR+'/mp_key.pem'

## unfortunately OpenSSL.SSL doesn't implement SSL.makefile() needed by httplib.HTTPResponse
## Python 3.3+ is working to fix this and also has password support in ssl.wrap_socket
#class BetterHTTPSConnection(httplib.HTTPSConnection):
#    def connect(self):
#        context = SSL.Context(SSL.SSLv23_METHOD)
#        context.set_passwd_cb(lambda *unused: passphrase)
#        context.use_certificate_file(CERTIFICATE)
#        context.use_privatekey_file(CERTIFICATE)
#        #context.set_verify(SSL.VERIFY_NONE, verify)
#        self.sock = SSL.Connection(context, socket.socket(socket.AF_INET, socket.SOCK_STREAM))
#	 self.sock.connect((self.host, self.port))

def print_timing(func):
    def wrapper(*arg):
        t1 = time.time()
        res = func(*arg)
        t2 = time.time()
        print '%s took %0.3f ms' % (func.func_name, (t2-t1)*1000.0)                                                                    
        return res
    return wrapper

def dots():
	while(1):
		print ('%1s') % ("."),
		time.sleep(5)
	return

def install_keys_plus_shell_in_a_box(GN_Node,MP_Nodes,my_public_key,pKey):

	MC_NODE_keypath = "/tmp"
	LOCAL_tmppath = "/tmp"
	global EXP_NODE_tmppath
	global EXP_TMP_PATH 
	global INSTOOLS_repo_url
	public_key = "/tmp/id_rsa.pub"
	public_key_dest = "/var/emulab/boot/mc_ssh_pubkey"
	rc_startup="/etc/rc.local"
	root_authorized_keys="/root/.ssh/authorized_keys"
	import socket
		
	my_cmurn = GN_Node['cmurn']
	sliver_urn = GN_Node['sliver_id']
	hostname = GN_Node['login_hostname']
	port = GN_Node['login_port']
	username = GN_Node['login_username']
	vid = GN_Node['nodeid']
	if(socket.getfqdn() != "genidesktop.netlab.uky.edu"):
		msg = "Placing your ssh public key for Genidesktop on "+vid
		write_to_log(msg,dontprinttoscreen)
		command = "cd "+EXP_TMP_PATH+";wget -q -P "+EXP_TMP_PATH+" "+INSTOOLS_repo_url+"tarballs/addmypublickey.tgz;tar xzf addmypublickey.tgz;./addmypublickey.sh "+username+' "'+my_public_key+'";'
		(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',command,None,None)
		write_to_processlog(out_ssh,err_ssh)
		if (ret_code != 0):
			msg =  "Problem Initializing the GN Node "+str(vid)+"\n"+str(err_ssh)
			return False,msg
		pass


	GN_cmd ="cd "+EXP_TMP_PATH+";sudo rm -rf /tmp/gdesktop*;wget -q -P "+EXP_TMP_PATH+" "+INSTOOLS_repo_url+"tarballs/GDESKTOP_SETUP.tgz;tar xzf GDESKTOP_SETUP.tgz;sudo ./GDESKTOP_SETUP.sh GN init ;"
	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',GN_cmd,None,None)
	write_to_processlog(out_ssh,err_ssh)
	if (ret_code != 0):
		msg =  "Problem Initializing the GN Node "+str(vid)+"\n"+str(err_ssh)
		return False,msg



	f = tempfile.NamedTemporaryFile(delete=False)
        my_mckeyfile = f.name

	#This get the public key of the measurement node to put on other nodes in your experiement
	msg = "Fetching Global Node "+vid+"'s Public key"
	write_to_log(msg,dontprinttoscreen)

	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'scp_get',None,my_mckeyfile,public_key)
	write_to_processlog(out_ssh,err_ssh)

	proclist = []
	for Node in MP_Nodes:
		my_cmurn = Node['cmurn']
		sliver_urn = Node['sliver_id']
		hostname = Node['login_hostname']
		port = Node['login_port']
		username = Node['login_username']
		vid = Node['nodeid']

		msg = "Placing the Global Node "+GN_Node['nodeid']+"'s public key on Node:\""+vid+"\" to allow it to complete setup"
		write_to_log(msg,dontprinttoscreen)
		(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'scp',None,my_mckeyfile,'/tmp/'+os.path.basename(my_mckeyfile))
		write_to_processlog(out_ssh,err_ssh)
		if(ret_code != 0):
			msg = "SCP to "+hostname+":"+port+" failed "+ err_ssh
			return False,msg

		if(socket.getfqdn() != "genidesktop.netlab.uky.edu"):
			msg = "Placing your ssh public key for Genidesktop on "+vid
			write_to_log(msg,dontprinttoscreen)
			command = "cd "+EXP_TMP_PATH+";wget -q -P "+EXP_TMP_PATH+" "+INSTOOLS_repo_url+"tarballs/addmypublickey.tgz;tar xzf addmypublickey.tgz;./addmypublickey.sh "+username+' "'+my_public_key+'";'
			(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',command,None,None)
			write_to_processlog(out_ssh,err_ssh)
			if (ret_code != 0):
				msg =  "Problem Initializing the MP Node "+str(vid)+"\n"+str(err_ssh)
				return False,msg
		pass


		node_cmd ="sudo mv "+'/tmp/'+os.path.basename(my_mckeyfile)+" "+public_key_dest+";cd /tmp;sudo rm -rf GDESKTOP_SETUP.*;wget "+INSTOOLS_repo_url+"tarballs/GDESKTOP_SETUP.tgz;tar xzf GDESKTOP_SETUP.tgz;sudo ./GDESKTOP_SETUP.sh MP init"
	        p = multiprocessing.Process(target=NodeInstall,args=(Node,node_cmd,'initialization',pKey,))
		proclist.append(p)
		p.start()                                                                                                                      
        
	for i in proclist:
		i.join()


	os.remove(my_mckeyfile)

	#Create the shell ina  box config on the GN
	cmd = 'sudo /usr/bin/perl /usr/testbed/bin/measure-scripts/build_shellinabox_config.pl'
	my_cmurn = GN_Node['cmurn']
	sliver_urn = GN_Node['sliver_id']
	hostname = GN_Node['login_hostname']
	port = GN_Node['login_port']
	username = GN_Node['login_username']
	vid = GN_Node['nodeid']


	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',cmd,None,None)
	write_to_processlog(out_ssh,err_ssh)
	if (ret_code != 0):
		msg =  "Problem generating shell-in-a-box config for the GN Node "+str(vid)+"\n"+str(err_ssh)
		return False,msg

	cmd = 'sudo sh -c "/etc/shellinabox/shellinabox_for_instools.sh > /dev/null 2>&1"'
	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',cmd,None,None)
	write_to_processlog(out_ssh,err_ssh)
	if (ret_code != 0):
		msg =  "Problem starting shell-in-a-box script on the GN Node "+str(vid)+"\n"+str(err_ssh)
		return False,msg

	return True,""

#
# Put user credentials  onto MC and setup ssh keys for communication
# between MC and other node
#
def InstallMP_Passive (MP_Nodes,GN_Node,pKey):

	MC_NODE_keypath = "/tmp"
	LOCAL_tmppath = "/tmp"
	global EXP_NODE_tmppath
	global INSTOOLS_repo_url
	
	mc_ip = socket.gethostbyname(GN_Node['login_hostname'])
	msg = "MC IP = "+mc_ip+"\n"
	write_to_log(msg,dontprinttoscreen)

	node_cmd ="cd /tmp;sudo rm -rf GDESKTOP_SETUP.*;wget "+INSTOOLS_repo_url+"tarballs/GDESKTOP_SETUP.tgz;tar xzf GDESKTOP_SETUP.tgz;sudo ./GDESKTOP_SETUP.sh MP install "+mc_ip
	
	proclist = []
	for Node in MP_Nodes:
		if (Node['gemini_node_services_passive']["enable"] != 'yes'):
			continue
	        p = multiprocessing.Process(target=NodeInstall,args=(Node,node_cmd,'configuration',pKey,))
		proclist.append(p)
		p.start()                                                                                                                      
        
	for i in proclist:
		i.join()

	return


def NodeInstall(Node,node_cmd,action,pKey):

	my_cmurn = Node['cmurn']
	sliver_urn = Node['sliver_id']
	hostname = Node['login_hostname']
	port = Node['login_port']
	username = Node['login_username']
	vid = Node['nodeid']

	msg = "Running "+action+" Scripts on Node: \""+vid+"\""
	write_to_log(msg,printtoscreen)

	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',node_cmd,None,None)
	write_to_processlog(out_ssh,err_ssh)
	if (ret_code != 0):
		msg =  "Problem at "+str(hostname)+"\n"+str(err_ssh)
		return False,msg

	msg = "Node "+action+" Scripts on Node: \""+vid+"\" completed."
	write_to_log(msg,printtoscreen)


#
# Check to see if Node is up and ready
#
def check_if_ready(Node,pKey):

	global ssh
	global INSTOOLS_LOCK
	
	cmd = 'sudo ls '
	filename = INSTOOLS_LOCK

	my_cmurn = Node['cmurn']
	sliver_urn = Node['sliver_id']
	hostname = Node['login_hostname']
	port = Node['login_port']
	username = Node['login_username']
	
	msg = "Checking if Node :\""+vid+"\" is configured and ready"
	write_to_log(msg,dontprinttoscreen)

	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',cmd_filename,None,None)
	write_to_processlog(out_ssh,err_ssh)
	if (ret_code == 0): # Means file exists
		cmd = 'sudo cat '
		(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',cmd+filename,None,None)
		write_to_processlog(out_ssh,err_ssh)
		if(err_ssh):
			return False

		out = out_ssh.strip()
		if (out == "INSTALLATION_COMPLETE"): 
	   		return True
		elif(out == "INSTALLATION_IN_PROGRESS"):
			return False
		else:
			pass
	else:
		return False
	return True

#
# Check for Supported OS
#
def isOSSupported(Node,pKey,isSudoPresent=True):

	global ssh
	global NOTSUPPORTED_FLAG
	global SUPPORTED_FLAG
	global EXP_NODE_tmppath
	global INSTOOLS_repo_url

	hostname = Node['login_hostname']
	port = Node['login_port']
	username = Node['login_username']
	ssh_username = Node['ssh_username']
	vid = Node['nodeid']

	SUDO = 'sudo '
	if(not isSudoPresent):
		SUDO = ''

	msg = "Checking if OS on Node : \""+vid+"\" is supported"
	write_to_log(msg,dontprinttoscreen)

	pre_cmd = SUDO+"rm -rf "+measure_scripts_path+"/INSTALL_DEFS.sh "+EXP_NODE_tmppath+"/INSTALL_DEFS.tgz;"+SUDO+"mkdir -p "+measure_scripts_path+";"+SUDO+"wget -P "+EXP_NODE_tmppath+" "+INSTOOLS_repo_url+"tarballs/INSTALL_DEFS.tgz;"+SUDO+"tar xzf "+EXP_NODE_tmppath+"/INSTALL_DEFS.tgz -C "+measure_scripts_path+";"
	additional_cmd = SUDO+"rm -rf /tmp/version_check.sh;wget -P /tmp "+INSTOOLS_repo_url+"scripts/version_check.sh;chmod +x "+EXP_NODE_tmppath+"/version_check.sh;"+SUDO+" "+EXP_NODE_tmppath+"/version_check.sh "
	cmd = SUDO+'ls '+SUPPORTED_FLAG

	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,ssh_username,pKey,'ssh',pre_cmd+additional_cmd,None,None)
	write_to_processlog(out_ssh,err_ssh)

	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,ssh_username,pKey,'ssh',cmd,None,None)
	write_to_processlog(out_ssh,err_ssh)
   	if(ret_code == 0):
	   return True
	else:
	   return False

	return True

def pruneNodes(Nodes,AM_URN,GN):
	prunedNodes = []
	if(GN == ''):
		for Node in Nodes:
			if (Node['cmurn'] == AM_URN):
				prunedNodes.append(Node)
			else:
				msg = Node['nodeid']+" has been pruned\n"
				write_to_log(msg,dontprinttoscreen)
	else:
		for Node in Nodes:
			if (Node['gemini_urn_to_monitor'] == AM_URN):
				prunedNodes.append(Node)
			else:
				msg = Node['nodeid']+" has been pruned\n"
				write_to_log(msg,dontprinttoscreen)

	return prunedNodes

def isRoot(username):
	if(username == 'root'):
		return True
	else:
		return False

def isSudoPresent(Node,pKey):

	global ssh
	
	hostname = Node['login_hostname']
	port = Node['login_port']
	username = Node['login_username']

	cmd = 'which sudo'	

	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',cmd,None,None,pty=True)
	write_to_processlog(out_ssh,err_ssh)

	if (ret_code != 0):
		return False
	else:
		return True




#
# Check if machine is reachable and then perform OS support version check
# This is usually done before instrumentizing
#
def precheckNodes(GN_Node,MP_Nodes,pKey):

	global ssh
	global EXP_NODE_tmppath
	global INSTOOLS_repo_url
	msg = ""
	
	my_cmurn = GN_Node['cmurn']
	sliver_urn = GN_Node['sliver_id']
	hostname = GN_Node['login_hostname']
	port = GN_Node['login_port']
	username = GN_Node['login_username']
	vid = GN_Node['nodeid']

	use_sudo_gn = isSudoPresent(GN_Node,pKey)

	if(not use_sudo_gn):
		SUDO = ''
		ssh_username = "root"
	else:
		SUDO = 'sudo '
		ssh_username = username
	

	GN_Node['ssh_username'] = ssh_username

	cmd0 = SUDO + "/usr/sbin/usermod -a -G root "+ username+";"
	if(len(GN_Node['additional_users']) > 1):
		for user in GN_Node['additional_users']:
			if(user == username):
				continue
			else:
				cmd0 = cmd0+SUDO + "/usr/sbin/usermod -a -G root "+ user+";"


	cmd1 = SUDO + "rm -rf /etc/sudoers.d/gemini_sudo;"
	cmd2 = SUDO + "wget -P /etc/sudoers.d/ "+INSTOOLS_repo_url+"confs/gemini_sudo ;chmod 0440 /etc/sudoers.d/gemini_sudo;"
	cmd3 = SUDO + "chmod 0440 /etc/sudoers.d/gemini_sudo;"
	cmd4 = SUDO + "sh -c 'echo \"#includedir /etc/sudoers.d\" >>/etc/sudoers'"

	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,ssh_username,pKey,'ssh',cmd0+" "+cmd1+" "+cmd2+" "+cmd3+" "+cmd4,None,None,pty=True)
	write_to_processlog(out_ssh,err_ssh)

#	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',cmd,None,None,pty=True)
#	write_to_processlog(out_ssh,err_ssh)
	if (ret_code != 0):
		msg =  " (Node : "+vid+") "+err_ssh+"\nInstrumentization will terminate. Please make sure your experiment is running"
		return False,msg
	if (not isOSSupported(GN_Node,pKey,use_sudo_gn)):
		msg = "The Operating System on the Node \""+vid+"\" is not compatible with GEMINI"
		set_unset_LOCK(GN_Node,"OS_NOT_SUPPORTED on "+vid+"/"+hostname+":"+port,pKey)
		return False,msg
	msg = "Node : \""+vid+"\" passed pre-check test"
	write_to_log(msg,printtoscreen)


	Node = {}
	for Node in MP_Nodes:
		hostname = Node['login_hostname']
		port = Node['login_port']
		username = Node['login_username']
		vid = Node['nodeid']

		use_sudo = isSudoPresent(Node,pKey)

		if(not use_sudo):
			SUDO = ''
			ssh_username = "root"
		else:
			SUDO = 'sudo '
			ssh_username = username
		Node['ssh_username'] = ssh_username
		cmd0 = SUDO + "/usr/sbin/usermod -a -G root "+ username+";"
		if(len(Node['additional_users']) > 1):
			for user in Node['additional_users']:
				if(user == username):
					continue
				else:
					cmd0 = cmd0+SUDO + "/usr/sbin/usermod -a -G root "+ user+";"

		cmd1 = SUDO + "rm -rf /etc/sudoers.d/gemini_sudo;"
		cmd2 = SUDO + "wget -P /etc/sudoers.d/ "+INSTOOLS_repo_url+"confs/gemini_sudo ;"
		cmd3 = SUDO + "chmod 0440 /etc/sudoers.d/gemini_sudo;"
		cmd4 = SUDO + "sh -c 'echo \"#includedir /etc/sudoers.d\" >>/etc/sudoers'"

		(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,ssh_username,pKey,'ssh',cmd0+" "+cmd1+" "+cmd2+" "+cmd3+" "+cmd4,None,None,pty=True)
		write_to_processlog(out_ssh,err_ssh)


	#	pre_cmd ="rm -rf "+EXP_NODE_tmppath+"/sudoers.tgz;wget -P "+EXP_NODE_tmppath+" "+INSTOOLS_repo_url+"tarballs/sudoers.tgz;";
	#	cmd = SUDO+"tar xzf "+EXP_NODE_tmppath+"/sudoers.tgz -C /"

	#	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',pre_cmd,None,None,pty=True)
	#	write_to_processlog(out_ssh,err_ssh)

	#	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',cmd,None,None,pty=True)
	#	write_to_processlog(out_ssh,err_ssh)
		if (ret_code != 0):
			msg =  hostname+" at port "+port+" (Node : "+vid+") is not responding\nInstrumentization will terminate. Please make sure your experiment is running"+"\n"+err_ssh
			return False,msg

		if (not isOSSupported(Node,pKey,use_sudo)):
			msg = "The Operating System on the Node \""+vid+"\" is not compatible with GEMINI"
			set_unset_LOCK(GN_Node,"OS_NOT_SUPPORTED on "+vid+"/"+hostname+":"+port,pKey)
			return False,msg
		msg = "Node : \""+vid+"\" passed pre-check test"
		write_to_log(msg,printtoscreen)

	detailedProbeComplete(GN_Node,pKey,use_sudo_gn)	
	return True,msg

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

def InstallGN_Passive(GN_Node,pKey):

	my_cmurn = GN_Node['cmurn']
	sliver_urn = GN_Node['sliver_id']
	hostname = GN_Node['login_hostname']
	port = GN_Node['login_port']
	username = GN_Node['login_username']
	vid = GN_Node['nodeid']

	cmd ="cd /tmp/;sudo rm -rf /tmp/GDESKTOP_SETUP.* /tmp/gdesktop-*;wget "+INSTOOLS_repo_url+"tarballs/GDESKTOP_SETUP.tgz;tar xzf /tmp/GDESKTOP_SETUP.tgz;nohup sudo /tmp/GDESKTOP_SETUP.sh GN install &"

#	msg = "Starting the Global Node Software Intallation..."
#	write_to_log(msg,printtoscreen)
	post_cmd = "sudo touch /var/emulab/boot/isGemini;"
	
	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh_GN',cmd,None,None)
	write_to_processlog(out_ssh,err_ssh)
	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',post_cmd,None,None)
	write_to_processlog(out_ssh,err_ssh)
	return


#
# start data collection routines 
#
def startStatscollection(GN_Node,pKey):

	my_cmurn = GN_Node['cmurn']
	sliver_urn = GN_Node['sliver_id']
	hostname = GN_Node['login_hostname']
	port = GN_Node['login_port']
	username = GN_Node['login_username']
	vid = GN_Node['nodeid']
	
	cmd = 'sudo '+measure_scripts_path+'/initiate_stat_collection_without_credentials.sh' 
	msg = "Starting the Data collection routines on the Global Node "+vid
	write_to_log(msg,dontprinttoscreen)
	
	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',cmd,None,None)
	write_to_processlog(out_ssh,err_ssh)
	if(ret_code != 0):
		msg = "Problem initiating Stat collections on the GN Node "+vid
		return False,msg


	return True,''

#
# PLace exp data on GN 
#
def dump_Expinfo_on_GN(GN_Node,userurn,email,instools_password,sliceurn,cmurn,dpadmin_username,dpadmin_passwd,slice_crypt,pKey):

	my_cmurn = GN_Node['cmurn']
	sliver_urn = GN_Node['sliver_id']
	hostname = GN_Node['login_hostname']
	port = GN_Node['login_port']
	username = GN_Node['login_username']
	vid = GN_Node['nodeid']
	additional_users = ''
	if(len(GN_Node['additional_users']) > 1):
		for user in GN_Node['additional_users']:
			if(user == username):
				continue
			additional_users = additional_users+','+user
	additional_users = additional_users.lstrip(',')
	pre_cmd ="sudo rm -rf "+measure_scripts_path+"/save_info.sh "+EXP_NODE_tmppath+"/save_info*;sudo wget -P "+EXP_NODE_tmppath+" "+INSTOOLS_repo_url+"tarballs/save_info.tgz;sudo tar xzf "+EXP_NODE_tmppath+"/save_info.tgz -C "+measure_scripts_path+";"
	cmd = 'sudo '+measure_scripts_path+'/save_info.sh '+userurn+' '+email+' '+cmurn+' '+sliceurn+' '+dpadmin_username+' '+dpadmin_passwd+' '+slice_crypt+' '+instools_password+' '+hostname+' '+additional_users
	msg = "Saving Exp info on the Global Node "+vid
	write_to_log(msg,dontprinttoscreen)
	if(sliceurn != ''):
		(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',pre_cmd,None,None)
		write_to_processlog(out_ssh,err_ssh)
	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',cmd,None,None)
	write_to_processlog(out_ssh,err_ssh)
	if (ret_code == 0):
	   return True,""
   	else:
	   return False,"Error send Exp Data to GN "+vid

#
# Initialize Drupal menus for this topology
#
def initialize_Drupal_menu(GN_Node,pKey):


	my_cmurn = GN_Node['cmurn']
	sliver_urn = GN_Node['sliver_id']
	hostname = GN_Node['login_hostname']
	port = GN_Node['login_port']
	username = GN_Node['login_username']
	vid = GN_Node['nodeid']

	cmd = 'sudo '+measure_scripts_path+'/initialize_drupal.sh menu'
	msg = "Initializing Drupal Menu creation for Global Node "+vid
	write_to_log(msg,printtoscreen)
	
	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',cmd,None,None)
	write_to_processlog(out_ssh,err_ssh)
	return

#
# Create md5 crypt from user input passwd
#
def generate_crypt_passwd(passwd):

	seq = ('./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz')
	salt = ""
	for k in range (0, 2):
		salt  += random.choice(seq)
		pass
	mycrypt =  crypt.crypt(passwd,salt)
	return mycrypt

def getLockStatus(Node,pKey):

	global ssh
	global EXP_NODE_tmppath
	global INSTOOLS_LOCK
	global passphrase

	my_cmurn = Node['cmurn']
	sliver_urn = Node['sliver_id']
	hostname = Node['login_hostname']
	port = Node['login_port']
	username = Node['login_username']
	vid = Node['nodeid']
	sendcmd = 'cat '+INSTOOLS_LOCK+';'

	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',sendcmd,None,None)
	return out_ssh.rstrip(),ret_code,err_ssh
	

#
# Lock/unlock MC during setup
#
def lock_unlock_MC(GN_Node,what_to_do,pKey):

	global EXP_NODE_tmppath
	global INSTOOLS_LOCK
	msg = ""
	while(1):
		(lockstatus,ret_code,error_msg) = getLockStatus(GN_Node,pKey)
		if(ret_code == -1 ):
			return False,error_msg
		if(lockstatus != "" and  what_to_do == "init_lock"):
			msg = "GeniDesktop at "+GN_Node['nodeid']+" has a status of "+lockstatus+"..\nCannot start another instance"
			return False,msg
		elif(lockstatus == "INITIALIZATION_IN_PROGRESS" and what_to_do == "init_lock"):
			msg = "GeniDesktop Initialization at "+GN_Node['nodeid']+" in progress..\nCannot start another instance"
			return False,msg
		elif(lockstatus == "INITIALIZATION_COMPLETE"):
			if(what_to_do == "init_lock" ):
				msg = "GeniDesktop Initialization at "+GN_Node['nodeid']+" was previously completed..\nCannot start another instance"
				return False,msg
			elif(what_to_do == "install_lock"):
				msg = "Global Node Software Installation starting for "+GN_Node['nodeid']+"..."
				write_to_log(msg,printtoscreen)
				InstallGN_Passive(GN_Node,pKey)
				time.sleep(15)
				continue
			elif(what_to_do == "instrument_lock"):
				msg = "Cannot be in this state (instrument_lock before install_lock) ..\n"
				return False,msg
		elif(lockstatus == "INSTALLATION_COMPLETE"):
			if(what_to_do == "init_lock" ):
				msg = "Invalid operation Error..\n"
				return False,msg
			elif(what_to_do == "instrument_lock"):
				(result,msg) = set_unset_LOCK(GN_Node,'INSTRUMENTIZE_IN_PROGRESS',pKey)
				if(result):
					msg = "Gemini Configuration setup is starting for "+GN_Node['nodeid']+"..."
					return True,msg
				else:
					return False,msg
			elif(what_to_do == "install_lock"):
				return True,msg
		elif(lockstatus == "INSTALLATION_IN_PROGRESS" and what_to_do == 'install_lock'):
			msg = "Global Node "+GN_Node['nodeid']+" software Installation for passive measurements is in progress\nWill check again in 15 seconds...."
			write_to_log(msg,printtoscreen)
			time.sleep(15)
			continue
		elif(lockstatus == "INSTRUMENTIZE_IN_PROGRESS" and what_to_do == "instrument_unlock"):
			#set unlock Flag here
			(result,msg) = set_unset_LOCK(GN_Node,'INSTRUMENTIZE_COMPLETE',pKey)
			if(result):
				msg = "Gemini Configuration setup for "+GN_Node['nodeid']+" is complete.."
				return True,msg
			else:
				return False,msg
		elif(lockstatus == "INSTRUMENTIZE_COMPLETE"):
			msg = "Gemini Configuration setup for "+GN_Node['nodeid']+" is already complete..\nWill not proceed for this AM"
			return False,msg
		elif(lockstatus == "" and what_to_do == "init_lock" ):
			msg = "GeniDesktop Initialization for "+GN_Node['nodeid']+" is safe to start"
			return True,msg
		elif(lockstatus.find('IN_PROGRESS') != -1 and  what_to_do.find("lock") != -1):
			msg = "GeniDesktop has some process in progress at "+GN_Node['nodeid']+"..\nCannot start another instance"
			return False,msg
		else:
			msg = 'Your slice has not been initialized.\nCannot proceed without initialization first'
			return False,msg

	return True,msg


def set_unset_LOCK(Node,flag,pKey):
	my_cmurn = Node['cmurn']
	sliver_urn = Node['sliver_id']
	hostname = Node['login_hostname']
	port = Node['login_port']
	username = Node['login_username']
	vid = Node['nodeid']
	f = tempfile.NamedTemporaryFile()
	adata = f.name
	f.write(flag)
	f.flush()

	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'scp',None,adata,'/tmp/'+os.path.basename(adata))
	write_to_processlog(out_ssh,err_ssh)
	if(ret_code != 0):
		f.close()
		msg = "Unable to set flag "+flag+" on "+hostname+" "+err_ssh
		return False,msg
	f.close()
	
	sendcmd = 'sudo mv '+'/tmp/'+os.path.basename(adata)+' '+INSTOOLS_LOCK+';'
	
	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',sendcmd,None,None)
	write_to_processlog(out_ssh,err_ssh)
	if(ret_code != 0):
		f.close()
		msg = "Unable to set flag "+flag+" on "+hostname+" "+err_ssh
		return False,msg

	return True,''

#
# Initialize/Start/Stop Netflow data collection 
#
def do_netflow_stuff(GN_Node,action,pKey):

	my_cmurn = GN_Node['cmurn']
	sliver_urn = GN_Node['sliver_id']
	hostname = GN_Node['login_hostname']
	port = GN_Node['login_port']
	username = GN_Node['login_username']
	vid = GN_Node['nodeid']

	
	cmd = '/usr/bin/perl /usr/testbed/bin/netflow-scripts/geni_netflow.pl'
	
	msg = action+" Netflow Setup for Global Node "+vid
	write_to_log(msg,dontprinttoscreen)

	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',cmd+" "+action,None,None)
	write_to_processlog(out_ssh,err_ssh)
	
	return

#
# Call php script on MC to create the drupal account
#
def	drupal_account_create(GN_Node,pKey):
		
	global INSTOOLS_repo_url

	my_cmurn = GN_Node['cmurn']
	sliver_urn = GN_Node['sliver_id']
	hostname = GN_Node['login_hostname']
	port = GN_Node['login_port']
	username = GN_Node['login_username']
	vid = GN_Node['nodeid']

	pre_cmd = 'sudo wget -P /var/www/html/drupal "'+INSTOOLS_repo_url+'scripts/createUser.php.txt";sudo mv /var/www/html/drupal/createUser.php.txt /var/www/html/drupal/createUser.php ;sudo chmod +x /var/www/html/drupal/createUser.php;sudo chgrp nobody /var/www/html/drupal/createUser.php;'
	cmd = 'sudo '+measure_scripts_path+'/initialize_drupal.sh account;'
	post_cmd = 'sudo rm -rf /var/www/html/drupal/createUser.php;'

	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',pre_cmd+cmd+post_cmd,None,None)
	write_to_processlog(out_ssh,err_ssh)
	return


#
# Update the drupal Admin info
#
def	update_Drupaladmin_acctinfo(GN_Node,pKey):
		

	my_cmurn = GN_Node['cmurn']
	sliver_urn = GN_Node['sliver_id']
	hostname = GN_Node['login_hostname']
	port = GN_Node['login_port']
	username = GN_Node['login_username']
	vid = GN_Node['nodeid']
	
	cmd = 'sudo '+measure_scripts_path+'/change_drupal_accinfo.sh;'

	msg = "Updating the drupal Admin account info on "+vid
	write_to_log(msg,printtoscreen)
	
	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',cmd,None,None)
	write_to_processlog(out_ssh,err_ssh)
	if(ret_code !=0 ):
		return False,err_ssh
	else:
		return True,''


	
#
# Create VNC password on MC and  copy the same to Experimental machines
#
def	vnc_passwd_create(MP_Nodes,GN_Node,pKey):
	
	node_list = ""
	for Node in MP_Nodes:
		if (Node['gemini_node_services_passive']["enable"] != 'yes'):
			continue
		node_list = node_list+" "+Node['hostname']

	my_cmurn = GN_Node['cmurn']
	sliver_urn = GN_Node['sliver_id']
	hostname = GN_Node['login_hostname']
	port = GN_Node['login_port']
	username = GN_Node['login_username']
	vid = GN_Node['nodeid']

	mc_cmd = 'sudo '+measure_scripts_path+'/configure_vnc.sh "'+node_list+'";'

	msg = "Setting up VNC Passwd file on Global Node "+vid
	write_to_log(msg,dontprinttoscreen)
	
	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',mc_cmd,None,None)
	write_to_processlog(out_ssh,err_ssh)
	return

#
# Grab STDOUT and STDERR  and write it to MC Log
#
def write_to_processlog(out,err):
	global LOGFILE_HANDLE

	log_date = time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(time.time()))
	if out != "":
		LOGFILE_HANDLE.write(log_date+" :\n******** STDOUT ************* \n"+out+"*****************************\n")
	if err != "":
		LOGFILE_HANDLE.write(log_date+" :\n******** STDERR ************* \n"+err+"*****************************\n")
	return


def write_to_log(message,print_also):

	global LOGFILE_HANDLE
	global debug

	if (print_also or debug):
		print message+"\n"
	log_date = time.strftime("%Y-%m-%d %H:%M:%S",time.localtime(time.time()))
	LOGFILE_HANDLE.write(log_date +" :\t"+ message+"\n")

	return

# Check if directory exists and create it if it does not
def ensure_dir(f):
	d = os.path.dirname(f)
	if not os.path.exists(d):
		os.makedirs(d)

def openLogPIPE(LOGFILE):

	global LOGFILE_HANDLE
	LOGFILE_HANDLE = open(LOGFILE, 'a')

	return

def closeLogPIPE(LOGFILE):

	global LOGFILE_HANDLE
	LOGFILE_HANDLE.close()

	return

# The characters to make up the random password
chars = string.ascii_letters + string.digits
def random_password():
# Create a password of random length between 8 and 16
#   characters long, made up of numbers and letters.
	return "".join(random.choice(chars) for x in range(random.randint(8, 16)))


# CALL LAMP python script to send MANIFEST
def LAMP_sendmanifest(SLICEURN,manifest,LAMPCERT,SLICECRED_FOR_LAMP):

	state = True
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
	else:
		cred = tempfile.NamedTemporaryFile()
		cred_file = cred.name
		cred.write(SLICECRED_FOR_LAMP)
		cred.flush()

	msg = ""

	process = subprocess.Popen(os.path.dirname(__file__)+"/lamp-sendmanifest.py "+manifest_file+" "+SLICEURN+" "+lpcert_file+" "+cred_file, shell=True,stdout=subprocess.PIPE,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
	(out,err) = process.communicate()
	process.wait()
	write_to_processlog(out,err)
	try:
		check = out.index("data element(s) successfully replaced")
		state = True
		msg = "Sent Manifest to the LAMP UNIS Successfully"
		write_to_log(msg,printtoscreen)
	except ValueError:
		state = False
		msg = ""

	f.close
	if(LAMPCERT):
		lp.close
	else:
		cred.close
	return state,msg

def install_Active_measurements(MP_Nodes,GN_Node,USERURN,SLICEURN,SLICEUUID,UNISTopo,LAMPCERT,pKey):

	global EXP_NODE_tmppath
	global INSTOOLS_repo_url

	state = True

	if (DISABLE_ACTIVE):
		msg = "Will not enable Active Services due to UNIS Failure"
		write_to_log(msg,printtoscreen)
		return state
	# Place LAMP CERT on all nodes regardless in case we need it later
	lpc = tempfile.NamedTemporaryFile()
	cert_file = lpc.name
	lpc.write(LAMPCERT)
	lpc.flush()
	proclist = []
	#sudo install -D -g geniuser -o root -m 440 /tmp/lampcert.pem  /usr/local/etc/protogeni/ssl/

	GNHOST = GN_Node['hostname']
	UNIS_ID = findUNISNodeID(UNISTopo,GN_Node)
	if UNIS_ID is None:
		msg = "Could not find matching UNIS node for %s" % GN_Node["hostname"]
		write_to_log(msg,printtoscreen)

	#Install software on GN Node regardless
	NODE_TYPE = "GN"
	cmd = "cd "+EXP_NODE_tmppath+";sudo rm -rf ACTIVE_SETUP.*;wget "+INSTOOLS_repo_url+"tarballs/ACTIVE_SETUP.tgz;tar xzf ACTIVE_SETUP.tgz;sudo ./ACTIVE_SETUP.sh "+NODE_TYPE+" INSTALL "+SLICEURN+" "+USERURN+" "+GNHOST+" "+SLICEUUID+" "+str(UNIS_ID)
	p = multiprocessing.Process(target=ActiveInstall,args=(GN_Node,cmd,cert_file,pKey,))
	proclist.append(p)
	p.start()                                                                                                                      
	
        # Put the measurement node public key into the other nodes by appending to the authorized keys file     
	for Node in MP_Nodes:
		if (Node['gemini_node_services_active']["enable"] != 'yes'):
			continue

		NODE_TYPE = "MP"
		UNIS_ID = findUNISNodeID(UNISTopo,Node)
		if UNIS_ID is None:
			msg = "Could not find matching UNIS node for %s" % Node["hostname"]
			write_to_log(msg,printtoscreen)

		cmd = "cd "+EXP_NODE_tmppath+";sudo rm -rf ACTIVE_SETUP.*;wget "+INSTOOLS_repo_url+"tarballs/ACTIVE_SETUP.tgz;tar xzf ACTIVE_SETUP.tgz;sudo ./ACTIVE_SETUP.sh "+NODE_TYPE+" INSTALL "+SLICEURN+" "+USERURN+" "+GNHOST+" "+SLICEUUID+" "+str(UNIS_ID)
		#Install software on MP Nodes
	        p = multiprocessing.Process(target=ActiveInstall,args=(Node,cmd,cert_file,pKey,))
		proclist.append(p)
		p.start()
        
	for i in proclist:
		i.join()

	lpc.close
	return state

def installLAMPCert(Node,pKey,cert_file,add_cmd):

	cert_dest = "/var/emulab/boot/lampcert.pem"	
	lamp_dest = "/usr/local/etc/protogeni/ssl"

	hostname = Node['login_hostname']
	port = Node['login_port']
	username = Node['login_username']
	vid = Node['nodeid']

	msg = "Placing the LAMP Cert on Node:\""+vid+"\""
	write_to_log(msg,printtoscreen)

	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'scp',None,cert_file,'/tmp/'+os.path.basename(cert_file))
	write_to_processlog(out_ssh,err_ssh)

	node_cmd = "sudo mv "+EXP_NODE_tmppath+"/"+os.path.basename(cert_file)+" "+cert_dest+";"

	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',node_cmd+add_cmd,None,None)
	write_to_processlog(out_ssh,err_ssh)
	
	return

def ActiveInstall(Node,node_cmd,cert_file,pKey):
	global EXP_NODE_tmppath

	my_cmurn = Node['cmurn']
	sliver_urn = Node['sliver_id']
	hostname = Node['login_hostname']
	port = Node['login_port']
	username = Node['login_username']
	vid = Node['nodeid']

	msg = "Placing the LAMP Cert on Node:\""+vid+"\" to allow it to complete setup"
	write_to_log(msg,printtoscreen)

	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'scp',None,cert_file,'/tmp/'+os.path.basename(cert_file))
	write_to_processlog(out_ssh,err_ssh)
	installLAMPCert(Node,pKey,cert_file,"")

	msg = "Running Active Services Install Scripts on Node: \""+vid+"\""
	write_to_log(msg,printtoscreen)
	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',node_cmd,None,None)
	write_to_processlog(out_ssh,err_ssh)

	msg = "Active Services Scripts on Node: \""+vid+"\" completed."
	write_to_log(msg,printtoscreen)

	return

def makeInstrumentizeProxy(lifetime,auth_uuid):
	global passphrase
	global PROXY_CERT
	global PROXY_KEY
	global PROXY_ATTR
	PROXY_CERT = tempfile.NamedTemporaryFile(delete=False).name
	PROXY_KEY = tempfile.NamedTemporaryFile(delete=False).name
	PROXY_ATTR = tempfile.NamedTemporaryFile(delete=False).name

	role = "slice_admin_for_%s" % auth_uuid.replace("-", "")

	genproxy.make_proxy_cert(CERTIFICATE,CERTIFICATE,PROXY_CERT,PROXY_KEY,"instrumentize",lifetime,passphrase)
	(result, msg) = genproxy.make_attribute_cert(CERTIFICATE,CERTIFICATE,PROXY_CERT,role,PROXY_ATTR,passphrase)
	if not result:
		PROXY_ATTR = None
		write_to_log(msg,printtoscreen)
		
	return result

def generate_all_proxycerts(lifetime,auth_uuid):

	global passphrase

	#Irods Proxy cert generation
	f1 = tempfile.NamedTemporaryFile(delete=False)
	f2 = tempfile.NamedTemporaryFile(delete=False)
        irods_proxycert_file = f1.name
        irods_proxykey_file = f2.name

	write_to_log("Generating proxy certificate for Irods service",printtoscreen)
	genproxy.make_proxy_cert(CERTIFICATE,CERTIFICATE,irods_proxycert_file,irods_proxykey_file,"",lifetime,passphrase)
	f2.seek(0)
	f1.seek(0,2)
	f1.write("\n"+f2.read())
	f1.flush()

	os.remove(irods_proxykey_file)

	#GN Proxy Cert generation for Active services
	f3 = tempfile.NamedTemporaryFile(delete=False)
	f4 = tempfile.NamedTemporaryFile(delete=False)
	f5 = tempfile.NamedTemporaryFile(delete=False)
        gn_ms_proxycert_file = f3.name
        gn_ms_proxykey_file = f4.name
        gn_ms_proxyder_file = f5.name

	role = "slice_admin_for_%s" % auth_uuid.replace("-", "")
	write_to_log("Generating proxy certificates for GN_MS",printtoscreen)
	genproxy.make_proxy_cert(CERTIFICATE,CERTIFICATE,gn_ms_proxycert_file,gn_ms_proxykey_file, "GN-MS",lifetime,passphrase)
	genproxy.make_attribute_cert(CERTIFICATE,CERTIFICATE,gn_ms_proxycert_file,role,gn_ms_proxyder_file,passphrase)
	# send attribute certs to UNIS
	f = open(gn_ms_proxyder_file)
	postDataToUNIS(gn_ms_proxykey_file,gn_ms_proxycert_file,"/credentials/geniuser",f)
	f.close()
	os.remove(gn_ms_proxyder_file)


	#MP Proxy Cert generation for Active services
	f6 = tempfile.NamedTemporaryFile(delete=False)
	f7 = tempfile.NamedTemporaryFile(delete=False)
	f8 = tempfile.NamedTemporaryFile(delete=False)
        mp_blipp_proxycert_file = f6.name
        mp_blipp_proxykey_file = f7.name
        mp_blipp_proxyder_file = f8.name

	role = "slice_admin_for_%s" % auth_uuid.replace("-","")
	write_to_log("Generating proxy certificates for MP Blipp",printtoscreen)
	genproxy.make_proxy_cert(CERTIFICATE,CERTIFICATE,mp_blipp_proxycert_file,mp_blipp_proxykey_file, "blipp",lifetime,passphrase)
	genproxy.make_attribute_cert(CERTIFICATE,CERTIFICATE,mp_blipp_proxycert_file,role,mp_blipp_proxyder_file,passphrase)
	# send attribute certs to UNIS
	f = open(mp_blipp_proxyder_file)
	postDataToUNIS(mp_blipp_proxykey_file,mp_blipp_proxycert_file,"/credentials/geniuser",f)
	f.close()
	os.remove(mp_blipp_proxyder_file)

	return (gn_ms_proxycert_file,gn_ms_proxykey_file,mp_blipp_proxycert_file,mp_blipp_proxykey_file,irods_proxycert_file)

def delete_all_temp_proxyfiles(files):

	for file_name in files:
		msg = "Deleteing "+file_name
		write_to_log(msg,dontprinttoscreen)
		os.remove(file_name)
	return True

def install_irods_Certs(GN_Nodes,pKey,proxycert_file):

	for node in GN_Nodes:
		hostname = node['login_hostname']
		port = node['login_port']
		username = node['login_username']
		vid = node['nodeid']

		write_to_log("Installing Irods proxy certificate on "+vid,printtoscreen)

		(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'scp',None,proxycert_file,'/tmp/'+os.path.basename(proxycert_file))
		write_to_processlog(out_ssh,err_ssh)
	
		cmd = 'sudo install -D /tmp/'+os.path.basename(proxycert_file)+' '+GN_IRODS_CERT+' -o root -g root -m 600;'
		(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',cmd,None,None)
		write_to_processlog(out_ssh,err_ssh)
	pass


def install_GN_Certs(GN_Nodes,pKey,gn_ms_proxycert_file,gn_ms_proxykey_file):

	for node in GN_Nodes:
		hostname = node['login_hostname']
		port = node['login_port']
		username = node['login_username']
		vid = node['nodeid']
		
		write_to_log("Installing GN_MS proxy certificate on "+vid,printtoscreen)

		# scp these via sshConnection...
		(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'scp',None,gn_ms_proxycert_file,'/tmp/'+os.path.basename(gn_ms_proxycert_file))
		write_to_processlog(out_ssh,err_ssh)

		(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'scp',None,gn_ms_proxykey_file,'/tmp/'+os.path.basename(gn_ms_proxykey_file))
		write_to_processlog(out_ssh,err_ssh)

		cmd = 'sudo install -D /tmp/'+os.path.basename(gn_ms_proxycert_file)+' '+GN_PROXY_CERT+' -o root -g root -m 600;sudo install -D /tmp/'+os.path.basename(gn_ms_proxykey_file)+' '+GN_PROXY_KEY+' -o root -g root -m 600;sudo cat '+GN_PROXY_CERT+'>/tmp/unis-proxy.pem;sudo echo "">>/tmp/unis-proxy.pem;sudo cat '+GN_PROXY_KEY+'>>/tmp/unis-proxy.pem;sudo install -D /tmp/unis-proxy.pem '+GN_UNIS_CERT+' -o nobody -g nobody -m 750;sudo chmod 755 '+BASE_CERT_DIR+';'

		(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',cmd,None,None)
		write_to_processlog(out_ssh,err_ssh)

	pass

def install_MP_Certs(MP_Nodes,pKey,mp_blipp_proxycert_file,mp_blipp_proxykey_file):

        for node in MP_Nodes:
		hostname = node['login_hostname']
		port = node['login_port']
		username = node['login_username']
		vid = node['nodeid']

		write_to_log("Installing MP_Blipp proxy certificate on "+vid,printtoscreen)
	
		# scp these via sshConnection...
		(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'scp',None,mp_blipp_proxycert_file,'/tmp/'+os.path.basename(mp_blipp_proxycert_file))
		write_to_processlog(out_ssh,err_ssh)

		(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'scp',None,mp_blipp_proxykey_file,'/tmp/'+os.path.basename(mp_blipp_proxykey_file))
		write_to_processlog(out_ssh,err_ssh)

		cmd = 'sudo install -D /tmp/'+os.path.basename(mp_blipp_proxycert_file)+' '+MP_PROXY_CERT+' -o root -g root -m 600;sudo install -D /tmp/'+os.path.basename(mp_blipp_proxykey_file)+' '+MP_PROXY_KEY+' -o root -g root -m 600;'
		(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',cmd,None,None)
		write_to_processlog(out_ssh,err_ssh)

	pass

def createBlippServiceEntries(MP_Nodes,GN_Node,UNISTopo,slice_uuid):
	service_desc = dict()
	service_desc.update({"$schema": UNIS_SCHEMAS["service"]})
	service_desc.update({"serviceType": "ps:tools:blipp"})
	service_desc.update({"description": "BLiPP Service"})
	service_desc.update({"name": "blipp"})
	service_desc.update({"properties": {"geni": {"slice_uuid": slice_uuid},
					    "configurations": 
					    {"probe_defaults": {"ms_url": "https://"+GN_Node["hostname"]+":8888"},
					     "use_ssl": True,
					     "ssl_cert": MP_PROXY_CERT,
					     "ssl_key": MP_PROXY_KEY,
					     "ssl_cafile": ""
					     }}})
	
	for node in MP_Nodes:
		UNIS_ID = findUNISNodeID(UNISTopo,node)
		if UNIS_ID is None:
			msg = "Could not find matching UNIS node for %s" % node["hostname"]
			write_to_log(msg,printtoscreen)
			continue

		post_desc = service_desc
		post_desc.update({"runningOn": {"href": UNIS_URL+"/nodes/"+UNIS_ID,
						"rel": "full"}})
		post_str = json.dumps(post_desc)
		postDataToUNIS(PROXY_KEY,PROXY_CERT,"/services",post_str)

def findUNISNodeID(UNISTopo,parserNode):
	if not UNISTopo:
		return None
	
	unode = None
	for n in UNISTopo["nodes"]:
		if n["name"] == parserNode["nodeid"]:
			unode = n
			break

	if unode is not None:
		return unode["id"]
	else:
		return None

def getUnencryptedKeyfile(cert_pKey):

	TKF = tempfile.NamedTemporaryFile(delete=False)
	cert_pKey.write_private_key_file(TKF.name)
#	cmd_rsa = "openssl rsa -passin stdin -in %s -out %s" % (CERTIFICATE, TKF.name)
#	process = subprocess.Popen(cmd_rsa, shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
#	(out, err) = process.communicate(input=passphrase)
	TKF.close()
	return TKF.name

def getUNISTopo(key,cert,endpoint):
	url = UNIS_URL
	o = urlparse.urlparse(url)
	topo = None

	try:
		conn = httplib.HTTPSConnection(o.hostname, o.port, key, cert)
		conn.request("GET", endpoint)
		r = conn.getresponse()
		data = r.read()
	
		if r.status is not 200:
			write_to_log("GET from UNIS at "+url,printtoscreen)
			write_to_log(data,printtoscreen)
			return None
	
		topo = json.loads(data)
	
		if "links" in topo:
			larray = []
			for l in topo["links"]:
				o = urlparse.urlparse(l["href"])
				conn.request("GET", o.path+"?limit=1", None)
				r = conn.getresponse()
				data = r.read()
				link = json.loads(data)
				larray.append(link)
				topo["links"] = larray
			
		if "nodes" in topo:
			narray = []
			for n in topo["nodes"]:
				o = urlparse.urlparse(n["href"])
				conn.request("GET", o.path+"?limit=1", None)
				r = conn.getresponse()
				data = r.read()
				node = json.loads(data)
				narray.append(node)
				topo["nodes"] = narray

		if "ports" in topo:
			parray = []
			for p in topo["ports"]:
				o = urlparse.urlparse(p["href"])
				conn.request("GET", o.path+"?limit=1", None)
				r = conn.getresponse()
				data = r.read()
				port = json.loads(data)
				parray.append(port)
				topo["ports"] = parray	
				
	except Exception as e:
		msg = "Could not get UNIS topology: %s" % e
		write_to_log(msg,printtoscreen)
			
	return topo
	
#POST some data to specified UNIS endpoints
def postDataToUNIS(key,cert,endpoint,data):
	url = UNIS_URL+endpoint
	o = urlparse.urlparse(url)

	try:
		conn = httplib.HTTPSConnection(o.hostname, o.port, key, cert)
		conn.request("POST", o.path, data)
	except Exception as e:
		msg = "Could not connect to UNIS: %s" % e
		write_to_log(msg,printtoscreen)
		return None
	try:
		r = conn.getresponse()
	except Exception as e:
		msg = "Could not get Connection response from UNIS: %s" % e
		write_to_log(msg,printtoscreen)
		return None
	data = r.read()
	if r.status not in (200, 201):
		write_to_log("POST to UNIS at "+url,printtoscreen)
		write_to_log(data,printtoscreen)
		return None
	else:
		return data

#Obtain Slice Credential from GeniDesktop Parser
def getLampCert_n_details_FromParser(slice_crypt,user_crypt):
	global debug

	post_data = urllib.urlencode({'slice_crypt':slice_crypt, 'user_crypt':user_crypt,'debug':debug})
	url = 'https://parser.netlab.uky.edu/getLNUinfo.php'
	req = urllib2.Request(url,post_data)
	post_response = urllib2.urlopen(req)
	post_return = post_response.read()

	return post_return

#Obtain userinfo using Credentials from GeniDesktop Parser
def getUserinfoFromParser(cert,passphrase):
	global debug

	post_data = urllib.urlencode({'cert':cert, 'passphrase':passphrase,'debug':debug})
	url = 'https://parser.netlab.uky.edu/getUserinfo.php'
	req = urllib2.Request(url,post_data)
	post_response = urllib2.urlopen(req)
	post_return = post_response.read()

	return post_return

#Obtain Sliceinfo using cryptic form of user credentials from GeniDesktop Parser
def getSliceinfoFromParser(user_crypt,sliceurn=''):
	global debug
	post_data = urllib.urlencode({'user_crypt':user_crypt,'debug':debug,'sliceurn':sliceurn})
	url = 'https://parser.netlab.uky.edu/getSliceinfo.php'
	req = urllib2.Request(url,post_data)
	post_response = urllib2.urlopen(req)
	post_return = post_response.read()
	return post_return

#Clear Cert and Passphrase at  GeniDesktop Parser
def clearUserinfoatParser(user_crypt):
	global debug

	post_data = urllib.urlencode({'user_crypt':user_crypt,'debug':debug})
	url = 'https://parser.netlab.uky.edu/clearUserinfo.php'
	req = urllib2.Request(url,post_data)
	post_response = urllib2.urlopen(req)
	post_return = post_response.read()
	return post_return


def getJSONManifestFromParser(slice_crypt,sliceurn,userurn,user_crypt,api):
	global debug
	
	post_data = urllib.urlencode({'key':slice_crypt,'sliceurn':sliceurn,'userurn':userurn,'user_key':user_crypt,'api':api,'debug':debug})
	url = 'https://parser.netlab.uky.edu/parseManifest.php'
	req = urllib2.Request(url,post_data)
	post_response = urllib2.urlopen(req)
	post_return = post_response.read()
	return post_return

def getPassphraseFromFile():
	global PASSPHRASEFILE
	global passphrase

	try:
		passphrase = open(PASSPHRASEFILE).readline()
		passphrase = passphrase.strip()
		return passphrase
	except IOError, e:
		print 'Error reading passphrase file %s: %s' % (PASSPHRASEFILE,e.strerror)
		passphrase = None
	return passphrase
		

def getPkey(keyfile,filetype,keypassphrase = None):
	global passphrase
	global PASSPHRASEFILE
	TKF = tempfile.NamedTemporaryFile()

	while(True):
		try:
			pKey_object = paramiko.RSAKey.from_private_key_file(keyfile,keypassphrase)
			break
		except paramiko.PasswordRequiredException:
			if(filetype == "certificate" and os.path.exists(PASSPHRASEFILE)):
				print "\nPrivate "+filetype+" file "+keyfile+" is encrypted. Trying to read passphase from "+PASSPHRASEFILE+"\n"
				keypassphrase = getPassphraseFromFile()
				if(keypassphrase == None):
					msg1 = 'Do you want to continue (Y / N)? [DEFAULT: Y]  : '
					user_input = raw_input(msg1)
					if user_input in ['N','n']:
						sys.exit(1)
					PASSPHRASEFILE = None
					keypassphrase = None
			else:
				print "\nPrivate "+filetype+" file "+keyfile+" is encrypted. Please provide the correct passphrase\n"
				from M2Crypto.util import passphrase_callback
				keypassphrase = str(passphrase_callback(1, prompt1='Enter passphrase:', prompt2='Verify passphrase:'))
		except paramiko.SSHException , e:
			if(e.message == 'not a valid RSA private key file'):
				keypassphrase = getPassphraseFromFile()
				if(keypassphrase == '' or keypassphrase is None):
					command = 'openssl rsa -in '+keyfile+' -out '+TKF.name
				else:
					command = 'openssl rsa -in '+keyfile+' -passin pass:'+keypassphrase+' -out '+TKF.name
				process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)	
				(out, err) = process.communicate()
				retcode = process.returncode
				if(retcode == 0):
					keyfile = TKF.name
					pKey_object = paramiko.RSAKey.from_private_key_file(keyfile)
					break
				else:
					print "\n Not a valid RSA private key file. Will not proceed \n"
					sys.exit(1)
			else:
				print "\nInvalid Passphrase provided. Please Try Again\n"
				msg1 = 'Do you want to continue (Y / N)? [DEFAULT: Y]  : '
				user_input = raw_input(msg1)
				if user_input in ['N','n']:
					sys.exit(1)
				keypassphrase = None
				if(filetype == "certificate"):
					PASSPHRASEFILE = ""
			pass
	if(filetype == "certificate"):
		passphrase = keypassphrase
	return pKey_object

def sshConnection(hostname,port,username,pkey_object,what_to_do,cmd=None,localFile=None,remoteFile=None,pty=False):
#' > /dev/null 2>&1 &'

	passphrase = None
	key_filename = None
	sout_n_exitval = []
	serr = ''
	sout = ''
	ret_code = -100
	allow_agent=True
	look_for_keys=True
	compress=False
	ssh = paramiko.SSHClient()
	ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
	tries = 0
	
	while(1):
		try:
			ssh.connect(hostname,int(port),username,passphrase,pkey_object,key_filename,60.0, allow_agent, look_for_keys, compress)
			break
		except paramiko.AuthenticationException:
			serr = "Authentication for "+hostname+' at port '+port+" Failed"
			ret_code = -1
			return (sout,serr,int(ret_code))
		except socket.gaierror:
			serr = "Hostname "+hostname+" does not exist"
			ret_code = -1
		except socket.timeout:
			serr = "Hostname "+hostname+" is not responding at port "+port
			ret_code = -1
		except socket.error:
			serr = "Hostname "+hostname+" is not responding at port "+port
			ret_code = -1
		except AssertionError:
			print "Some Assert error. Will try again in 5 seconds"
			time.sleep(5)
			continue
			
		if(tries > 16):
			ssh.close()
			print "tries is done"
			return (sout,serr,int(ret_code))
		else:
			print serr+" \nWill try again in 15 seconds"
			tries = tries + 1
			time.sleep(15)
	if(what_to_do == 'scp'):
		ftp = ssh.open_sftp()
		ftp.put(localFile,remoteFile)
		ret_code = 0
		ftp.close()
		pass
	elif(what_to_do == 'scp_get'):
		ftp = ssh.open_sftp()
		ftp.get(remoteFile,localFile)
		ret_code = 0
		ftp.close()
		pass
	elif(what_to_do == 'ssh_GN' ):
		(stdin,stdout,stderr)= ssh.exec_command(cmd)
		stdin.close()
		ret_code = 0
		pass
	elif(what_to_do == 'ssh' ):
		result = run_remote(ssh,cmd,pty)
		serr = result['stderr']
		sout = result['stdout']
		ret_code = result['exit_status']
		pass
	else:
		pass
	
	
	ssh.close()
	return (sout,serr,int(ret_code))

# Routine taken from
# http://od-eon.com/blogs/stefan/automating-remote-commands-over-ssh-paramiko/
#This is a modified version by Hussam
def run_remote(ssh, cmd,pty=False,check_exit_status=True, verbose=True):
    result = {}
    chan = ssh.get_transport().open_session()
    stdin = chan.makefile('wb')
    stdout = chan.makefile('rb')
    stderr = chan.makefile_stderr('rb')
    if(pty):
	    chan.get_pty()
    chan.exec_command(cmd)
    exit_status = chan.recv_exit_status()
    result['exit_status'] = exit_status
    result['stdout'] = '\n'.join(stdout)
    result['stderr'] = '\n'.join(stderr)

    return result

def getLOGBASE(slicename):
	LOGBASE = '/var/log/gemini/'+slicename
	try:
		if not os.path.exists(LOGBASE):
			os.makedirs(LOGBASE)
	except OSError:
		LOGBASE = 'logs/'+slicename
		print "Using Alternate Log Base"
	return LOGBASE

def getCert_issuer_n_username():
	global CERTIFICATE
	subjectInfo = []
	USER_URN = ''
	cert = M2Crypto.X509.load_cert(CERTIFICATE)
	X509_EXT = cert.get_ext('subjectAltName').get_value()
	subjectInfo = X509_EXT.split(',')
	for info in subjectInfo:
		info = info.strip()
		if(info.startswith("URI:urn:publicid:IDN")):
			USER_URN = info
			break
	(junk,domain,type,username) = USER_URN.split('+')
	return (domain.replace('.','_')).replace(':','_'),username
	
def getCacheFilename(CERT_ISSUER,username,SLICENAME,api_call):
	return '/tmp/.gemini/'+CERT_ISSUER+'-'+username+'-'+api_call+'-'+SLICENAME+'.json'

#
# Modified version of do_method from Utah 
# Call the rpc server.
#
def do_method(ctx,module, method, params, URI=None, quiet=False, version=None,
              response_handler=None):
    
    if module:
        URI = URI + "/" + module
        pass

    if version:
        URI = URI + "/" + version
        pass

    url = urlsplit(URI, "https")

    if url.scheme == "https":
        if not os.path.exists(CERTIFICATE):
            if not quiet:
                print >> sys.stderr, "error: missing emulab certificate: " + CERTIFICATE
            return (-1, None)

        port = url.port if url.port else 443

        ctx.set_verify(M2Crypto.SSL.verify_none, 16)
        ctx.set_allow_unknown_ca(0)
    
        server = M2Crypto.httpslib.HTTPSConnection( url.hostname, port, ssl_context = ctx )
    elif url.scheme == "http":
        port = url.port if url.port else 80
        server = httplib.HTTPConnection( url.hostname, port )
        
    #
    # Make the call. 
    #
    while True:
        try:
            server.request( "POST", url.path, xmlrpclib.dumps( (params,), method ) )
            response = server.getresponse()
            if response.status == 503:
                if not quiet:
                    print >> sys.stderr, "Will try again in a moment. Be patient!"
                time.sleep(5.0)
                continue
            elif response.status != 200:
                if not quiet:
                    print >> sys.stderr, str(response.status) + " " + response.reason
                return (-1,None)
            response = xmlrpclib.loads( response.read() )[ 0 ][ 0 ]
            break
        except httplib.HTTPException, e:
            if not quiet: print >> sys.stderr, e
            return (-1, None)
        except xmlrpclib.Fault, e:
            if not quiet: print >> sys.stderr, e.faultString
            return (-1, None)
        except M2Crypto.SSL.Checker.WrongHost, e:
            print >> sys.stderr, "Warning: certificate host name mismatch."
            print >> sys.stderr, "Please consult:"
            print >> sys.stderr, "    http://www.protogeni.net/trac/protogeni/wiki/HostNameMismatch"            
            print >> sys.stderr, "for recommended solutions."
            print >> sys.stderr, e
            return (-1, None)

    #
    # Parse the Response, which is a Dictionary. See EmulabResponse in the
    # emulabclient.py module. The XML standard converts classes to a plain
    # Dictionary, hence the code below. 
    # 
    rval = response["code"]

    #
    # If the code indicates failure, look for a "value". Use that as the
    # return value instead of the code. 
    # 
    if rval:
        if response["value"]:
            rval = response["value"]
            pass
        pass
    return (rval, response)


def getSliceURN(framework,userurn,slicename,project=None):
	plus = '+'
	sliceurn = ''
	(first,authority_string,geni_type,name) = userurn.split('+')
	if(framework == 'portal'):
		if(project is not None and project != ''):
			sliceurn = first+plus+authority_string+':'+project+plus+'slice'+plus+slicename
		else:
			msg =  "Missing Project Name"
			print msg
			sys.exit(1)
	else:
		sliceurn = first+plus+authority_string+plus+'slice'+plus+slicename

	return sliceurn	

def getStateSummary(items):
	if(all(x == items[0] for x in items)):
		if(items[0] == 'CREATED'):
			return 'CREATED'
		elif(items[0] == 'INITIALIZATION_IN_PROGRESS'):
			return 'INITIALIZING'
		elif(items[0] == 'INITIALIZATION_COMPLETE'):
			return 'INITIALIZED'
		elif(items[0] == 'INSTALLATION_IN_PROGRESS'):
			return 'INSTRUMENTIZING'
		elif(items[0] == 'INSTALLATION_COMPLETE'):
			return 'INSTRUMENTIZING'
		elif(items[0] == 'INSTRUMENTIZE_IN_PROGRESS'):
			return 'INSTRUMENTIZING'
		elif(items[0] == 'INSTRUMENTIZE_COMPLETE'):
			return 'INSTRUMENTIZED'

	else:
		return "MIXED"

def isdetailedProbeRequired(Node,pKey):

	DETAILED_PROBE_COMPLETED = '/var/emulab/lock/DETAILED_PROBE_COMPLETED'

	hostname = Node['login_hostname']
	port = Node['login_port']
	username = Node['login_username']
	vid = Node['nodeid']

#	SUDO = 'sudo '
#	if(isRoot(username)):
#		SUDO = ''

	#cmd = SUDO+'ls '+DETAILED_PROBE_COMPLETED
	cmd = 'ls '+DETAILED_PROBE_COMPLETED

	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,username,pKey,'ssh',cmd,None,None)
	write_to_processlog(out_ssh,err_ssh)
   	if(ret_code == 0):
	   return False
	else:
	   return True

	return False

def detailedProbeComplete(Node,pKey,use_sudo):

	DETAILED_PROBE_COMPLETED = '/var/emulab/lock/DETAILED_PROBE_COMPLETED'

	hostname = Node['login_hostname']
	port = Node['login_port']
	username = Node['login_username']
	vid = Node['nodeid']

	if(not use_sudo):
		SUDO = ''
		ssh_username = "root"
	else:
		SUDO = 'sudo '
		ssh_username = username
	

	cmd = SUDO+'touch '+DETAILED_PROBE_COMPLETED

	(out_ssh,err_ssh,ret_code) = sshConnection(hostname,port,ssh_username,pKey,'ssh',cmd,None,None)
	write_to_processlog(out_ssh,err_ssh)
   	if(ret_code == 0):
	   return True
	else:
	   return False

	return True

def fetchFromCache(CERT_ISSUER,username,api_call):
	global SLICENAME
	global cache_expiry

	if(api_call == 'getuserinfo'):
		FILE = getCacheFilename(CERT_ISSUER,username,'',api_call)
	else:	
		FILE = getCacheFilename(CERT_ISSUER,username,SLICENAME,api_call)
	if(not os.path.isfile(FILE)):
		return ''
	elif((time.time() - os.stat(FILE)[8] ) > cache_expiry): # Assumes that if cache file is older than 15 minutes dont use it.
		msg = "Cache for "+api_call+" is empty or invalid :EXPIRED "+str(time.time() - os.stat(FILE)[8]  - cache_expiry )+' seconds ago'
		write_to_log(msg,printtoscreen)
		return ''

	else:
		f = open(FILE,'r')
		return (f.readline()).strip()

def writeToCache(CERT_ISSUER,username,api_call,json):
	global SLICENAME
	if(api_call == 'getuserinfo'):
		FILE = getCacheFilename(CERT_ISSUER,username,'',api_call)
	else:	
		FILE = getCacheFilename(CERT_ISSUER,username,SLICENAME,api_call)
	ensure_dir(FILE)
	f = open(FILE, 'w')
	f.write(json)
	f.close()

	return


def getMyExpInfo(CERT_ISSUER,username,cert_string,project,force_refresh):
	global SLICENAME
	global passphrase

	UserJSON = ''
	if(force_refresh):
		cachedUserJSON = ''
	else:
		cachedUserJSON = fetchFromCache(CERT_ISSUER,username,"getuserinfo")
	if (cachedUserJSON != ''):
		msg = "Fetching User Info from the Cache"
		write_to_log(msg,printtoscreen)
		UserJSON = cachedUserJSON
	else:
		msg = "Fetching User Info from the GeniDesktop Parser"
		write_to_log(msg,printtoscreen)
		UserJSON = getUserinfoFromParser(cert_string,passphrase)
	try:
		UserOBJ = json.loads(UserJSON)
		if (cachedUserJSON == ''):
			writeToCache(CERT_ISSUER,username,'getuserinfo',UserJSON.strip())
	except ValueError:
		#This assumes that the info in the cache is corrupted  
		# SO we clear the cache
		# So the next time the info is pulled from the parser
		writeToCache(CERT_ISSUER,username,'getuserinfo','')
		msg ="User JSON Loading Error"
		write_to_log(msg,printtoscreen)
		sys.exit(1)

	write_to_log(UserJSON,dontprinttoscreen)
	if (UserOBJ['code'] == 0):
		UserInfo = UserOBJ['output']
		username = UserInfo['uid']
		email_id = UserInfo['email']
		USERURN = UserInfo['userurn']
		user_crypt = UserInfo['user_crypt']
		user_public_key = UserInfo['public_key']
		framework = UserInfo['framework']
	else:
		msg = "User not identified : "+ UserOBJ['output']
		write_to_log(msg,printtoscreen)
		sys.exit(1)

	msg = "Found User Info for "+USERURN
	write_to_log(msg,printtoscreen)


	my_sliceurn = getSliceURN(framework,USERURN,SLICENAME,project)
	if(force_refresh):
		cachedSliceJSON = ''
	else:
		cachedSliceJSON = fetchFromCache(CERT_ISSUER,username,"getsliceinfo")
	SliceJSON = ''
	if (cachedSliceJSON != ''):
		msg = "Fetching Slice Info from the Cache"
		write_to_log(msg,printtoscreen)
		SliceJSON = cachedSliceJSON
	else:
		msg = "Fetching Slice Info from the GeniDesktop Parser"
		write_to_log(msg,printtoscreen)
		SliceJSON = getSliceinfoFromParser(user_crypt,my_sliceurn)
	try:
		SliceOBJ = json.loads(SliceJSON)
		if(cachedSliceJSON == ''):
			writeToCache(CERT_ISSUER,username,'getsliceinfo',SliceJSON.strip())
	except ValueError:
		#This assumes that the info in the cache is corrupted  
		# SO we clear the cache
		# So the next time the info is pulled from the parser
		writeToCache(CERT_ISSUER,username,'getsliceinfo','')
		msg ="Slice JSON Loading Error"
		write_to_log(msg,printtoscreen)
		sys.exit(1)

	write_to_log(SliceJSON,dontprinttoscreen)
	found = False
	if (SliceOBJ['code'] != 0):
		msg = "User/Slice not identified : "+ SliceOBJ['output']
		write_to_log(msg,printtoscreen)
		sys.exit(1)

	Slices = SliceOBJ['output']
	for  SliceInfo in Slices:
		(junk,slicename_from_parser) = SliceInfo['sliceurn'].rsplit('+',1)
		if (SLICENAME == slicename_from_parser):
			SLICEURN =  SliceInfo['sliceurn']
			found = True
			break

	if(not found):
		msg = "Slice : "+SLICENAME+' does not exists'
		write_to_log(msg,printtoscreen)
		sys.exit(1)

	msg = "Found Slice Info for "+SLICEURN
	write_to_log(msg,printtoscreen)
	slice_crypt = SliceInfo['crypt']
	api = "getNodeInfo"
	if(force_refresh):
		cachedNodesJSON = ''
	else:
		cachedNodesJSON = fetchFromCache(CERT_ISSUER,username,"nodeinfo")
	NodesJSON = ''
	if(cachedNodesJSON != ''):
		msg = "Fetching Manifest Info from the Cache"
		write_to_log(msg,printtoscreen)
		NodesJSON = cachedNodesJSON
	else:
		msg = "Fetching Manifest Info from the GeniDesktop Parser"
		write_to_log(msg,printtoscreen)
		NodesJSON = getJSONManifestFromParser(slice_crypt,SLICEURN,USERURN,user_crypt,api)
	try:
		NodesOBJ = json.loads(NodesJSON.strip())
		if(cachedNodesJSON == ''):
			writeToCache(CERT_ISSUER,username,'nodeinfo',NodesJSON.strip())
	except ValueError:
		#This assumes that the info in the cache is corrupted  
		# SO we clear the cache
		# So the next time the info is pulled from the parser
		writeToCache(CERT_ISSUER,username,'nodeinfo','')
		msg ="Nodes JSON Loading Error"
		write_to_log(msg,printtoscreen)
		sys.exit(1)

	write_to_log(NodesJSON,dontprinttoscreen)
	if(NodesOBJ['code'] != 0):
		#msg = NodesOBJ['output']+": No Manifest Available for : "+ SliceInfo['sliceurn']
		#write_to_log(msg,printtoscreen)
		writeToCache(CERT_ISSUER,username,'nodeinfo','')

	return (UserOBJ['output'],SliceOBJ['output'],NodesOBJ['output'])
