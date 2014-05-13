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
import json
import datetime
import gemini_util	# Import user defined routines
import multiprocessing
import argparse
from os.path import expanduser

def InstrumentizeProcess(my_manager,pruned_GN_Nodes,pruned_MP_Nodes,pKey,gn_ms_proxycert_file,gn_ms_proxykey_file,mp_blipp_proxycert_file,mp_blipp_proxykey_file,USERURN,email_id,SLICEURN,slice_uuid,unis_topo,q):

	# This lock will also install sftware needed for Passive measurements on GN which cannot be done in parallel
	# with any other operations
	(status,msg) = gemini_util.lock_unlock_MC(pruned_GN_Nodes[0],"install_lock",pKey)
	if(not status):
		msg = msg + "\nConfiguring next AM if available"
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
		q.put("done_flag")
		return
	else:
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)

	# This lock will just set a flag on the GN to indicate the beginning of the configuration process
	(status,msg) = gemini_util.lock_unlock_MC(pruned_GN_Nodes[0],"instrument_lock",pKey)
	if(not status):
		msg = msg + "\nConfiguring next AM if available"
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
		q.put("done_flag")
	else:
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)

	(status,msg) = gemini_util.update_Drupaladmin_acctinfo(pruned_GN_Nodes[0],pKey)
	if(not status):
		msg = msg + "\nERROR @ {"+my_manager+"} :: Problem updating  Drupal Admin AccInfo\nYour Gemini configuration will not work\nPlease abort and contact GEMINI Dev Team for help\n"
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
		sys.exit(1)

	msg = "Installing and configuring MP Nodes for Passive Measurements at "+my_manager
	gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	gemini_util.InstallMP_Passive (pruned_MP_Nodes,pruned_GN_Nodes[0],pKey)
	msg = "Starting Passive Measurements Data Collection for MP Nodes at "+my_manager
	gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	(status,msg) = gemini_util.startStatscollection(pruned_GN_Nodes[0],pKey)
	if(not status):
		msg = msg + "\nERROR @ {"+my_manager+"} :: Problem starting Passive measurement data collection\nYour Gemini configuration will not work\nPlease abort and contact GEMINI Dev Team for help\n"
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
		sys.exit(1)
	gemini_util.do_netflow_stuff(pruned_GN_Nodes[0],'init',pKey)
#	gemini_util.do_netflow_stuff(pruned_GN_Nodes[0],'start',keyfile)
	gemini_util.vnc_passwd_create(pruned_MP_Nodes,pruned_GN_Nodes[0],pKey)
	gemini_util.drupal_account_create(pruned_GN_Nodes[0],pKey)

	if(not gemini_util.DISABLE_ACTIVE):
		msg = "Installing Proxy Certificates for nodes at "+my_manager
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
		gemini_util.install_GN_Certs(pruned_GN_Nodes,pKey,gn_ms_proxycert_file,gn_ms_proxykey_file)
		gemini_util.install_MP_Certs(pruned_MP_Nodes,pKey,mp_blipp_proxycert_file,mp_blipp_proxykey_file)

	if(not gemini_util.DISABLE_ACTIVE):
		msg = "Creating BLiPP service configurations, sending to UNIS for nodes at "+my_manager
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
		gemini_util.createBlippServiceEntries(pruned_MP_Nodes,pruned_GN_Nodes[0],unis_topo[my_manager],slice_uuid)

		msg = "Installing and configuring MP Nodes for Active Measurements at "+my_manager
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
		#gemini_util.install_Active_measurements(pruned_MP_Nodes,pruned_GN_Nodes[0],USERURN,SLICEURN,slice_uuid,unis_topo[my_manager],LAMPCERT,pKey)
		gemini_util.install_Active_measurements(pruned_MP_Nodes,pruned_GN_Nodes[0],USERURN,SLICEURN,slice_uuid,unis_topo[my_manager],pKey)
	gemini_util.initialize_Drupal_menu(pruned_GN_Nodes[0],pKey)

	# This is just to make sure we have the right user info who instrumented the slice
	# A scenario  here is in case of a shared slice where one user initializes the slice and another instruments it.
	(result,msg) = gemini_util.dump_Expinfo_on_GN(pruned_GN_Nodes[0],USERURN,email_id,'','','','','','',pKey)

	# Unlock the GN
	(status,msg) = gemini_util.lock_unlock_MC(pruned_GN_Nodes[0],"instrument_unlock",pKey)
	if(not status):
		msg = msg + "\nERROR @ {"+my_manager+"} :: Problem unlocking\nYour Gemini configuration will not work\nPlease abort and contact GEMINI Dev Team for help\n"
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
		sys.exit(1)
	return




