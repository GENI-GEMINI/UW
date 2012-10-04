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
import pwd
import getopt
import os
import time
import re
import xmlrpclib
from M2Crypto import X509
import urllib
from xml.dom.minidom import parse, parseString, Node
import xml.parsers.expat
import string
import hashlib
import gemini_util	# Import user defined routines

USE_VIRTUAL_MC=None
other_details = ""
managers_to_monitor = []
my_managers = []

def Usage():
        print "usage: " + sys.argv[ 0 ] + " [option...]"
        print """Options:
    -d, --debug                         be verbose about XML methods invoked
    -f file, --certificate=file         read SSL certificate from file
                                            [default: ~/.ssl/encrypted.pem]
    -h, --help                          show options and usage
    -l uri, --sa=uri                    specify uri of slice authority
                                            [default: local]"""
        if "ACCEPTSLICENAME" in globals():
            print """    -n name, --slicename=name           specify human-readable name of slice
                                            [default: mytestslice]"""
        print """    -p file, --passphrase=file          read passphrase from file
                                            [default: ~/.ssl/password]"""



execfile( "test-common.py" )
LOCALTIME = time.strftime("%Y%m%dT%H:%M:%S",time.localtime(time.time()))
LOGFILE = "logs/instrumentize-"+SLICENAME+"_"+LOCALTIME+".log"
(CERT_ISSUER,username)=(cert.get_subject().OU).split(".",1)
keyfile=""
passphrase = ""
gemini_util.ensure_dir(LOGFILE)

#
# Get a credential for myself, that allows me to do things at the SA.
#

mycredential = get_self_credential()
msg = "Got my SA credential"
gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)


#
# Lookup slice.
#
params = {}
params["credential"] = mycredential
params["type"]       = "Slice"
params["hrn"]        = SLICENAME
rval,response = do_method("sa", "Resolve", params)
if rval:
    Fatal("No such slice at SA");
    pass
else:
    #
    # Get the slice credential.
    #
	myslice = response["value"]
	gemini_util.write_to_log(LOGFILE,str(myslice),gemini_util.dontprinttoscreen,debug)
	your_cms = myslice["component_managers"]
	if(len(your_cms) == 0):
		msg = "This Slice has no slivers to instrumentize "
		gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
		sys.exit(1)
	msg = "This Slice spans these CMs "+str(your_cms)
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	msg = "Asking for slice credential for " + SLICENAME
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	slicecred = get_slice_credential( myslice, mycredential )
	msg = "Got the slice credential"
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	pass

#Stripped_slice_cred
SLICECRED_FOR_LAMP = slicecred.replace('<?xml version="1.0" encoding="UTF-8" standalone="no"?>','',1).lstrip()

#
# Get my email address
#
params = {}
params["hrn"] = username
params["credential"] = mycredential
params["type"]       = "User"
rval,response = do_method("sa", "Resolve", params)
if rval:
    Fatal("Could not resolve " + params[ "hrn" ] )
    pass
print "Found user record at the SA"
if debug: print str(response)
email_id = response["value"]["email"]
USERURN = response["value"]["urn"]
msg = "Your user account details obtained are: "+\
		"\nUsername		: "+username+\
		"\nUserURN		: "+USERURN+\
		"\nEmail ID		: "+email_id+\
		"\nCertificate Issuer	: "+CERT_ISSUER
gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)

#
# Ask the clearinghouse for a list of component managers. 
#
params = {}
params["credential"] = mycredential
rval,response = do_method("ch", "ListComponents", params)
if rval:
	Fatal("Could not get a list of components from the ClearingHouse")
	pass

#
# Ask each manager for its list
# and check again the CM's used in the rspec
# This is another pre-check on the rspec supplied.
#
msg = "\n***************************************\n* List of CM registerd at the Clearing House *\n***************************************\n"
gemini_util.write_to_log(LOGFILE,msg,gemini_util.dontprinttoscreen,debug)
for manager in response["value"]:
	msg = manager["hrn"] + "[" + manager[ "urn" ] + "]: " + manager["url"]
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.dontprinttoscreen,debug)
	if (manager["urn"] in your_cms):
			my_managers.append(manager)
	pass
if (len(my_managers) == 0 ):
	Fatal("You do not have any resources to instrumentize\n OR \nComponent Managers used in the request rspec no longer exist\nPlease check your original experiment and contact your site Admins")

# Give a choice to instrumentize all or part of the topology if it spans more than one CM
if (len(my_managers) > 1 ):
	my_managers = gemini_util.CM_Choices(my_managers,"add")

