#!/usr/bin/env python3
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# This is a substantially modified copy of the testGeogrid_ISCE.py script
# as described in the README.md in this directory. See the LICENSE file in this
# directory for the original terms and conditions, and CHANGES.diff for a detailed
# description of the changes. Notice, all changes are released under the terms
# and conditions of hyp3-autorift's LICENSE.
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# Copyright 2019 California Institute of Technology. ALL RIGHTS RESERVED.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# United States Government Sponsorship acknowledged. This software is subject to
# U.S. export control laws and regulations and has been classified as 'EAR99 NLR'
# (No [Export] License Required except when exporting to an embargoed country,
# end user, or in support of a prohibited end use). By downloading this software,
# the user agrees to comply with all applicable U.S. export laws and regulations.
# The user has the responsibility to obtain export licenses, or other export
# authority as may be required before exporting this software to any 'EAR99'
# embargoed foreign country or citizen of those countries.
#
# Authors: Piyush Agram, Yang Lei
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
import argparse
import os
import re
from datetime import date

import numpy as np
from geogrid import GeogridOptical
from osgeo import gdal

def cmdLineParse():
    '''
    Command line parser.
    '''
    parser = argparse.ArgumentParser(description='Output geo grid')
    parser.add_argument('-r', '--input_r', dest='indir_r', type=str, required=True,
            help='Input reference image file name (in GeoTIFF format and Cartesian coordinates)')
    parser.add_argument('-s', '--input_s', dest='indir_s', type=str, required=True,
            help='Input secondary image file name (in GeoTIFF format and Cartesian coordinates)')
#    parser.add_argument('-o', '--output', dest='outfile', type=str, default='geogrid.csv',
#            help='Output grid mapping')
    parser.add_argument('-d', '--dem', dest='demfile', type=str, required=True,
            help='Input DEM')
    parser.add_argument('-sx', '--dhdx', dest='dhdxfile', type=str, default="",
            help='Input slope in X')
    parser.add_argument('-sy', '--dhdy', dest='dhdyfile', type=str, default="",
            help='Input slope in Y')
    parser.add_argument('-vx', '--vx', dest='vxfile', type=str, default="",
            help='Input velocity in X')
    parser.add_argument('-vy', '--vy', dest='vyfile', type=str, default="",
            help='Input velocity in Y')
    parser.add_argument('-srx', '--srx', dest='srxfile', type=str, default="",
            help='Input search range in X')
    parser.add_argument('-sry', '--sry', dest='sryfile', type=str, default="",
            help='Input search range in Y')
    parser.add_argument('-csminx', '--csminx', dest='csminxfile', type=str, default="",
            help='Input chip size min in X')
    parser.add_argument('-csminy', '--csminy', dest='csminyfile', type=str, default="",
            help='Input chip size min in Y')
    parser.add_argument('-csmaxx', '--csmaxx', dest='csmaxxfile', type=str, default="",
            help='Input chip size max in X')
    parser.add_argument('-csmaxy', '--csmaxy', dest='csmaxyfile', type=str, default="",
            help='Input chip size max in Y')
    parser.add_argument('-ssm', '--ssm', dest='ssmfile', type=str, default="",
            help='Input stable surface mask')
    parser.add_argument('-urlflag', '--urlflag', dest='urlflag', type=int, required=False,
            help='flag for reading and coregistering optical data (GeoTIFF images, e.g. Landsat): use 1 for url read and 0 for local machine read; if not specified (i.e. None; default), will just read from local machine without coregistration')

    return parser.parse_args()

class Dummy(object):
    pass





def loadMetadata(indir):
    '''
    Input file.
    '''
    DS = gdal.Open(indir, gdal.GA_ReadOnly)
    trans = DS.GetGeoTransform()

    info = Dummy()
    info.startingX = trans[0]
    info.startingY = trans[3]
    info.XSize = trans[1]
    info.YSize = trans[5]

    if re.findall("L8",DS.GetDescription()).__len__() > 0:
        nameString = os.path.basename(DS.GetDescription())
        info.time = nameString.split('_')[3]
    elif re.findall("S2",DS.GetDescription()).__len__() > 0:
        info.time = DS.GetDescription().split('_')[2]
    else:
        raise Exception('Optical data NOT supported yet!')

    info.numberOfLines = DS.RasterYSize
    info.numberOfSamples = DS.RasterXSize

    info.filename = indir


    return info