def main(argv=None):

	#############################################
	# MAIN PROCESS
	#############################################
	other_details = ""
	managers = []
	GN_Nodes = []
	MP_Nodes = []
	keyfile = ""
	force_refresh = False
	FILE = ''
	SLICEURN = ''
	AMURNS = ''
	email_id = ''
	DONE=0
	
	gn_ms_proxycert_file = None
	gn_ms_proxykey_file= None
	mp_blipp_proxycert_file = None
	mp_blipp_proxykey_file = None


	parser = argparse.ArgumentParser(description='Print Experiment state summary for GeniDesktop in JSON Format')
	parser.add_argument('-d','--debug',action='store_true',help='Be Verbose')
	parser.add_argument('--devel',action='store_true',help='Use Development version of GEMINI repository code [only for GEMINI developers]')
	parser.add_argument('--force_refresh',action='store_true',help='Force fetch all user/slice/sliver info rather than using locally cached version')
	parser.add_argument('--disable_active',action='store_true',help='Disable IU Active Measurement Install')
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

	if (args.disable_active):
		print "User requested to disable Active Measurements setup"
		gemini_util.DISABLE_ACTIVE = True

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
	expiry = SliceInfo['expires']
	slice_uuid = SliceInfo['uuid']

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

	if(not gemini_util.DISABLE_ACTIVE):
		msg = "Registering Slice with UNIS and posting Manifests to UNIS"
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
		REGUNISJSON = gemini_util.register_experiment_with_UNIS(slice_crypt,user_crypt)
		try:
			REGUNISOBJ = json.loads(REGUNISJSON)
			gemini_util.write_to_log(REGUNISJSON,gemini_util.dontprinttoscreen)
		except ValueError:
			msg ="REGUNIS Info JSON Loading Error"
			gemini_util.write_to_log(msg,gemini_util.printtoscreen)
			sys.exit(1)

		if (REGUNISOBJ['code'] != 0):
			msg = "GeniDesktop to UNIS registration Error : "+ REGUNISOBJ['output']
			gemini_util.write_to_log(msg,gemini_util.printtoscreen)
			msg = "Active Services will be disabled to continue with the Instrumentation process"
			gemini_util.write_to_log(msg,gemini_util.printtoscreen)
			gemini_util.DISABLE_ACTIVE = True

	if(not gemini_util.DISABLE_ACTIVE):
		slice_lifetime = {}
		if (slice_uuid):
			expiration = datetime.datetime.strptime(expiry,"%Y-%m-%dT%H:%M:%SZ")
			now = datetime.datetime.now(expiration.tzinfo)
			td = expiration - now
			slice_lifetime = int(td.seconds + td.days * 24 * 3600)
			validity = datetime.timedelta(seconds=slice_lifetime)
			# adding 30 days lifetime to avoid GEMINI proxy cert expiration for most experimenters
			slice_lifetime = validity.days + 30
			#Now setup a proxy cert for the instrumentize script so we can talk to UNIS without keypass
			gemini_util.makeInstrumentizeProxy(slice_lifetime,slice_uuid)
			if not (gemini_util.PROXY_ATTR):
				msg = "ERROR: Could not complete proxy certificate creation for instrumentize process"
				gemini_util.write_to_log(msg,gemini_util.printtoscreen)
				msg = "Active Services will be disabled to continue with the Instrumentation process"
				gemini_util.write_to_log(msg,gemini_util.printtoscreen)
				gemini_util.DISABLE_ACTIVE = True

			#Send the proxy cert to UNIS so we can use this identity to query UNIS later
			f = open(gemini_util.PROXY_ATTR)
			res = gemini_util.postDataToUNIS(gemini_util.PROXY_KEY,gemini_util.PROXY_CERT,"/credentials/geniuser",f)
			f.close()
			os.remove(gemini_util.PROXY_ATTR)
			if res is None:
				msg="Failed to register instrumentize proxy cert"
				gemini_util.write_to_log(msg,gemini_util.printtoscreen)
				msg = "Active Services will be disabled to continue with the Instrumentation process"
				gemini_util.write_to_log(msg,gemini_util.printtoscreen)
				gemini_util.DISABLE_ACTIVE = True
	
	
		else:
			msg = "Could not get slice UUID from slice credential. GEMINI Services may fail."
			gemini_util.write_to_log(msg,gemini_util.printtoscreen)
			sys.exit(1)
 
		(gn_ms_proxycert_file,gn_ms_proxykey_file,mp_blipp_proxycert_file,mp_blipp_proxykey_file) = gemini_util.generate_all_proxycerts(slice_lifetime,slice_uuid)



	proclist = []
	results = []
	unis_topo = {}
	for my_manager in managers:	

		msg =  "Starting instrumentize process for Nodes at "+my_manager
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)

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

		endpoint = "/domains/%s" % (my_manager.replace('urn:publicid:IDN+','').replace('+authority+cm','')+'+slice+'+gemini_util.SLICENAME).replace('+','_')
		if(not gemini_util.DISABLE_ACTIVE):
			unis_topo[my_manager] = gemini_util.getUNISTopo(gemini_util.PROXY_KEY,gemini_util.PROXY_CERT,endpoint)

		my_queue = multiprocessing.Queue()
		p = multiprocessing.Process(target=InstrumentizeProcess,args=(my_manager,pruned_GN_Nodes,pruned_MP_Nodes,pKey,gn_ms_proxycert_file,gn_ms_proxykey_file,mp_blipp_proxycert_file,mp_blipp_proxykey_file,USERURN,email_id,SLICEURN,slice_uuid,unis_topo,my_queue,))
		proclist.append(p)
		results.append(my_queue)
		p.start()                                                                                                                      

	#while(True):
	#	pending_proclist = []
	#	for i in proclist:
	#		if(i.exitcode is None):
	#			pending_proclist.append(i)
	#			continue
	#		elif(i.exitcode != 0):
	#			sys.exit(i.exitcode)
	#		else:
	#			continue
	#	if not pending_proclist:
	#		break
	#	else:
	#		proclist = pending_proclist
	#	time.sleep(5)
	#	pass


	for i in proclist:
		i.join()
		if(i.exitcode != 0):
			sys.exit(i.exitcode)

	for result in results:
		if(result.empty()):
			DONE = 1


	if(not gemini_util.DISABLE_ACTIVE):
		tmp_proxyfiles = [gemini_util.PROXY_CERT,gemini_util.PROXY_KEY,gn_ms_proxycert_file,gn_ms_proxykey_file,mp_blipp_proxycert_file,mp_blipp_proxykey_file]
		status = gemini_util.delete_all_temp_proxyfiles(tmp_proxyfiles)
	if(DONE):
		msg = "Gemini Instrumentize Complete\n Go to the GeniDesktop to login"
		gemini_util.write_to_log(msg,gemini_util.printtoscreen)
	gemini_util.closeLogPIPE(LOGFILE)




if __name__ == "__main__":
  sys.exit(main())



