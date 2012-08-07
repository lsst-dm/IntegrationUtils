#!/usr/bin/env python

import os
import  sys
import wclutils
import time
import re
from collections import OrderedDict
from WrapperUtils import *
from WrapperFuncs import *

debug = 0

#
# - Following are for expanding ${...} type patterns
#

var_re = re.compile("[$]{(.*?)}")

def expandDollarVars(fulldict, temp_dict, configval):
    if debug: print "expanding configval:", configval
    temp_dict1 = {}

    def replfunc(configval, fulldict = fulldict, temp_dict = temp_dict):
        return expandVar(configval, fulldict, temp_dict)
    
    limit = 100
    while var_re.search(configval) and limit > 0:
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
        
def recurseExpand(res,cur):
    for sk in cur:
	if cur[sk].__class__ == ''.__class__:
	    cur[sk] = expandDollarVars(res, cur, cur[sk])
	else:
	    recurseExpand(res,cur[sk])

#
# - Following are for expanding $HEAD{filename,var1,var2,...} type patterns
#

dhead_re = re.compile("[$]HEAD{(.*?)}")

def expandDollarHead(configval):
    if debug: print "expanding configval:", configval

    def replfunc(match):
        return expandHead(match)
    
    limit = 100
    while dhead_re.search(configval) and limit > 0:
        configval = dhead_re.sub( replfunc, configval )
        limit = limit - 1
    return configval

dheadv_re = re.compile("([^:\s]+)(:(\d+)){0,1}$")

def expandHead(match):
    
    hklst = match.group(1).split(',')

    tmpdct = {}
    for item in hklst[1:]:
        patmatch = dheadv_re.match(item)
	if patmatch:
	    if patmatch.group(3):
	        kdu = patmatch.group(3)
	    else:
        	kdu = '0'
        else:
            print "Incorrect wcl syntax for $HEAD. Exiting."
    	    exit(1)
        # Group the keywords to extract according to hdu number
        if kdu not in tmpdct:
            tmpdct[kdu]=[] 
    	tmpdct[kdu].append(patmatch.group(1))
    
    fitsfile = hklst[0]
    hklst=[]
    hdulist = fits_open(fitsfile,'readonly')
    for kdu in tmpdct:
        hdu = int(kdu)
	for keyword in tmpdct[kdu]: 
            value = get_header_keyword(hdulist[hdu],keyword)
            if value != None:
	        hklst.append(str(value))
            else:
                print "Failed to get keyword %s from file %s; Exiting" % (keyword,fitsfile)
                exit(1)
    fits_close(hdulist)
    
    return ','.join(hklst)

def recurseExpandDollarHead(res,cur):
    for sk in cur:
	if cur[sk].__class__ == ''.__class__:
	    cur[sk] = expandDollarHead(cur[sk])
	else:
	    recurseExpandDollarHead(res,cur[sk])

#
# - Following are for expanding $FUNC{funcname,var1,var2,...} type patterns
#

dfunc_re = re.compile("[$]FUNC{(.*?)}")

def expandDollarFunc(configval):
    if debug: print "expanding configval:", configval

    def replfunc(match):
        return expandFunc(match)
    
    limit = 100
    while dfunc_re.search(configval) and limit > 0:
        configval = dfunc_re.sub( replfunc, configval )
        limit = limit - 1
    return configval

def expandFunc(match):
    
    fxargs = match.group(1).split(',')
    
    funcname = fxargs[0]
    fxargs = fxargs[1:]
    
    m = sys.modules['WrapperFuncs']
    func = getattr(m,funcname)

    return str(func(fxargs))

def recurseExpandDollarFunc(res,cur):
    for sk in cur:
	if cur[sk].__class__ == ''.__class__:
	    cur[sk] = expandDollarFunc(cur[sk])
	else:
	    recurseExpandDollarFunc(res,cur[sk])

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
   
    expandFileRange(res.get('file',{}))

    for k in res.keys():
         recurseExpandDollarHead(res, res[k])

    for k in res.keys():
         recurseExpandDollarFunc(res, res[k])

    return res

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

    for k in ('file', 'parents', 'children'):
        provenance[k] = WCLOptions.get(k,{})
    
    prov_file =  "proto_prov.wcl"
    status = writeProvenance(prov_file,OrderedDict(provenance=provenance))

    if status != 0:
	print "Failed to open %s. Exiting." %  prov_file
	exit(1)

argpos_re = re.compile("^_(\d+)_\S*$")

def buildStockCommand(WCLOptions, nth = 1, doubledash = 0):

    if not "exec_%d" % nth in WCLOptions:
         return None

    if WCLOptions["exec_%d" % nth].has_key("command"):
        print "command field is deprecrated! use execname!"
        cmdlist = [ WCLOptions["exec_%d" % nth]["command"] ]
    else:
        cmdlist = [ WCLOptions["exec_%d" % nth]["execname"] ]
 
    # 
    # If "cmdline" section exists, old style "cmdopts", "cmdargs", and 
    # "cmdflags" sections will be ignored
    #
    if  WCLOptions["exec_%d" % nth].has_key("cmdline"):

        tmpdct = {}

	for k, v in WCLOptions["exec_%d" % nth]["cmdline"].items():

            patmatch = argpos_re.match(k)
	    if patmatch:
	        tmpdct[patmatch.group(1)] = v
            else:
                if not k.startswith('_'):
                    if v != "_flag":
			cmdlist.append("%s%s '%s'" %(["-","--"][doubledash], k, v))
		    else:
	                cmdlist.append("%s%s" %(["-","--"][doubledash], k))
	        else:
	            cmdlist.append("'%s'" % v)
	
        # insert position sensitive arguments into specified location in argument list
	for k in sorted(tmpdct.iterkeys()):
	    cmdlist.insert(int(k),"'%s'" % tmpdct[k])
	
    else:
    
        if  WCLOptions["exec_%d" % nth].has_key("cmdargs"):
            print "cmdargs is now deprecated!"
	    for v in WCLOptions["exec_%d" % nth]["cmdargs"].split(','):
	        cmdlist.append(v)

        if  WCLOptions["exec_%d" % nth].has_key("cmdflags"):
            print "cmdflags is now deprecated!"
	    for v in WCLOptions["exec_%d" % nth]["cmdflags"].split(','):
		cmdlist.append("%s%s" % (["-","--"][doubledash], v))
     
        if  WCLOptions["exec_%d" % nth].has_key("cmdopts"):
            print "cmdopts is now deprecated!"
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
