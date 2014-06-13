#!/usr/bin/python

'''
Created on Oct 2, 2012

@author: ezkissel
'''

import sys
import argparse
import requests

def main(argv=None):

    usage_desc = "usage: unis_client.py <URL> <action> <certfile> [file]"

    parser = argparse.ArgumentParser(description='process args', usage=usage_desc, epilog='foo bar help')
    parser.add_argument('URL')
    parser.add_argument('action')
    parser.add_argument('certfile')
    parser.add_argument('sendfile', nargs='?')

    args = parser.parse_args()
    f = None

    if args.sendfile != None:
        try:
            f = open(args.sendfile, 'r')
            f = f.read()
        except IOError, msg:
            print 'could not open file: ' + msg.strerror
            return

    r = requests.request(args.action, args.URL, data=f, cert=(args.certfile), verify=False)

    data = r.text

    print "\nServer Response: %d" % (r.status_code)

    print "Response data (%d bytes):" % len(data)
    print "================================================================================"
    print data
    print "================================================================================"


if __name__ == '__main__':
    sys.exit(main())
