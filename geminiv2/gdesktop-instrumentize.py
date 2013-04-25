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
import uuid
import json
import time
import datetime
import gemini_util	# Import user defined routines
from lxml import etree
from unisencoder.decoder import RSpec3Decoder

other_details = ""
managers = []
GN_Nodes = []
MP_Nodes = []
debug           = 0
keyfile = ""
force_refresh = '1'
FILE = ''
DONE=0


def Usage():
        print "usage: " + sys.argv[ 0 ] + " [option...]"
        print """Options:
    -d, --debug                         be verbose about XML methods invoked
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

try:
    opts, REQARGS = getopt.gnu_getopt( sys.argv[ 1: ], "dhxk:f:n:j:p:",
                                   [ "debug","help","no_force_refresh","pkey=","certificate=",
                                     "slicename=","loadFromFile="
                                     "passphrase="] )
except getopt.GetoptError, err:
    print >> sys.stderr, str( err )
    Usage()
    sys.exit( 1 )

args = REQARGS

for opt, arg in opts:
    if opt in ( "-d", "--debug" ):
        debug = 1
    elif opt in ( "-x","--no_force_refresh" ):
        force_refresh = '0'
    elif opt in ( "-k", "--pkey" ):
        keyfile = arg
	if(not (keyfile != '' and os.path.isfile(keyfile))):
		print "Please provide a valid private key file"
		sys.exit(1)
	else:
		SSH_pkey = gemini_util.getPkey(keyfile,"SSH key")

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

	
mylogbase = gemini_util.getLOGBASE()
LOCALTIME = time.strftime("%Y%m%dT%H:%M:%S",time.localtime(time.time()))
LOGFILE = mylogbase+"/gdesktop-instrumentize-"+gemini_util.SLICENAME+"_"+LOCALTIME+".log"
gemini_util.ensure_dir(LOGFILE)

try:
	cf = open(gemini_util.CERTIFICATE,'r')
except:
	msg = "Error opening Certificate"
        gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
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
		msg = "Cache is empty or invalid :EXPIRED "+str(time.time() - os.stat(FILE)[8] - gemini_util.cache_expiry )+' seconds ago'
		gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
		FILE = ''
	else:
		f = open(FILE,'r')

# The FILE variable is pretty tricky
# Check if user provides the JSON FIle
# next resort look for JSON from cache in /tmp/
# If all else fails fetch from parser.


if (FILE):
	msg = "Fetching User Info from the Cache"
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	UserJSON = f.readline()
else:
	msg = "Fetching User Info from the GeniDesktop Parser"
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	UserJSON = gemini_util.getUserinfoFromParser(cf.read(),gemini_util.passphrase,LOGFILE,debug)
cf.close()
try:
	UserOBJ = json.loads(UserJSON)
	gemini_util.write_to_log(LOGFILE,UserJSON,gemini_util.dontprinttoscreen,debug)
except ValueError:
	if(FILE):
		#This assumes that the info in the cache is corrupted remove the cache and exit 
		# So the next time its called again, fresh info from the parser is pulled
		os.unlink(FILE)
	
	msg ="User JSON Loading Error"
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	sys.exit(1)

if (UserOBJ['code'] == 0):
	UserInfo = UserOBJ['output']
	username = UserInfo['uid']
	email_id = UserInfo['email']
	USERURN = UserInfo['userurn']
	user_crypt = UserInfo['user_crypt']
	#CERT_ISSUER = UserInfo['certificate_issuer']
else:
	msg = "User not identified : "+ UserOBJ['output']
        gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	sys.exit(1)

msg = "Found User Info for "+USERURN
gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
if (FILE):
	msg = "Fetching Slice Info from the Cache"
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	SliceJSON = f.readline()
else:
	msg = "Fetching Slice Info from the GeniDesktop Parser"
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	SliceJSON = gemini_util.getSliceinfoFromParser(user_crypt,LOGFILE,debug)
try:
	SliceOBJ = json.loads(SliceJSON)
except ValueError:
	if(FILE):
		#This assumes that the info in the cache is corrupted remove the cache and exit 
		# So the next time its called again, fresh info from the parser is pulled
		os.unlink(FILE)
		
	msg ="Slice JSON Loading Error"
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	sys.exit(1)

gemini_util.write_to_log(LOGFILE,SliceJSON,gemini_util.dontprinttoscreen,debug)
found = gemini_util.FALSE
if (SliceOBJ['code'] != 0):
	msg = "User/Slice not identified : "+ SliceOBJ['output']
        gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
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
        gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	sys.exit(1)

msg = "Found Slice Info for "+SLICEURN
gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
slice_crypt = SliceInfo['crypt']
api = "getNodeInfo"
if(FILE):
	msg = "Fetching Manifest Info from the Cache"
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	NodesJSON= f.readline()
else:
	msg = "Fetching Manifest Info from the GeniDesktop Parser"
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	NodesJSON = gemini_util.getJSONManifestFromParser(slice_crypt,gemini_util.SLICENAME,api,force_refresh,LOGFILE,debug)
try:
	NodesOBJ = json.loads(NodesJSON)
	gemini_util.write_to_log(LOGFILE,NodesJSON,gemini_util.dontprinttoscreen,debug)
except ValueError:
	if(FILE):
		#This assumes that the info in the cache is corrupted remove the cache and exit 
		# So the next time its called again, fresh info from the parser is pulled
		os.unlink(FILE)
	
	msg ="Nodes JSON Loading Error"
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	sys.exit(1)

if(NodesOBJ['code'] != 0):
	msg = NodesOBJ['output']+": No Manifest Available for : "+ SliceInfo['sliceurn']
        gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
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
        gemini_util.write_to_log(LOGFILE,msg,gemini_util.dontprinttoscreen,debug)

msg = "***********************************\n"+\
"You have "+str(len(MP_Nodes))+" MP Nodes and "+str(len(GN_Nodes))+" GN Nodes\n"+\
"***********************************\n"
gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)


if (len(GN_Nodes) == 0):
	msg = "No GN Nodes Present. Will not proceed"
        gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	sys.exit(1)


msg = "Fetching Lamp Certificate and other information from the GeniDesktop Parser"
gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
LAMPJSON = gemini_util.getLampCert_n_details_FromParser(slice_crypt,user_crypt,LOGFILE,debug)

try:
	LAMPOBJ = json.loads(LAMPJSON)
	gemini_util.write_to_log(LOGFILE,LAMPJSON,gemini_util.dontprinttoscreen,debug)
except ValueError:
	if(FILE):
		#This assumes that the info in the cache is corrupted remove the cache and exit 
		# So the next time its called again, fresh info from the parser is pulled
		os.unlink(FILE)
	
	msg ="LAMP Info JSON Loading Error"
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	sys.exit(1)

slice_uuid = ''
slicecred = ''
expiry = ''
LAMPCERT = ''
if (LAMPOBJ['code'] == 0):
	LampInfo = LAMPOBJ['output']
	slicecred = LampInfo['credential']
	expiry = LampInfo['expiry']
	slice_uuid = LampInfo['uuid']
	LAMPCERT = LampInfo['lampcert']
else:
	msg = "Error obtaining Lamp Info : "+ LAMPOBJ['output']
        gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	sys.exit(1)

if(not FILE):
	# Save all jsons to cache
	cachefilename = gemini_util.getCacheFilename(CERT_ISSUER,username,gemini_util.SLICENAME)
	gemini_util.ensure_dir(cachefilename)
	f = open(cachefilename, 'w')
	f.write(UserJSON.strip()+"\n")
	f.write(SliceJSON.strip()+"\n")
	f.write(NodesJSON.strip())
	f.close
	
if(LAMPCERT == ''):
	msg = "Lamp Certificate Not Found.\nActive Services will be disabled to continue with the Instrumentation process"
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	gemini_util.DISABLE_ACTIVE = gemini_util.TRUE
else:
	SLICECRED_FOR_LAMP = slicecred.replace('<?xml version="1.0" encoding="UTF-8" standalone="no"?>','',1).lstrip()
	slice_lifetime = {}
	if (slice_uuid):
	        expiration = datetime.datetime.strptime(expiry,"%Y-%m-%dT%H:%M:%SZ")
	        now = datetime.datetime.now(expiration.tzinfo)
	        td = expiration - now
	        slice_lifetime = int(td.seconds + td.days * 24 * 3600)
		validity = datetime.timedelta(seconds=slice_lifetime)
		slice_lifetime = validity.days + 1
		#Now setup a proxy cert for the instrumentize script so we can talk to UNIS without keypass
		gemini_util.makeInstrumentizeProxy(slice_lifetime,slice_uuid,LOGFILE,debug)
		if not (gemini_util.PROXY_ATTR):
			msg = "ERROR: Could not complete proxy certificate creation for instrumentize process"
			gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
			msg = "Active Services will be disabled to continue with the Instrumentation process"
			gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
			gemini_util.DISABLE_ACTIVE = gemini_util.TRUE
		else:
			pass
			# temporary hack to write out an unencrypted keyfile for the slice registration call to UNIS
			TEMP_KEYFILE = gemini_util.getUnencryptedKeyfile(CERT_pkey,LOGFILE,debug)
			msg="Registering slice credential with Global UNIS"
			gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
			res1 = gemini_util.postDataToUNIS(TEMP_KEYFILE,gemini_util.CERTIFICATE,"/credentials/genislice",slicecred,LOGFILE,debug)
			os.remove(TEMP_KEYFILE)
			f = open(gemini_util.PROXY_ATTR)
			res2 = gemini_util.postDataToUNIS(gemini_util.PROXY_KEY,gemini_util.PROXY_CERT,"/credentials/geniuser",f,LOGFILE,debug)
			f.close()
			os.remove(gemini_util.PROXY_ATTR)
			if res1 or res2 is None:
				msg="Failed to register slice credential"
				gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
				msg = "Active Services will be disabled to continue with the Instrumentation process"
				gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
				gemini_util.DISABLE_ACTIVE = gemini_util.TRUE
	else:
	        msg = "Could not get slice UUID from slice credential"
	        gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
		msg = "Active Services will be disabled to continue with the Instrumentation process"
		gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
		gemini_util.DISABLE_ACTIVE = gemini_util.TRUE

for my_manager in managers:

	# STEP 1: Check nodes for OS Compatibilty
	pruned_GN_Nodes = gemini_util.pruneNodes(GN_Nodes,my_manager,'GN',LOGFILE,debug)
	if (len(pruned_GN_Nodes) == 0):
		msg = "No GN Nodes that monitor MP Nodes at  AM = "+my_manager+" present. Continuing with the next AM if available"
		gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
		continue
	if (len(pruned_GN_Nodes) > 1):
		msg = "Multiple GN Nodes that monitor MP Nodes at AM = "+my_manager+" present . This is not supported yet"
		gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
		sys.exit(1)

	pruned_MP_Nodes = gemini_util.pruneNodes(MP_Nodes,my_manager,'',LOGFILE,debug)

	# This lock will also install sftware needed for Passive measurements on GN which cannot be done in parallel
	# with any other operations
	(status,msg) = gemini_util.lock_unlock_MC(pruned_GN_Nodes[0],"install_lock",LOGFILE,pKey,debug)
	if(not status):
		msg = msg + "\nConfiguring next AM if available"
		gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
		continue
	else:
		gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)

	# This lock will just set a flag on the GN to indicate the beginning of the configuration process
	(status,msg) = gemini_util.lock_unlock_MC(pruned_GN_Nodes[0],"instrument_lock",LOGFILE,pKey,debug)
	if(not status):
		msg = msg + "\nConfiguring next AM if available"
		gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
		continue
	else:
		gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)

	(status,msg) = gemini_util.update_Drupaladmin_acctinfo(pruned_GN_Nodes[0],LOGFILE,pKey,debug)
	if(not status):
		msg = msg + "\nERROR @ {"+my_manager+"} :: Problem updating  Drupal Admin AccInfo\nYour Gemini configuration will not work\nPlease abort and contact GEMINI Dev Team for help\n"
		gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
		sys.exit(1)

	msg = "Installing and configuring MP Nodes for Passive Measurements"
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	gemini_util.InstallMP_Passive (pruned_MP_Nodes,pruned_GN_Nodes[0],debug,LOGFILE,pKey)
	msg = "Starting Passive Measurements Data Collection for MP Nodes"
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	(status,msg) = gemini_util.startStatscollection(pruned_GN_Nodes[0],LOGFILE,pKey,debug )
	if(not status):
		msg = msg + "\nERROR @ {"+my_manager+"} :: Problem starting Passive measurement data collection\nYour Gemini configuration will not work\nPlease abort and contact GEMINI Dev Team for help\n"
		gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
		sys.exit(1)
	gemini_util.do_netflow_stuff(pruned_GN_Nodes[0],'init',LOGFILE,pKey,debug)
#	gemini_util.do_netflow_stuff(pruned_GN_Nodes[0],'start',LOGFILE,keyfile,debug)
	gemini_util.vnc_passwd_create(pruned_MP_Nodes,pruned_GN_Nodes[0],LOGFILE,pKey,debug)
	gemini_util.drupal_account_create(pruned_GN_Nodes[0],LOGFILE,pKey,debug)

	msg = "Generating and installing certificates"
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	if(not gemini_util.DISABLE_ACTIVE):
		gemini_util.install_GN_Certs(pruned_GN_Nodes,pKey,slice_lifetime,slice_uuid,LOGFILE,debug)
		gemini_util.install_MP_Certs(pruned_MP_Nodes,pKey,slice_lifetime,slice_uuid,LOGFILE,debug)
	gemini_util.install_irods_Certs(pruned_GN_Nodes,pKey,slice_lifetime,LOGFILE,debug)

	if(not gemini_util.DISABLE_ACTIVE):
		msg = "Creating BLiPP service configurations, sending to UNIS"
		gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
		gemini_util.createBlippServiceEntries(pruned_MP_Nodes,pruned_GN_Nodes[0],slice_uuid,LOGFILE,debug)

		msg = "Installing and configuring MP Nodes for Active Measurements"
		gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
		gemini_util.install_Active_measurements(pruned_MP_Nodes,pruned_GN_Nodes[0],USERURN,SLICEURN,slice_uuid,LAMPCERT,LOGFILE,pKey,debug)

	gemini_util.initialize_Drupal_menu(pruned_GN_Nodes[0],LOGFILE,pKey,debug)
	# Unlock the GN
	(status,msg) = gemini_util.lock_unlock_MC(pruned_GN_Nodes[0],"instrument_unlock",LOGFILE,pKey,debug)
	if(not status):
		msg = msg + "\nERROR @ {"+my_manager+"} :: Problem unlocking\nYour Gemini configuration will not work\nPlease abort and contact GEMINI Dev Team for help\n"
		gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
		sys.exit(1)
	DONE=1


os.remove(gemini_util.PROXY_CERT)
os.remove(gemini_util.PROXY_KEY)
if(DONE):
	msg = "Gemini Instrumentize Complete\n Go to the GeniDesktop to login"
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
