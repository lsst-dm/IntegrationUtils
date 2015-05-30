#!/usr/bin/env python

# $Id$
# $Rev::                                  $:  # Revision of last commit.
# $LastChangedBy::                        $:  # Author of last commit.
# $LastChangedDate::                      $:  # Date of last commit.

"""
Contains misc integration utilities
"""

import shlex
import re
import despymisc.subprocess4 as subprocess4
import despymisc.miscutils as miscutils
from collections import OrderedDict


#######################################################################
def run_exec(cmd):
    retcode = None
    procinfo = None
    
    subp = subprocess4.Popen(shlex.split(cmd), shell=False)
    retcode = subp.wait4()
    procinfo = dict((field, getattr(subp.rusage, field)) for field in ['ru_idrss', 'ru_inblock', 'ru_isrss', 'ru_ixrss', 'ru_majflt', 'ru_maxrss', 'ru_minflt', 'ru_msgrcv', 'ru_msgsnd', 'ru_nivcsw', 'ru_nsignals', 'ru_nswap', 'ru_nvcsw', 'ru_oublock', 'ru_stime', 'ru_utime'])

    return (retcode, procinfo)


#######################################################################
def remove_column_format(columns):
    """ Return columns minus any formatting specification """

    columns2=[]
    for col in columns:
        if col.startswith('$FMT{'):
            rmatch = re.match(r'\$FMT\{\s*([^,]+)\s*,\s*(\S+)\s*\}', col)
            if rmatch:
                columns2.append(rmatch.group(2).strip())
            else:
                miscutils.fwdie("Error: invalid FMT column: %s" % (col), 1)
        else:
            columns2.append(col)
    return columns2


#######################################################################
def convert_col_string_to_list(colstr, with_format=True):
    columns = re.findall(r'\$\S+\{.*\}|[^,\s]+', colstr)

    if not with_format:
        columns = remove_column_format(columns)
    return columns


#######################################################################
def get_fullnames_from_listfile(listfile, linefmt, colstr):
    miscutils.fwdebug(0, 'INTGMISC_DEBUG', 'colstr=%s' % colstr)
    columns = convert_col_string_to_list(colstr, False)
    miscutils.fwdebug(0, 'INTGMISC_DEBUG', 'columns=%s' % columns)

    fullnames = {}
    pos2fsect = {} 
    for pos in range(0, len(columns)):
        lcol = columns[pos].lower()
        if lcol.endswith('.fullname'):
            filesect = lcol[:-9]
            pos2fsect[pos] = filesect
            fullnames[filesect] = []
        # else a data column instead of a filename
    miscutils.fwdebug(0, 'INTGMISC_DEBUG', 'pos2fsect=%s' % pos2fsect)

    if linefmt == 'config' or linefmt == 'wcl':
        miscutils.fwdie('Error:  wcl list format not currently supported (%s)' % listfile, 1)
    else:
        with open(listfile, 'r') as listfh:
            for line in listfh:
                line = line.strip()

                # convert line into python list 
                lineinfo = []
                if linefmt == 'textcsv':
                    lineinfo = miscutils.fwsplit(line, ',')
                elif linefmt == 'texttab':
                    lineinfo = miscutils.fwsplit(line, '\t')
                elif linefmt == 'textsp':
                    lineinfo = miscutils.fwsplit(line, ' ')
                else:
                    miscutils.fwdie('Error:  unknown linefmt (%s)' % linefmt, 1)
            
                # save each fullname in line
                for pos in pos2fsect:
                    fullnames[pos2fsect[pos]].append(lineinfo[pos])

    return fullnames
