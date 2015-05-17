#!/usr/bin/env python

""" Generic wrapper """

import sys

import intgutils.basic_wrapper as basic_wrapper

def main():
    """ entry point """
    bwrap = basic_wrapper.BasicWrapper(sys.argv[1])
    bwrap.run_wrapper()
    bwrap.write_outputwcl()
    sys.exit(bwrap.get_status())

if __name__ == "__main__":
    main()
