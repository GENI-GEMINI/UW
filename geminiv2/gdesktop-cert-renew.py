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
import tempfile
import gemini_util	# Import user defined routines

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
    -r PROJECT, --project=PROJECT	Name of project. (For use with portal framework.)
    -p file, --passphrase=file          read passphrase from file
                                            [default: ~/.ssl/password]"""

try:
    opts, REQARGS = getopt.gnu_getopt( sys.argv[ 1: ], "dhxk:f:n:p:r:",
                                   [ "debug","help","no_force_refresh","pkey=","certificate=",
                                     "slicename=","passphrase=","project="] )
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
    elif opt in ( "-x","--no_force_refresh" ):
        force_refresh = '0'
    elif opt in ( "-r", "--project"):
		project = arg
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
			Usage()
			sys.exit(1)
		else:
			mylogbase = gemini_util.getLOGBASE(gemini_util.SLICENAME)
			LOCALTIME = time.strftime("%Y%m%dT%H:%M:%S",time.localtime(time.time()))
			LOGFILE = mylogbase+"/gdesktop-instrumentize-"+LOCALTIME+".log"
			gemini_util.ensure_dir(LOGFILE)
			gemini_util.openLogPIPE(LOGFILE)
    elif opt in ( "-p", "--passphrasefile" ):
        gemini_util.PASSPHRASEFILE = arg
    elif opt in ( "-k", "--pkey" ):
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

(UserInfo,Slices,Nodes) = gemini_util.getMyExpInfo(CERT_ISSUER,username,cf.read(),project,force_refresh)
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
		found = gemini_util.TRUE
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
                msg = "Your username differs from the username in the manifest. So i will change it the correct one for my use"
                gemini_util.write_to_log(msg,gemini_util.printtoscreen)
                Node['login_username'] = username
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


msg = "Fetching Lamp Certificate and other information from the GeniDesktop Parser"
gemini_util.write_to_log(msg,gemini_util.printtoscreen)
LAMPJSON = gemini_util.getLampCert_n_details_FromParser(slice_crypt,user_crypt)
try:
	LAMPOBJ = json.loads(LAMPJSON)
	gemini_util.write_to_log(LAMPJSON,gemini_util.dontprinttoscreen)
except ValueError:
	msg ="LAMP Info JSON Loading Error"
	gemini_util.write_to_log(msg,gemini_util.printtoscreen)
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
	gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	sys.exit(1)

if(LAMPCERT == ''):
	msg = "Lamp Certificate was Not Found. Some services may not work correctly"
	gemini_util.write_to_log(msg,gemini_util.printtoscreen)


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
	gemini_util.makeInstrumentizeProxy(slice_lifetime,slice_uuid)
	if not (gemini_util.PROXY_ATTR):
		msg = "ERROR: Could not complete proxy certificate creation for instrumentize process"
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
		msg = "Active Services will be disabled to continue with the Instrumentation process"
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
		gemini_util.DISABLE_ACTIVE = gemini_util.TRUE

	# temporary hack to write out an unencrypted keyfile for the slice registration call to UNIS
	TEMP_KEYFILE = gemini_util.getUnencryptedKeyfile(CERT_pkey)
	msg="Registering slice credential with Global UNIS"
	gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	res1 = gemini_util.postDataToUNIS(TEMP_KEYFILE,gemini_util.CERTIFICATE,"/credentials/genislice",slicecred)
	os.remove(TEMP_KEYFILE)
	f = open(gemini_util.PROXY_ATTR)
	res2 = gemini_util.postDataToUNIS(gemini_util.PROXY_KEY,gemini_util.PROXY_CERT,"/credentials/geniuser",f)
	f.close()
	os.remove(gemini_util.PROXY_ATTR)
	if res1 or res2 is None:
		msg="Failed to register slice credential"
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
		msg = "Active Services will be disabled to continue with the Instrumentation process"
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
		gemini_util.DISABLE_ACTIVE = gemini_util.TRUE
else:
	msg = "Could not get slice UUID from slice credential. GEMINI Services may fail."
	gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	sys.exit(1)

gn_ms_proxycert_file = None
gn_ms_proxykey_file= None
mp_blipp_proxycert_file = None
mp_blipp_proxykey_file = None 
irods_proxycert_file = None
(gn_ms_proxycert_file,gn_ms_proxykey_file,mp_blipp_proxycert_file,mp_blipp_proxykey_file,irods_proxycert_file) = gemini_util.generate_all_proxycerts(slice_lifetime,slice_uuid)

lpc = tempfile.NamedTemporaryFile()
cert_file = lpc.name
lpc.write(LAMPCERT)
lpc.flush()
for my_manager in managers:

	# STEP 1: Check nodes for OS Compatibilty
	pruned_GN_Nodes = gemini_util.pruneNodes(GN_Nodes,my_manager,'GN')
	if (len(pruned_GN_Nodes) == 0):
		msg = "No GN Nodes that monitor MP Nodes at  AM = "+my_manager+" present. Continuing with the next AM if available"
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
		continue
	if (len(pruned_GN_Nodes) > 1):
		msg = "Multiple GN Nodes that monitor MP Nodes at AM = "+my_manager+" present . This is not supported yet"
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
		sys.exit(1)

	pruned_MP_Nodes = gemini_util.pruneNodes(MP_Nodes,my_manager,'')

	msg = "Generating and installing certificates"
	gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	if(not gemini_util.DISABLE_ACTIVE):
		gemini_util.install_GN_Certs(pruned_GN_Nodes,pKey,gn_ms_proxycert_file,gn_ms_proxykey_file)
		gemini_util.install_MP_Certs(pruned_MP_Nodes,pKey,mp_blipp_proxycert_file,mp_blipp_proxykey_file)
	gemini_util.install_irods_Certs(pruned_GN_Nodes,pKey,irods_proxycert_file)

	cmd = "sudo cp /var/emulab/boot/lampcert.pem /usr/local/etc/protogeni/ssl/lampcert.pem;"
	for node in pruned_GN_Nodes:
		add_cmd = "sudo /etc/init.d/httpd reload;"
		gemini_util.installLAMPCert(node,pKey,cert_file,cmd+add_cmd)
	
	for node in pruned_MP_Nodes:
		gemini_util.installLAMPCert(node,pKey,cert_file,cmd)

	DONE=1


tmp_proxyfiles = [gemini_util.PROXY_CERT,gemini_util.PROXY_KEY,gn_ms_proxycert_file,gn_ms_proxykey_file,mp_blipp_proxycert_file,mp_blipp_proxykey_file,irods_proxycert_file]
status = gemini_util.delete_all_temp_proxyfiles(tmp_proxyfiles)
if(DONE):
	msg = "Gemini Instrumentize Complete\n Go to the GeniDesktop to login"
	gemini_util.write_to_log(msg,gemini_util.printtoscreen)
gemini_util.closeLogPIPE(LOGFILE)
