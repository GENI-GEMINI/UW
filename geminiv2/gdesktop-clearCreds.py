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
import gemini_util	# Import user defined routines

debug           = 0


def Usage():
        print "usage: " + sys.argv[ 0 ] + " [option...]"
        print """Options:
    -d, --debug                         be verbose about XML methods invoked
    -f file, --certificate=file         read SSL certificate from file
                                            [default: ~/.ssl/encrypted.pem]
    -h, --help                          show options and usage
    -p file, --passphrase=file          read passphrase from file
                                            [default: ~/.ssl/password]"""

try:
    opts, REQARGS = getopt.gnu_getopt( sys.argv[ 1: ],"dhf:p:",[ "debug","help","certificate=","passphrase="] )
except getopt.GetoptError, err:
    print >> sys.stderr, str( err )
    Usage()
    sys.exit( 1 )

args = REQARGS

for opt, arg in opts:
    if opt in ( "-d", "--debug" ):
        debug = 1
    elif opt in ( "-f", "--certificatefile" ):
        gemini_util.CERTIFICATE = arg
    elif opt in ( "-h", "--help" ):
        Usage()
        sys.exit( 0 )
    elif opt in ( "-p", "--passphrasefile" ):
        gemini_util.PASSPHRASEFILE = arg


mylogbase = gemini_util.getLOGBASE()
LOCALTIME = time.strftime("%Y%m%dT%H:%M:%S",time.localtime(time.time()))
LOGFILE = mylogbase+"/gdesktop-clearCreds-"+gemini_util.SLICENAME+"_"+LOCALTIME+".log"
gemini_util.ensure_dir(LOGFILE)

try:
	cf = open(gemini_util.CERTIFICATE,'r')
except:
	msg = "Error opening Certificate"
        gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	sys.exit(1)

# Check if passphrase provided is valid
# If passphrase is not provided prompt for it.
try:
	ctx = M2Crypto.SSL.Context("sslv23")
	ctx.load_cert(gemini_util.CERTIFICATE,gemini_util.CERTIFICATE,gemini_util.PassPhraseCB)
	(CERT_ISSUER,username) = gemini_util.getCert_issuer_n_username()
except M2Crypto.SSL.SSLError:
	msg = "Invalid passphrase provided"
        gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	sys.exit(1)

msg = "Fetching User Info from the GeniDesktop Parser"
gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
UserJSON = gemini_util.getUserinfoFromParser(cf.read(),gemini_util.passphrase,LOGFILE,debug)
try:
	UserOBJ = json.loads(UserJSON)
except ValueError:
	msg ="User JSON Loading Error"
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	sys.exit(1)

gemini_util.write_to_log(LOGFILE,UserJSON,gemini_util.dontprinttoscreen,debug)
if (UserOBJ['code'] == 0):
	UserInfo = UserOBJ['output']
	username = UserInfo['uid']
	email_id = UserInfo['email']
	USERURN = UserInfo['userurn']
	user_crypt = UserInfo['user_crypt']
#	CERT_ISSUER = UserInfo['certificate_issuer']
else:
	msg = "User not identified : "+ UserOBJ['output']
        gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	sys.exit(1)
msg = "Found User Info for "+USERURN
gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)

msg = "Logging you out from GENIDesktop Parser Compoenent"
gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
JSON = gemini_util.clearUserinfoatParser(user_crypt,LOGFILE,debug)
try:
	OBJ = json.loads(JSON)
except ValueError:
	msg ="JSON Loading Error"
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	sys.exit(1)

gemini_util.write_to_log(LOGFILE,JSON,gemini_util.dontprinttoscreen,debug)
if (OBJ['code'] != 0):
	msg = "Could not clear your info from the Genidesktop Parser : "+ OBJ['output']
        gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	sys.exit(1)
else:
	msg = "Your User info has been sucessfully purged from the Genidesktop Parser"
        gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	sys.exit(0)