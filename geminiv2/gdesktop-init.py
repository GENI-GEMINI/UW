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
#import urllib
import hashlib
import json
import multiprocessing
import gemini_util	# Import user defined routines

other_details = ""
managers = []
GN_Nodes = []
MP_Nodes = []
debug           = 0
keyfile = ""
force_refresh = '1'
FILE = ''


def Usage():
        print "usage: " + sys.argv[ 0 ] + " [option...]"
        print """Options:
    -d, --debug                         be verbose about XML methods invoked
    --devel	                        Use Devel version [only for developers]
    -x, --no_force_refresh                  Do not force parser to get fresh manifests from AMs
    -k, --pkey=file			Private SSH RSA Key file
    -f file, --certificate=file         read SSL certificate from file
                                            [default: ~/.ssl/encrypted.pem]
    -h, --help                          show options and usage
    -n name, --slicename=name           specify human-readable name of slice
                                            [default: mytestslice]
    -j file, --loadFromFile=file          read all experiemnt info from File
							[To be used by GENI Desktop only]
    -p file, --passphrase=file          read passphrase from file
                                            [default: ~/.ssl/password]"""

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
    opts, REQARGS = getopt.gnu_getopt( sys.argv[ 1: ], "dhxk:f:n:j:p:",
                                   [ "debug","help","no_force_refresh","pkey=","certificate=",
                                     "slicename=","loadFromFile=","devel","passphrase="] )
except getopt.GetoptError, err:
    print >> sys.stderr, str( err )
    Usage()
    sys.exit( 1 )

args = REQARGS

for opt, arg in opts:
    if opt in ( "-d", "--debug" ):
        gemini_util.debug = 1
    elif opt in ( "--devel" ):
        gemini_util.version = gemini_util.devel_version
	gemini_util.INSTOOLS_repo_url = gemini_util.mc_repo_rooturl+"GEMINI/"+gemini_util.version+"/"
    elif opt in ( "-x","--no_force_refresh" ):
        force_refresh = '0'
    elif opt in ( "-f", "--certificatefile" ):
        gemini_util.CERTIFICATE = arg
    elif opt in ( "-h", "--help" ):
        Usage()
        sys.exit( 0 )
    elif opt in ( "-n", "--slicename" ):
        gemini_util.SLICENAME = arg
	# check if slicename is not empty
	if(gemini_util.SLICENAME == ''):
		print "Please provide a slicename"
		sys.exit(1)
	else:
		mylogbase = gemini_util.getLOGBASE()
		LOCALTIME = time.strftime("%Y%m%dT%H:%M:%S",time.localtime(time.time()))
		LOGFILE = mylogbase+"/gdesktop-init-"+gemini_util.SLICENAME+"_"+LOCALTIME+".log"
		gemini_util.ensure_dir(LOGFILE)
		gemini_util.openLogPIPE(LOGFILE)
		pass
    elif opt in ( "-p", "--passphrasefile" ):
        gemini_util.PASSPHRASEFILE = arg
    elif opt in ( "-j", "--loadFromFile" ):
        FILE = arg
	# check if FILE exists
	if(not os.path.isfile(FILE)):
		print "Please provide a Slice/Exp Info File Name. (To be run only by the GENI Desktop)"
		sys.exit(1)
	else:
		f = open(FILE,'r')
    elif opt in ( "-k", "--pkey" ):
        keyfile = arg
	if(not (keyfile != '' and os.path.isfile(keyfile))):
		print "Please provide a valid private key file"
		sys.exit(1)
	else:
		SSH_pkey = gemini_util.getPkey(keyfile,"SSH key")

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

if(not FILE):
	#loading cache file
	FILE = gemini_util.getCacheFilename(CERT_ISSUER,username,gemini_util.SLICENAME)
	if(not os.path.isfile(FILE)):
		FILE = ''
	elif((time.time() - os.stat(FILE)[8] ) > gemini_util.cache_expiry): # Assumes that if cache file is older than 15 minutes dont use it.
		msg = "Cache is empty or invalid :EXPIRED "+str(time.time() - os.stat(FILE)[8]  - gemini_util.cache_expiry )+' seconds ago'
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
		FILE = ''

	else:
		f = open(FILE,'r')

# The FILE variable is pretty tricky
# Check if user provides the JSON FIle
# next resort look for JSON from cache in /tmp/
# If all else fails fetch from parser.

if (FILE):
	msg = "Fetching User Info from the Cache"
	gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	UserJSON = f.readline()
else:
	msg = "Fetching User Info from the GeniDesktop Parser"
	gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	UserJSON = gemini_util.getUserinfoFromParser(cf.read(),gemini_util.passphrase)
