#!/usr/bin/env python

import os
import  sys
import wclutils
import time
import re
from collections import OrderedDict
from WrapperUtils import *

debug = 1

def expandDollarVars(fulldict, temp_dict, filepat):
    if debug: print "expanding filepat:", filepat
    temp_dict1 = {}
    filepars = re.findall("\${(.+?)}",filepat)
    for filepar in filepars:

        if filepar.find(":") > 0:
            name, func = filepar.split(":")
        else:
            name = filepar
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
	    d = d[list[i]]

        parval = d

        if parval.__class__ != ''.__class__:
            print "variable ", name ," lookup yeilded dictionary: ", d
            exit(1)

        #
        # handle ranges
        #
        if parval.startswith("(") and parval.endswith(")"):
            temp_dict1[filepar]=parval
            continue

        #
        # apply formatting functions:
        # :n makes applies %0nd format
        # :trim trims off .whatever suffixes
        #
        if func[0] in "0123456789":
            format = "%%0%sd" % func
            if debug: print "applying func %s to %s" % (func, parval)
            if debug: print "format is %s" % format
            parval = format % int(parval)
 
        if func == 'trim':
            parval =parval[0:parval.find('.')]
         
        filepat = filepat.replace('${'+filepar+'}',parval)
        if debug: print filepat

    filelist = [filepat] # .. create an initial file list with one item

    for key in temp_dict1.keys():

        if debug: print "Now doing %s list items" % key
        templist = [] # .. temporary list for each key

        for filelist_item in filelist:
       
            for item in temp_dict1[key].lstrip("(").rstrip(")").split(","):

                # ... Check to see if this is a range of numeric values
                isRange = False
                if item.count("-") == 1:
	            nums = item.split("-")
                    if len(nums) == 2:
                        if nums[0].isdigit() and nums[1].isdigit():
	                    num1 = int(nums[0])
	                    num2 = int(nums[1])
	                    if num1 > num2:
                                print "Lower bound %d > upper bound %d" % (num1,num2)
                                exit(1)
                            isRange = True
                       
                # ... Case when range of numeric values     
                if isRange:
                    for i in range(num1,num2+1):
	                if i < 10:
	                    nums = '0'+str(i)
                        else:
	                    nums = str(i)
                        newitem = filelist_item.replace('${'+key+'}',nums)
                        templist.append(newitem)

                # ... Case when single item or numeric value
                else:
                    tmps = item
                    if tmps.isdigit():
                        num = int(tmps)
	                if num < 10:
	                    tmps = '0'+str(num)
                        else:
	                    tmps = str(num)
                    newitem = filelist_item.replace('${'+key+'}',tmps)
                    templist.append(newitem)  

        filelist = templist # .. update the filelist
        if debug:
            for item in filelist:
                print item

    if len(filelist) > 1:
        return filelist
    else:
        return filelist[0]
    
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
    return res

def recurseExpand(res,cur):
    for sk in cur:
	if cur[sk].__class__ == ''.__class__:
	    cur[sk] = expandDollarVars(res, cur, cur[sk])
	else:
	    recurseExpand(res,cur[sk])

def genProvenance(WCLOptions, exitstatus, starttime):
    provenance=OrderedDict()

    provenance['wrapper'] =  OrderedDict(exitstatus = exitstatus , walltime =  time.time() - starttime)

    exec01 = OrderedDict()
    exec01['application'] = 'DECam_crosstalk'
    exec01['walltime'] = provenance['wrapper']['walltime']
    cmdlineargs = ''
    for args in sys.argv[1:]:
	cmdlineargs += ' ' + args
    exec01['commandline'] = os.path.realpath(sys.argv[0])+cmdlineargs

    for ftype in [ 'input', 'output', 'ancillary' ]:

	files = OrderedDict()
	n_file = 1
	for x in WCLOptions.get(ftype,{}).keys():
	    if WCLOptions[ftype][x].has_key('file_template'):
		for fname in WCLOptions[ftype][x]['file_template']['filename']:
     
		    if 0 == os.access(fname, os.R_OK):
			files['file_%d' % n_file] = OrderedDict()
			files['file_%d' % n_file].update(WCLOptions[ftype][x]['file_template'])
			files['file_%d' % n_file]['filename'] = fname
			n_file = n_file + 1
		    else:
			print "Expected ", ftype, " file ", fname , "not present"
			exit(1)
	    else:
		fname =  WCLOptions[ftype][x]['filename']
		if 0 == os.access(fname, os.R_OK):
		    files['file_%d' % n_file] = WCLOptions[ftype][x]
		    n_file = n_file+ 1
		else:
		    print "Expected ", ftype, " file ", fname , "not present"
		    exit(1)
		
	exec01[ftype] = files

    provenance['exec01'] = exec01
    prov_file = "proto_prov.wcl"

    status = writeProvenance(prov_file,OrderedDict(provenance=provenance))
    if status != 0:
	print "Failed to open %s. Exiting." %  prov_file
	exit(1)

def buildStockCommand(WCLOptions, doubledash = 0):
    cmdlist = [ WCLOptions["config"]["command"] ]

    for k, v in WCLOptions["config"]["command_line"].items():
	if k.startswith("_"):
	    cmdlist.append(v)
	else:
	    cmdlist.append("%s%s" %(["-","--"][doubledash], k))
	    cmdlist.append(v)

    if WCLOptions["config"].has_key("outlog"):
         cmdlist.append("> %s 2>&1" % WCLOptions["config"]["outlog"])

    return ' '.join(cmdlist)


