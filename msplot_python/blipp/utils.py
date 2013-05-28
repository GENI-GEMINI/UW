from copy import deepcopy
import re

def try__import__(name):
    try:
        ret=__import__(name)
    except ImportError:
        SETTINGS_FILE = "blipp" + "." + name
        try:
            ret=__import__(SETTINGS_FILE)
            ret = getattr(ret, name)
        except ImportError:
            ret=None

    return ret

def blipp_import(name, **kwargs):
    try:
        ret = __import__(name, fromlist=[1])
    except ImportError:
        ret = __import__("blipp." + name, fromlist=[1])
    return ret

def blipp_import_method(method_string):
    mod, dot, method = method_string.rpartition(".")
    mod = blipp_import(mod)
    return mod.__getattribute__(method)

def full_event_types(data, EVENT_TYPES):
    result = {}
    if isinstance(data.itervalues().next(), dict):
        for subject in data.keys():
            subresult = {}
            for k,v in data[subject].iteritems():
                subresult[EVENT_TYPES[k]]=v
            result[subject]=subresult
        return result
    else:
        for k,v in data.iteritems():
            result[EVENT_TYPES[k]]=v
        return result

def delete_nones(adict):
    '''Recursively delete None (json null) values from a deeply nested
    dictionary'''
    del_keys = []
    for k,v in adict.iteritems():
        if isinstance(v, dict):
            delete_nones(v)
        elif v==None:
            del_keys.append(k)

    for k in del_keys:
        del adict[k]

def merge_dicts(adict, overriding):
    '''Recursively merge two deeply nested dictionaries, preferring
    values from 'overriding' when there are colliding keys'''
    for k,v in overriding.iteritems():
        if isinstance(v, dict):
            merge_dicts(adict.setdefault(k, {}), v)
        else:
            adict[k] = v

def reconcile_config(defaults, master):
    ans = deepcopy(defaults)
    for key, val in master.iteritems():
        if not isinstance(val, dict):
            ans[key] = val
        else:
            if key in ans:
                ans[key] = reconcile_config(ans[key], master[key])
            else:
                ans[key] = deepcopy(val)
    return ans

def query_string_from_dict(adict, prefix=""):
    '''Construct a UNIS REST API query string from a dictionary'''
    retstring = ""
    if prefix:
        prefix += "."
    for k,v in adict.items():
        if isinstance(v, dict):
            retstring += query_string_from_dict(v, prefix + str(k))
        else:
            if isinstance(v, bool): # bool goes first because isinstance(False, int)==True *sigh*
                retstring += prefix + str(k) + "=boolean:" + str(v).lower() + "&"
            elif isinstance(v, int):
                retstring += prefix + str(k) + "=number:" + str(v) + "&"
            elif isinstance(v, str):
                retstring+= prefix + str(k) + "=" + v + "&"
            elif isinstance(v, unicode):
                retstring+= prefix + str(k) + "=" + v + "&"
            else:
                print "ATTEMPT TO QUERY ON NON SUPPORTED TYPE:"
                print v

    return retstring

def clean_mac(mac):
    mac = mac.strip().lower().replace(":", "")
    mac = mac.replace(" ", "")
    try:
        return re.search('([0-9a-f]{12})', mac).groups()[0]
    except AttributeError:
        return None