cf.close()
try:
	UserOBJ = json.loads(UserJSON)
except ValueError:
	if(FILE):
		#This assumes that the info in the cache is corrupted remove the cache and exit 
		# So the next time its called again, fresh info from the parser is pulled
		os.unlink(FILE)
	msg ="User JSON Loading Error"
	gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	sys.exit(1)

gemini_util.write_to_log(UserJSON,gemini_util.dontprinttoscreen)
if (UserOBJ['code'] == 0):
	UserInfo = UserOBJ['output']
	username = UserInfo['uid']
	email_id = UserInfo['email']
	USERURN = UserInfo['userurn']
	user_crypt = UserInfo['user_crypt']
	user_public_key = UserInfo['public_key']
	framework = UserInfo['framework']
	if(framework == 'portal'):
		msg = "Please make sure that the below shown SSH Public key is in the list of keys registered at your Slice Authority\n"+user_public_key+"\n"
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	#CERT_ISSUER = UserInfo['certificate_issuer']
else:
	msg = "User not identified : "+ UserOBJ['output']
        gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	sys.exit(1)

msg = "Found User Info for "+USERURN
gemini_util.write_to_log(msg,gemini_util.printtoscreen)
if (FILE):
	msg = "Fetching Slice Info from the Cache"
	gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	SliceJSON = f.readline()
else:
	msg = "Fetching Slice Info from the GeniDesktop Parser"
	gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	SliceJSON = gemini_util.getSliceinfoFromParser(user_crypt)
try:
	SliceOBJ = json.loads(SliceJSON)
except ValueError:
	if(FILE):
		#This assumes that the info in the cache is corrupted remove the cache and exit 
		# So the next time its called again, fresh info from the parser is pulled
		os.unlink(FILE)
	
	msg ="Slice JSON Loading Error"
	gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	sys.exit(1)

gemini_util.write_to_log(SliceJSON,gemini_util.dontprinttoscreen)
found = gemini_util.FALSE
if (SliceOBJ['code'] != 0):
	msg = "User/Slice not identified : "+ SliceOBJ['output']
        gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	sys.exit(1)

Slices = SliceOBJ['output']
for  SliceInfo in Slices:
	(junk,slicename_from_parser) = SliceInfo['sliceurn'].rsplit('+',1)
	if (gemini_util.SLICENAME == slicename_from_parser):
		SLICEURN =  SliceInfo['sliceurn']
		found = gemini_util.TRUE
		break

if(not found):
	msg = "Slice : "+gemini_util.SLICENAME+' does not exists'
        gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	sys.exit(1)

msg = "Found Slice Info for "+SLICEURN
gemini_util.write_to_log(msg,gemini_util.printtoscreen)
slice_crypt = SliceInfo['crypt']
api = "getNodeInfo"
if(FILE):
	msg = "Fetching Manifest Info from the Cache"
	gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	NodesJSON= f.readline()
else:
	msg = "Fetching Manifest Info from the GeniDesktop Parser"
	gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	NodesJSON = gemini_util.getJSONManifestFromParser(slice_crypt,gemini_util.SLICENAME,api,force_refresh)
try:
	NodesOBJ = json.loads(NodesJSON)
except ValueError:
	if(FILE):
		#This assumes that the info in the cache is corrupted remove the cache and exit 
		# So the next time its called again, fresh info from the parser is pulled
		os.unlink(FILE)
	
	msg ="Nodes JSON Loading Error"
	gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	sys.exit(1)

gemini_util.write_to_log(NodesJSON,gemini_util.dontprinttoscreen)
if(NodesOBJ['code'] != 0):
	msg = NodesOBJ['output']+": No Manifest Available for : "+ SliceInfo['sliceurn']
        gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	sys.exit(1)

Nodes = NodesOBJ['output']
for Node in Nodes:
	nodeid = Node['nodeid']
	hostname = Node['hostname']
	ismc = Node['ismc']
	login_hostname = Node['login_hostname']
	login_username = Node['login_username']
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
m = hashlib.sha1(user_crypt)
user_password_for_drupal = m.hexdigest()

if(not FILE):
	# Save all jsons to cache
	cachefilename = gemini_util.getCacheFilename(CERT_ISSUER,username,gemini_util.SLICENAME)
	gemini_util.ensure_dir(cachefilename)
	f = open(cachefilename, 'w')
	f.write(UserJSON.strip()+"\n")
	f.write(SliceJSON.strip()+"\n")
	f.write(NodesJSON.strip())
	f.close

proclist = []
for my_manager in managers:

	msg =  "Starting instrumentize process for Nodes at ["+my_manager+"] "
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




