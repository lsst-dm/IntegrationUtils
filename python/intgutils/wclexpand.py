#!/usr/bin/env python

import os
import  sys
import wclutils
import time
import re
from collections import OrderedDict
from WrapperUtils import *

debug = 1

var_re = re.compile("\${(.*?)}")

def expandDollarVars(fulldict, temp_dict, configval):
    if debug: print "expanding configval:", configval
    temp_dict1 = {}

    def replfunc(configval, fulldict = fulldict, temp_dict = temp_dict):
        return expandVar(configval, fulldict, temp_dict)
    
    limit = 100
    while var_re.search(configval, 1) and limit > 0:
        configval = var_re.sub( replfunc, configval ) 
        limit = limit - 1
 
    return configval

def expandVar(match, fulldict, temp_dict):

    if debug: print "expandvar"

    varname = match.group(1)

    if debug: print "expandvar varname is " , varname

    if varname.find(":") > 0:
	name, func = varname.split(":")
    else:
	name = varname
	func = "none"

    #
    # handle foo.bar.baz or just foo
    #
    if name.find(".") > 0:
	list = name.split(".")
	d = fulldict
    else:
	list = [name]
	d = temp_dict

    for i in range(0,len(list)):
	try:
	    d = d[list[i]]
	except:
	    print "undefined section in ", '.'.join(list)
	    d = {}

    expanded = d

    if debug: print "found", expanded
    #
    # apply formatting functions:
    # :n makes applies %0nd format
    # :trim trims off .whatever suffixes
    #
    if func[0] in "0123456789":
	format = "%%0%sd" % func
	if debug: print "applying func %s to %s" % (func, expanded)
	if debug: print "format is %s" % format
	expanded = format % int(expanded)

    if func == 'trim':
	expanded =expanded[0:expanded.find('.')]

    if debug: print "converted ", varname, " to ", expanded 

    return expanded
     
range_re = re.compile("\(([0-9]+)-([0-9]+)\)(:[0-9]+)?")

def expandFileRange(dict):

    for k in dict.keys():
       if dict[k].has_key("filename"):
           filename = dict[k]["filename"]
           m = range_re.search(filename)

           if m and m.group(3):
              replfmt = "%%%sd" % m.group(3)[1:]
           else:
              replfmt = "%d"

	   if m:
	       template = dict[k]
               del dict[k]
               for i in range(int(m.group(1)), int(m.group(2))):
                    k2 = "%s_%d" % (k, i)
                    repl=replfmt % i
                    dict[k2] = {}
                    dict[k2].update(template)
                    newfilename = range_re.sub(repl, dict[k2]["filename"])
                    dict[k2]["filename"] = newfilename
        
def expandWCL(wrapopts):
    res = dict()
    if debug: print "we are in:" , os.getcwd()
    for wcltype in ["config", "input", "output", "ancilliary"]:
        try:
	    if wcltype in wrapopts and wrapopts[wcltype]:
		fwcl = open(wrapopts[wcltype],"r")
		res.update(wclutils.read_wcl(fwcl))
		fwcl.close()
	except:
            raise
	    # print "Failed to open '%s'. Exiting." %  wrapopts[wcltype]
	    # generate_provenance_on_exit(prov_file,starttime=starttime,exit_status=1)
	    # exit(1)
    if debug: print res

    for k in res.keys():
         recurseExpand(res, res[k])
   
    expandFileRange(res['files'])

    return res

def recurseExpand(res,cur):
    for sk in cur:
	if cur[sk].__class__ == ''.__class__:
	    cur[sk] = expandDollarVars(res, cur, cur[sk])
	else:
	    recurseExpand(res,cur[sk])

def genProvenance(WCLOptions, exitstatus, starttime):
    provenance=OrderedDict()

    cmdlineargs = ''
    for args in sys.argv[1:]:
	cmdlineargs += ' ' + args

    provenance['wrapper'] =  OrderedDict(exitstatus = exitstatus , walltime =  time.time() - starttime, cmdlineargs = cmdlineargs)
    provenance['wrapper'].update(WCLOptions.get('wrapper',{}))

    i = 1
    while WCLOptions.has_key("exec_%d"%i ):
         provenance["exec_%d"%i] = WCLOptions["exec_%d"%i]
         i = i + 1

    for k in ('files', 'parents', 'children'):
        provenance[k] = WCLOptions.get(k,{})
    
    prov_file =  "proto_prov.wcl"
    status = writeProvenance(prov_file,OrderedDict(provenance=provenance))

    if status != 0:
	print "Failed to open %s. Exiting." %  prov_file
	exit(1)

def buildStockCommand(WCLOptions, nth = 1,  doubledash = 0):

    if not "exec_%d" % nth in WCLOptions:
         return None

    cmdlist = [ WCLOptions["exec_%d" % nth]["command"] ]
 
    if  WCLOptions["exec_%d" % nth].has_key("cmdargs"):
	for v in WCLOptions["exec_%d" % nth]["cmdargs"].split(','):
	    cmdlist.append(v)

    if  WCLOptions["exec_%d" % nth].has_key("cmdflags"):
	for v in WCLOptions["exec_%d" % nth]["cmdflags"].split(','):
	    cmdlist.append("%s%s" % (["-","--"][doubledash], v))
     
    if  WCLOptions["exec_%d" % nth].has_key("cmdopts"):
	for k, v in WCLOptions["exec_%d" % nth]["cmdopts"].items():
	    cmdlist.append("%s%s" %(["-","--"][doubledash], k))
	    cmdlist.append(v)

    return ' '.join(cmdlist)


if __name__ == '__main__':
    print "argv: ", sys.argv
    os.chdir('test')
    f = open('testlist', 'r')
    for line in f.readlines():
        print "line: " , line
        argv = line[:-1].split(' ')
        sys.argv = ['testing'] + argv
        print "argv: ", sys.argv
        p = WrapperOptionParser()
        WrapperOptions = p.parse()
        WCLOptions = expandWCL(WrapperOptions)
        print "got WCLOptions of", WCLOptions
        print "would build command:" , buildStockCommand(WCLOptions)
 
        print "provenance:"
        genProvenance(WCLOptions, 1, time.time()) 
        os.system("cat proto_prov.wcl")

    f.close()