#Now for each CM do all of this
for my_manager in my_managers:

	CM_URN = my_manager["urn"]
	CM_URI = my_manager["url"]
	CM_HRN = my_manager["hrn"]
	AM_URI = my_manager["am_uri"] = gemini_util.get_AM_URI(CM_URI)

	msg = "Talking to CM HRN = "+CM_HRN
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)

	#
	# Get the sliver status from this AM
	#
	params = [SLICEURN, [slicecred]]
	try:
		response = do_method("am", "SliverStatus", params,URI=AM_URI,version="1.0",response_handler=geni_am_response_handler)
		if(response["geni_status"] != "ready"):
			msg = "Your Slivers at "+AM_URI+" is not ready.\nPlease wait for it to be ready and then try to instrument your slice...."
			gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
			sys.exit()
	except xmlrpclib.Fault, e:
		Fatal("Could not get sliver status: %s" % (str(e)))

	#
	# Obtain Manifest from this AM
	#
	options = {}
	options["geni_slice_urn"] = SLICEURN
	params = [[slicecred], options]
	try:
		response = do_method("am", "ListResources", params,URI=AM_URI,version="1.0",response_handler=geni_am_response_handler)
		my_manager["manifest"] = response
		my_manager["manifest_dom"] = parseString(my_manager["manifest"])
		my_manager["manifest_version"] = gemini_util.getRspecVersion(my_manager["manifest_dom"])
	except xmlrpclib.Fault, e:
		Fatal("Could not get a list of resources: %s" % (str(e)))



	# Obtain the advertisement rspec from this AM
	# Will extract the location info and use it to annotate manifest later
	options = {}
	params = [[mycredential], options]
	try:
		response = do_method("am", "ListResources", params,URI=AM_URI,version="1.0",response_handler=geni_am_response_handler)
		AM_Resources = response
		Resources_dom = parseString(AM_Resources)
		#get Rspec Version
		am_resources_rspec_version = gemini_util.getRspecVersion(Resources_dom)
		Nodes_in_Resources = Resources_dom.getElementsByTagName('node')
		resources_node_count = Nodes_in_Resources.length
		AM_Resources_location = {}
		for i in range(0,resources_node_count):
			AM_Resources_location[gemini_util.get_component_urn_value(am_resources_rspec_version,Nodes_in_Resources.item(i))] = Nodes_in_Resources.item(i).getElementsByTagName('location').item(0)
		pass

		my_manager["node_location_array"] = AM_Resources_location
	except xmlrpclib.Fault, e:
		Fatal("Could not get a list of resources: %s" % (str(e)))



	msg = "\n***************************************\n* Original Manifest for this Topology *\n***************************************\n"+str(my_manager["manifest"])+"\n***************************************\n"
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.dontprinttoscreen,debug)
	
# SSH into each node and check if all node OSes are supported
# 
for my_manager in my_managers:

	msg = "Checking if Nodes at AM --> "+my_manager["am_uri"]+" for \n"+"1. Check if Global Node Present\n2. Find Nodes to be monitored by GEMINI\n3. OS Compatibility of selected Nodes\n"
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	(result,my_manager["GN_sliver_urn"],my_manager["GN_isVirtual"],nodes_sliver_urns,msg) = gemini_util.precheckNodes(my_manager["manifest_dom"],my_manager["manifest_version"],my_manager["urn"],username,keyfile,LOGFILE,debug)
	if(result):
		if(my_manager["GN_sliver_urn"] != ""):
			
			msg = "All nodes at AM --> "+my_manager["am_uri"]+" are GEMINI capable.\nWill proceed with the Instumentize Process\n"
			gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
			my_manager["nodes_sliver_urn"] = nodes_sliver_urns
			managers_to_monitor.append(my_manager)
		else:
			msg = "Nothing to monitor at AM --> "+my_manager["am_uri"]+"\n\n"
			gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
			continue

	else:
		msg = "ERROR @ {"+my_manager["am_uri"]+"} :: "+msg+"\nWill terminate now.\n,"
		gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
		sys.exit(1)

	# Fetching LAMP Cert 
	msg = "Asking for my lamp certificate\n"
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)

	params = {}
	params["credential"] = (slicecred,)
	rval,response = do_method("lamp", "GetLAMPSliceCertificate", params, URI=gemini_util.lampca)
	if rval:
	    Fatal("Could not get ticket: " + response)
	    pass

	LAMPCERT = response["value"]
	if (not LAMPCERT.find("BEGIN RSA PRIVATE KEY") or not LAMPCERT.find("BEGIN CERTIFICATE")):
		msg = "Failed to get valid certificate from LAMP CA. Got \n"+LAMPCERT+"instead\n"
		gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
		sys.exit(1)
	else:
		msg = "Certificate from LAMP CA\n"+LAMPCERT+"\n"
		gemini_util.write_to_log(LOGFILE,msg,gemini_util.dontprinttoscreen,debug)
		my_manager["LAMPCERT"] = LAMPCERT
	pass

	#Sending Manifest to UNIS
	(state,msg) = gemini_util.LAMP_sendmanifest(SLICEURN,my_manager["manifest"],my_manager["LAMPCERT"],SLICECRED_FOR_LAMP,LOGFILE,debug)
	if( not state):
		msg = msg +"\nFailed to send manifest to UNIS\n"
		gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
		sys.exit(1)
	else:
		gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)



