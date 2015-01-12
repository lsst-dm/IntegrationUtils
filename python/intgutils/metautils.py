#!/usr/bin/env python

# $Id$
# $Rev::                                  $:  # Revision of last commit.
# $LastChangedBy::                        $:  # Author of last commit.
# $LastChangedDate::                      $:  # Date of last commit.

"""
Contains utilities for use with generating WCL for collecting file metadata/updating headers
"""

from collections import OrderedDict

import despymisc.miscutils as miscutils
import filemgmt.filemgmt_defs as fmdefs
import intgutils.metadefs as metadefs



##################################################################################################
def get_metadata_specs(ftype, filetype_metadata, file_header_info=None, sectlabel=None, updatefits=False):
    """ Return wcl describing metadata to gather for given filetype """
    # note:  When manually ingesting files generated externally to the framework, we do not want to modify the files (i.e., no updating/inserting headers

    metaspecs = OrderedDict()

    (reqmeta, optmeta, updatemeta) = create_file_metadata_dict(ftype, filetype_metadata, sectlabel, file_header_info)

    if reqmeta:
        metaspecs[metadefs.WCL_META_REQ] = OrderedDict()

        # convert names from specs to wcl
        valspecs = [fmdefs.META_HEADERS, fmdefs.META_COMPUTE, fmdefs.META_WCL]
        wclspecs = [metadefs.WCL_META_HEADERS, metadefs.WCL_META_COMPUTE, metadefs.WCL_META_WCL]
        for i in range(len(valspecs)):
            if valspecs[i] in reqmeta:
                metaspecs[metadefs.WCL_META_REQ][wclspecs[i]] = reqmeta[valspecs[i]]

    if optmeta:
        metaspecs[metadefs.WCL_META_OPT] = OrderedDict()

        # convert names from specs to wcl
        valspecs = [fmdefs.META_HEADERS, fmdefs.META_COMPUTE, fmdefs.META_WCL]
        wclspecs = [metadefs.WCL_META_HEADERS, metadefs.WCL_META_COMPUTE, metadefs.WCL_META_WCL]
        for i in range(len(valspecs)):
            if valspecs[i] in optmeta:
                metaspecs[metadefs.WCL_META_OPT][wclspecs[i]] = optmeta[valspecs[i]]

    #print 'keys = ', metaspecs.keys()
    if updatefits:
        if updatemeta:
            updatemeta[metadefs.WCL_UPDATE_WHICH_HEAD] = '0'  # framework always updates primary header
            metaspecs[metadefs.WCL_UPDATE_HEAD_PREFIX+'0'] = updatemeta
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
    reqmeta = {}
    optmeta = {}
    updatemeta = {}

    if filetype in filetype_metadata:
        for hdname in filetype_metadata[filetype]:
            if isinstance(filetype_metadata[filetype][hdname], dict):
                #print "Working on metadata dict for hdname=%s" % hdname
    
                # required
                if fmdefs.META_REQUIRED in filetype_metadata[filetype][hdname]:
                    (treq, tupdate) = create_one_sect_metadata_info(hdname, fmdefs.META_REQUIRED, 
                                                                    filetype_metadata[filetype][hdname][fmdefs.META_REQUIRED],
                                                                    sectlabel, file_header_info) 
                    if treq is not None:
                        #print "found required"
                        for k in treq:
                            if k in reqmeta:
                                reqmeta[k] += "," + treq[k]
                            else:
                                reqmeta[k] = treq[k]

                    if tupdate is not None:
                        #print "found required update"
                        for k in tupdate:
                            if k in updatemeta:
                                updatemeta[k] += "," + tupdate[k]
                            else:
                                updatemeta[k] = tupdate[k]

                # optional
                if fmdefs.META_OPTIONAL in filetype_metadata[filetype][hdname]:
                    (topt, tupdate) = create_one_sect_metadata_info(hdname, fmdefs.META_OPTIONAL,
                                                                    filetype_metadata[filetype][hdname][fmdefs.META_OPTIONAL],
                                                                    sectlabel, file_header_info)
                    #print "topt = ", topt
                    #print "tupdate = ", tupdate
                    if topt is not None:
                        #print "found optional"
                        for k in topt:
                            if k in optmeta:
                                optmeta[k] += "," + topt[k]
                            else:
                                optmeta[k] = topt[k]
                            
                    if tupdate is not None:
                        #print "found optional update"
                        for k in tupdate:
                            if k in updatemeta:
                                updatemeta[k] += "," + tupdate[k]
                            else:
                                updatemeta[k] = tupdate[k]

    if len(reqmeta) == 0:
        reqmeta = None
    if len(optmeta) == 0:
        optmeta = None
    if len(updatemeta) == 0:
        updatemeta = None
    return (reqmeta, optmeta, updatemeta)


