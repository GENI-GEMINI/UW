#!/usr/bin/python

import os
import sys
import shutil
import subprocess
import gemini_util
import tempfile

# writes once, doesn't change
CSRCONF_FILENAME="/tmp/csr.conf"

CSRCONF = '''
[ req ]
  default_bits       = 1024
  distinguished_name = req_distinguished_name
  encrypt_rsa_key    = no
  default_md         = md5

[ req_distinguished_name ]

[ v3_proxy ]
  basicConstraints=CA:FALSE
  authorityKeyIdentifier=keyid,issuer:always
  proxyCertInfo=critical,language:id-ppl-independent,pathlen:0
'''

CMD_ISSUER_SUBJECT = '''
openssl x509 -noout -in %s -subject
'''

CMD_CERT_REQUEST = '''
openssl req -new -config %s -keyout %s -out %s -subj \"%s/CN=%s\"
'''

CMD_CREATE_PROXY = '''
openssl x509 -passin stdin -req -CAcreateserial -in %s -days %d -out %s -CA %s -CAkey %s -extfile %s -extensions v3_proxy
'''

CMD_CREATE_ATTR = '''
cd /tmp/; creddy --attribute --issuer %s --key %s --role %s --subject-cert %s --out %s
'''

def make_proxy_cert(icert, ikey, pcert, pkey, CN, lifetime, PASSPHRASE):
    TEMP_REQFILE = tempfile.NamedTemporaryFile(delete=True)

    try:
        with open(CSRCONF_FILENAME) as f: pass
    except IOError as e:
        f = open(CSRCONF_FILENAME, 'w')
        f.write(CSRCONF)
        f.close()
    if ((PASSPHRASE is None) or not len(PASSPHRASE)):
        PASSPHRASE = "\n"

    cmd_subj = CMD_ISSUER_SUBJECT % icert    
    process = subprocess.Popen(cmd_subj, shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = process.communicate()
    issuer_subject = out.split("subject= ")[1].strip('\n')

    cmd_req = CMD_CERT_REQUEST % (CSRCONF_FILENAME, pkey, TEMP_REQFILE.name, issuer_subject, CN)
    process = subprocess.Popen(cmd_req, shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = process.communicate()
    
    cmd_proxy = CMD_CREATE_PROXY % (TEMP_REQFILE.name, lifetime, pcert, icert, ikey, CSRCONF_FILENAME)
    process = subprocess.Popen(cmd_proxy, shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = process.communicate(input=PASSPHRASE)

    # complete the certificate chain from the user's cert
    # but make sure to throw away the private key
    try:
        with open(icert) as f:
            mark = False
            d = open(pcert, 'a')
            for line in f:
                if ("BEGIN RSA PRIVATE KEY" in line):
                    mark = True
                if ("END RSA PRIVATE KEY" in line):
                    mark = False
                    continue
                if not mark:
                    d.write(line)
            d.close()
            f.close()
    except IOError as e:
        print "Could not open issuer certificate!"
        sys.exit(1)

    TEMP_REQFILE.close()


def make_attribute_cert(icert, ikey, scert, role, outcert, PASSPHRASE):

    state = True
    msg = None

    cmd_attr = CMD_CREATE_ATTR % (icert, ikey, role, scert, outcert)
    process = subprocess.Popen(cmd_attr, shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = process.communicate(input=str(PASSPHRASE))

    try:
        check = out.index("Enter passphrase for privateKey from file:")
    except ValueError:
        if not len(out) and not len(err):
            pass
        else:
            msg = "Creddy could not create attribute certificate"
            state = False

    return state, msg

def __test():
    import optparse
    
    usage = "%prog [options]"
    desc = "proxy and attribute cert test"
    
    parser = optparse.OptionParser(usage=usage, description=desc)
    parser.add_option("-c", "--cert", dest="icert", default="~/.ssl/encrypted.pem", help="user (issuer) certificate")
    parser.add_option("-k", "--key", dest="ikey", default="~/.ssl/encrypted.pem", help="user (issuer) key")
    parser.add_option("-s", "--scert", dest="scert", default=None, help="subject cert (e.g. proxy cert)")
    parser.add_option("-a", "--attribute", dest="attr", action="store_true", help="make an attribute certificate")
    parser.add_option("-r", "--role", dest="role", default=None, help="role to assign")
    parser.add_option("-l", "--lifetime", dest="lt", default=7, help="certificate lifetime (default=%default)")
    parser.add_option("-o", "--certout", dest="outcert", default=None, help="name of output certificate")
    parser.add_option("-u", "--keyout", dest="outkey", default=None, help="name of output key file")
    parser.add_option("-n", "--cn", dest="cn", default="12345678", help="common name to append to proxy subject")
    options, args = parser.parse_args(sys.argv[1:])

    from M2Crypto.util import passphrase_callback
    passphrase = str(passphrase_callback(1, "Enter passphrase:", "Verify passphrase:"))
    
    if options.attr and options.role and options.scert and options.outcert:
        make_attribute_cert(options.icert, options.ikey, options.scert, options.role, options.outcert, passphrase)
        
    if (not options.attr) and options.outcert and options.outkey:
        make_proxy_cert(options.icert, options.ikey, options.outcert, options.outkey, options.cn, options.lt, passphrase)

if __name__ == "__main__":
    __test()

