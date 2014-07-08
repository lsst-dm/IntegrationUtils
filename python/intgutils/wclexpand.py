#!/usr/bin/env python

"""
Utilities for expanding $func{whatever} type syntax
in wcl files. 

Usual Usage:
        from wclexpand.py import expandWCL
        from WrapperUtils import WrapperOptionParser

        p = WrapperOptionParser()
        WrapperOptions = p.parse()
        WCLOptions = expandWCL(WrapperOptions)

However direct usage of the various internal routines
is sometimes appropriate.
"""
import os
import sys
from  intgutils import wclutils
import time
import re
from collections import OrderedDict
from wrappers.WrapperUtils import *
from wrappers.WrapperFuncs import *

debug = 0

#
# - Following are for expanding ${...} type patterns
#

var_re = re.compile("[$]{(.*?)}")
comma_re = re.compile("\s*,\s*")

def expandDollarVars(fulldict, temp_dict, configval, loopcheck = {}):
    """
    Replace ${variable} or ${sect.subsect.variable} with values in dict

    Arguments are:
    * fulldict -- whole dictionary for looking up full path (sect.subsect...)
        values
    * temp_dict -- subditionary for local paths
    * configval -- value from configuration in which do do the expansion
    * loopcheck -- list of variables we're currently expanding to avoid
        infinite recursion
    """
    if debug: print "expanding configval:", configval
    temp_dict1 = {}

    def replfunc(configval, fulldict = fulldict, temp_dict = temp_dict, loopcheck = loopcheck):
        """ temporary local function to pass into re.sub() -- defines default parameters """
        return expandVar(configval, fulldict, temp_dict, loopcheck)
    
    limit = 100
    while var_re.search(configval) and limit > 0:
        configval = var_re.sub( replfunc, configval ) 
        limit = limit - 1
 
    return configval

def expandVar(match, fulldict, temp_dict, loopcheck = {}):
    """
        replace a variable with its value, given a regexp match

        also handles functions on the end like :2 for 2 column
        padded, and :trim for filename suffix trimming.  These
        functions should later be in a table(!)

        >>> fulldict = {'a': {'b':'c', 'd': 'e', 'foo':'data'}}; \
            m = re.search('\${(.*?)}', "this is ${foo} stuff"); \
            expandVar(m, fulldict, fulldict['a'])
	'data'
        >>> fulldict = {'a': {'b':'c', 'd': 'e', 'foo':'data'}};  \
	    m = re.search('\${(.*?)}', "this is ${a.foo} stuff"); \
	    expandVar(m, fulldict, fulldict['a'])
	'data'
        >>> fulldict = {'a': {'b':'c', 'd': 'e', 'foo':'data'}}; \
	     m = re.search('\${(.*?)}', "this is ${a.b} stuff"); \
	     expandVar(m, fulldict, fulldict['a'])
	'c'
    """

    if debug: print "expandvar"

    varname = match.group(1)

    if debug: print "expandvar varname is " , varname
    if debug: print "expandvar fulldict: " , fulldict
    if debug: print "expandvar temp_dict: " ,  temp_dict
    if debug: print "expandvar loopcheck: " ,  loopcheck

    if varname in loopcheck:
        raise KeyError("Error: .wcl file definition involves itself", varname)

    loopcheck[varname] = 1

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
        if temp_dict.has_key(name):
	   d = temp_dict
        else:
           d = fulldict

    for i in range(0,len(list)):
	try:
	    d = d[list[i]]
	except:
	    print "undefined section", list[i] ," in ", '.'.join(list)
	    d = {}

    expanded = expandDollarVars(fulldict, temp_dict,  d, loopcheck)

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
        trimstart=expanded.rfind('/')
        if trimstart == -1:
           trimstart = 0
	expanded =expanded[0:expanded.find('.',trimstart)]

    del loopcheck[varname]

    if debug: print "converted ", varname, " to ", expanded 

    return expanded
     