#####################################################################################################
def create_one_sect_metadata_info(whichhdu, derived_from, filetype_metadata, sectlabel = None, file_header_info=None):

    metainfo = OrderedDict()
    updatemeta = OrderedDict()

    hdustr = ''
    if whichhdu.lower() != 'primary' and whichhdu != '0':
        hdustr = ':%s' % whichhdu
    

    if fmdefs.META_HEADERS in filetype_metadata:
        keylist = [ '%s%s' % (k,hdustr) for k in filetype_metadata[fmdefs.META_HEADERS].keys()]  # add which header to keys
        metainfo[fmdefs.META_HEADERS] = ','.join(keylist)

    if fmdefs.META_COMPUTE in filetype_metadata:
        if file_header_info is not None:   # if supposed to update headers and update DB
            updatemeta.update(create_update_items(derived_from, filetype_metadata[fmdefs.META_COMPUTE].keys(), file_header_info))

            if fmdefs.META_HEADERS not in metainfo:
                metainfo[fmdefs.META_HEADERS] = ""
            else:
                metainfo[fmdefs.META_HEADERS] += ','
            metainfo[fmdefs.META_HEADERS] += ','.join(filetype_metadata[fmdefs.META_COMPUTE].keys())  # after update, keys in primary

        else:  # just compute values for DB
            metainfo[fmdefs.META_COMPUTE] = ','.join(filetype_metadata[fmdefs.META_COMPUTE].keys())

    if fmdefs.META_COPY in filetype_metadata:
        if file_header_info is not None:   # if supposed to update headers and update DB
            updatemeta.update(create_copy_items(whichhdu, derived_from, filetype_metadata[fmdefs.META_COPY].keys()))
            if fmdefs.META_HEADERS not in metainfo:
                metainfo[fmdefs.META_HEADERS] = ""
            else:
                metainfo[fmdefs.META_HEADERS] += ','

            metainfo[fmdefs.META_HEADERS] += ','.join(filetype_metadata[fmdefs.META_COPY].keys())
        else:  # just compute values for DB
            keylist = [ '%s%s' % (k,hdustr) for k in filetype_metadata[fmdefs.META_COPY].keys()]  # add which header to keys
            if fmdefs.META_HEADERS not in metainfo:
                metainfo[fmdefs.META_HEADERS] = ""
            else:
                metainfo[fmdefs.META_HEADERS] += ','

            metainfo[fmdefs.META_HEADERS] += ','.join(keylist)

    if fmdefs.META_WCL in filetype_metadata:
        wclkeys = []
        for k in filetype_metadata[fmdefs.META_WCL].keys():
             if sectlabel is not None:
                 wclkey = '%s.%s' % (sectlabel, k)
             else:
                 wclkey = k
             wclkeys.append(wclkey)
        metainfo[fmdefs.META_WCL] = ','.join(wclkeys)

    if len(updatemeta) == 0:
        updatemeta = None

    return (metainfo, updatemeta)



#######################################################################
def create_copy_items(srchdu, metastatus, file_header_names):
    """ Create the update wcl for headers that should be copied from another header """

    updateDict = OrderedDict()
    for name in file_header_names:
        if metastatus == fmdefs.META_REQUIRED:
            updateDict[name] = "$REQCOPY{%s:%s}" % (name.upper(), srchdu)
        elif metastatus == fmdefs.META_OPTIONAL:
            updateDict[name] = "$OPTCOPY{%s:%s}" % (name.upper(), srchdu)
        else:
            miscutils.fwdie('Error:  Unknown metadata metastatus (%s)' % (metastatus), metadefs.MD_EXIT_FAILURE)

    return updateDict



###########################################################################
def create_update_items(metastatus, file_header_names, file_header_info, header_value=None):
    """ Create the update wcl for headers that should be updated """
    updateDict = OrderedDict()

    for name in file_header_names:
        #print "looking for %s in file_header_info" % name
        if name not in file_header_info:
            #print "file_header_info.keys() = ", file_header_info.keys()
            miscutils.fwdie('Error: Missing entry in file_header_info for %s' % name, metadefs.MD_EXIT_FAILURE)

        # Example: $HDRFNC{BAND}/Filter identifier/str
        if header_value is not None and name in header_value:
            updateDict[name] = header_value[name]
        elif metastatus == fmdefs.META_REQUIRED:
            updateDict[name] = "$HDRFNC{%s}" % (name.upper())
        elif metastatus == fmdefs.META_OPTIONAL:
            updateDict[name] = "$OPTFNC{%s}" % (name.upper())
        else:
            miscutils.fwdie('Error:  Unknown metadata metastatus (%s)' % (metastatus), metadefs.MD_EXIT_FAILURE)

        if file_header_info[name]['fits_data_type'].lower() == 'none':
            miscutils.fwdie('Error:  Missing fits_data_type for file header %s\nCheck entry in OPS_FILE_HEADER table' % name, metadefs.MD_EXIT_FAILURE)

        # Requires 'none' to not be a valid description
        if file_header_info[name]['description'].lower() == 'none':
            miscutils.fwdie('Error:  Missing description for file header %s\nCheck entry in OPS_FILE_HEADER table' % name, metadefs.MD_EXIT_FAILURE)

        updateDict[name] += "/%s/%s" % (file_header_info[name]['description'],
                                        file_header_info[name]['fits_data_type'])

    return updateDict


