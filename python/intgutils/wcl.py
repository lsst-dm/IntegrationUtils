#!/usr/bin/env python

# $Id$
# $Rev::                                  $:  # Revision of last commit.
# $LastChangedBy::                        $:  # Author of last commit. 
# $LastChangedDate::                      $:  # Date of last commit.

"""
Contains utilities for use with the Workflow Control Language
"""

# Notes:
#     * position of <<include matters, all includes not processed first
#     * includes do not expand wildcards

import sys
import re
import os
from collections import OrderedDict
from collections import Mapping
import copy


import despymisc.miscutils as miscutils

class WCL(OrderedDict):
    def __init__(self, *args, **kwds):
        """ Initialize with given wcl """
    
        OrderedDict.__init__(self, *args, **kwds)
        self.search_order = OrderedDict()

    ###########################################################################
    def set_search_order(self, search_order):
        self.search_order = search_order


    ###########################################################################
    def __contains__(self, key, opts=None):
        """ D.__contains__(k) -> True if D has a key k, else False """
        (found, value) = self.search(key, opts)
        return found

    ###########################################################################
    def __getitem__(self, key, default=None, opts=None):
        """ x.__getitem__(y) <==> x[y] """

        (found, value) = self.search(key, opts)
        if not found:
            value = default
        return value

    ###########################################################################
    def __setitem__(self, key, val):
        """ x.__setitem__(i, y) <==> x[i]=y """
        OrderedDict.__setitem__(self, key, val)


    ###########################################################################
    def set(self, key, val):
        """ Sets value of key in wcl, follows section notation """

        miscutils.fwdebug(9, "WCL_DEBUG", "BEG")

        subkeys = key.split('.')
        valkey = subkeys.pop()
        wcldict = self
        for k in subkeys:
            wcldict = OrderedDict.__getitem__(wcldict,k)

        OrderedDict.__setitem__(wcldict, valkey, val)

        miscutils.fwdebug(9, "WCL_DEBUG", "END")



    ###########################################################################
    def search(self, key, opt=None):
        """ Searches for key using given opt following hierarchy rules """

        miscutils.fwdebug(8, 'WCL_DEBUG', "\tBEG")
        miscutils.fwdebug(8, 'WCL_DEBUG',
                 "\tinitial key = '%s'" % key)
        miscutils.fwdebug(8, 'WCL_DEBUG',
                 "\tinitial opts = '%s'" % opt)

        found = False
        value = ''
        if hasattr(key, 'lower'):
            key = key.lower()
        else:
            print "key = %s" % key

        # if key contains period, use it exactly instead of scoping rules
        if isinstance(key, str) and '.' in key:
            miscutils.fwdebug(8, 'WCL_DEBUG', "\t. in key '%s'" % key)

            value = self
            found = True
            for k in key.split('.'):
                miscutils.fwdebug(8, 'WCL_DEBUG', "\t\t partial key '%s'" % k)
                if k in value:
                    value = OrderedDict.__getitem__(value,k)
                    miscutils.fwdebug(8, 'WCL_DEBUG', "\t\t next val '%s'" % value)
                    found = True
                else:
                    value = ''
                    found = False
                    break
            
        else:
            # start with stored current values
            if OrderedDict.__contains__(self, 'current'):
                curvals = copy.deepcopy(OrderedDict.__getitem__(self, 'current'))
            else:
                curvals = OrderedDict()

            # override with current values passed into function if given
            if opt is not None and PF_CURRVALS in opt:
                for k,v in opt[PF_CURRVALS].items():
                    #print "using specified curval %s = %s" % (k,v)
                    curvals[k] = v

            #print "curvals = ", curvals
            if key in curvals:
                #print "found %s in curvals" % (key)
                found = True
                value = curvals[key]
            elif opt and 'searchobj' in opt and key in opt['searchobj']:
                found = True
                value = opt['searchobj'][key]
            else:
                #print dir(self)
                if hasattr(self, 'search_order'):
                    for sect in self.search_order:
                        #print "Searching section %s for key %s" % (sect, key)
                        if "curr_" + sect in curvals:
                            currkey = curvals['curr_'+sect]
                            #print "\tcurrkey for section %s = %s" % (sect, currkey)
                            if sect in self:
                                sectdict = OrderedDict.__getitem__(self,sect)
                                if currkey in sectdict:
                                    if key in sectdict[currkey]:
                                        found = True
                                        value = sectdict[currkey][key]
                                        break

            # lastly check global values
            if not found:
                #print "\t%s not found, checking global values" % (key)
                if OrderedDict.__contains__(self, key):
                    found = True
                    value = OrderedDict.__getitem__(self,key)


        if not found and opt and 'required' in opt and opt['required']:
            print "\n\nError: search for %s failed" % (key)
            print "\tcurrent = ", OrderedDict.__getitem__(self,'current')
            print "\topt = ", opt
            print "\tcurvals = ", curvals
            print "\n\n"
            raise KeyError("Error: Search failed (%s)" % key)

        if found and opt and 'replace_vars' in opt and opt['replace_vars']:
            opt['replace_vars'] = False
            value = self.replace_vars(value, opt)

        miscutils.fwdebug(8, 'WCL_DEBUG', "\tEND: found=%s, value=%s" % (found, value))
        return (found, value)


    ###########################################################################
    def replace_vars(self, value, opts=None):
        """ Replace variables in given value """
        miscutils.fwdebug(5, 'WCL_DEBUG', "BEG")
        miscutils.fwdebug(6, 'WCL_DEBUG', "\tinitial value = '%s'" % value)
        miscutils.fwdebug(6, 'WCL_DEBUG', "\tinitial opts = '%s'" % opts)

        maxtries = 1000    # avoid infinite loop
        count = 0
        done = False
        while not done and count < maxtries:
            done = True

            m = re.search("(?i)\$opt\{([^}]+)\}", value)
            while m and count < maxtries:
                count += 1
                var = m.group(1)
                print "opt var=",var
                parts = var.split(':')
                newvar = parts[0]
                if len(parts) > 1:
                    prpat = "%%0%dd" % int(parts[1])
                (haskey, newval) = self.search(newvar, opts)
                print "opt: type(newval):", newvar, type(newval)
                if haskey:
                    if '(' in newval or ',' in newval:
                        if 'expand' in opts and opts['expand']:
                            newval = '$LOOP{%s}' % var   # postpone for later expanding
                    elif len(parts) > 1:
                        newval = prpat % int(self.replace_vars(newval, opts))
                else:
                    newval = ""
                print "val = %s" % newval
                value = re.sub("(?i)\$opt{%s}" % var, newval, value)
                print value
                done = False
                m = re.search("(?i)\$opt\{([^}]+)\}", value)

            m = re.search("(?i)\$\{([^}]+)\}", value)
            while m and count < maxtries:
                count += 1
                var = m.group(1)
                miscutils.fwdebug(6, 'WCL_DEBUG', "\tfound req ${}: %s " % (var))
                parts = var.split(':')
                newvar = parts[0]
                miscutils.fwdebug(6, 'WCL_DEBUG', "\treq: newvar: %s " % (newvar))
                if len(parts) > 1:
                    prpat = "%%0%dd" % int(parts[1])
                (haskey, newval) = self.search(newvar, opts)
                miscutils.fwdebug(6, 'WCL_DEBUG',
                      "\treq: after search haskey, newvar, newval, type(newval): %s, %s %s %s" % (haskey, newvar, newval, type(newval)))
                if haskey:
                    newval = str(newval)
                    if '(' in newval or ',' in newval:
                        if opts is not None and 'expand' in opts and opts['expand']:
                            newval = '$LOOP{%s}' % var   # postpone for later expanding
                        miscutils.fwdebug(6, 'WCL_DEBUG', "\tnewval = %s" % newval)
                    elif len(parts) > 1:
                        try:
                            newval = prpat % int(self.replace_vars(newval, opts))
                        except ValueError as err:
                            print str(err)
                            print "prpat =", prpat
                            print "newval =", newval
                            raise err
                    value = re.sub("(?i)\${%s}" % var, newval, value)
                    done = False
                else:
                    raise KeyError("Error: Could not find value for %s" % newvar)
                m = re.search("(?i)\$\{([^}]+)\}", value)

        valuedone = []
        if '$LOOP' in value:
            if opts is not None:
                opts['required'] = True
                opts['replace_vars'] = False
            else:
                opts = {'required': True, 'replace_vars': False}

            looptodo = [ value ]
            while len(looptodo) > 0 and count < maxtries:
                count += 1
                miscutils.fwdebug(6, 'WCL_DEBUG',
                        "todo loop: before pop number in looptodo = %s" % len(looptodo))
                value = looptodo.pop()
                miscutils.fwdebug(6, 'WCL_DEBUG',
                        "todo loop: after pop number in looptodo = %s" % len(looptodo))

                miscutils.fwdebug(3, 'WCL_DEBUG', "todo loop: value = %s" % value)
                m = re.search("(?i)\$LOOP\{([^}]+)\}", value)
                var = m.group(1)
                parts = var.split(':')
                newvar = parts[0]
                if len(parts) > 1:
                    prpat = "%%0%dd" % int(parts[1])
                miscutils.fwdebug(6, 'WCL_DEBUG', "\tloop search: newvar= %s" % newvar)
                miscutils.fwdebug(6, 'WCL_DEBUG', "\tloop search: opts= %s" % opts)
                (haskey, newval) = self.search(newvar, opts)
                if haskey:
                    miscutils.fwdebug(6, 'WCL_DEBUG', "\tloop search results: newva1= %s" % newval)
                    newvalarr = fwsplit(newval)
                    for nv in newvalarr:
                        miscutils.fwdebug(6, 'WCL_DEBUG', "\tloop nv: nv=%s" % nv)
                        if len(parts) > 1:
                            try:
                                nv = prpat % int(nv)
                            except ValueError as err:
                                print str(err)
                                print "prpat =", prpat
                                print "nv =", nv
                                raise err
                        miscutils.fwdebug(6, 'WCL_DEBUG', "\tloop nv2: nv=%s" % nv)
                        miscutils.fwdebug(6, 'WCL_DEBUG', "\tbefore loop sub: value=%s" % value)
                        valsub = re.sub("(?i)\$LOOP\{%s\}" % var, nv, value)
                        miscutils.fwdebug(6, 'WCL_DEBUG', "\tafter loop sub: value=%s" % valsub)
                        if '$LOOP{' in valsub:
                            miscutils.fwdebug(6, 'WCL_DEBUG', "\t\tputting back in todo list")
                            looptodo.append(valsub)
                        else:
                            valuedone.append(valsub)
                            miscutils.fwdebug(6, 'WCL_DEBUG', "\t\tputting back in done list")
                miscutils.fwdebug(6, 'WCL_DEBUG', "\tNumber in todo list = %s" % len(looptodo))
                miscutils.fwdebug(6, 'WCL_DEBUG', "\tNumber in done list = %s" % len(valuedone))
            miscutils.fwdebug(6, 'WCL_DEBUG', "\tEND OF WHILE LOOP = %s" % len(valuedone))

        if count >= maxtries:
            raise Exception("Error: replace_vars function aborting from infinite loop '%s'")

        miscutils.fwdebug(6, 'WCL_DEBUG', "\tvaluedone = %s" % valuedone)
        miscutils.fwdebug(6, 'WCL_DEBUG', "\tvalue = %s" % value)
        miscutils.fwdebug(5, 'WCL_DEBUG', "END")

        if len(valuedone) > 1:
            return valuedone
        elif len(valuedone) == 1:
            return valuedone[0]
        else:
            return value

    def replace_varsKeep(self, value, opts=None):
        """ Replace variables in given value """
        miscutils.fwdebug(5, 'WCL_DEBUG', "BEG")
        miscutils.fwdebug(6, 'WCL_DEBUG', "\tinitial value = '%s'" % value)
        miscutils.fwdebug(6, 'WCL_DEBUG', "\tinitial opts = '%s'" % opts)

        keep = {}

        maxtries = 1000    # avoid infinite loop
        count = 0
        done = False
        while not done and count < maxtries:
            done = True

            m = re.search("(?i)\$opt\{([^}]+)\}", value)
            while m and count < maxtries:
                count += 1
                var = m.group(1)
                print "opt var=",var
                parts = var.split(':')
                newvar = parts[0]
                if len(parts) > 1:
                    prpat = "%%0%dd" % int(parts[1])
                (haskey, newval) = self.search(newvar, opts)
                print "opt: type(newval):", newvar, type(newval)
                if haskey:
                    if '(' in newval or ',' in newval:
                        if 'expand' in opts and opts['expand']:
                            newval = '$LOOP{%s}' % var   # postpone for later expanding
                    elif len(parts) > 1:
                        newval = prpat % int(self.replace_vars(newval, opts))
                        keep[newvar] = newval
                    else:
                        keep[newvar] = newval
                else:
                    newval = ""
                print "val = %s" % newval
                value = re.sub("(?i)\$opt{%s}" % var, newval, value)
                print value
                done = False
                m = re.search("(?i)\$opt\{([^}]+)\}", value)

            m = re.search("(?i)\$\{([^}]+)\}", value)
            while m and count < maxtries:
                count += 1
                var = m.group(1)
                parts = var.split(':')
                newvar = parts[0]
                miscutils.fwdebug(6, 'WCL_DEBUG', "\twhy req: newvar: %s " % (newvar))
                if len(parts) > 1:
                    prpat = "%%0%dd" % int(parts[1])
                (haskey, newval) = self.search(newvar, opts)
                miscutils.fwdebug(6, 'WCL_DEBUG',
                      "\twhy req: haskey, newvar, newval, type(newval): %s, %s %s %s" % (haskey, newvar, newval, type(newval)))
                if haskey:
                    newval = str(newval)
                    if '(' in newval or ',' in newval:
                        if opts is not None and 'expand' in opts and opts['expand']:
                            newval = '$LOOP{%s}' % var   # postpone for later expanding
                        miscutils.fwdebug(6, 'WCL_DEBUG', "\tnewval = %s" % newval)
                    elif len(parts) > 1:
                        try:
                            newval = prpat % int(self.replace_vars(newval, opts))
                            keep[newvar] = newval
                        except ValueError as err:
                            print str(err)
                            print "prpat =", prpat
                            print "newval =", newval
                            raise err
                    else:
                        keep[newvar] = newval

                    value = re.sub("(?i)\${%s}" % var, newval, value)
                    done = False
                else:
                    raise KeyError("Error: Could not find value for %s" % newvar)
                m = re.search("(?i)\$\{([^}]+)\}", value)

        print "keep = ", keep

        valpair = (value, keep)
        valuedone = []
        if '$LOOP' in value:
            if opts is not None:
                opts['required'] = True
                opts['replace_vars'] = False
            else:
                opts = {'required': True, 'replace_vars': False}

            looptodo = [ valpair ]
            while len(looptodo) > 0 and count < maxtries:
                count += 1
                miscutils.fwdebug(6, 'WCL_DEBUG',
                        "todo loop: before pop number in looptodo = %s" % len(looptodo))
                valpair = looptodo.pop()
                miscutils.fwdebug(6, 'WCL_DEBUG',
                        "todo loop: after pop number in looptodo = %s" % len(looptodo))

                miscutils.fwdebug(3, 'WCL_DEBUG', "todo loop: value = %s" % valpair[0])
                m = re.search("(?i)\$LOOP\{([^}]+)\}", valpair[0])
                var = m.group(1)
                parts = var.split(':')
                newvar = parts[0]
                if len(parts) > 1:
                    prpat = "%%0%dd" % int(parts[1])
                miscutils.fwdebug(6, 'WCL_DEBUG', "\tloop search: newvar= %s" % newvar)
                miscutils.fwdebug(6, 'WCL_DEBUG', "\tloop search: opts= %s" % opts)
                (haskey, newval) = self.search(newvar, opts)
                if haskey:
                    miscutils.fwdebug(6, 'WCL_DEBUG', "\tloop search results: newva1= %s" % newval)
                    newvalarr = fwsplit(newval)
                    for nv in newvalarr:
                        miscutils.fwdebug(6, 'WCL_DEBUG', "\tloop nv: nv=%s" % nv)
                        if len(parts) > 1:
                            try:
                                nv = prpat % int(nv)
                            except ValueError as err:
                                print str(err)
                                print "prpat =", prpat
                                print "nv =", nv
                                raise err
                        miscutils.fwdebug(6, 'WCL_DEBUG', "\tloop nv2: nv=%s" % nv)
                        miscutils.fwdebug(6, 'WCL_DEBUG', "\tbefore loop sub: value=%s" % value)
                        valsub = re.sub("(?i)\$LOOP\{%s\}" % var, nv, value)
                        keep = copy.deepcopy(valpair[1])
                        keep[newvar] = nv
                        miscutils.fwdebug(6, 'WCL_DEBUG', "\tafter loop sub: value=%s" % valsub)
                        if '$LOOP{' in valsub:
                            miscutils.fwdebug(6, 'WCL_DEBUG', "\t\tputting back in todo list")
                            looptodo.append((valsub, keep))
                        else:
                            valuedone.append((valsub, keep))
                            miscutils.fwdebug(6, 'WCL_DEBUG', "\t\tputting back in done list")
                miscutils.fwdebug(6, 'WCL_DEBUG', "\tNumber in todo list = %s" % len(looptodo))
                miscutils.fwdebug(6, 'WCL_DEBUG', "\tNumber in done list = %s" % len(valuedone))
            miscutils.fwdebug(6, 'WCL_DEBUG', "\tEND OF WHILE LOOP = %s" % len(valuedone))

        if count >= maxtries:
            raise Exception("Error: replace_vars function aborting from infinite loop '%s'" % value)

        miscutils.fwdebug(6, 'WCL_DEBUG', "\tvaluedone = %s" % valuedone)
        miscutils.fwdebug(6, 'WCL_DEBUG', "\tvalue = %s" % value)
        miscutils.fwdebug(5, 'WCL_DEBUG', "END")

        if len(valuedone) > 1:
            return valuedone
        elif len(valuedone) == 1:
            return valuedone[0]
        else:
            return valpair


    #######################################################################
    def search_wcl_for_variables(wcl):
        miscutils.fwdebug(9, "WCL_DEBUG", "BEG")
        usedvars = {}
        for key, val in wcl.items():
            if type(val) is dict or type(val) is OrderedDict:
                uvars = search_wcl_for_variables(val)
                if uvars is not None:
                    usedvars.update(uvars)
            elif type(val) is str:
                viter = [m.group(1) for m in re.finditer('(?i)\$\{([^}]+)\}', val)]
                for vstr in viter:
                    if ':' in vstr:
                        vstr = vstr.split(':')[0]
                    usedvars[vstr] = True
            else:
                miscutils.fwdebug(9, "WCL_DEBUG", "Note: wcl is not string.    key = %s, type(val) = %s, val = '%s'" % (key, type(val), val))

        miscutils.fwdebug(9, "WCL_DEBUG", "END")
        return usedvars




    #######################################################################
    def write_wcl(self, out_file=None, sortit=False, indent=4):
        """Outputs a given dictionary in WCL format where items within 
           the same sub-dictionary are output in alphabetical order"""

        if out_file is None:
            out_file = sys.stdout

        self._recurs_write_wcl(self, out_file, sortit, indent, 0)
    
    
    def _recurs_write_wcl(self, wcl_dict, out_file, sortit, inc_indent, curr_indent):
        """Internal recursive function to do actual WCL writing"""
        if len(wcl_dict) > 0: 
            if sortit:
                dictitems = sorted(wcl_dict.items())
            else:
                dictitems = wcl_dict.items()
    
            for key, value in dictitems:
                if isinstance(value, dict):
                    print >> out_file, ' ' * curr_indent + "<" + str(key) + ">"
                    self._recurs_write_wcl(value, out_file, sortit, inc_indent, 
                                        curr_indent + inc_indent) 
                    print >> out_file, ' ' * curr_indent + "</" + str(key) + ">"
                else:
                    print >> out_file, ' ' * curr_indent + str(key) + \
                            " = " + str(value)
    
    
    def read_wcl(self, in_file=None, cmdline=False, filename='stdin'):
        """Reads WCL text from an open file object and returns a dictionary"""
    
        curr = self
        stack = []  # to keep track of current sub-dictionary
        stackkeys = ['__topwcl__']  # to keep track of current section key
        stack.append(curr) # 
    
        line = in_file.readline()
        linecnt = 1
        while line:
            # delete comments
            line = line.split('#')[0]
    
            # skip comment line or empty line
            if re.search("\S", line):
                # handle includes
                patmatch = re.search("<<include (\S+)>>", line)
                if patmatch is not None:
                    # expand ~ and env vars in filename
                    filename2 = os.path.expandvars(os.path.expanduser(patmatch.group(1)))
    
                    wclobj2 = WCL()
                    with open(filename2, "r") as wclfh:
                        wclobj2.read_wcl(wclfh, cmdline, filename2)
                    self.update(wclobj2)
                    line = in_file.readline()
                    linecnt += 1
                    continue
        
                # handle group closing line <\string>
                pat_match = re.search("^\s*</\s*(\S+)\s*>\s*$", line)
                if pat_match is not None:
                    key = pat_match.group(1).lower()
                    if key == 'cmdline' or key == 'replace':
                        cmdline = False
                    sublabel = '__sublabel__' in curr   
                    if sublabel:
                        del curr['__sublabel__']
            
                    if key == stackkeys[len(stackkeys)-1]:
                        stackkeys.pop()
                        stack.pop()
                        curr = stack[len(stack)-1]
                    elif sublabel: 
                        if key == stackkeys[len(stackkeys) - 2]:
                            stackkeys.pop()
                            stack.pop()
                            curr = stack[len(stack)-1]
    
                            stackkeys.pop()
                            stack.pop()
                            curr = stack[len(stack)-1]
                        else:
                            print "******************************"
                            print "Linecnt =", linecnt
                            print "Line =", line.strip()
                            print "Closing Key =", key
                            _print_stack(stackkeys, stack)
    
                            raise SyntaxError('File %s Line %d - Error:  Invalid or missing section close.   Got close for %s. Expecting close for %s.' % (filename, linecnt, key, stackkeys[len(stackkeys) - 2]))
                    else:
                        print "******************************"
                        print "Linecnt =", linecnt
                        print "Line =", line.strip()
                        print "Closing Key =", key
                        _print_stack(stackkeys, stack)
                        raise SyntaxError('File %s Line %d - Error:  Invalid or missing section close.  Got close for %s. Expecting close for %s.' % (filename, linecnt, key, stackkeys[len(stackkeys)-1]))
                        
                    line = in_file.readline()
                    linecnt += 1
                    continue
        
                # handle group opening line <key sublabel> or <key>
                pat_match = re.search("^\s*<(\S+)\s*(\S+)?>\s*$", line)
                if pat_match is not None:
                    key = pat_match.group(1).lower()
    
                    # check for case where missing / when closing section
                    if key == stackkeys[-1]:
                        print "******************************"
                        print "Linecnt =", linecnt
                        print "Line =", line.strip()
                        print "Opening Key =", key
                        _print_stack(stackkeys, stack)
                        raise SyntaxError('File %s Line %d - Error:  found child section with same name (%s)' % (filename, linecnt, key))
    
                    stackkeys.append(key)
    
                    if not key in curr: 
                        curr[key] = OrderedDict()
    
                    stack.append(curr[key])
                    curr = curr[key]
        
                    if key == 'cmdline' or key == 'replace':
                        cmdline = True
    
                    if pat_match.group(2) is not None:
                        val = pat_match.group(2).lower()
                        stackkeys.append(val)
                        if not val in curr: 
                            curr[val] = OrderedDict()
                        curr[val]['__sublabel__'] = True
                        stack.append(curr[val])
                        curr = curr[val]
                    line = in_file.readline()
                    linecnt += 1
                    continue
        
                # handle key/val line: key = val 
                pat_key_val = "^\s*(\S+)(\s*=\s*)(.+)\s*$"
                pat_match = re.search(pat_key_val, line)
                if pat_match is not None:
                    key = pat_match.group(1)
                    if not cmdline:
                        key = key.lower()
                    curr[key] = pat_match.group(3).strip()
                    line = in_file.readline()
                    linecnt += 1
                    continue
    
                pat_key_val = "^\s*(\S+)(\s+)([^=].*)\s*$"
                pat_match = re.search(pat_key_val, line)
                if pat_match is not None:
                    key = pat_match.group(1)
                    if not cmdline:
                        key = key.lower()
                    curr[key] = pat_match.group(3).strip()
                    line = in_file.readline()
                    linecnt += 1
                    continue
                
                print "Warning: Ignoring line #%d (did not match patterns):" % linecnt
                print line
        
            # goto next line if no matches
            line = in_file.readline()
            linecnt += 1
        
        # done parsing input, should only be main dict in stack
        if len(stack) != 1 or len(stackkeys) != 1:
            _print_stack(stackkeys, stack)
            raise SyntaxError("File %s - Error parsing wcl_file.  Check that all sections have closing line." % filename)

    ############################################################
    def update(self, udict):
        """ update allowing for nested dictionaries """

        for k, v in udict.iteritems():
            if isinstance(v, Mapping):
                r = miscutils.updateOrderedDict(self.get(k, OrderedDict()), v)
                self[k] = r
            else:
                self[k] = udict[k]
        
    
    ############################################################
    def _run_test():
        """Calls read and write routines as a test"""
    
        # created in order for the following variables
        # to be local instead of at module level
    
        if len(sys.argv) != 2:
            test_wcl_fh = sys.stdin
            test_fname = 'stdin'
        else:
            test_fname = sys.argv[1]
            test_wcl_fh = open(test_fname, "r")

        testwcl = WCL()
        try:
            testwcl.read_wcl(test_wcl_fh, filename=test_fname)
        except SyntaxError as err:
            print err
            sys.exit(1)
            
        test_wcl_fh.close()
        testwcl.write_wcl(sys.stdout, False, 4)
    #   testwcl.write_wcl(sys.stdout, True, 4)
    
    
    ############################################################
    def _print_stack(stackkeys, stack):
        print "----- STACK -----"
        if len(stackkeys) != len(stack):
            print "\tWarning: stackkeys and stack not same length"
        for i in range(0,max(len(stackkeys), len(stack))):
            k = None
            s = None
            if i < len(stackkeys):
                k = stackkeys[i] 
            if i < len(stack):
                s = stack[i].keys()
            print "\t%d: %s = %s" % (i, k, s)
        print "\n\n"
        
    
if __name__ ==  "__main__":
    _run_test()
