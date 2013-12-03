#! /usr/bin/env python
#
# GENIPUBLIC-COPYRIGHT
# Copyright (c) 2008-2009 University of Utah and the Flux Group.
# All rights reserved.
# 
# Permission to use, copy, modify and distribute this software is hereby
# granted provided that (1) source code retains these copyright, permission,
# and disclaimer notices, and (2) redistributions including binaries
# reproduce the notices in supporting documentation.
#
# THE UNIVERSITY OF UTAH ALLOWS FREE USE OF THIS SOFTWARE IN ITS "AS IS"
# CONDITION.  THE UNIVERSITY OF UTAH DISCLAIMS ANY LIABILITY OF ANY KIND
# FOR ANY DAMAGES WHATSOEVER RESULTING FROM THE USE OF THIS SOFTWARE.
# ------------------------------------------------------------------------------
# Adapted for use in the GENI INSTOOLS Project 
# http://groups.geni.net/geni/wiki/InstrumentationTools
# ------------------------------------------------------------------------------



import sys
import getopt
import os
import time
import M2Crypto
import hashlib
import json
import multiprocessing
import gemini_util	# Import user defined routines
from os.path import expanduser

other_details = ""
managers = []
GN_Nodes = []
MP_Nodes = []
keyfile = ""
force_refresh = False
FILE = ''
SLICEURN = ''
AMURNS = ''

def Usage():
        print "usage: " + sys.argv[ 0 ] + " [option...]"
        print """Options:
    -d, --debug                         Be verbose
    -k, --pkey=file			Private SSH RSA Key file
    -f file, --certificate=file         Read SSL certificate from file
                                            [default: ~/.ssl/encrypted.pem]
    -p file, --passphrase=file          Read passphrase for certificate from file
                                            [default: ~/.ssl/password]
    -a urns, --amurns=list		Comma separated list of AM URNs where the user 
					has slivers for this slice
					    [default: Poll all AMs registered for this Clearing House]
    -h, --help                          Show options and usage
    -n name, --slicename=name           Specify human-readable name of slice
    -r PROJECT, --project=PROJECT	Name of project. (For use with portal framework.)
    --force_refresh                     Force fetch all user/slice/sliver info rather than using locally cached version
    --devel	                        Use Development version [only for developers]"""

def InitProcess(my_manager,pruned_GN_Nodes,pruned_MP_Nodes):

	global USERURN
	global email_id
	global user_password_for_drupal
	global SLICEURN
	global dpadmin_username
	global dpadmin_passwd
	global slice_crypt
	global pKey
	global user_public_key


	# STEP 1: Check nodes for OS Compatibilty
	msg = "Checking if Nodes at AM --> "+my_manager+" for \n"+"1. Check if Global Node Present\n2. Find Nodes to be monitored by GEMINI\n3. OS Compatibility of selected Nodes"
	gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	(result,msg) = gemini_util.precheckNodes(pruned_GN_Nodes[0],pruned_MP_Nodes,pKey)
	if(result):
		msg = "All nodes at AM --> "+my_manager+" are GEMINI capable.\nWill proceed with the GENI Desktop Init Process"
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)

	else:
		msg = "ERROR @ {"+my_manager+"} :: "+msg
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
		sys.exit(1)

	(status,msg) = gemini_util.lock_unlock_MC(pruned_GN_Nodes[0],"init_lock",pKey)
	msg = "["+my_manager+"] "+msg
	if(not status):
		msg = msg + "\nConfiguring next AM if available"
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
		return
	else:
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)


	#Place on the GN Node - DRUPAL_ADMIN_PASSWORD , userurn , sliceurn , slicename, cmurn, cmhrn , vnc_passwd, topinfo, portal_public_key
	(result,msg) = gemini_util.dump_Expinfo_on_GN(pruned_GN_Nodes[0],USERURN,email_id,user_password_for_drupal,SLICEURN,my_manager,dpadmin_username,dpadmin_passwd,slice_crypt,pKey)
	if(result):
		msg = "GN that monitors MP Nodes at  "+my_manager+" has all the Exp info it needs. Will now proceed with the Initialization process."
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)

	else:
		msg = "GN ERROR @ {"+my_manager+"} :: while placing Exp info "+str(msg)
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
		sys.exit(1)

	# STEP 2 : Download Passive measurement scripts and start ssh-key generator on the GN
	# STEP 2b : Save MC public key onto a file pn GN, fetch it from the GN and place it on all MP Nodes
	# STEP 3 : Install Shell in a box on all nodes and generate the Shellinabox config
	(result,msg) = gemini_util.install_keys_plus_shell_in_a_box(pruned_GN_Nodes[0],pruned_MP_Nodes,user_public_key,pKey)
	if(result):
		msg = "All nodes at AM --> "+my_manager+" have been Initialized."
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)

	else:
		msg = "ERROR @ {"+my_manager+"} :: during Initialization "+str(msg)
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
		sys.exit(1)

	return
 

