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
import hashlib
import json
import multiprocessing
import gemini_util	# Import user defined routines

other_details = ""
managers = []
jsonresult = {}
GN_Nodes = []
MP_Nodes = []
keyfile = ""
force_refresh = '1'
FILE = ''


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
    -j file, --loadFromFile=file        read all experiemnt info from File
							[To be used by GENI Desktop only]
    -r PROJECT, --project=PROJECT	Name of project. (For use with portal framework.)
    -p file, --passphrase=file          read passphrase from file
                                            [default: ~/.ssl/password]"""

def opStatusProcess(Node,queue):
	global pKey

	(init_status,ret_code,err_msg) = gemini_util.getLockStatus(Node,pKey)
	if(ret_code == -1 ):
		msg = "SSH_ERROR - "+err_msg
       		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
		queue.put(msg)
		sys.exit(1)

	if(init_status == ""):
		init_status = "NEW"
	elif(not init_status.startswith('IN')):
       		gemini_util.write_to_log(init_status,gemini_util.printtoscreen)
		queue.put(init_status)
		sys.exit(1)
		

	queue.put([Node['nodeid'],init_status])
	return  

try:
    opts, REQARGS = getopt.gnu_getopt( sys.argv[ 1: ], "dhxk:f:n:j:p:r:",
                                   [ "debug","help","no_force_refresh","pkey=","certificate=",
                                     "slicename=","loadFromFile=",
                                     "passphrase=","project="] )
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
		LOGFILE = mylogbase+"/gdesktop-opstatus-"+LOCALTIME+".log"
		gemini_util.ensure_dir(LOGFILE)
		gemini_util.openLogPIPE(LOGFILE)
    elif opt in ( "-p", "--passphrasefile" ):
        gemini_util.PASSPHRASEFILE = arg
    elif opt in ( "-j", "--loadFromFile" ):
        FILE = arg
	# check if FILE exists
	if(not os.path.isfile(FILE)):
		print "Please provide a Slice/Exp Info File Name. (To be run only by the GENI Desktop)"
		Usage()
		sys.exit(1)
	else:
		f = open(FILE,'r')
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
        gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	sys.exit(1)

# Check if passphrase provided for certificate is valid
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
	framework = UserInfo['framework']
#	CERT_ISSUER = UserInfo['certificate_issuer']
else:
	msg = "User not identified : "+ UserOBJ['output']
        gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	sys.exit(1)
msg = "Found User Info for "+USERURN
gemini_util.write_to_log(msg,gemini_util.printtoscreen)
my_sliceurn = gemini_util.getSliceURN(framework,USERURN,gemini_util.SLICENAME,project)
if (FILE):
	msg = "Fetching Slice Info from the Cache"
	gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	SliceJSON = f.readline()
else:
	msg = "Fetching Slice Info from the GeniDesktop Parser"
	gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	SliceJSON = gemini_util.getSliceinfoFromParser(user_crypt,my_sliceurn)
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
	NodesOBJ = json.loads(NodesJSON.strip())
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
	jsonresult["status"] = "ERROR"
	jsonresult["details"] = "NO MANIFEST PRESENT"
	print json.dumps(jsonresult)
	sys.exit(0)

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


if(not FILE):
	# Save all jsons to cache
	cachefilename = gemini_util.getCacheFilename(CERT_ISSUER,username,gemini_util.SLICENAME)
	gemini_util.ensure_dir(cachefilename)
	f = open(cachefilename, 'w')
	f.write(UserJSON.strip()+"\n")
	f.write(SliceJSON.strip()+"\n")
	f.write(NodesJSON.strip())
	f.close


details = {}
result = {}

if (len(GN_Nodes) == 0):
	msg = "No GN Nodes Present. Will not proceed"
        gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	jsonresult["status"] = "ERROR"
	jsonresult["details"] = "NO GLOBAL NODE PRESENT"
else:
	proclist = []
	results = []
	for Node in GN_Nodes:

		result_queue = multiprocessing.Queue()
		p = multiprocessing.Process(target=opStatusProcess,args=(Node,result_queue,))
		proclist.append(p)
		p.start()                                                                                                                      
		results.append(result_queue)
	myexitcode = 0
	for i in proclist:
		i.join()
		if(i.exitcode != 0):
			myexitcode = i.exitcode
	mystates = []
	for result in results:
		if(not result.empty()):
			l = result.get()
			if ((type(l) is str) or (type(l) is unicode)):
				jsonresult['details'] = l
				break
			else:
				sliver_id  = l[0]
				status = l[1]
				mystates.append(status)
				details[sliver_id] = status
				jsonresult['details'] = details
	if (myexitcode != 0 ): 
		jsonresult["status"] = "ERROR"
	else:
		jsonresult['status'] = gemini_util.getStateSummary(mystates)
	gemini_util.closeLogPIPE(LOGFILE)
print json.dumps(jsonresult)