range_re = re.compile("\(([0-9]+)([-,0-9]+)\)(:[0-9]+)?")

def expandrange(s):
    """
    convert ranges like "1-10,20-15" into python list of integers

    >>> expandrange("1-10,20-15")
    [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    """
    res = []
    for p in s.split(','):
        l = p.split('-')
        if len(l) == 2:
            for i in  range(int(l[0]),int(l[1])+1):
                res.append(i)   
        else:
            res.append(int(l[0]))
    return res

def expandFileRange(dict):
    """
    given a wcl dict with filename entries with embedded ranges, yeild 
    a wcl dict with multiple file elements with each range element expanded 

    >>> d = { "file": { "filename": "apple(1-10):3.xyz", "type": "foo"}}; \
        expandFileRange(d); \
        d
    {'file': {'type': 'foo', 'filename': 'apple001.xyz,apple002.xyz,apple003.xyz,apple004.xyz,apple005.xyz,apple006.xyz,apple007.xyz,apple008.xyz,apple009.xyz,apple010.xyz'}}
    """

    for k in dict.keys():
       if dict[k].has_key("filename"):
           filename = dict[k]["filename"]

           m = range_re.search(filename)

           if m and m.group(3):
              replfmt = "%%0%sd" % m.group(3)[1:]
           else:
              replfmt = "%d"

	   if m:
	       l = []
               for i in expandrange(m.group(1)+m.group(2)):
                    repl=replfmt % i
                    newfilename = range_re.sub(repl, dict[k]["filename"])
                    l.append(newfilename)
               dict[k]["filename"]=','.join(l)
        
def recurseExpand(res,cur):
    """
        Recursivley expand variables in strings in a wcl dictionary
    """
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
    """
    Replace $HEAD{xxx} with the approprate header variable
    """
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
    """
    given a match object, return the headers involved
    """
    
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
    """
        recursivley walk a wcl dictionary, doing $HEAD{..} expansion
    """
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
    """
        expand $FUNC{whatever} in text
    """
    if debug: print "expanding configval:", configval

    def replfunc(match):
        return expandFunc(match)
    
    limit = 100
    while dfunc_re.search(configval) and limit > 0:
        configval = dfunc_re.sub( replfunc, configval )
        limit = limit - 1
    return configval

def expandFunc(match):
    """
    Given ap match object, get the corresponding function value
    """
    
    fxargs = match.group(1).split(',')
    
    funcname = fxargs[0]
    fxargs = fxargs[1:]
    
    m = sys.modules['wrappers.WrapperFuncs']
    func = getattr(m,funcname)

    return str(func(fxargs))

def recurseExpandDollarFunc(res,cur):
    """
    recursively apply expansion of  $FUNC{whatever}
    """
    for sk in cur:
	if cur[sk].__class__ == ''.__class__:
	    cur[sk] = expandDollarFunc(cur[sk])
	else:
	    recurseExpandDollarFunc(res,cur[sk])

#
# - Following are for expanding $RNMLST{prefix,file1,file2,...} type patterns
#

drnmlst_re = re.compile("[$]RNMLST{(.*?)}")

def expandDollarRnmLst(configval):
    """
        expand $RNMLST{whatever} in text
    """
    if debug: print "expanding configval:", configval

    def replfunc(match):
        return expandRnmLst(match)
    
    limit = 100
    while drnmlst_re.search(configval) and limit > 0:
        configval = drnmlst_re.sub( replfunc, configval )
        limit = limit - 1
    return configval

def expandRnmLst(match):
    """
    Given ap match object, get the corresponding function value
    """
    
    rnmlstargs = match.group(1).split(',')
    
    fprfx = rnmlstargs[0]
    flist = rnmlstargs[1:]

    flist_new = []
    for f in flist:
        flist_new.append(fprfx+f)
    
    return ','.join(flist_new)
    
def recurseExpandDollarRnmLst(res,cur):
    """
    recursively apply expansion of $RNMLST{whatever}
    """
    for sk in cur:
	if cur[sk].__class__ == ''.__class__:
	    cur[sk] = expandDollarRnmLst(cur[sk])
	else:
	    recurseExpandDollarRnmLst(res,cur[sk])

