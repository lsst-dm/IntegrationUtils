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
from collections import OrderedDict
from collections import Mapping

def write_wcl(wcl_dict, out_file=None, sortit=False, indent=4):
    """Outputs a given dictionary in WCL format where items within 
       the same sub-dictionary are output in alphabetical order"""
    if out_file is None:
        out_file = sys.stdout
    if wcl_dict is None:
        assert("Passed in None for dictionary arg")
    if not isinstance(wcl_dict, dict):
        assert("Passed in non-dictionary object for dictionary arg")
    _recurs_write_wcl(wcl_dict, out_file, sortit, indent, 0)


def _recurs_write_wcl(wcl_dict, out_file, sortit, inc_indent, curr_indent):
    """Internal recursive function to do actual WCL writing"""
    if len(wcl_dict) > 0: 
        if sortit:
            dictitems = sorted(wcl_dict.items())
        else:
            dictitems = wcl_dict.items()

        for key, value in dictitems:
            if isinstance(value, dict):
                print >> out_file, ' ' * curr_indent + "<" + str(key) + ">"
                _recurs_write_wcl(value, out_file, sortit, inc_indent, 
                                    curr_indent + inc_indent) 
                print >> out_file, ' ' * curr_indent + "</" + str(key) + ">"
            else:
                print >> out_file, ' ' * curr_indent + str(key) + \
                        " = " + str(value)


def read_wcl(in_file=None, cmdline=False):
    """Reads WCL text from an open file object and returns a dictionary"""
    wcl_dict = OrderedDict()
    curr = wcl_dict
    stack = []  # to keep track of current sub-dictionary
    stack.append(wcl_dict) # 

    line = in_file.readline()
    while line:
        # delete comments
        line = line.split('#')[0]

        # skip comment line or empty line
        if re.search("\S", line):
            # handle includes
            patmatch = re.search("<<include (\S+)>>", line)
            if patmatch is not None:
                wcl_file2 = open(patmatch.group(1))
                wcl_dict2 = read_wcl(wcl_file2, cmdline)
                wcl_file2.close()
                updateDict(wcl_dict, wcl_dict2)
                line = in_file.readline()
                continue
    
            # handle group closing line <\string>
            pat_match = re.search("^\s*</\s*(\S+)\s*>\s*$", line)
            if pat_match is not None:
                key = pat_match.group(1).lower()
                if key == 'cmdline' or key == 'replace':
                    cmdline = False
                stack.pop()
                curr = stack[len(stack)-1]
                while not key in curr: 
                    stack.pop()
                    curr = stack[len(stack)-1]
                line = in_file.readline()
                continue
    
            # handle group opening line <str1 str2> or <str1>
            pat_match = re.search("^\s*<(\S+)\s*(\S+)?>\s*$", line)
            if pat_match is not None:
                key = pat_match.group(1).lower()
    
                if not key in curr: 
                    curr[key] = OrderedDict()
                stack.append(curr[key])
                curr = curr[key]
    
                if key == 'cmdline' or key == 'replace':
                    cmdline = True

                if pat_match.group(2) is not None:
                    val = pat_match.group(2).lower()
                    if not val in curr: 
                        curr[val] = OrderedDict()
                    stack.append(curr[val])
                    curr = curr[val]
                line = in_file.readline()
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
                continue

            pat_key_val = "^\s*(\S+)(\s+)([^=].*)\s*$"
            pat_match = re.search(pat_key_val, line)
            if pat_match is not None:
                key = pat_match.group(1)
                if not cmdline:
                    key = key.lower()
                curr[key] = pat_match.group(3).strip()
                line = in_file.readline()
                continue
            
            print "Warning: Ignoring the following line (did not match patterns):"
            print line
    
        # goto next line if no matches
        line = in_file.readline()
    
    # done parsing input, should only be main dict in stack
    if len(stack) != 1:
        assert("Error parsing wcl_file.  Check that all groups \
                have closing line.")

    return wcl_dict

def updateDict(d, u):
    """ update dictionary recursively to update nested dictionaries """
    for k, v in u.iteritems():
        if isinstance(v, Mapping):
            r = updateDict(d.get(k, {}), v)
            d[k] = r
        else:
            d[k] = u[k]
    return d
    

############################################################
def _run_test():
    """Calls read and write routines as a test"""

    # created in order for the following variables
    # to be local instead of at module level

    if len(sys.argv) != 2:
        test_wcl_file = sys.stdin
    else:
        test_fname = sys.argv[1]
        test_wcl_file = open(test_fname, "r")
    test_wcl_dict = read_wcl(test_wcl_file)
    test_wcl_file.close()
    write_wcl(test_wcl_dict, sys.stdout, False, 4)
#    write_wcl(test_wcl_dict, sys.stdout, True, 4)

if __name__ ==  "__main__":
    _run_test()
