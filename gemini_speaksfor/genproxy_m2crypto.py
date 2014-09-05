import time
import sys
from M2Crypto import X509, EVP, RSA, ASN1, SSL

def make_proxy_request(bits, subject):
    pk = EVP.PKey()
    x = X509.Request()
    rsa = RSA.gen_key(bits, 65537, lambda: None)
    pk.assign_rsa(rsa)
    x.set_pubkey(pk)
    x.set_subject(subject)
    x.sign(pk,'sha1')
    return x, pk


def sign_proxy_request(req, icert, ikey, lifetime):
    pkey = req.get_pubkey()
    subject = req.get_subject()
    cert = X509.X509()
    cert.set_serial_number(1)
    cert.set_version(2)
    
    t = long(time.time())
    now = ASN1.ASN1_UTCTIME()
    now.set_time(t)
    expire = ASN1.ASN1_UTCTIME()
    expire.set_time(t + lifetime * 24 * 60 * 60)
    cert.set_not_before(now)
    cert.set_not_after(expire)

    cert.set_issuer(subject)
    cert.set_subject(subject)
    cert.set_pubkey(pkey)
    cert.add_ext(X509.new_extension('basicConstraints', 'CA:FALSE', True))
    #cert.add_ext(X509.new_extension('subjectKeyIdentifier', cert.get_fingerprint()))
    cert.add_ext(X509.new_extension('authorityKeyIdentifier', "keyid"))
    cert.add_ext(X509.new_extension("proxyCertInfo", "critical,language:id-ppl-anyLanguage,pathlen:00", True))
    cert.sign(issuer_key, 'sha1')
    return cert, pkey


CERTIFICATE = "kissel.pem"

cert = X509.load_cert(CERTIFICATE)
key = EVP.load_key(CERTIFICATE)

sub = cert.get_subject()

(req, key) = make_proxy_request(1024, sub)

(proxy_cert, proxy_key) = sign_proxy_request(req, cert, key, 7)

proxy_cert.save("test.pem")

print proxy_cert 