#############################################
# MAIN PROCESS
#############################################


try:
    opts, REQARGS = getopt.gnu_getopt( sys.argv[ 1: ], "dhk:f:n:p:r:a:",
                                   [ "debug","help","force_refresh","pkey=","certificate=",
                                     "slicename=","devel","passphrase=","project=","amurns="] )
except getopt.GetoptError, err:
    print >> sys.stderr, str( err )
    Usage()
    sys.exit( 1 )

args = REQARGS
LOGFILE = None
project = None
for opt, arg in opts:
    if opt in ( "-d", "--debug" ):
        gemini_util.debug = 1
    elif opt == "--devel":
        gemini_util.version = gemini_util.devel_version
	gemini_util.INSTOOLS_repo_url = gemini_util.mc_repo_rooturl+"GEMINI/"+gemini_util.version+"/"
    elif opt == "--force_refresh":
        force_refresh = True
    elif opt in ( "-r", "--project"):
	project = arg
    elif opt in ( "-a", "--amurns"):
	result = gemini_util.isValidURNs(arg)
	if(result):
		AMURNS = arg
	else:
		print "Invalid AM URNS Provided"
        	sys.exit( 1 )
	
    elif opt in ( "-f", "--certificate" ):
	if(arg.startswith('~')):
		arg = arg.replace('~',expanduser("~"),1)
        gemini_util.CERTIFICATE = arg
    elif opt in ( "-h", "--help" ):
        Usage()
        sys.exit( 0 )
    elif opt in ( "-n", "--slicename" ):
		gemini_util.SLICENAME = arg
		# check if slicename is not empty
		if(gemini_util.SLICENAME == ''):
			print "Please provide a slicename"
			Usage()
			sys.exit(1)
		else:
			mylogbase = gemini_util.getLOGBASE(gemini_util.SLICENAME)
			LOCALTIME = time.strftime("%Y%m%dT%H:%M:%S",time.localtime(time.time()))
			LOGFILE = mylogbase+"/gdesktop-init-"+LOCALTIME+".log"
			gemini_util.ensure_dir(LOGFILE)
			gemini_util.openLogPIPE(LOGFILE)
			pass
    elif opt in ( "-p", "--passphrase" ):
	if(arg.startswith('~')):
		arg = arg.replace('~',expanduser("~"),1)
        gemini_util.PASSPHRASEFILE = arg
    elif opt in ( "-k", "--pkey" ):
	if(arg.startswith('~')):
		arg = arg.replace('~',expanduser("~"),1)
        keyfile = arg
	if(not (keyfile != '' and os.path.isfile(keyfile))):
		print "Please provide a valid private key file"
		Usage()
		sys.exit(1)
	else:
		SSH_pkey = gemini_util.getPkey(keyfile,"SSH key")

if (LOGFILE is None):
	print "Please provide a slicename"
	Usage()
	sys.exit(1)
	
try:
	cf = open(gemini_util.CERTIFICATE,'r')
except:
	msg = "Error opening Certificate"
	gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	sys.exit(1)

# Check if passphrase provided is valid
# If passphrase is not provided prompt for it.
CERT_pkey = gemini_util.getPkey(gemini_util.CERTIFICATE,"certificate")
(CERT_ISSUER,username) = gemini_util.getCert_issuer_n_username()

if(not (keyfile != '' and os.path.isfile(keyfile))):
	pKey = CERT_pkey
else:
	pKey = SSH_pkey


(UserInfo,Slices,Nodes) = gemini_util.getMyExpInfo(CERT_ISSUER,username,cf.read(),project,force_refresh,AMURNS)
cf.close()
username = UserInfo['uid']
email_id = UserInfo['email']
USERURN = UserInfo['userurn']
user_crypt = UserInfo['user_crypt']
framework = UserInfo['framework']
user_public_key = UserInfo['public_key']
	
