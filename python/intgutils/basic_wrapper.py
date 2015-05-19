#!/usr/bin/env python

import time
import shlex
import os
import sys
import subprocess
import re
import pyfits
import traceback
import errno
from collections import OrderedDict


import despymisc.subprocess4 as subprocess4
import despyfits.fits_special_metadata as fspmeta
import intgutils.intgdefs as intgdefs
import intgutils.intgmisc as intgmisc
import despyfits.fitsutils as fitsutils
import despymisc.miscutils as miscutils
from intgutils.wcl import WCL


WRAPPER_OUTPUT_PREFIX='WRAP: '


class BasicWrapper():
    ###################################################################### 
    def __init__ (self, wclfile, debug = 1):
        """ Read input wcl to initialize object """

        self.input_filename = wclfile
        self.inputwcl = WCL()
        with open(wclfile, 'r') as infh:
            self.inputwcl.read_wcl(infh)
        self.debug = debug
        provdict = OrderedDict({intgdefs.PROV_INPUTS: OrderedDict(),
                                intgdefs.PROV_OUTPUTS: OrderedDict(),
                                intgdefs.PROV_WDF: OrderedDict()})
        self.outputwcl = WCL({'wrapper': OrderedDict(), 
                              #intgdefs.OW_META_SECT: OrderedDict(),
                              intgdefs.OW_PROV_SECT: provdict,
                              intgdefs.OW_OUTPUTS_BY_SECT: {}})

        self.last_num_derived = 0
        self.last_num_meta = 0

    ###################################################################### 
    def get_prov_info(self, fullname):
        parsemask = miscutils.CU_PARSE_FILENAME | miscutils.CU_PARSE_COMPRESSION
        (basename, compression) = miscutils.parse_fullname(fullname, parsemask)
        if compression is not None:
            basename += compression
        return basename
    

    ###################################################################### 
    def get_exec_sections(self, wcl, prefix):
        """ Returns exec sections appearing in given wcl """
        execs = {}
        for key, val in wcl.items():
            miscutils.fwdebug(3, "BASICWRAP_DEBUG", "\tsearching for exec prefix in %s" % key, WRAPPER_OUTPUT_PREFIX)

            if re.search("^%s\d+$" % prefix, key):
                miscutils.fwdebug(4, "BASICWRAP_DEBUG", "\tFound exec prefex %s" % key, WRAPPER_OUTPUT_PREFIX)
                execs[key] = val
        return execs


    ###################################################################### 
    def check_command_line(self, execnum, exwcl):
        """ Ensure that certain command line arguments are specified """


        if intgdefs.IW_CHECK_COMMAND in self.inputwcl and \
           miscutils.convertBool(self.inputwcl[intgdefs.IW_CHECK_COMMAND]):
        
            if intgdefs.IW_EXEC_DEF in self.inputwcl:
                execdefs = self.inputwcl[intgdefs.IW_EXEC_DEF]
                if ( execname.lower() in execdefs and \
                     intgdefs.IW_CMD_REQ_ARGS in execdefs[execname.lower()] ):
                    req_args = miscutils.fwsplit(execdefs[execname.lower()][intgdefs.IW_CMD_REQ_ARGS], ',') 

                    
        return 0


    ###################################################################### 
    def create_command_line(self, execnum, exwcl): 
        """ Create command line string handling hyphens appropriately"""
        miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "execnum = '%s', exwcl = '%s'" % (execnum, exwcl), WRAPPER_OUTPUT_PREFIX)

        cmdstr = ""
        if 'execname' in exwcl:
            cmdlist = [exwcl['execname']]

            if 'cmdline' in exwcl:
                posargs = {}  # save positional args to insert later
    
                # loop through command line args
                for key, val in exwcl['cmdline'].items():
                    miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "key = '%s', val = '%s'" % (key, val), WRAPPER_OUTPUT_PREFIX)
                    expandval = self.inputwcl.replace_vars(val)  # replace any variables
                    miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "expandval = '%s'" % (expandval), WRAPPER_OUTPUT_PREFIX)

                    if key.startswith('_'):
                        patmatch = re.match('_(\d+)', key)
                        if patmatch:
                            posargs[patmatch.group(1)] = expandval  # save for later
                        else:
                            raise ValueError('Invalid positional argument name: %s' % key)
                    else:
                        if 'cmd_hyphen' in exwcl:
                            if exwcl['cmd_hyphen'] == 'alldouble':
                                hyphen = '--'
                            elif exwcl['cmd_hyphen'] == 'allsingle':
                                hyphen = '-'
                            elif exwcl['cmd_hyphen'] == 'mixed_gnu':
                                if len(key) == 1:
                                    hyphen = '-'
                                else:
                                    hyphen = '--'
                            else:
                                raise ValueError('Invalid cmd_hyphen value (%s)' % exwcl['cmd_hyphen'])
                        else:
                            hyphen = '-'

                        if expandval == '_flag':
                            cmdlist.append(" %s%s" % (hyphen, key))
                        else:
                            cmdlist.append(" %s%s %s" % (hyphen, key, expandval))

                # insert position sensitive arguments into specified location in argument list
                for k in sorted(posargs.iterkeys()):
                    cmdlist.insert(int(k),"%s" % posargs[k])

            # convert list of args into string
            miscutils.fwdebug(6, 'BASICWRAP_DEBUG', "cmdlist = '%s'" % (cmdlist), WRAPPER_OUTPUT_PREFIX)
            cmdstr = ' '.join(cmdlist)
        else:
            print "Error: missing execname in wcl for exec #%d" % execnum
            print "exec wcl = %s" % exwcl
            raise KeyError('Missing execname in wcl for exec #%d' % execnum)

        miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "cmdstr = '%s'" % (cmdstr), WRAPPER_OUTPUT_PREFIX)
        return cmdstr


    ###################################################################### 
    def get_exec_version(self, execnum, exwcl):
        """ Run command with version flag and parse output for version information """  
        # assumes exit code for version is 0
        ver = None

        if intgdefs.IW_EXEC_DEF in self.inputwcl:
            execdefs = self.inputwcl[intgdefs.IW_EXEC_DEF] 
            if ( execname.lower() in execdefs and
                'version_flag' in execdefs[execname.lower()] and
                'version_pattern' in execdefs[execname.lower()] ):
                verflag = execdefs[execname.lower()]['version_flag']
                verpat = execdefs[execname.lower()]['version_pattern']
    
                cmd = "%s %s" % (execname, verflag)
                try:
                    process = subprocess.Popen(cmd.split(),
                                               shell=False,
                                               stdout=subprocess.PIPE,
                                               stderr=subprocess.STDOUT)
                except:
                    (type, value) = sys.exc_info()[0:1]
                    print "********************"
                    print "Unexpected error: %s - %s" % (type, value)
                    print "cmd> %s" % cmd
                    print "Probably could not find %s in path" % cmd.split()[0]
                    print "Check for mispelled execname in submit wcl or"
                    print "    make sure that the corresponding eups package is in the metapackage and it sets up the path correctly"
                    raise
    
                process.wait()
                out = process.communicate()[0]
                if process.returncode != 0:
                    miscutils.fwdebug(0, 'BASICWRAP_DEBUG', "INFO:  problem when running code to get version", WRAPPER_OUTPUT_PREFIX)
                    miscutils.fwdebug(0, 'BASICWRAP_DEBUG', "\t%s %s %s" % (execname, verflag, verpat), WRAPPER_OUTPUT_PREFIX)
                    miscutils.fwdebug(0, 'BASICWRAP_DEBUG', "\tcmd> %s" % cmd, WRAPPER_OUTPUT_PREFIX)
                    miscutils.fwdebug(0, 'BASICWRAP_DEBUG', "\t%s" % out, WRAPPER_OUTPUT_PREFIX)
                    ver = None
                else:
                    # parse output with verpat
                    try:
                        m = re.search(verpat, out)
                        if m:
                            ver = m.group(1)
                        else:
                            miscutils.fwdebug(1, 'BASICWRAP_DEBUG', "re.search didn't find version for exec %s" % execname, WRAPPER_OUTPUT_PREFIX)
                        miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "\tcmd output=%s" % out, WRAPPER_OUTPUT_PREFIX)
                        miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "\tcmd verpat=%s" % verpat, WRAPPER_OUTPUT_PREFIX)
                    except Exception as err:
                        #print type(err)
                        ver = None
                        print "Error: Exception from re.match.  Didn't find version: %s" % err
                        raise
            else:
                miscutils.fwdebug(1, 'BASICWRAP_DEBUG', "INFO: Could not find version info for exec %s" % execname, WRAPPER_OUTPUT_PREFIX)
                ver = None
    
        return ver



    ###################################################################### 
    def run_exec(self, cmd):
        """ Run given command line """  

        retcode = None
        procinfo = None
        
        sys.stdout.flush() 
        try:
            (retcode, procinfo) = intgmisc.run_exec(cmd)
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                raise

            print "********************"
            (type, value, traceback) = sys.exc_info()
            print "%s - %s" % (type, value)
            print "cmd> %s" % cmd
            print "Probably could not find %s in path" % cmd.split()[0]
            print "Check for mispelled execname in submit wcl or"
            print "    make sure that the corresponding eups package is in "
            print "    the metapackage and it sets up the path correctly"
            raise
            
        sys.stdout.flush()

        if retcode != 0:
            miscutils.fwdebug(3, "BASICWRAP_DEBUG", "\tInfo: cmd exited with non-zero exit code = %s" % retcode, WRAPPER_OUTPUT_PREFIX)
            miscutils.fwdebug(3, "BASICWRAP_DEBUG", "\tInfo: failed cmd = %s" % cmd, WRAPPER_OUTPUT_PREFIX)
        else:
            miscutils.fwdebug(3, "BASICWRAP_DEBUG", "\tInfo: cmd exited with exit code = 0", WRAPPER_OUTPUT_PREFIX)

        miscutils.fwdebug(3, "BASICWRAP_DEBUG", "END", WRAPPER_OUTPUT_PREFIX)
        return retcode, procinfo

    ###################################################################### 
    def check_files(self, fullnames):

        exists = []
        missing = []
        for fname in fullnames:
            if os.path.exists(fname):
                exists.append(self.get_prov_info(fname))
            else:
                missing.append(fname)
        return (exists, missing)
        
    

    ###################################################################### 
    def check_input_files(self, sectname):
        """ Check that the files for a single input file section exist """

        fnames = miscutils.fwsplit(self.inputwcl[intgdefs.IW_FILE_SECT][sectname]['fullname'], ',')
        (exists1, missing1) = self.check_files(fnames)
        return ({sectname: exists1}, missing1)
                    
                    

    ###################################################################### 
    def check_input_lists(self, sectname):
        """ Check that the list and contained files for a single input list section exist """

        ldict = self.inputwcl[intgdefs.IW_LIST_SECT][sectname]
        # check list itself exists
        listname = ldict['fullname']
        miscutils.fwdebug(3, "BASICWRAP_DEBUG", "\tInfo: Checking existence of '%s'" % listname, WRAPPER_OUTPUT_PREFIX)

        if not os.path.exists(listname):
            miscutils.fwdebug(0, "BASICWRAP_DEBUG", "\tError: input list '%s' does not exist." % listname, WRAPPER_OUTPUT_PREFIX)
            raise IOError("List not found: %s does not exist" % listname)

        fullnames = get_fullnames_from_listfile(listfile, linefmt, colstr)
        
        existfiles = {}
        missingfiles = []
        for sect in fullnames:
            (existfiles[sect], missing1) = self.check_files(fullnames)
            missingfiles.extend(missing1)
        return (existfiles, missingfiles)


    ###################################################################### 
    def check_inputs(self, execnum, exwcl):
        """ Check which input files/lists do not exist """
        
        already_checked_list = {}

        existfiles = {}
        missingfiles = []
        if intgdefs.IW_INPUTS in exwcl:
            for sect in miscutils.fwsplit(exwcl[intgdefs.IW_INPUTS], ','):
                sectkeys = sect.split('.')
                if sectkeys[0] == intgdefs.IW_FILE_SECT:
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

        return (existfiles, missingfiles)


    ###################################################################### 
    def check_output_files(self, sectname):
        """ Check that the files for a single output file section exist """

        miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "INFO: Beg sectname=%s" % sectname, WRAPPER_OUTPUT_PREFIX)
        existfiles = {}
        missingfiles = {}

        if sectname in self.inputwcl[intgdefs.IW_FILE_SECT]:
            if 'fullname' in self.inputwcl[intgdefs.IW_FILE_SECT][sectname]:
                miscutils.fwdebug(3, "BASICWRAP_DEBUG", "INFO: fullname = %s" % self.inputwcl[intgdefs.IW_FILE_SECT][sectname]['fullname'], WRAPPER_OUTPUT_PREFIX)
                fnames = miscutils.fwsplit(self.inputwcl[intgdefs.IW_FILE_SECT][sectname]['fullname'], ',')
                exists = []
                missing = []
                for f in fnames:
                    miscutils.fwdebug(3, "BASICWRAP_DEBUG", "\tInfo: Checking existence of file '%s'" % f, WRAPPER_OUTPUT_PREFIX)
                    if os.path.exists(f) and os.path.getsize(f) > 0:
                        exists.append(f)
                    else:
                        missing.append(f)
                        miscutils.fwdebug(3, "BASICWRAP_DEBUG", "\tError: output file '%s' does not exist." % f, WRAPPER_OUTPUT_PREFIX)
                if len(exists) > 0:
                    existfiles[sectname] = exists
                if len(missing) > 0:
                    missingfiles[sectname] = missing
                   
        miscutils.fwdebug(6, 'BASICWRAP_DEBUG', "INFO: existfiles=%s" % existfiles, WRAPPER_OUTPUT_PREFIX)
        miscutils.fwdebug(6, 'BASICWRAP_DEBUG', "INFO: missingfiles=%s" % missingfiles, WRAPPER_OUTPUT_PREFIX)
        miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "INFO: end", WRAPPER_OUTPUT_PREFIX)

        return (existfiles, missingfiles)


    ###################################################################### 
    def check_outputs(self, execnum, exwcl):
        """ Check which output files were created, renaming if necessary """

        miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "INFO: Beg execnum=%s" % execnum, WRAPPER_OUTPUT_PREFIX)

        existfiles = {}
        missingfiles = {}
        
        if intgdefs.IW_OUTPUTS in exwcl:
            for sect in miscutils.fwsplit(exwcl[intgdefs.IW_OUTPUTS]):
                sectkeys = sect.split('.')
                miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "INFO: sectkeys=%s" % sectkeys, WRAPPER_OUTPUT_PREFIX)
                if sectkeys[0] == intgdefs.IW_FILE_SECT:
                    (existfiles, missingfiles) = self.check_output_files(sectkeys[1])
                elif sectkeys[0] == intgdefs.IW_LIST_SECT:
                    raise KeyError("Unsupported output data section %s" % sectkeys[0])
                else:
                    raise KeyError("Unknown data section %s" % sectkeys[0])

        miscutils.fwdebug(6, 'BASICWRAP_DEBUG', "INFO: existfiles=%s" % existfiles, WRAPPER_OUTPUT_PREFIX)
        miscutils.fwdebug(6, 'BASICWRAP_DEBUG', "INFO: missingfiles=%s" % missingfiles, WRAPPER_OUTPUT_PREFIX)
        miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "INFO: end", WRAPPER_OUTPUT_PREFIX)

        return (existfiles, missingfiles)


    ###################################################################### 
    def create_provenance(self, execsect, execnum, exwcl, infiles, outfiles):
        """ Create provenance wcl """
        # assumes infiles and outfiles are DB filenames, not fullnames
        #(status, provenance) = self.create_provenance(ekey, iw_exec, inputs, existfiles)

        miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "INFO: Beg", WRAPPER_OUTPUT_PREFIX)
        miscutils.fwdebug(6, 'BASICWRAP_DEBUG', "INFO: execnum = %s" % execnum, WRAPPER_OUTPUT_PREFIX)
        miscutils.fwdebug(6, 'BASICWRAP_DEBUG', "INFO: infiles = %s" % infiles, WRAPPER_OUTPUT_PREFIX)
        miscutils.fwdebug(6, 'BASICWRAP_DEBUG', "INFO: outfiles = %s" % outfiles, WRAPPER_OUTPUT_PREFIX)

        prov = OrderedDict()

        # used
        if len(infiles) > 0:
            all_infiles = []
            for sublist in infiles.values():
                all_infiles.extend(sublist)
            prov[intgdefs.PROV_INPUTS] = OrderedDict({execsect: ','.join(all_infiles)})

        # was_generated_by
        if len(outfiles) > 0:
            all_outfiles = []
            for sublist in outfiles.values():
                all_outfiles.extend(sublist)
            prov[intgdefs.PROV_OUTPUTS] = OrderedDict({execsect: ','.join(all_outfiles)})


        # was_derived_from
        if intgdefs.IW_WDF in exwcl:
            derived_pairs = miscutils.fwsplit(exwcl[intgdefs.IW_WDF], ',')
            prov[intgdefs.PROV_WDF] = OrderedDict()
            for dp in derived_pairs:
                (parent_sect, child_sect) = miscutils.fwsplit(dp, ':')
                parent_key = miscutils.fwsplit(parent_sect, '.')[-1]
                child_key = miscutils.fwsplit(child_sect, '.')[-1]
                
                self.last_num_derived += 1
                key = 'derived_%d' % self.last_num_derived
                prov[intgdefs.PROV_WDF][key] = OrderedDict()
                prov[intgdefs.PROV_WDF][key]['parents'] = ','.join(infiles[parent_key])
                prov[intgdefs.PROV_WDF][key]['children'] = ','.join(outfiles[child_key])
                
        miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "INFO: End", WRAPPER_OUTPUT_PREFIX)
        return (0, prov)
        

    ###################################################################### 
    def update_headers_file(self, hdulist, filesdef, update_info):
        """ Update/insert key/value into header of single output file """

        miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "INFO: begin", WRAPPER_OUTPUT_PREFIX)
        fullname = hdulist.filename()

        # camsym = $HDRFNC{CAMSYM}/a char for Camera (D,S)/str
        # update_info = {whichhdu :[(key, val, def)]}
        miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "INFO: fullname=%s, update_info=%s" % (fullname, update_info), WRAPPER_OUTPUT_PREFIX)

        for whichhdu in sorted(update_info.keys()):
            if whichhdu is None:
                whichhdu = 'Primary'

            try:
                fitshdu = int(whichhdu)  # if number, convert type
            except ValueError:
                fitshdu = whichhdu.upper()
         
            hdr = hdulist[fitshdu].header
            for key, updline in update_info[whichhdu].items():
                data = miscutils.fwsplit(updline, '/')
                
                miscutils.fwdebug(6, 'BASICWRAP_DEBUG', "INFO: whichhdu=%s, data=%s" % (whichhdu, data), WRAPPER_OUTPUT_PREFIX)
                if '$HDRFNC' in data[0]:
                    match = re.search("(?i)\$HDRFNC\{([^}]+)\}", data[0])
                    if match:
                        funckey = match.group(1)
                        smf = getattr(fspmeta, 'func_%s' % funckey.lower())
                        val = smf(fullname, hdulist, whichhdu)
                else:
                    val = self.inputwcl.replace_vars(data[0])

                hdr.update(key.upper(), val, data[1])

        miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "INFO: end", WRAPPER_OUTPUT_PREFIX)


    ###################################################################### 
    def process_output_file(self, outfile, filedef, metadef):
        """ Steps """
        
        miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "INFO: begin", WRAPPER_OUTPUT_PREFIX)
        miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "INFO: outfile = %s" % outfile, WRAPPER_OUTPUT_PREFIX)

        # open file
        hdulist = pyfits.open(outfile, 'update')
 
        # update headers
        updatedef = None
        if 'update' in metadef:
            updatedef = metadef['update']

        # call even if no update in case special wrapper has overloaded func
        self.update_headers_file(hdulist, filedef, updatedef)

        # read metadata
        metadata = self.gather_metadata_file(hdulist, metadef)

        # close file
        hdulist.close()

        miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "INFO: end", WRAPPER_OUTPUT_PREFIX)
        return metadata

    
    ###################################################################### 
    def process_all_output_files(self, outfiles):
        """ """

        miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "INFO: begin", WRAPPER_OUTPUT_PREFIX)
        metadata = {}

        for filesect, filelist in outfiles.items():
            filedef = self.inputwcl[intgdefs.IW_FILE_SECT][filesect]
            filetype = filedef['filetype']
            metadef = self.inputwcl[intgdefs.IW_META_SECT][filetype]
            self.last_num_meta += 1 
            for file in filelist:
                metadata['file_%d'% self.last_num_meta] = self.process_output_file(file, filedef, metadef)
                self.last_num_meta += 1

        miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "INFO: end", WRAPPER_OUTPUT_PREFIX)
        return metadata



    ###################################################################### 
    def gather_metadata_file(self, hdulist, metadata_defs):
        """ gather metadata for a single file """

        fullname = hdulist.filename()
        miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "INFO: file=%s" % (fullname), WRAPPER_OUTPUT_PREFIX)
        metadata = { 'fullname': fullname }

        if 'wcl' in metadata_defs:
            miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "INFO: wcl=%s" % (metadata_defs['wcl']), WRAPPER_OUTPUT_PREFIX)
            
            for wclkey in miscutils.fwsplit(metadata_defs['wcl'], ','):
                metakey = wclkey.split('.')[-1]
                if metakey == 'fullname':
                    metadata['fullname'] = fullname
                elif metakey == 'filename':
                    metadata['filename'] = miscutils.parse_fullname(fullname, miscutils.CU_PARSE_FILENAME)
                else:
                    miscutils.fwdebug(6, 'BASICWRAP_DEBUG', "INFO: wclkey=%s" % (wclkey), WRAPPER_OUTPUT_PREFIX)
                    metadata[metakey] = self.inputwcl[wclkey]

        if 'headers' in metadata_defs:
            miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "INFO: headers=%s" % (metadata_defs['headers']), WRAPPER_OUTPUT_PREFIX)
            for hdu, keys in metadata_defs['headers'].items():
                miscutils.fwdebug(6, 'BASICWRAP_DEBUG', "INFO: hdu=%s, keys=%s" % (hdu, keys), WRAPPER_OUTPUT_PREFIX)
                for key in miscutils.fwsplit(keys, ','):
                    try:
                        metadata[key] = fitsutils.get_hdr_value(hdulist, key.upper(), hdu)
                    except KeyError:
                        miscutils.fwdebug(0, 'BASICWRAP_DEBUG', "INFO: didn't find key %s in %s header of file %s" % (key, hdu, fullname), WRAPPER_OUTPUT_PREFIX)
        
        miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "INFO: end", WRAPPER_OUTPUT_PREFIX)
        return metadata


    ###################################################################### 
    def write_outputwcl(self, outfilename = None):
        """ Write output wcl to file """

        if outfilename is None:
            outfilename = self.inputwcl['wrapper']['outputwcl']

        miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "outfilename = %s" % outfilename, WRAPPER_OUTPUT_PREFIX)

        # create output wcl directory if needed
        outwcldir = miscutils.parse_fullname(outfilename, miscutils.CU_PARSE_PATH)
        miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "outwcldir = %s" % outwcldir, WRAPPER_OUTPUT_PREFIX)
        if outwcldir is not None:
            miscutils.coremakedirs(outwcldir)

        with open(outfilename, 'w') as wclfh:
            self.outputwcl.write_wcl(wclfh, True)


    ###################################################################### 
    def get_status(self):
        return self.outputwcl['wrapper']['status']

    ###################################################################### 
    def start(self, sect, name):
        sect[name] = {'start_time': time.time()}
        
    ###################################################################### 
    def end(self, sect, name, status):
        sect[name]['end_time'] = time.time()
        sect[name]['status'] = status

    ###################################################################### 
    def run_wrapper(self):
        miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "INFO: Begin", WRAPPER_OUTPUT_PREFIX)
        self.outputwcl['wrapper']['start_time'] = time.time()
        self.outputwcl[intgdefs.OW_EXEC_SECT] = {}
        try:
            execs = self.get_exec_sections(self.inputwcl, intgdefs.IW_EXEC_PREFIX)
            miscutils.fwdebug(6, 'BASICWRAP_DEBUG', "INFO:  exec sections = %s" % execs, WRAPPER_OUTPUT_PREFIX)

            execnum = 1
            for ekey, iw_exec in sorted(execs.items()):
                ow_exec = {'task_info': {}}
                self.outputwcl[intgdefs.OW_EXEC_SECT][execnum] = ow_exec

                self.start(ow_exec['task_info'], 'check_input')
                (inputs, missing_inputs) = self.check_inputs(ekey, iw_exec)
                if len(missing_inputs) != 0:
                    self.end(ow_exec['task_info'], 'check_input', 1)
                    for f in missing_inputs:
                        miscutils.fwdebug(0, "BASICWRAP_DEBUG", "\tError: input '%s' does not exist." % f, WRAPPER_OUTPUT_PREFIX)
                    raise IOError("At least one input file not found.")    # if missing inputs, just abort

                self.end(ow_exec['task_info'], 'check_input', 0)
            
                self.start(ow_exec['task_info'], 'check_command_line')
                status = self.check_command_line(ekey, iw_exec)
                self.end(ow_exec['task_info'], 'check_command_line', status)

                self.start(ow_exec['task_info'], 'create_command_line')
                ow_exec['cmdline'] = self.create_command_line(ekey, iw_exec)
                self.end(ow_exec['task_info'], 'create_command_line', 0)

                if status == 0:
                    self.start(ow_exec['task_info'], 'run_command')
                    miscutils.fwdebug(6, "BASICWRAP_DEBUG", "ekey = %s, cmdline = %s" % (ekey,ow_exec['cmdline']), WRAPPER_OUTPUT_PREFIX)
                    print '*' * 70
                    (status, procinfo) = self.run_exec(ow_exec['cmdline'])
                    print '*' * 70
                    self.end(ow_exec['task_info'], 'run_command', status)
                    ow_exec['status'] = status
                    ow_exec['procinfo'] = procinfo

                self.start(ow_exec['task_info'], 'check_output')
                (outexist, outmissing) = self.check_outputs(ekey, iw_exec)
                if len(outmissing) > 0:
                    status = 1
                else:
                    status = 0
                self.end(ow_exec['task_info'], 'check_output', status)
                ow_exec['status'] = status


                # save fullnames from outexist to outputs by section
                miscutils.fwdebug(6, 'BASICWRAP_DEBUG', "INFO: before adding  outputs_by_sect=%s" % (self.outputwcl[intgdefs.OW_OUTPUTS_BY_SECT]), WRAPPER_OUTPUT_PREFIX)
                for exlabel, exlist in outexist.items():
                    if exlabel not in self.outputwcl[intgdefs.OW_OUTPUTS_BY_SECT]:
                        self.outputwcl[intgdefs.OW_OUTPUTS_BY_SECT][exlabel] = []
                    miscutils.fwdebug(6, 'BASICWRAP_DEBUG', "INFO: adding to sect=%s: %s" % (exlabel, exlist), WRAPPER_OUTPUT_PREFIX)
                    self.outputwcl[intgdefs.OW_OUTPUTS_BY_SECT][exlabel].extend(exlist)

                # convert probably fullnames in outexist to filename+compression
                new_outexist = OrderedDict()
                for exlabel, exlist in outexist.items():
                    newlist = []
                    for fullname in exlist:
                        (filename, compext) = miscutils.parse_fullname(fullname, miscutils.CU_PARSE_FILENAME | miscutils.CU_PARSE_COMPRESSION)
                        if compext is not None:
                            filename += compext
                        newlist.append(filename)
                    
                    new_outexist[exlabel] = newlist

                self.start(ow_exec['task_info'], 'provenance')
                (status, provenance) = self.create_provenance(ekey, execnum, iw_exec, inputs, new_outexist)
                self.end(ow_exec['task_info'], 'provenance', status)
                ow_exec['status'] = status
                if status == 0 and len(provenance) > 0:
                    if intgdefs.PROV_INPUTS in provenance:
                        self.outputwcl[intgdefs.OW_PROV_SECT][intgdefs.PROV_INPUTS].update(provenance[intgdefs.PROV_INPUTS])
                    if intgdefs.PROV_OUTPUTS in provenance:
                        self.outputwcl[intgdefs.OW_PROV_SECT][intgdefs.PROV_OUTPUTS].update(provenance[intgdefs.PROV_OUTPUTS])
                    if intgdefs.PROV_WDF in provenance:
                        self.outputwcl[intgdefs.OW_PROV_SECT][intgdefs.PROV_WDF].update(provenance[intgdefs.PROV_WDF])
                    

                #self.start(ow_exec['task_info'], 'metadata')
                #metadata = self.process_all_output_files(outexist)
                #self.end(ow_exec['task_info'], 'metadata', status)
                #if status == 0 and len(metadata) > 0:
                #    self.outputwcl[intgdefs.OW_META_SECT].update(metadata)

                ow_exec['status'] = 0
                execnum += 1

            self.outputwcl['wrapper']['status'] = 0
        except Exception as ex:
            (exc_type, exc_value, exc_trback) = sys.exc_info()
            #print "%s: %s" % (type, value)
            #traceback.print_tb(trback, limit=1, file=sys.stdout)
            traceback.print_exception(exc_type, exc_value, exc_trback,
                             #         limit=2, file=sys.stdout)
                                      file=sys.stdout)
            self.outputwcl['wrapper']['status'] = 1

        
        miscutils.fwdebug(6, 'BASICWRAP_DEBUG', "INFO: outputwcl[intgdefs.OW_OUTPUTS_BY_SECT]=%s" % (self.outputwcl[intgdefs.OW_OUTPUTS_BY_SECT]), WRAPPER_OUTPUT_PREFIX)
        for fsname, fslist in self.outputwcl[intgdefs.OW_OUTPUTS_BY_SECT].items():
            miscutils.fwdebug(6, 'BASICWRAP_DEBUG', "INFO: making string for sect %s: %s" % (fsname, fslist), WRAPPER_OUTPUT_PREFIX)
            self.outputwcl[intgdefs.OW_OUTPUTS_BY_SECT][fsname] = ','.join(fslist)
        self.outputwcl['wrapper']['end_time'] = time.time()

        miscutils.fwdebug(3, 'BASICWRAP_DEBUG', "INFO: end", WRAPPER_OUTPUT_PREFIX)



