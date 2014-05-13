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
import argparse
import gemini_util	# Import user defined routines
from os.path import expanduser


def opStatusProcess(GN_Node,MP_Nodes,pKey,slice_crypt,user_crypt,queue):

	# Check if GD has access to these nodes
	# this will also add access automatically if it does not and let us know 
	msg = "Check if GeniDesktop Tool has access to your slivers (and add if needed) at "+GN_Node['gemini_urn_to_monitor']
	gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	(msg,result) = gemini_util.addGDAccesstoSlivers(slice_crypt,user_crypt,GN_Node['gemini_urn_to_monitor'])
	if(not result):
		queue.put(msg)
		sys.exit(1)

	# extensive check performed once on all nodes 
	# split process by filtering nodes based on CM URN
	# grouping GN[cmurn] = MP[cmurn]
	(isdetailcheckRequired,ret_code,err_ssh) = gemini_util.isdetailedProbeRequired(GN_Node,pKey)
	if(ret_code == -1):
		msg = "SSH_ERROR - "+err_ssh
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
		queue.put(msg)
		sys.exit(1)


	if(isdetailcheckRequired):
		gemini_util.precheckNodes(GN_Node,MP_Nodes,pKey)
	pass	


	(init_status,ret_code,err_msg) = gemini_util.getLockStatus(GN_Node,pKey)
	if(ret_code == -1 ):
		msg = "SSH_ERROR - "+err_msg
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
		queue.put(msg)
		sys.exit(1)

	if(init_status == ""):
		init_status = "CREATED"
	elif(not init_status.startswith('IN')):
		gemini_util.write_to_log(init_status,gemini_util.printtoscreen)
		queue.put(init_status)
		sys.exit(1)
		

	queue.put([GN_Node['nodeid'],init_status])
	return  
	


def main(argv=None):

	managers = []
	jsonresult = {}
	GN_Nodes = []
	MP_Nodes = []
	keyfile = ""
	force_refresh = False
	FILE = ''
	SLICEURN = ''
	AMURNS = ''


	parser = argparse.ArgumentParser(description='Print Experiment state summary for GeniDesktop in JSON Format')
	parser.add_argument('-d','--debug',action='store_true',help='Be Verbose')
	parser.add_argument('--devel',action='store_true',help='Use Development version of GEMINI repository code [only for GEMINI developers]')
	parser.add_argument('--force_refresh',action='store_true',help='Force fetch all user/slice/sliver info rather than using locally cached version')
	parser.add_argument('-n','--sliceurn',help='Slice URN of the Slice',required=True)
	parser.add_argument('-a','--amurns',help='Comma seperated list of AM URNs where the user has slivers for this slice')
	parser.add_argument('-k','--pkey',help='Your private SSH RSA Key file')
	parser.add_argument('-f','--certificate',help='Read SSL certificate from file',required=True)
	parser.add_argument('-p','--passphrase',help='Read passphrase for certificate from file')
	

	args = parser.parse_args()

	LOGFILE = None
	project = None

	if (args.debug):
		gemini_util.debug = True

	if (args.devel):
		gemini_util.version = gemini_util.devel_version
	gemini_util.INSTOOLS_repo_url = gemini_util.mc_repo_rooturl+"GEMINI/"+gemini_util.version+"/"

	if (args.force_refresh):
		force_refresh = True

	if (args.amurns):
		result = gemini_util.isValidAMURNs(args.amurns)
		if(result):
			AMURNS = args.amurns
		else:
			print "Invalid AM URNS Provided"
			parser.print_help()
			sys.exit(1)
	
	if(args.certificate):
		if ((args.certificate).startswith('~')):
			gemini_util.CERTIFICATE = (args.certificate).replace('~',expanduser("~"),1)
		else:
			gemini_util.CERTIFICATE = args.certificate

	SLICEURN = args.sliceurn
	print SLICEURN
	if (not gemini_util.isValidURN(SLICEURN,'slice')):
		print "Not a valid SliceURN"
		parser.print_help()
		sys.exit(1)
	(project,gemini_util.SLICENAME) = gemini_util.getSlicename_N_Project(SLICEURN)
	mylogbase = gemini_util.getLOGBASE(SLICEURN)
	LOCALTIME = time.strftime("%Y%m%dT%H:%M:%S",time.localtime(time.time()))
	LOGFILE = mylogbase+"/"+os.path.basename(__file__)+"-"+LOCALTIME+".log"
	gemini_util.ensure_dir(LOGFILE)
	gemini_util.openLogPIPE(LOGFILE)

	if (args.passphrase):
		if((args.passphrase).startswith('~')):
			gemini_util.PASSPHRASEFILE = (args.passphrase).replace('~',expanduser("~"),1)
		else:
			gemini_util.PASSPHRASEFILE = args.passphrase
	if (args.pkey):
		if((args.pkey).startswith('~')):
			keyfile = (args.pkey).replace('~',expanduser("~"),1)
		else:
			keyfile = args.pkey
	if(not (keyfile != '' and os.path.isfile(keyfile))):
		print "Please provide a valid private key file"
		parser.print_help()
		sys.exit(1)
	else:
		SSH_pkey = gemini_util.getPkey(keyfile,"SSH key")

	if (LOGFILE is None):
		print "Please provide a slicename"
		parser.print_help()
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


	(UserInfo,Slices,Nodes) = gemini_util.getMyExpInfo(CERT_ISSUER,username,cf.read(),project,force_refresh,AMURNS)
	cf.close()
	username = UserInfo['uid']
	email_id = UserInfo['email']
	USERURN = UserInfo['userurn']
	user_crypt = UserInfo['user_crypt']
	framework = UserInfo['framework']
	
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
		jsonresult["status"] = "CREATED"
		jsonresult["details"] = "No Resources Present"
		print json.dumps(jsonresult)
		sys.exit(0)
	if(len(Nodes) == 0):
		jsonresult["status"] = "ERROR"
		jsonresult["details"] = "Sliver with No Resources Present.Delete it before continuing."
		print json.dumps(jsonresult)
		sys.exit(0)
  

	for Node in Nodes:
		nodeid = Node['nodeid']
		hostname = Node['hostname']
		ismc = Node['ismc']
		login_hostname = Node['login_hostname']
		if(Node['login_username'] != username):
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

	details = {}
	result = {}

	if (len(GN_Nodes) == 0):
		msg = "No GN Nodes Present. Will not proceed"
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
		jsonresult["status"] = "CREATED"
		jsonresult["details"] = "Has Resources but no Global Node"
	else:
		proclist = []
		results = []
		for GN_Node in GN_Nodes:
			pruned_MP_Nodes = gemini_util.pruneNodes(MP_Nodes,GN_Node['gemini_urn_to_monitor'],'')
			result_queue = multiprocessing.Queue()
			p = multiprocessing.Process(target=opStatusProcess,args=(GN_Node,pruned_MP_Nodes,pKey,slice_crypt,user_crypt,result_queue,))
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


if __name__ == "__main__":
  sys.exit(main())

