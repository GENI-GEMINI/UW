import os
import sys
import subprocess

CSRCONF_FILENAME="/tmp/csr.conf"
TEMP_REQFILE="proxy.csr"

CSRCONF = '''
[ req ]
  distinguished_name = req_distinguished_name

[ req_distinguished_name ]

[ v3_proxy ]
  basicConstraints=CA:FALSE
  authorityKeyIdentifier=keyid,issuer:always
  proxyCertInfo=critical,language:id-ppl-anyLanguage,pathlen:0
'''

CMD_ISSUER_SUBJECT = '''
openssl x509 -noout -in %s -subject
'''

CMD_CERT_REQUEST = '''
openssl req -new -nodes -keyout %s -out %s -newkey rsa:%d -subj \"%s\"
'''

CMD_CREATE_PROXY = '''
openssl x509 -req -CAcreateserial -in %s -days %d -out %s -CA %s -CAkey %s -extfile %s -extensions v3_proxy
'''


def make_proxy_cert(icert, ikey, pcert, pkey, bits, lifetime):
    try:
        with open(CSRCONF_FILENAME) as f: pass
    except IOError as e:
        f = open(CSRCONF_FILENAME, 'w')
        f.write(CSRCONF)
        f.close()

    cmd_subj = CMD_ISSUER_SUBJECT % icert    
    process = subprocess.Popen(cmd_subj, shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = process.communicate()
    process.wait()    
    issuer_subject = out.split("subject= ")[1].strip('\n')

    cmd_req = CMD_CERT_REQUEST % (pkey, TEMP_REQFILE, bits, issuer_subject)
    process = subprocess.Popen(cmd_req, shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = process.communicate()
    process.wait()
    
    cmd_req = CMD_CREATE_PROXY % (TEMP_REQFILE, lifetime, pcert, icert, ikey, CSRCONF_FILENAME)
    process = subprocess.Popen(cmd_req, shell=True, stdout=subprocess.PIPE, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    (out, err) = process.communicate()
    process.wait()

    try:
        with open(icert) as f:
            d = open(pcert, 'a')
            found = False
            for line in f:
                if (found or "BEGIN CERTIFICATE" in line):
                    found = True
                    d.write(line)
            d.close()
            f.close()
    except IOError as e:
        print "Could not open issuer certificate!"
        exit(1)

    os.remove(TEMP_REQFILE)