#
# - Following are for expanding $LSTCOL{listname,var1,var2,...} type patterns
#

dlstcol_re = re.compile("[$]LSTCOL{(.*?)}")

def expandDollarLstCol(fulldict, configval):
    """
        expand $LSTCOL{whatever} in text
    """
    if debug: print "expanding configval:", configval

    def replfunc(match,fulldict=fulldict):
        return expandLstCol(match,fulldict)
    
    limit = 100
    while dlstcol_re.search(configval) and limit > 0:
        configval = dlstcol_re.sub( replfunc, configval )
        limit = limit - 1
    return configval

def expandLstCol(match,fulldict):
    """
    Given a match object, get the corresponding column entry from the listfile
    """
    
    lstargs = match.group(1).split(',')
    
    listmode = int(lstargs[0])
    listname = lstargs[1]
    lineno = int(lstargs[2])
    lstargs = lstargs[3:]

    try:
        f = open(listname)
        lines = f.readlines()
	f.close()
    except:
        print "Failed to open %s. Exiting." %  listname
        exit(1)
   
    icol = -1
    varsel = []
    for key in fulldict['list']:
    	if 'fullname' in fulldict['list'][key]:
    	    if fulldict['list'][key]['fullname']==listname:
    		if 'columns' in fulldict['list'][key]:  	
    		    clmlst = fulldict['list'][key]['columns'].split(',')
                    if lineno >=0: 
                        line = lines[lineno]
                        varall = line[:-1].split()
    		        for itemc in lstargs:
    			    if itemc.find(":")>0:
    			        item, func = itemc.split(":")
    			    else:
    			        item = itemc
    			        func = "none"
    			    if item in clmlst:
    			        icol = clmlst.index(item)
    			        v = varall[icol]
    			        if func == 'trim':
    				    v = v[v.rfind('/')+1:v.find('.')]
    			        varsel.append(v)
    			    else:
    			        print "%s not found in column list. Exiting." %  item
    			        exit(1)
                    else:
                        if len(lstargs) != 1:
                            print "Can only specify one column when reading entire column"
                            exit(1)
			itemc = lstargs[0]
    			if itemc.find(":")>0:
    			    item, func = itemc.split(":")
    			else:
    			    item = itemc
    			    func = "none"
    			if item in clmlst:
    			    icol = clmlst.index(item)
                            # now loop over the lines
			    lno = 0
			    while lno < len(lines):
			        varall = lines[lno][:-1].split()
    			        v = varall[icol]
    			        if func == 'trim':
    			    	    v = v[v.rfind('/')+1:v.find('.')]
    			        varsel.append(v)
				lno += 1
    			else:
    			    print "%s not found in column list. Exiting." %  item
    			    exit(1)
    		    break
    		else:
    		    print "Did not find columns keyword. Exiting."
    		    exit(1)

    if len(varsel) > 0:
        if listmode == 0:
            # list of files returned as a file containing the filenames
	    if lineno >= 0:
	        print "LSTCOL expander: listmode == 1 only supported when reading an entire single column."
		exit(1)
	    if icol < 0:
	        print "LSTCOL expander: Column index not found for listmode == 1."
		exit(1)
            # construct name of file that will hold the list by prepending column number
            outlist = 'c'+str(icol)+'-'+os.path.basename(listname)
            print "LSTCOL expander: checking existence of %s" % outlist
            if os.path.exists(outlist):
                print "LSTCOL expander: file %s exists" % outlist
                print "LSTCOL expander: now deleting %s" % outlist
                os.remove(outlist)
	    print "LSTCOL expander: creating/recreating %s" % outlist
            nl = 0
	    fout = open(outlist,'w')
	    for v in varsel:
	        fout.write(v+'\n')
		nl += 1
	    fout.close()
	    print "LSTCOL expander: wrote %s lines to %s" % (nl,outlist)
	    return outlist
	elif listmode == 1:
	    # list of files returned as a comma seperated list of filenames
            return ','.join(varsel)
	else:
     	    print "LSTCOL expander: unknown listmode option."
	    exit(1) 
    else:
     	print "Failed to find listfile column variables." 
        exit(1)

