#!/usr/bin/env python

# $Id$
# $Rev::                                  $:  # Revision of last commit.
# $LastChangedBy::                        $:  # Author of last commit.
# $LastChangedDate::                      $:  # Date of last commit.

"""
Contains utilities for use with generating WCL for collecting file metadata/updating headers
"""

from collections import OrderedDict
from coreutils.miscutils import *

META_HEADERS = 'h'
META_COMPUTE = 'c'
META_WCL = 'w'
META_COPY = 'p'
META_REQUIRED = 'r'
META_OPTIONAL = 'o'

WCL_META_HEADERS = 'headers'
WCL_META_COMPUTE = 'compute'
WCL_META_WCL = 'wcl'
WCL_UPDATE_HEAD_PREFIX = 'hdrupd_'
WCL_UPDATE_WHICH_HEAD = 'headers'
WCL_REQ_META = 'req_metadata'
WCL_OPT_META = 'opt_metadata'

MD_EXIT_FAILURE = 1

##################################################################################################
def get_metadata_specs(ftype, filetype_metadata, file_header_info=None, sectlabel=None, updatefits=False):
    """ Return wcl describing metadata to gather for given filetype """
    # note:  When manually ingesting files generated externally to the framework, we do not want to modify the files (i.e., no updating/inserting headers

    #print "ftype =", ftype
    metaspecs = OrderedDict()

    (reqmeta, optmeta, updatemeta) = create_file_metadata_dict(ftype, filetype_metadata, sectlabel, file_header_info)

    #print "reqmeta =", reqmeta
    #print "======================================================================"
    #print "optmeta =", optmeta
    #print "======================================================================"
    #print "updatemeta =", updatemeta
    #print "======================================================================"
    #sys.exit(1)

    if reqmeta:
        metaspecs[WCL_REQ_META] = OrderedDict()

        # convert names from specs to wcl
        valspecs = [META_HEADERS, META_COMPUTE, META_WCL]
        wclspecs = [WCL_META_HEADERS, WCL_META_COMPUTE, WCL_META_WCL]
        for i in range(len(valspecs)):
            if valspecs[i] in reqmeta:
                metaspecs[WCL_REQ_META][wclspecs[i]] = reqmeta[valspecs[i]]

    if optmeta:
        metaspecs[WCL_OPT_META] = OrderedDict()

        # convert names from specs to wcl
        valspecs = [META_HEADERS, META_COMPUTE, META_WCL]
        wclspecs = [WCL_META_HEADERS, WCL_META_COMPUTE, WCL_META_WCL]
        for i in range(len(valspecs)):
            if valspecs[i] in optmeta:
                metaspecs[WCL_OPT_META][wclspecs[i]] = optmeta[valspecs[i]]

    #print 'keys = ', metaspecs.keys()
    if updatefits:
        if updatemeta:
            updatemeta[WCL_UPDATE_WHICH_HEAD] = '0'  # framework always updates primary header
            metaspecs[WCL_UPDATE_HEAD_PREFIX+'0'] = updatemeta
    elif updatemeta is not None:
        print "WARNING:  create_file_metadata_dict incorrectly returned values to update."
        print "\tContinuing but not updating these values."
        print "\tReport this to code developer."
        print "\t\t", updatemeta
        updatemeta = None

    # return None if no metaspecs
    if len(metaspecs) == 0:
        metaspecs = None

    return metaspecs


##################################################################################################
def create_file_metadata_dict(filetype, filetype_metadata, sectlabel = None, file_header_info=None):
    reqmeta = None
    optmeta = None
    updatemeta = None

    if filetype in filetype_metadata:
        # required
        if META_REQUIRED in filetype_metadata[filetype]:
            (reqmeta, updatemeta) = create_one_sect_metadata_info(META_REQUIRED, 
                                                                  filetype_metadata[filetype][META_REQUIRED],
                                                                  sectlabel, file_header_info) 

        # optional
        if META_OPTIONAL in filetype_metadata[filetype]:
            (optmeta, tmp_updatemeta) = create_one_sect_metadata_info(META_OPTIONAL,
                                                                  filetype_metadata[filetype][META_OPTIONAL],
                                                                  sectlabel, file_header_info)
            #print "tmp_updatemeta =", tmp_updatemeta
            if tmp_updatemeta is not None:
                if updatemeta is None:
                    updatemeta = tmp_updatemeta
                else:
                    updatemeta.update(tmp_updatemeta)

    return (reqmeta, optmeta, updatemeta)


