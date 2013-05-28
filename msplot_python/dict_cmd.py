'''Extension of cmd class for navigating a python dict as though it
were a directory structure.
'''
###TODO need a general way cleaning path input
###TODO mkdir should handle full paths and -p
__author__ = "Matthew Jaffee <matthew.jaffee@gmail.com>"

import cmd
import shlex
from pprint import pprint

SEP = "/"
UP = ".."
class DictCmd(cmd.Cmd):
    def __init__(self, start_dict):
        if start_dict:
            self.d = start_dict
        else:
            self.d = {}
        self.cwd = self.d
        self.cwd_path = []
        cmd.Cmd.__init__(self)

    def do_cd(self, path):
        '''Change the current level of view of the dict to be at <key>
        cd <key>'''
        new_wd_path = self.path_list(path)
        try:
            cwd, new_wd_path = self.dict_for_path(new_wd_path, self.d)
        except KeyError:
            print "%s not found" % path
            return
        if not isinstance(cwd, dict):
            print "%s is not a directory" % path
            return
        self.cwd_path = new_wd_path
        self.cwd = cwd

    def complete_cd(self, text, l, b, e):
        text = l.split()[1]
        path_list = self.path_list(text)
        text = path_list[-1]
        cwd, p = self.dict_for_path(path_list[:-1], self.d)
        return [ x for x,y in cwd.iteritems()
                 if isinstance(y, dict) and x.startswith(text) ]

    def do_mkdir(self, path):
        '''Create an empty dict with key <name> at the current
        level
        mkdir <name>
        '''
        path_list = self.path_list(path)
        try:
            cwd, p = self.dict_for_path(path_list[:-1], self.d)
        except KeyError:
            print "%s does not exist"%path
        name = path_list[-1]
        if name in cwd:
            print "%s already exists"%name
            return
        cwd[name] = {}

    def do_pwd(self, none):
        print SEP + SEP.join(self.cwd_path)

    def do_set(self, line):
        line = shlex.split(line)
        if len(line)<2:
            print "Usage: set <key> <value>"
            return
        path_list = self.path_list(line[0])
        try:
            cwd, p = self.dict_for_path(path_list[:-1], self.d)
        except KeyError:
            print "No such path %s" % line[0]
        cwd[path_list[-1]] = self._val_from_input(line[1])

    def complete_set(self, text, l, b, e):
        text = l.split()[1]
        path_list = self.path_list(text)
        text = path_list[-1]
        cwd, p = self.dict_for_path(path_list[:-1], self.d)
        if b==4 or b==5:
            return [ x for x in cwd.keys()
                     if x.startswith(text) ]
        else:
            return []

    def do_del(self, path):
        path_list = self.path_list(path)
        try:
            cwd, p = self.dict_for_path(path_list[:-1], self.d)
        except KeyError:
            print "path %s does not exist" % path
            return
        if path_list[-1] in cwd:
            del cwd[path_list[-1]]
        else:
            print "%s does not exist in %s" % (path_list[-1], "/" + "/".join(path_list[:-1]))

    def complete_del(self, text, l, b, e):
        text = l.split()[1]
        path_list = self.path_list(text)
        text = path_list[-1]
        cwd, p = self.dict_for_path(path_list[:-1], self.d)
        return [ x for x in cwd.keys()
                 if x.startswith(text) ]

    def do_ls(self, path):
        if path:
            path = self.path_list(path)
        else:
            path = self.cwd_path
        try:
            cwd, newpath = self.dict_for_path(path, self.d)
        except KeyError:
            print "No such path %s" % path
            return
        for k,v in cwd.iteritems():
            if isinstance(v, dict):
                print col.DIR + k + col.ENDC
            else:
                print "%s: %s" % (k, v)

    def complete_ls(self, text, l, b, e):
        text = l.split()[1]
        path_list = self.path_list(text)
        text = path_list[-1]
        cwd, p = self.dict_for_path(path_list[:-1], self.d)
        return [ x for x,y in cwd.iteritems()
                 if isinstance(y, dict) and x.startswith(text) ]

    def do_lsd(self, path):
        if path:
            path = self.path_list(path)
        else:
            path = self.cwd_path
        try:
            cwd, newpath = self.dict_for_path(path, self.d)
        except KeyError:
            print "No such path %s" % path
            return
        pprint(cwd)

    def complete_lsd(self, text, l, b, e):
        text = l.split()[1]
        path_list = self.path_list(text)
        text = path_list[-1]
        cwd, p = self.dict_for_path(path_list[:-1], self.d)
        return [ x for x,y in cwd.iteritems()
                 if isinstance(y, dict) and x.startswith(text) ]

    def dict_for_path(self, new_path, d):
        '''given a path list and a config dict returns
        (config at path, path_list)
        '''
        cwd_stack = []
        cwd = d
        num = 0
        for key in new_path:
            if key == "":
                continue
            num += 1
            if key == UP and cwd_stack:
                cwd = cwd_stack.pop()[0]
                continue
            elif key == UP:
                continue
            ocwd = cwd
            cwd = cwd[key]
            cwd_stack.append((ocwd, key))
        return (cwd, [ x[1] for x in cwd_stack ])

    def path_list(self, path):
        '''path list from a string path separated by SEP'''
        if path=="" or path[0]==SEP:
            path_list = path[1:].split(SEP)
        else:
            path_list = self.cwd_path + path.split(SEP)
        return path_list

    def _val_from_input(self, inp):
        '''Take user input, and try to convert it to JSON appropriate
        python values.
        '''
        val = inp
        try:
            val = int(inp)
            return val
        except Exception:
            val = inp
        if val == "false":
            return False
        if val == "true":
            return True
        if (val[0] == "'" and val[-1] == "'") or\
                (val[0] == '"' and val[-1] == '"'):
            return val[1:-1]
        return val

    def do_EOF(self, line):
        return True

class col:
    HEADER = '\033[35m'# PINK
    DIR = '\033[34m' # BLUE
    PROMPT = '\033[32m' # GREEN
    WARNING = '\033[33m' # YELLOW
    FAIL = '\033[31m' # RED
    ENDC = '\033[39m' # BLACK


if __name__ == "__main__":
    DictCmd({}).cmdloop()
