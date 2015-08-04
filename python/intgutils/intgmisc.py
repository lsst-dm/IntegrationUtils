#!/usr/bin/env python

# $Id$
# $Rev::                                  $:  # Revision of last commit.
# $LastChangedBy::                        $:  # Author of last commit.
# $LastChangedDate::                      $:  # Date of last commit.

"""
Contains misc integration utilities
"""

import shlex
import os
import re
import despymisc.subprocess4 as subprocess4
import despymisc.miscutils as miscutils

######################################################################
def check_files(fullnames):
    """ Check whether given files do exist on disk """

    exists = []
    missing = []
    for fname in fullnames:
        if os.path.exists(fname):
            bname = miscutils.parse_fullname(fname, miscutils.CU_PARSE_BASENAME)
            exists.append(bname)
            print "check_files: exists: ", fname, bname
        else:
            print "check_files: missing: ", fname
            missing.append(fname)
    print "check_files: exists =", exists
    print "check_files: missing =", missing
    return (exists, missing)

#######################################################################
def get_cmd_hyphen(hyphen_type, cmd_option):
    """ Determine correct hyphenation for command line argument """

    hyphen = '-'

    if hyphen_type == 'alldouble':
        hyphen = '--'
    elif hyphen_type == 'allsingle':
        hyphen = '-'
    elif hyphen_type == 'mixed_gnu':
        if len(cmd_option) == 1:
            hyphen = '-'
        else:
            hyphen = '--'
    else:
        raise ValueError('Invalid cmd hyphen type (%s)' % hyphen_type)

    return hyphen

#######################################################################
def get_exec_sections(wcl, prefix):
    """ Returns exec sections appearing in given wcl """
    execs = {}
    for key, val in wcl.items():
        if miscutils.fwdebug_check(3, "INTGMISC_DEBUG"):
            miscutils.fwdebug_print("\tsearching for exec prefix in %s" % key)

        if re.search(r"^%s\d+$" % prefix, key):
            if miscutils.fwdebug_check(4, "INTGMISC_DEBUG"):
                miscutils.fwdebug_print("\tFound exec prefex %s" % key)
            execs[key] = val
    return execs

#######################################################################
def run_exec(cmd):
    """ Run an executable with given command returning process information """

    procfields = ['ru_idrss', 'ru_inblock', 'ru_isrss', 'ru_ixrss',
                  'ru_majflt', 'ru_maxrss', 'ru_minflt', 'ru_msgrcv',
                  'ru_msgsnd', 'ru_nivcsw', 'ru_nsignals', 'ru_nswap',
                  'ru_nvcsw', 'ru_oublock', 'ru_stime', 'ru_utime']
    retcode = None
    procinfo = None

    subp = subprocess4.Popen(shlex.split(cmd), shell=False)
    retcode = subp.wait4()
    procinfo = dict((field, getattr(subp.rusage, field)) for field in procfields)

    return (retcode, procinfo)


#######################################################################
def remove_column_format(columns):
    """ Return columns minus any formatting specification """

    columns2 = []
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
    """ convert a string of columns to list of columns """
    columns = re.findall(r'\$\S+\{.*\}|[^,\s]+', colstr)

    if not with_format:
        columns = remove_column_format(columns)
    return columns


#######################################################################
def get_fullnames_from_listfile(listfile, linefmt, colstr):
    """ Read a list file returning fullnames from the list """

    if miscutils.fwdebug_check(3, 'INTGMISC_DEBUG'):
        miscutils.fwdebug_print('colstr=%s' % colstr)

    columns = convert_col_string_to_list(colstr, False)

    if miscutils.fwdebug_check(3, 'INTGMISC_DEBUG'):
        miscutils.fwdebug_print('columns=%s' % columns)

    fullnames = {}
    pos2fsect = {}
    for pos in range(0, len(columns)):
        lcol = columns[pos].lower()
        if lcol.endswith('.fullname'):
            filesect = lcol[:-9]
            pos2fsect[pos] = filesect
            fullnames[filesect] = []
        # else a data column instead of a filename

    if miscutils.fwdebug_check(3, 'INTGMISC_DEBUG'):
        miscutils.fwdebug_print('pos2fsect=%s' % pos2fsect)

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
