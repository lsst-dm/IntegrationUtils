#!/usr/bin/env python

# $Id$
# $Rev::                                  $:  # Revision of last commit.
# $LastChangedBy::                        $:  # Author of last commit.
# $LastChangedDate::                      $:  # Date of last commit.

"""
Contains definition of basic wrapper class
"""

import time
import os
import sys
import subprocess
import traceback
import re
import errno
from collections import OrderedDict

import intgutils.intgdefs as intgdefs
import intgutils.intgmisc as intgmisc
import despymisc.miscutils as miscutils
import despymisc.provdefs as provdefs

from intgutils.wcl import WCL


WRAPPER_OUTPUT_PREFIX = 'WRAP: '


class BasicWrapper(object):
    """ Basic wrapper class """

    ######################################################################
    def __init__(self, wclfile, debug=1):
        """ Read input wcl to initialize object """

        self.input_filename = wclfile
        self.inputwcl = WCL()
        with open(wclfile, 'r') as infh:
            self.inputwcl.read_wcl(infh)
        self.debug = debug

        # note: WGB handled by file registration using OW_OUTPUTS_BY_SECT
        provdict = OrderedDict({provdefs.PROV_USED: OrderedDict(),
                                provdefs.PROV_WDF: OrderedDict()})
        self.outputwcl = WCL({'wrapper': OrderedDict(),
                              intgdefs.OW_PROV_SECT: provdict,
                              intgdefs.OW_OUTPUTS_BY_SECT: {}})

        self.last_num_derived = 0
        self.last_num_meta = 0
        self.curr_task = []
        self.curr_exec = None

    ######################################################################
    def get_status(self):
        """ Return status of wrapper execution """
        status = 1
        if 'status' in self.outputwcl['wrapper']:
            status = self.outputwcl['wrapper']['status']

        return status

    ######################################################################
    def check_command_line(self, exsect, exwcl):
        """ Ensure that certain command line arguments are specified """
        # pylint: disable=unused-argument

        self.start_exec_task('check_command_line')

        #if intgdefs.IW_CHECK_COMMAND in self.inputwcl and \
        #   miscutils.convertBool(self.inputwcl[intgdefs.IW_CHECK_COMMAND]):
        #
        #    if intgdefs.IW_EXEC_DEF in self.inputwcl:
        #        execdefs = self.inputwcl[intgdefs.IW_EXEC_DEF]
        #
        #        execsect = "%s_%s" % (intgdefs.IW_EXEC_PREFIX, execnum)
        #        if (execsect.lower() in execdefs and
        #                intgdefs.IW_CMD_REQ_ARGS in execdefs[execsect.lower()]):
        #            req_args = miscutils.fwsplit(execdefs[execsect.lower()][intgdefs.IW_CMD_REQ_ARGS], ',')
        #

        self.end_exec_task(0)

        return 0


    ######################################################################
    def create_command_line(self, execnum, exwcl):
        """ Create command line string handling hyphens appropriately"""
        if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
            miscutils.fwdebug_print("execnum = '%s', exwcl = '%s'" % (execnum, exwcl),
                                    WRAPPER_OUTPUT_PREFIX)
        self.start_exec_task('create_command_line')

        cmdstr = ""
        if 'execname' in exwcl:
            cmdlist = [exwcl['execname']]

            if 'cmdline' in exwcl:
                posargs = {}  # save positional args to insert later

                hyphen_type = 'allsingle'
                if 'cmd_hyphen' in exwcl:
                    hyphen_type = exwcl['cmd_hyphen']

                # loop through command line args
                for key, val in exwcl['cmdline'].items():
                    if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
                        miscutils.fwdebug_print("key = '%s', val = '%s'" % (key, val),
                                                WRAPPER_OUTPUT_PREFIX)
                    expandval = self.inputwcl.replace_vars(val)  # replace any variables
                    if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
                        miscutils.fwdebug_print("expandval = '%s'" % (expandval),
                                                WRAPPER_OUTPUT_PREFIX)

                    if key.startswith('_'):
                        patmatch = re.match(r'_(\d+)', key)
                        if patmatch:
                            posargs[patmatch.group(1)] = expandval  # save for later
                        else:
                            raise ValueError('Invalid positional argument name: %s' % key)
                    else:
                        hyphen = intgmisc.get_cmd_hyphen(hyphen_type, key)

                        if expandval == '_flag':
                            cmdlist.append(" %s%s" % (hyphen, key))
                        else:
                            cmdlist.append(" %s%s %s" % (hyphen, key, expandval))

                # insert position sensitive arguments into specified location in argument list
                for k in sorted(posargs.iterkeys()):
                    cmdlist.insert(int(k), "%s" % posargs[k])

            # convert list of args into string
            if miscutils.fwdebug_check(6, 'BASICWRAP_DEBUG'):
                miscutils.fwdebug_print("cmdlist = '%s'" % (cmdlist), WRAPPER_OUTPUT_PREFIX)
            cmdstr = ' '.join(cmdlist)
        else:
            print "Error: missing execname in wcl for exec #%d" % execnum
            print "exec wcl = %s" % exwcl
            raise KeyError('Missing execname in wcl for exec #%d' % execnum)

        if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
            miscutils.fwdebug_print("cmdstr = '%s'" % (cmdstr), WRAPPER_OUTPUT_PREFIX)
        self.curr_exec['cmdline'] = cmdstr
        self.end_exec_task(0)


    ######################################################################
    def save_exec_version(self, exwcl):
        """ Run command with version flag and parse output for version information """
        # assumes exit code for version is 0

        self.start_exec_task('save_exec_version')

        ver = None

        execname = exwcl['execname']
        if 'version_flag' in exwcl and 'version_pattern' in exwcl:
            verflag = exwcl['version_flag']
            verpat = exwcl['version_pattern']

            cmd = "%s %s" % (execname, verflag)
            try:
                process = subprocess.Popen(cmd.split(),
                                           shell=False,
                                           stdout=subprocess.PIPE,
                                           stderr=subprocess.STDOUT)
            except:
                (exc_type, exc_value) = sys.exc_info()[0:1]
                print "********************"
                print "Unexpected error: %s - %s" % (exc_type, exc_value)
                print "cmd> %s" % cmd
                print "Probably could not find %s in path" % cmd.split()[0]
                print "Check for mispelled execname in submit wcl or"
                print "    make sure that the corresponding eups package is in the metapackage "
                print "    and it sets up the path correctly"
                raise

            process.wait()
            out = process.communicate()[0]
            if process.returncode != 0:
                miscutils.fwdebug_print("INFO:  problem when running code to get version",
                                        WRAPPER_OUTPUT_PREFIX)
                miscutils.fwdebug_print("\t%s %s %s" % (execname, verflag, verpat),
                                        WRAPPER_OUTPUT_PREFIX)
                miscutils.fwdebug_print("\tcmd> %s" % cmd, WRAPPER_OUTPUT_PREFIX)
                miscutils.fwdebug_print("\t%s" % out, WRAPPER_OUTPUT_PREFIX)
                ver = None
            else:
                # parse output with verpat
                try:
                    vmatch = re.search(verpat, out)
                    if vmatch:
                        ver = vmatch.group(1)
                    else:
                        if miscutils.fwdebug_check(1, 'BASICWRAP_DEBUG'):
                            miscutils.fwdebug_print("re.search didn't find version for exec %s" % \
                                                    execname, WRAPPER_OUTPUT_PREFIX)
                        if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
                            miscutils.fwdebug_print("\tcmd output=%s" % out, WRAPPER_OUTPUT_PREFIX)
                            miscutils.fwdebug_print("\tcmd verpat=%s" % verpat,
                                                    WRAPPER_OUTPUT_PREFIX)
                except Exception as err:
                    #print type(err)
                    ver = None
                    print "Error: Exception from re.match.  Didn't find version: %s" % err
                    raise
        else:
            miscutils.fwdebug_print("INFO: Could not find version info for exec %s" % execname,
                                    WRAPPER_OUTPUT_PREFIX)
            ver = None

        if ver is not None:
            self.curr_exec['version'] = ver
        self.end_exec_task(0)

    ######################################################################
    def create_output_dirs(self, exwcl):
        """ Make directories for output files """

        self.start_exec_task('create_output_dirs')

        if intgdefs.IW_OUTPUTS in exwcl:
            for sect in miscutils.fwsplit(exwcl[intgdefs.IW_OUTPUTS]):
                sectkeys = sect.split('.')
                if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
                    miscutils.fwdebug_print("INFO: sectkeys=%s" % sectkeys, WRAPPER_OUTPUT_PREFIX)
                if sectkeys[0] == intgdefs.IW_FILE_SECT:
                    sectname = sectkeys[1]
                    if sectname in self.inputwcl[intgdefs.IW_FILE_SECT]:
                        if 'fullname' in self.inputwcl[intgdefs.IW_FILE_SECT][sectname]:
                            fullnames = self.inputwcl[intgdefs.IW_FILE_SECT][sectname]['fullname']
                            if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
                                miscutils.fwdebug_print("INFO: fullname = %s" % fullnames,
                                                        WRAPPER_OUTPUT_PREFIX)
                            if '$RNMLST{' in fullnames:
                                raise ValueError('$RNMLST in output filename')
                            else:
                                for fname in miscutils.fwsplit(fullnames, ','):
                                    outdir = os.path.dirname(fname)
                                    miscutils.coremakedirs(outdir)

        self.end_exec_task(0)

    ######################################################################
    def run_exec(self):
        """ Run given command line """

        if miscutils.fwdebug_check(6, 'BASICWRAP_DEBUG'):
            miscutils.fwdebug_print("cmdline = %s" % (self.curr_exec['cmdline']),
                                    WRAPPER_OUTPUT_PREFIX)
        print '*' * 70

        self.start_exec_task('run_exec')
        cmdline = self.curr_exec['cmdline']

        retcode = None
        procinfo = None

        sys.stdout.flush()
        try:
            (retcode, procinfo) = intgmisc.run_exec(cmdline)
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                raise

            print "********************"
            (exc_type, exc_value, _) = sys.exc_info()
            print "%s - %s" % (exc_type, exc_value)
            print "cmd> %s" % cmdline
            print "Probably could not find %s in path" % cmdline.split()[0]
            print "Check for mispelled execname in submit wcl or"
            print "    make sure that the corresponding eups package is in "
            print "    the metapackage and it sets up the path correctly"
            raise

        sys.stdout.flush()

        if retcode != 0:
            if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
                miscutils.fwdebug_print("\tInfo: cmd exited with non-zero exit code = %s" % retcode,
                                        WRAPPER_OUTPUT_PREFIX)
                miscutils.fwdebug_print("\tInfo: failed cmd = %s" % cmdline, WRAPPER_OUTPUT_PREFIX)
        else:
            if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
                miscutils.fwdebug_print("\tInfo: cmd exited with exit code = 0",
                                        WRAPPER_OUTPUT_PREFIX)

        if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
            miscutils.fwdebug_print("END", WRAPPER_OUTPUT_PREFIX)
        print '*' * 70
        self.curr_exec['status'] = retcode
        self.curr_exec['procinfo'] = procinfo

        self.end_exec_task(retcode)


    ######################################################################
    def check_input_files(self, sectname):
        """ Check that the files for a single input file section exist """

        print "check_input_files: sectname = ", sectname
        fnames = miscutils.fwsplit(self.inputwcl[intgdefs.IW_FILE_SECT][sectname]['fullname'], ',')
        print "check_input_files: fnames = ", fnames
        (exists1, missing1) = intgmisc.check_files(fnames)
        return ({sectname: exists1}, missing1)


    ######################################################################
    def check_input_lists(self, sectname):
        """ Check that the list and contained files for a single input list section exist """

        ldict = self.inputwcl[intgdefs.IW_LIST_SECT][sectname]
        # check list itself exists
        listname = ldict['fullname']
        if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
            miscutils.fwdebug_print("\tInfo: Checking existence of '%s'" % listname,
                                    WRAPPER_OUTPUT_PREFIX)

        listfmt = intgdefs.DEFAULT_LIST_FORMAT
        if intgdefs.LIST_FORMAT in ldict:
            listfmt = ldict[intgdefs.LIST_FORMAT]

        existfiles = {}
        missingfiles = []

        if not os.path.exists(listname):
            miscutils.fwdebug_print("\tError: input list '%s' does not exist." % listname,
                                    WRAPPER_OUTPUT_PREFIX)
            raise IOError("List not found: %s does not exist" % listname)

        list_filename = miscutils.parse_fullname(listname, miscutils.CU_PARSE_FILENAME)
        existfiles['%s.%s'%(intgdefs.IW_LIST_SECT, sectname)] = [list_filename]

        fullnames = intgmisc.get_fullnames_from_listfile(listname, listfmt, ldict['columns'])
        if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
            miscutils.fwdebug_print("\tInfo: fullnames=%s" % fullnames, WRAPPER_OUTPUT_PREFIX)

        for sect in fullnames:
            (existfiles[sect], missing1) = intgmisc.check_files(fullnames[sect])
            missingfiles.extend(missing1)

        if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
            miscutils.fwdebug_print("\tInfo: exists=%s" % existfiles, WRAPPER_OUTPUT_PREFIX)
            miscutils.fwdebug_print("\tInfo: missing=%s" % missingfiles, WRAPPER_OUTPUT_PREFIX)

        return (existfiles, missingfiles)

    ######################################################################
    def check_output_files(self, sectname):
        """ Check that the files for a single output file section exist """

        if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
            miscutils.fwdebug_print("INFO: Beg sectname=%s" % sectname, WRAPPER_OUTPUT_PREFIX)
        existfiles = []
        missingfiles = []

        if sectname in self.inputwcl[intgdefs.IW_FILE_SECT]:
            if 'fullname' in self.inputwcl[intgdefs.IW_FILE_SECT][sectname]:
                fnames = miscutils.fwsplit(self.inputwcl[intgdefs.IW_FILE_SECT][sectname]['fullname'], ',')
                if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
                    miscutils.fwdebug_print("INFO: fullname = %s" % fnames, WRAPPER_OUTPUT_PREFIX)
                for filen in fnames:
                    if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
                        miscutils.fwdebug_print("\tInfo: Checking existence of file '%s'" % filen,
                                                WRAPPER_OUTPUT_PREFIX)
                    if os.path.exists(filen) and os.path.getsize(filen) > 0:
                        existfiles.append(filen)
                    else:
                        missingfiles.append(filen)
                        if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
                            miscutils.fwdebug_print("\tError: output file '%s' does not exist." % \
                                                    filen, WRAPPER_OUTPUT_PREFIX)

        if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
            miscutils.fwdebug_print("INFO: existfiles=%s" % existfiles, WRAPPER_OUTPUT_PREFIX)
            miscutils.fwdebug_print("INFO: missingfiles=%s" % missingfiles, WRAPPER_OUTPUT_PREFIX)
        if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
            miscutils.fwdebug_print("INFO: end", WRAPPER_OUTPUT_PREFIX)

        return (existfiles, missingfiles)


    ######################################################################
    def check_inputs(self, exwcl):
        """ Check which input files/lists do not exist """

        self.start_exec_task('check_inputs')
        already_checked_list = {}

        existfiles = {}
        missingfiles = []
        if intgdefs.IW_INPUTS in exwcl:
            for sect in miscutils.fwsplit(exwcl[intgdefs.IW_INPUTS], ','):
                sectkeys = sect.split('.')
                if sectkeys[0] == intgdefs.IW_FILE_SECT:
                    print "sectkeys[1] = ", sectkeys[1]
                    (exists, missing) = self.check_input_files(sectkeys[1])
                    existfiles.update(exists)
                    missingfiles.extend(missing)
                elif sectkeys[0] == intgdefs.IW_LIST_SECT:
                    if sectkeys[1] not in already_checked_list:
                        (exists, missing) = self.check_input_lists(sectkeys[1])
                        existfiles.update(exists)
                        missingfiles.extend(missing)
                        already_checked_list[sectkeys[1]] = True
                else:
                    print "exwcl[intgdefs.IW_INPUTS]=", exwcl[intgdefs.IW_INPUTS]
                    print "sect = ", sect
                    print "sectkeys = ", sectkeys
                    raise KeyError("Unknown data section %s" % sectkeys[0])

        print "existfiles= ", existfiles
        if len(missingfiles) != 0:
            for mfile in missingfiles:
                miscutils.fwdebug_print("\tError: input '%s' does not exist." % mfile,
                                        WRAPPER_OUTPUT_PREFIX)
            raise IOError("At least one input file not found.")    # if missing inputs, just abort

        self.end_exec_task(0)
        return existfiles


    ######################################################################
    def transform_inputs(self, exwcl):
        """ Transform inputs stored by DESDM into form needed by exec """
        # pylint: disable=unused-argument
        self.start_exec_task('transform_inputs')
        self.end_exec_task(0)

    ######################################################################
    def transform_outputs(self, exwcl):
        """ Transform outputs created by exec into form needed by DESDM """
        # pylint: disable=unused-argument
        self.start_exec_task('transform_outputs')
        self.end_exec_task(0)

    ######################################################################
    def check_outputs(self, exwcl):
        """ Check which output files were created, renaming if necessary """

        if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
            miscutils.fwdebug_print("INFO: Beg", WRAPPER_OUTPUT_PREFIX)

        self.start_exec_task('check_outputs')

        existfiles = {}
        missingfiles = {}

        if intgdefs.IW_OUTPUTS in exwcl:
            for sect in miscutils.fwsplit(exwcl[intgdefs.IW_OUTPUTS]):
                sectkeys = sect.split('.')
                if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
                    miscutils.fwdebug_print("INFO: sectkeys=%s" % sectkeys, WRAPPER_OUTPUT_PREFIX)
                if sectkeys[0] == intgdefs.IW_FILE_SECT:
                    (exists, missing) = self.check_output_files(sectkeys[1])
                    existfiles.update({sectkeys[1]:exists})
                    if len(missing) > 0:
                        missingfiles.update({sectkeys[1]:missing})
                elif sectkeys[0] == intgdefs.IW_LIST_SECT:
                    raise KeyError("Unsupported output data section %s" % sectkeys[0])
                else:
                    raise KeyError("Unknown data section %s" % sectkeys[0])

        if miscutils.fwdebug_check(6, 'BASICWRAP_DEBUG'):
            miscutils.fwdebug_print("INFO: existfiles=%s" % existfiles, WRAPPER_OUTPUT_PREFIX)
            miscutils.fwdebug_print("INFO: missingfiles=%s" % missingfiles, WRAPPER_OUTPUT_PREFIX)

        if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
            miscutils.fwdebug_print("INFO: end", WRAPPER_OUTPUT_PREFIX)

        if len(missingfiles) > 0:
            status = 1
        else:
            status = 0
        self.end_exec_task(status)
        return existfiles


    ######################################################################
    def save_provenance(self, execsect, exwcl, infiles, outfiles):
        """ Create provenance wcl """
        self.start_exec_task('save_provenance')

        if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
            miscutils.fwdebug_print("INFO: Beg", WRAPPER_OUTPUT_PREFIX)
        if miscutils.fwdebug_check(6, 'BASICWRAP_DEBUG'):
            miscutils.fwdebug_print("INFO: infiles = %s" % infiles, WRAPPER_OUTPUT_PREFIX)
            miscutils.fwdebug_print("INFO: outfiles = %s" % outfiles, WRAPPER_OUTPUT_PREFIX)

        # convert probably fullnames in outexist to filename+compression
        new_outfiles = OrderedDict()
        for exlabel, exlist in outfiles.items():
            if miscutils.fwdebug_check(6, 'BASICWRAP_DEBUG'):
                miscutils.fwdebug_print("INFO: exlabel=%s exlist=%s" % (exlabel, exlist),
                                        WRAPPER_OUTPUT_PREFIX)
            newlist = []
            for fullname in exlist:
                basename = miscutils.parse_fullname(fullname, miscutils.CU_PARSE_BASENAME)
                newlist.append(basename)
            if miscutils.fwdebug_check(6, 'BASICWRAP_DEBUG'):
                miscutils.fwdebug_print("INFO: newlist=%s" % (newlist), WRAPPER_OUTPUT_PREFIX)

            new_outfiles[exlabel] = newlist

        prov = self.outputwcl[intgdefs.OW_PROV_SECT]

        # used
        if len(infiles) > 0:
            all_infiles = []
            for key, sublist in infiles.items():
                all_infiles.extend(sublist)
            prov[provdefs.PROV_USED][execsect] = provdefs.PROV_DELIM.join(all_infiles)

        # was_generated_by - done by PFW when saving metadata

        # was_derived_from
        if intgdefs.IW_DERIVATION in exwcl:
            wdf = prov[provdefs.PROV_WDF]
            derived_pairs = miscutils.fwsplit(exwcl[intgdefs.IW_DERIVATION], provdefs.PROV_DELIM)
            for dpair in derived_pairs:
                if miscutils.fwdebug_check(6, 'BASICWRAP_DEBUG'):
                    miscutils.fwdebug_print("INFO: dpair = %s" % dpair, WRAPPER_OUTPUT_PREFIX)
                (parent_sect, child_sect) = miscutils.fwsplit(dpair, ':')
                parent_key = miscutils.fwsplit(parent_sect, '.')[-1]
                child_key = miscutils.fwsplit(child_sect, '.')[-1]

                if miscutils.fwdebug_check(6, 'BASICWRAP_DEBUG'):
                    miscutils.fwdebug_print("INFO: parent_key = %s" % parent_key,
                                            WRAPPER_OUTPUT_PREFIX)
                    miscutils.fwdebug_print("INFO: child_key = %s" % child_key,
                                            WRAPPER_OUTPUT_PREFIX)

                self.last_num_derived += 1
                key = 'derived_%d' % self.last_num_derived
                if miscutils.fwdebug_check(6, 'BASICWRAP_DEBUG'):
                    miscutils.fwdebug_print("INFO: key = %s" % key, WRAPPER_OUTPUT_PREFIX)
                    miscutils.fwdebug_print("INFO: before wdf = %s" % prov[provdefs.PROV_WDF],
                                            WRAPPER_OUTPUT_PREFIX)

                wdf[key] = OrderedDict()

                if parent_key in infiles:
                    wdf[key][provdefs.PROV_PARENTS] = provdefs.PROV_DELIM.join(infiles[parent_key])
                elif parent_key in new_outfiles:   
                    # this output was generated within same program/wrapper from other output files
                    parents = []
                    for outparent in outfiles[parent_key]:
                        parents.append(miscutils.parse_fullname(outparent, miscutils.CU_PARSE_FILENAME))
                    wdf[key][provdefs.PROV_PARENTS] = provdefs.PROV_DELIM.join(parents)
                else:
                    miscutils.fwdebug_print("parent_key = %s" % parent_key, WRAPPER_OUTPUT_PREFIX)
                    miscutils.fwdebug_print("infiles.keys() = %s" % infiles.keys(),
                                            WRAPPER_OUTPUT_PREFIX)
                    miscutils.fwdebug_print("outfiles.keys() = %s" % outfiles.keys(),
                                            WRAPPER_OUTPUT_PREFIX)
                    miscutils.fwdebug_print("used = %s" % exwcl[intgdefs.IW_INPUTS],
                                            WRAPPER_OUTPUT_PREFIX)
                    miscutils.fwdie("ERROR: Could not find parent files for %s" % (dpair), 1)

                wdf[key][provdefs.PROV_CHILDREN] = provdefs.PROV_DELIM.join(new_outfiles[child_key])
                if miscutils.fwdebug_check(6, 'BASICWRAP_DEBUG'):
                    miscutils.fwdebug_print("INFO: after wdf = %s" % prov[provdefs.PROV_WDF],
                                            WRAPPER_OUTPUT_PREFIX)

        if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
            miscutils.fwdebug_print("INFO: End", WRAPPER_OUTPUT_PREFIX)

        self.end_exec_task(0)
        return prov


    ######################################################################
    def write_outputwcl(self, outfilename=None):
        """ Write output wcl to file """

        if outfilename is None:
            outfilename = self.inputwcl['wrapper']['outputwcl']

        if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
            miscutils.fwdebug_print("outfilename = %s" % outfilename, WRAPPER_OUTPUT_PREFIX)

        # create output wcl directory if needed
        outwcldir = miscutils.parse_fullname(outfilename, miscutils.CU_PARSE_PATH)
        if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
            miscutils.fwdebug_print("outwcldir = %s" % outwcldir, WRAPPER_OUTPUT_PREFIX)
        miscutils.coremakedirs(outwcldir)

        with open(outfilename, 'w') as wclfh:
            self.outputwcl.write_wcl(wclfh, True)


    ######################################################################
    def start_exec_task(self, name):
        """ Save start execution info """
        self.curr_task.append(name)
        self.curr_exec['task_info'][name] = {'start_time': time.time()}

    ######################################################################
    def end_exec_task(self, status):
        """ Save end execution info """
        name = self.curr_task.pop()

        task_info = self.curr_exec['task_info'][name]
        task_info['status'] = status
        task_info['end_time'] = time.time()

        # just for human reading convenience
        task_info['walltime'] = task_info['end_time'] - task_info['start_time']


    ######################################################################
    def end_all_tasks(self, status):
        """ End all exec tasks in case of exiting nested tasks """
        end_time = time.time()
        for name in reversed(self.curr_task):
            task_info = self.curr_exec['task_info'][name]
            task_info['status'] = status
            task_info['end_time'] = end_time

            # just for human reading convenience
            task_info['walltime'] = task_info['end_time'] - task_info['start_time']

        self.curr_task = []


    ######################################################################
    def save_outputs_by_section(self, ekey, outexist):
        """ save fullnames from outexist to outputs by section """
        if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
            miscutils.fwdebug_print("INFO: before adding  outputs_by_sect=%s" % \
                                    (self.outputwcl[intgdefs.OW_OUTPUTS_BY_SECT]),
                                    WRAPPER_OUTPUT_PREFIX)
        for exlabel, exlist in outexist.items():
            print 'ekey = ', ekey
            print 'exlabel = ', exlabel
            print 'exlist = ', exlist
            if exlabel not in self.outputwcl[intgdefs.OW_OUTPUTS_BY_SECT]:
                self.outputwcl[intgdefs.OW_OUTPUTS_BY_SECT][exlabel] = {}
            if ekey not in self.outputwcl[intgdefs.OW_OUTPUTS_BY_SECT][exlabel]:
                self.outputwcl[intgdefs.OW_OUTPUTS_BY_SECT][exlabel][ekey] = []

            if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
                miscutils.fwdebug_print("INFO: adding to sect=%s: %s" % (exlabel, exlist),
                                        WRAPPER_OUTPUT_PREFIX)
            self.outputwcl[intgdefs.OW_OUTPUTS_BY_SECT][exlabel][ekey].extend(exlist)

        if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
            miscutils.fwdebug_print("INFO: after adding  outputs_by_sect=%s" % \
                                    (self.outputwcl[intgdefs.OW_OUTPUTS_BY_SECT]),
                                    WRAPPER_OUTPUT_PREFIX)


    ######################################################################
    def cleanup(self):
        """ Remove intermediate files from wrapper execution """
        self.outputwcl['wrapper']['cleanup_start'] = time.time()
        self.outputwcl['wrapper']['cleanup_end'] = time.time()

    ######################################################################
    def run_wrapper(self):
        """ Workflow for this wrapper """
        if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
            miscutils.fwdebug_print("INFO: Begin", WRAPPER_OUTPUT_PREFIX)
        self.outputwcl['wrapper']['start_time'] = time.time()
        try:
            execs = intgmisc.get_exec_sections(self.inputwcl, intgdefs.IW_EXEC_PREFIX)
            if miscutils.fwdebug_check(6, 'BASICWRAP_DEBUG'):
                miscutils.fwdebug_print("INFO:  exec sections = %s" % execs, WRAPPER_OUTPUT_PREFIX)

            for ekey, iw_exec in sorted(execs.items()):
                ow_exec = {'task_info': {}}
                self.outputwcl[ekey] = ow_exec
                self.curr_exec = ow_exec

                self.transform_inputs(iw_exec)
                inputs = self.check_inputs(iw_exec)
                self.check_command_line(ekey, iw_exec)
                self.save_exec_version(iw_exec)
                self.create_command_line(ekey, iw_exec)
                self.create_output_dirs(iw_exec)
                self.run_exec()
                self.transform_outputs(iw_exec)
                outexist = self.check_outputs(iw_exec)
                self.save_outputs_by_section(ekey, outexist)
                self.save_provenance(ekey, iw_exec, inputs, outexist)

                ow_exec['status'] = 0

            self.cleanup()
            self.outputwcl['wrapper']['status'] = 0
        except Exception:
            (exc_type, exc_value, exc_trback) = sys.exc_info()
            traceback.print_exception(exc_type, exc_value, exc_trback,
                                      file=sys.stdout)
            self.outputwcl['wrapper']['status'] = 1
            self.end_all_tasks(1)


        if miscutils.fwdebug_check(6, 'BASICWRAP_DEBUG'):
            miscutils.fwdebug_print("INFO: outputwcl[intgdefs.OW_OUTPUTS_BY_SECT]=%s" % \
                                    (self.outputwcl[intgdefs.OW_OUTPUTS_BY_SECT]),
                                    WRAPPER_OUTPUT_PREFIX)
        for fsname, fssect in self.outputwcl[intgdefs.OW_OUTPUTS_BY_SECT].items():
            if miscutils.fwdebug_check(6, 'BASICWRAP_DEBUG'):
                miscutils.fwdebug_print("INFO: making string for sect %s: %s" % (fsname, fssect),
                                        WRAPPER_OUTPUT_PREFIX)
            for exname, exlist in fssect.items():
                self.outputwcl[intgdefs.OW_OUTPUTS_BY_SECT][fsname][exname] = provdefs.PROV_DELIM.join(exlist)
        self.outputwcl['wrapper']['end_time'] = time.time()

        if miscutils.fwdebug_check(3, 'BASICWRAP_DEBUG'):
            miscutils.fwdebug_print("INFO: end", WRAPPER_OUTPUT_PREFIX)