# Repeat the loop for each CM
# Create all required directories for the INSTOOLS Code if needed.
# Do all instrumentation stuff here.
# and intrument.
dp_username = "drupal_admin"
dp_passwd = gemini_util.random_password()
m = hashlib.sha1(PassPhraseCB(1))
password = m.hexdigest()
crypt_passwd = gemini_util.generate_crypt_passwd(password,LOGFILE,debug)




for my_manager in managers_to_monitor:

	# Check if GN Node startup scripts have completed
	# If its not yet started, it will do that too.
	(status,msg) = gemini_util.lock_unlock_MC(my_manager["GN_sliver_urn"],"lock",username,LOGFILE,keyfile,debug)
	if(not status):
		msg = msg + "Configuring next AM \n"
		gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
		continue
	else:
		gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)

	annotated_manifest = gemini_util.addNodeLocation(my_manager["manifest_dom"],my_manager["manifest_version"],my_manager["urn"],my_manager["node_location_array"],LOGFILE,debug)
        gemini_util.copy_manifest_to_MC(annotated_manifest,my_manager["GN_sliver_urn"],username,LOGFILE,keyfile,debug )
        gemini_util.send_to_instools_portal(my_manager["GN_sliver_urn"],username,crypt_passwd,password,email_id,my_manager["urn"],my_manager["hrn"],SLICENAME,CERT_ISSUER,LOGFILE,keyfile,debug)
        gemini_util.update_Drupaladmin_acctinfo(my_manager["GN_sliver_urn"],username,dp_username,dp_passwd,LOGFILE,keyfile,debug)
        rval = gemini_util.setupkeys (my_manager["nodes_sliver_urn"],username,my_manager["GN_sliver_urn"],my_manager["GN_isVirtual"], debug, LOGFILE,keyfile)

        gemini_util.startStatscollection(my_manager["urn"],my_manager["hrn"],SLICEURN,USERURN,my_manager["GN_sliver_urn"],username,LOGFILE,keyfile,debug )

        gemini_util.do_netflow_stuff(my_manager["GN_sliver_urn"],'init',username,LOGFILE,keyfile,debug)
#	gemini_util.do_netflow_stuff(my_manager["GN_sliver_urn"],'start',username,LOGFILE,keyfile,debug)
#       gemini_util.check_netflow_data_generated(my_manager["GN_sliver_urn"],username,LOGFILE,keyfile,debug)


        gemini_util.send_polldata_file(my_manager["GN_sliver_urn"],username,crypt_passwd,LOGFILE,keyfile,debug)
        gemini_util.vnc_passwd_create(my_manager["nodes_sliver_urn"],my_manager["GN_sliver_urn"],username,LOGFILE,keyfile,debug)
        gemini_util.drupal_account_create(my_manager["GN_sliver_urn"],username,password,email_id,dp_username,dp_passwd,LOGFILE,keyfile,debug)

	#Do all active measurement stuff
        gemini_util.install_Active_measurements(my_manager["nodes_sliver_urn"],my_manager["GN_sliver_urn"],username,USERURN,SLICEURN,my_manager["LAMPCERT"],LOGFILE,keyfile,debug)

        gemini_util.initialize_Drupal_menu(my_manager["GN_sliver_urn"],username,SLICENAME,dp_username,dp_passwd,LOGFILE,keyfile,debug)
	# Unlock the GN
	(status,msg) = gemini_util.lock_unlock_MC(my_manager["GN_sliver_urn"],"unlock",username,LOGFILE,keyfile,debug)
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)

	pass

if(len(managers_to_monitor) > 0):
	msg = "Drupal passwd for admin is "+dp_passwd
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.dontprinttoscreen,debug)
	# Provide user information needed to login to GEMINI PORTAL
	msg = "Visit https://geminiportal.netlab.uky.edu and fill out the requested information for a complete View of your Network Topology. \nYour Portal login details are\nUsername : "+username+"\nPassword : "+password+" \nEmail Address : "+email_id+"\nCertificate Issuer	: "+CERT_ISSUER+"\nSlicename : "+SLICENAME+"\n" 
	gemini_util.write_to_log(LOGFILE,msg,gemini_util.printtoscreen,debug)
	pass
