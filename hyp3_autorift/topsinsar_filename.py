#!/usr/bin/env python3

########
#Yang Lei, Jet Propulsion Laboratory
#November 2017

import argparse

def loadXml():
    import os
    from topsApp import TopsInSAR
    insar = TopsInSAR(name="topsApp")
    insar.configure()
    master_filename = os.path.basename(insar.master.safe[0])
    slave_filename = os.path.basename(insar.slave.safe[0])
    return master_filename, slave_filename

def cmdLineParse():
    '''
        Command line parser.
        '''
    parser = argparse.ArgumentParser(description="Single-pair InSAR processing of Sentinel-1 data using ISCE modules")
    
    return parser.parse_args()


if __name__ == '__main__':
    import scipy.io as sio
    master_filename, slave_filename = loadXml()
    print(master_filename)
    print(slave_filename)
    sio.savemat('topsinsar_filename.mat',{'master_filename':master_filename,'slave_filename':slave_filename})