def coregisterLoadMetadata(indir_r, indir_s, urlflag):
    '''
        Input file.
        '''

    obj = GeogridOptical()

    x1a, y1a, xsize1, ysize1, x2a, y2a, xsize2, ysize2, trans = obj.coregister(indir_r, indir_s, urlflag)

    if urlflag is 1:
        DS = gdal.Open('/vsicurl/%s' % (indir_r))
    else:
        DS = gdal.Open(indir_r, gdal.GA_ReadOnly)

    info = Dummy()
    info.startingX = trans[0]
    info.startingY = trans[3]
    info.XSize = trans[1]
    info.YSize = trans[5]

    if re.findall("L8",DS.GetDescription()).__len__() > 0:
        nameString = os.path.basename(DS.GetDescription())
        info.time = nameString.split('_')[3]
    elif re.findall("S2",DS.GetDescription()).__len__() > 0:
        info.time = DS.GetDescription().split('_')[2]
    else:
        raise Exception('Optical data NOT supported yet!')

    info.numberOfLines = ysize1
    info.numberOfSamples = xsize1

    info.filename = indir_r

    if urlflag is 1:
        DS1 = gdal.Open('/vsicurl/%s' %(indir_s))
    else:
        DS1 = gdal.Open(indir_s, gdal.GA_ReadOnly)

    info1 = Dummy()

    if re.findall("L8",DS1.GetDescription()).__len__() > 0:
        nameString1 = os.path.basename(DS1.GetDescription())
        info1.time = nameString1.split('_')[3]
    elif re.findall("S2",DS1.GetDescription()).__len__() > 0:
        info1.time = DS1.GetDescription().split('_')[2]
    else:
        raise Exception('Optical data NOT supported yet!')

    return info, info1


def runGeogrid(info, info1, dem, dhdx, dhdy, vx, vy, srx, sry, csminx, csminy, csmaxx, csmaxy, ssm, urlflag):
    '''
    Wire and run geogrid.
    '''

    obj = GeogridOptical()

    obj.startingX = info.startingX
    obj.startingY = info.startingY
    obj.XSize = info.XSize
    obj.YSize = info.YSize
    d0 = date(np.int(info.time[0:4]),np.int(info.time[4:6]),np.int(info.time[6:8]))
    d1 = date(np.int(info1.time[0:4]),np.int(info1.time[4:6]),np.int(info1.time[6:8]))
    date_dt_base = d1 - d0
    obj.repeatTime = np.abs(date_dt_base.total_seconds())
#    obj.repeatTime = (info1.time - info.time) * 24.0 * 3600.0
    obj.numberOfLines = info.numberOfLines
    obj.numberOfSamples = info.numberOfSamples
    obj.nodata_out = -32767
    obj.chipSizeX0 = 240

    obj.urlflag = urlflag
    obj.dat1name = info.filename
    obj.demname = dem
    obj.dhdxname = dhdx
    obj.dhdyname = dhdy
    obj.vxname = vx
    obj.vyname = vy
    obj.srxname = srx
    obj.sryname = sry
    obj.csminxname = csminx
    obj.csminyname = csminy
    obj.csmaxxname = csmaxx
    obj.csmaxyname = csmaxy
    obj.ssmname = ssm
    obj.winlocname = "window_location.tif"
    obj.winoffname = "window_offset.tif"
    obj.winsrname = "window_search_range.tif"
    obj.wincsminname = "window_chip_size_min.tif"
    obj.wincsmaxname = "window_chip_size_max.tif"
    obj.winssmname = "window_stable_surface_mask.tif"
    obj.winro2vxname = "window_rdr_off2vel_x_vec.tif"
    obj.winro2vyname = "window_rdr_off2vel_y_vec.tif"

    obj.runGeogrid()


def main():
    '''
    Main driver.
    '''

    inps = cmdLineParse()

    if inps.urlflag is not None:
        metadata_r, metadata_s = coregisterLoadMetadata(inps.indir_r, inps.indir_s, inps.urlflag)
    else:
        metadata_r = loadMetadata(inps.indir_r)
        metadata_s = loadMetadata(inps.indir_s)

    runGeogrid(metadata_r, metadata_s, inps.demfile, inps.dhdxfile, inps.dhdyfile, inps.vxfile, inps.vyfile, inps.srxfile, inps.sryfile, inps.csminxfile, inps.csminyfile, inps.csmaxxfile, inps.csmaxyfile, inps.ssmfile, inps.urlflag)


if __name__ == '__main__':
    main()