def recurseExpandDollarLstCol(res,cur):
    """
    recursively apply expansion of  $FUNC{whatever}
    """
    for sk in cur:
	if cur[sk].__class__ == ''.__class__:
	    cur[sk] = expandDollarLstCol(res,cur[sk])
	else:
	    recurseExpandDollarLstCol(res,cur[sk])

#
# - This will replace a pattern of type $lpXX{KEYWORD} with the value 
#   corresponding to key='KEYWORD' in the user-supplied dictionary "rd":
#
#     $lpXX{KEYWORD} ==>> rd['KEYWORD']
#
dkey_re = re.compile("[$]lpXX{(.*?)}")

def replaceDollarKey(configval,rd):
    if debug: print "replacing configval:", configval

    def replfunc(match,rd=rd):
        return rd[match.group(1)]
    
    limit = 100
    while dkey_re.search(configval) and limit > 0:
        configval = dkey_re.sub( replfunc, configval )
        limit = limit - 1
    return configval

def recurseReplaceDollarKey(res,cur,rd):
    for sk in cur:
	if cur[sk].__class__ == ''.__class__:
	    cur[sk] = replaceDollarKey(cur[sk],rd)
	else:
	    recurseReplaceDollarKey(res,cur[sk],rd)

def replaceRange(configval):
    if debug: print "replacing configval:", configval

    def replfunc(match):
        if match.group(3):
            replfmt = "%%%sd" % match.group(3)[1:]
        else:
            replfmt = "%d"
        return ','.join([replfmt % item for item in expandrange(match.group(1)+match.group(2))])

    limit = 100
    while range_re.search(configval) and limit > 0:
        configval = range_re.sub( replfunc, configval )
        limit = limit - 1
    return configval

def recurseReplaceRange(res,cur):
    for sk in cur:
	if cur[sk].__class__ == ''.__class__:
	    cur[sk] = replaceRange(cur[sk])
	else:
	    recurseReplaceRange(res,cur[sk])

def expandWCL(wrapopts):
    """
       Expand variable, header, and function references from wcl files 
       mentioned in the passed-in wrapper options.
    """

    res = dict()

    foundconfig = False
    
    if debug: print "we are in:" , os.getcwd()
    if debug: print "wrapopts are:" , wrapopts
    for wcltype in ["config", "input", "output", "ancilliary"]:
        try:
	    if wcltype in wrapopts and wrapopts[wcltype]:
		fwcl = open(wrapopts[wcltype],"r")
		#res.update(wclutils.read_wcl(fwcl))
		res = wclutils.updateDict(res, wclutils.read_wcl(fwcl))
		fwcl.close()
                foundconfig = True
	except:
            raise
	    # print "Failed to open '%s'. Exiting." %  wrapopts[wcltype]
	    # generate_provenance_on_exit(prov_file,starttime=starttime,exit_status=1)
	    # exit(1)

    if not foundconfig:
        raise Exception("At least one config file option (--config, --input, --output, or --ancillary) must be specified")

    if debug: print "before override:", res

    #
    # handle override arguments
    #
    overrides = wrapopts.get('overrides',[])
    if debug: print "overrides are:" , overrides
    for override in overrides:
        arg,val = override.split('=',2)
        if debug: print "overriding %s to %s", arg, val
        path=arg.split('.')
        if debug: print "path: ", path
        d = res
        for c in path[:-1]:
           d = d[c]
        d[path[-1]] = val

    if debug: print "after override:", res

    recurseExpand(res, res)
   
    expandFileRange(res.get('file',{}))

    recurseExpandDollarLstCol(res, res)

    recurseExpandDollarHead(res, res)

    recurseExpandDollarFunc(res, res)

    recurseExpandDollarRnmLst(res, res)
    
    return res