for  SliceInfo in Slices:
	(junk,slicename_from_parser) = SliceInfo['sliceurn'].rsplit('+',1)
	if (gemini_util.SLICENAME == slicename_from_parser):
		SLICEURN =  SliceInfo['sliceurn']
		found = True
		break

if(not found):
	msg = "Slice : "+gemini_util.SLICENAME+' does not exists'
	gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	sys.exit(1)

msg = "Found Slice Info for "+SLICEURN
gemini_util.write_to_log(msg,gemini_util.printtoscreen)
slice_crypt = SliceInfo['crypt']

if(isinstance(Nodes, basestring)):
	msg = Nodes+": No Manifest Available for : "+ SliceInfo['sliceurn']
	gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	sys.exit(1)

for Node in Nodes:
	nodeid = Node['nodeid']
	hostname = Node['hostname']
	ismc = Node['ismc']
	login_hostname = Node['login_hostname']
        if( Node['login_username'] != username):
		msg = "Login Username obtained from manifest is "+Node['login_username']+ " for node "+nodeid+". Will change it to "+username+" for GEMINI Instrumentation setup"
                gemini_util.write_to_log(msg,gemini_util.printtoscreen)
                Node['login_username'] = username
	login_username = Node['login_username']
	other_members = Node['additional_users']
	login_port = Node['login_port']
	mchostname = Node['mchostname']
	cmurn = Node['cmurn']
	gemini_node_type = Node['gemini_node_type']
	sliver_id = Node['sliver_id']
	if(gemini_node_type == 'global_node'):
		GN_Nodes.append(Node)
	elif(gemini_node_type == 'mp_node'):
		MP_Nodes.append(Node)
	if(Node['cmurn'] not in managers):
		managers.append(Node['cmurn'])

	msg = "*****************************\n"+\
	"NodeID => "+nodeid+"\n"+ \
	"Hostname =>" +hostname+"\n"+  \
	"isMC => "+ismc+"\n"+ \
	"Hostname to login => "+login_hostname+"\n"+ \
	"Username to login with => "+login_username+"\n"+ \
	"SSH port to use for Login => "+login_port+"\n"+ \
	"Other members on this Node => "+' , '.join(other_members)+"\n"+ \
	"Sliver_id => "+sliver_id+"\n"+ \
	"Its CMURN => "+cmurn+"\n"+ \
	"Gemini Node Type => "+gemini_node_type+"\n"+ \
	"MC Hostname => "+mchostname+"\n"+"**********************"
        gemini_util.write_to_log(msg,gemini_util.dontprinttoscreen)

msg = "***********************************\n"+\
"You have "+str(len(MP_Nodes))+" MP Nodes and "+str(len(GN_Nodes))+" GN Nodes\n"+\
"***********************************\n"
gemini_util.write_to_log(msg,gemini_util.printtoscreen)
if (len(GN_Nodes) == 0):
	msg = "No GN Nodes Present. Will not proceed"
        gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	sys.exit(1)

dpadmin_username = "drupal_admin"
dpadmin_passwd = gemini_util.random_password()
m = hashlib.sha1(slice_crypt)
user_password_for_drupal = m.hexdigest()

proclist = []
for my_manager in managers:

	msg =  "Starting initialization process for Nodes at ["+my_manager+"] "
	gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	pruned_GN_Nodes = gemini_util.pruneNodes(GN_Nodes,my_manager,'GN')
	if (len(pruned_GN_Nodes) == 0):
		msg = "No GN Nodes Present that monitor MP Nodes at  AM = "+my_manager+" . Continuing with the next AM if available"
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
		continue
	if (len(pruned_GN_Nodes) > 1):
		msg = "Multiple GN Nodes Present that monitor this  AM = "+my_manager+" . This is not supported yet"
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
		sys.exit(1)

	pruned_MP_Nodes = gemini_util.pruneNodes(MP_Nodes,my_manager,'')

	p = multiprocessing.Process(target=InitProcess,args=(my_manager,pruned_GN_Nodes,pruned_MP_Nodes,))
	proclist.append(p)
	p.start()                                                                                                                      

while(True):
	pending_proclist = []
	for i in proclist:
		if(i.exitcode is None):
			pending_proclist.append(i)
			continue
		elif(i.exitcode != 0):
			sys.exit(i.exitcode)
		else:
			continue
	if not pending_proclist:
		break
	else:
		proclist = pending_proclist
	time.sleep(5)
	pass

gemini_util.closeLogPIPE(LOGFILE)