#####################################################################################################
def create_one_sect_metadata_info(derived_from, filetype_metadata, sectlabel = None, file_header_info=None):

    metainfo = OrderedDict()
    updatemeta = OrderedDict()

    #print "create_one_sect_metadata_info:"
    #wclutils.write_wcl(filetype_metadata)
    #wclutils.write_wcl(file_header_info)
    print file_header_info

    if META_HEADERS in filetype_metadata:
        metainfo[META_HEADERS] = ','.join(filetype_metadata[META_HEADERS].keys())

    if META_COMPUTE in filetype_metadata:
        if file_header_info is not None:   # if supposed to update headers and update DB
            updatemeta.update(create_update_items(derived_from, filetype_metadata[META_COMPUTE].keys(), file_header_info))
            if META_HEADERS not in metainfo:
                metainfo[META_HEADERS] = ""
            else:
                metainfo[META_HEADERS] += ','

            metainfo[META_HEADERS] += ','.join(filetype_metadata[META_COMPUTE].keys())
        else:  # just compute values for DB
            metainfo[META_COMPUTE] = ','.join(filetype_metadata[META_COMPUTE].keys())

    if META_COPY in filetype_metadata:
        if file_header_info is not None:   # if supposed to update headers and update DB
            updatemeta.update(create_copy_items(derived_from, filetype_metadata[META_COPY].keys()))
            if META_HEADERS not in metainfo:
                metainfo[META_HEADERS] = ""
            else:
                metainfo[META_HEADERS] += ','

            metainfo[META_HEADERS] += ','.join(filetype_metadata[META_COPY].keys())
        else:  # just compute values for DB
            metainfo[META_COMPUTE] = ','.join(filetype_metadata[META_COPY].keys())
    if META_WCL in filetype_metadata:
        wclkeys = []
        for k in filetype_metadata[META_WCL].keys():
             if sectlabel is not None:
                 wclkey = '%s.%s' % (sectlabel, k)
             else:
                 wclkey = k
             wclkeys.append(wclkey)
        metainfo[META_WCL] = ','.join(wclkeys)

    #print "create_one_sect_metadata_info:"
    #print "\tmetainfo = ", metainfo
    #print "\tupdatemeta = ", updatemeta

    if len(updatemeta) == 0:
        updatemeta = None

    return (metainfo, updatemeta)



#######################################################################
def create_copy_items(metastatus, file_header_names):
    """ Create the update wcl for headers that should be copied from another header """

    updateDict = OrderedDict()
    for name in file_header_names:
        if metastatus == META_REQUIRED:
            updateDict[name] = "$REQCOPY{%s:LDAC_IMHEAD}" % (name.upper())
        elif metastatus == META_OPTIONAL:
            updateDict[name] = "$OPTCOPY{%s:LDAC_IMHEAD}" % (name.upper())
        else:
            fwdie('Error:  Unknown metadata metastatus (%s)' % (metastatus), PF_EXIT_FAILURE)

    return updateDict



###########################################################################
def create_update_items(metastatus, file_header_names, file_header_info, header_value=None):
    """ Create the update wcl for headers that should be updated """
    updateDict = OrderedDict()
    print metastatus
    print file_header_names

    for name in file_header_names:
        print "looking for %s in file_header_info" % name
        if name not in file_header_info:
            print "file_header_info.keys() = ", file_header_info.keys()
            fwdie('Error: Missing entry in file_header_info for %s' % name, MD_EXIT_FAILURE)

        # Example: $HDRFNC{BAND}/Filter identifier/str
        if header_value is not None and name in header_value:
            updateDict[name] = header_value[name]
        elif metastatus == META_REQUIRED:
            updateDict[name] = "$HDRFNC{%s}" % (name.upper())
        elif metastatus == META_OPTIONAL:
            updateDict[name] = "$OPTFNC{%s}" % (name.upper())
        else:
            fwdie('Error:  Unknown metadata metastatus (%s)' % (metastatus), MD_EXIT_FAILURE)

        if file_header_info[name]['fits_data_type'].lower() == 'none':
            fwdie('Error:  Missing fits_data_type for file header %s\nCheck entry in OPS_FILE_HEADER table' % name, MD_EXIT_FAILURE)

        # Requires 'none' to not be a valid description
        if file_header_info[name]['description'].lower() == 'none':
            fwdie('Error:  Missing description for file header %s\nCheck entry in OPS_FILE_HEADER table' % name, MD_EXIT_FAILURE)

        updateDict[name] += "/%s/%s" % (file_header_info[name]['description'],
                                        file_header_info[name]['fits_data_type'])

    return updateDict