def genProvenance(WCLOptions, exitstatus, starttime):
    """
       Generate a proveneance file by manufacturing a wcl dictionary
       with subdictionaries from the input, etc. and dumping it 
       to a file.
    """
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

#MMGdef buildStockCommand(WCLOptions, nth = 1, doubledash = 0):
#MMG EXEC_CMD_HYPHENS = allsingle  # alldouble, mixed_gnu
def buildStockCommand(WCLOptions, nth = 1, cmd_hyphen = None):
    """
        Build a command line from an expanded wcl options file
    """

    if not "exec_%d" % nth in WCLOptions:
         print "Severe warning: in buildStockCommand could not find exec section named 'exec_%d'" % nth
         return None

    if WCLOptions["exec_%d" % nth].has_key("command"):
        print "command field is deprecrated! use execname!"
        cmdlist = [ WCLOptions["exec_%d" % nth]["command"] ]
    else:
        cmdlist = [ WCLOptions["exec_%d" % nth]["execname"] ]

    # function arg overrides exec section
    if cmd_hyphen is None and WCLOptions["exec_%d" % nth].has_key("cmd_hyphen"):
        cmd_hyphen = WCLOptions["exec_%d" % nth]["cmd_hyphen"] 
 
    hyphen = '-'
    if cmd_hyphen == "alldouble":
        hyphen = '--'
    elif not isinstance(cmd_hyphen, str):   # deprecated doubledash behavior
        if cmd_hyphen:
            hyphen = '--'

    # If "cmdline" section exists, old style "cmdopts", "cmdargs", and 
    # "cmdflags" sections will be ignored
    #
    if  WCLOptions["exec_%d" % nth].has_key("cmdline"):

        tmpdct = {}

	for k, v in WCLOptions["exec_%d" % nth]["cmdline"].items():
            if cmd_hyphen == "mixed_gnu":  # determine single or double depending upon char or word opt
                if len(k) > 1:
                    hyphen = '--'
                else:
                    hyphen = '-'

            patmatch = argpos_re.match(k)
	    if patmatch:
	        tmpdct[patmatch.group(1)] = v
            else:
                if not k.startswith('_'):   # if not a positional argument
                    if v != "_flag":  # if not a flag option
			#SNE cmdlist.append("%s%s '%s'" %(hyphen, k, v))
			cmdlist.append("%s%s %s" %(hyphen, k, v))
		    else:
	                cmdlist.append("%s%s" %(hyphen, k))
	        else:
	            #SNE cmdlist.append("'%s'" % v)
	            cmdlist.append("%s" % v)
	
        # insert position sensitive arguments into specified location in argument list
	for k in sorted(tmpdct.iterkeys()):
	    #SNE cmdlist.insert(int(k),"'%s'" % tmpdct[k])
	    cmdlist.insert(int(k),"%s" % tmpdct[k])
	
    else:
        if  WCLOptions["exec_%d" % nth].has_key("cmdargs"):
            print "cmdargs is now deprecated!"
	    for v in comma_re.split(WCLOptions["exec_%d" % nth]["cmdargs"]):
	        cmdlist.append(v)

        if  WCLOptions["exec_%d" % nth].has_key("cmdflags"):
            print "cmdflags is now deprecated!"
	    for v in comma_re.split(WCLOptions["exec_%d" % nth]["cmdflags"]):
		cmdlist.append("%s%s" % (["-","--"][cmd_hyphen], v))
     
        if  WCLOptions["exec_%d" % nth].has_key("cmdopts"):
            print "cmdopts is now deprecated!"
	    for k, v in WCLOptions["exec_%d" % nth]["cmdopts"].items():
	        cmdlist.append("%s%s" %(["-","--"][cmd_hyphen], k))
	        cmdlist.append(v)

    return ' '.join(cmdlist)

if __name__ == '__main__':
    debug = 1
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
