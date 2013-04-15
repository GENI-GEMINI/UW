'''
Usage: plotcmd.py <ms-url> [-c CERT] [-k KEY] [-u UNIS]

Options:
  -u UNIS --unis-url=UNIS   UNIS url [default: https://unis.incntre.iu.edu:8443].
  -c CERT --cert=CERT       SSL cert location
  -k KEY --key=KEY          SSL key location

'''
from dict_cmd import DictCmd
from docopt import docopt
from blipp.utils import query_string_from_dict
import requests
import ms_plot

class PlotCmd(DictCmd):
    def __init__(self, args):
        self.args = args
        self.prompt = col.PROMPT + "plotcmd>>> " + col.ENDC
        if args['--cert']:
            args['--key'] = args['--cert'] if not args['--key'] else args['--key']
            self.cert_key = (args['--cert'], args['--key'])
        else:
            self.cert_key = None

        ms_plot.cert_key = self.cert_key
        self.md_list = [] # list of metadata object from MS
        DictCmd.__init__(self, {})

    def do_query(self, qstr):
        '''query [qstr]
        query the ms for metadata and store it in
        self.md_list. If qstr is given, it is used as the query
        (everything after the ? mark in the URL. If it is not given, a
        query is generated based on the items in the current dict.
        '''
        if not qstr:
            qstr = query_string_from_dict(self.d)
        if self.cert_key:
            r = requests.get(args["--unis-url"] + "/metadata?" + qstr, cert=self.cert_key, verify=False)
        else:
            r = requests.get(args["--unis-url"] + "/metadata?" + qstr)
        self.md_list = r.json()
        for md in r.json():
            print md["eventType"]

    def do_add(self, qstr):
        '''add [qstr]
        add metadata to self.md_list
        '''
        if not qstr:
            qstr = query_string_from_dict(self.d)
        if self.cert_key:
            r = requests.get(args["--unis-url"] + "/metadata?" + qstr, cert=self.cert_key, verify=False)
        else:
            r = requests.get(args["--unis-url"] + "/metadata?" + qstr)
        self.md_list.extend(r.json)
        self.uniquify_md_list()
        for md in r.json:
            print md["eventType"]

    def do_print(self, none):
        for md in self.md_list:
            print md["id"]

    def do_plot(self, none):
        ms_plot.mds = self.md_list
        ms_plot.plot_all()

    def uniquify_md_list(self):
        id_list = [ md["id"] for md in self.md_list ]
        id_list = list(set(id_list))
        if len(id_list) < len(self.md_list):
            print "should have implemented uniquify"

class col:
    HEADER = '\033[35m'# PINK
    DIR = '\033[34m' # BLUE
    PROMPT = '\033[32m' # GREEN
    WARNING = '\033[33m' # YELLOW
    FAIL = '\033[31m' # RED
    ENDC = '\033[39m' # BLACK

if __name__ == '__main__':
    args = docopt(__doc__, version='plotcmd 0.1')
    print args
    PlotCmd(args).cmdloop()
