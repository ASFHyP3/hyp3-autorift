#!/usr/bin/env python3
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
# This is a substantially modified copy of the testautoRIFT_ISCE.py script
# provided in the autoRIFT v1.0.4 release, See the LICENSE file in this directory
# for the original terms and conditions, and CHANGES.diff for a detailed
# description of the changes. Notice, all changes are released under the terms
# and conditions of hyp3-autorift's LICENSE.
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
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
# Author: Yang Lei
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
import argparse
import logging
import subprocess
import time
from datetime import date

import cv2
import numpy as np
import scipy.io as sio
from osgeo import gdal

from hyp3_autorift import netcdf_output as no


def runCmd(cmd):
    out = subprocess.getoutput(cmd)
    return out


def cmdLineParse():
    '''
    Command line parser.
    '''

    parser = argparse.ArgumentParser(description='Output geo grid')
    parser.add_argument('-m', '--input_m', dest='indir_m', type=str, required=True,
            help='Input master image file name (in ISCE format and radar coordinates) '
                 'or Input master image file name (in GeoTIFF format and Cartesian coordinates)')
    parser.add_argument('-s', '--input_s', dest='indir_s', type=str, required=True,
            help='Input slave image file name (in ISCE format and radar coordinates) '
                 'or Input slave image file name (in GeoTIFF format and Cartesian coordinates)')
    parser.add_argument('-g', '--input_g', dest='grid_location', type=str, required=False,
            help='Input pixel indices file name')
    parser.add_argument('-o', '--input_o', dest='init_offset', type=str, required=False,
            help='Input search center offsets ("downstream" reach location) file name')
    parser.add_argument('-vx', '--input_vx', dest='offset2vx', type=str, required=False,
            help='Input pixel offsets to vx conversion coefficients file name')
    parser.add_argument('-vy', '--input_vy', dest='offset2vy', type=str, required=False,
            help='Input pixel offsets to vy conversion coefficients file name')
    parser.add_argument('-fo', '--flag_optical', dest='optical_flag', type=bool, required=False, default=0,
            help='flag for reading optical data (e.g. Landsat): use 1 for on and 0 (default) for off')
    parser.add_argument('-nc', '--sensor_flag_netCDF', dest='nc_sensor', type=str, required=False, default=None,
            help='flag for packaging output formatted for Sentinel ("S") and Landsat ("L") dataset; default is None')

    return parser.parse_args()


class Dummy(object):
    pass


def loadProduct(filename):
    '''
    Load the product using Product Manager.
    '''
    import isce
    from imageMath import IML

    IMG = IML.mmapFromISCE(filename, logging)
    img = IMG.bands[0]
    return img


def loadProductOptical(filename):
    '''
    Load the product using Product Manager.
    '''
    ds = gdal.Open(filename)
    band = ds.GetRasterBand(1)
    
    img = band.ReadAsArray()
    img = img.astype(np.float32)
    
    band=None
    ds=None
    
    return img


def runAutorift(I1, I2, xGrid, yGrid, Dx0, Dy0, noDataMask, optflag, nodata):
    '''
    Wire and run geogrid.
    '''
    import isce
    from components.contrib.geo_autoRIFT.autoRIFT import autoRIFT_ISCE
    import isceobj

    obj = autoRIFT_ISCE()
    obj.configure()

    # take the amplitude only for the radar images
    if optflag == 0:
        I1 = np.abs(I1)
        I2 = np.abs(I2)

    obj.I1 = I1
    obj.I2 = I2

    # create the grid if it does not exist
    if xGrid is None:
        m,n = obj.I1.shape
        xGrid = np.arange(obj.SkipSampleX+10,n-obj.SkipSampleX,obj.SkipSampleX)
        yGrid = np.arange(obj.SkipSampleY+10,m-obj.SkipSampleY,obj.SkipSampleY)
        nd = xGrid.__len__()
        md = yGrid.__len__()
        obj.xGrid = np.int32(np.dot(np.ones((md,1)),np.reshape(xGrid,(1,xGrid.__len__()))))
        obj.yGrid = np.int32(np.dot(np.reshape(yGrid,(yGrid.__len__(),1)),np.ones((1,nd))))
        noDataMask = np.logical_not(obj.xGrid)
    else:
        obj.xGrid = xGrid
        obj.yGrid = yGrid
        if optflag == 1:
            obj.ChipSizeMaxX = 32
            obj.ChipSizeMinX = 16
            obj.ChipSize0X = 16
    
    # generate the nodata mask where offset searching will be skipped based on
    # 1) imported nodata mask and/or 2) zero values in the image
    for ii in range(obj.xGrid.shape[0]):
        for jj in range(obj.xGrid.shape[1]):
            if (obj.yGrid[ii,jj] != nodata)&(obj.xGrid[ii,jj] != nodata):
                if (I1[obj.yGrid[ii,jj]-1,obj.xGrid[ii,jj]-1]==0)|(I2[obj.yGrid[ii,jj]-1,obj.xGrid[ii,jj]-1]==0):
                    noDataMask[ii,jj] = True

    # mask out nodata to skip the offset searching using the nodata mask (by setting SearchLimit to be 0)
    obj.SearchLimitX = obj.SearchLimitX * np.logical_not(noDataMask)
    obj.SearchLimitY = obj.SearchLimitY * np.logical_not(noDataMask)

    # create the downstream search offset if not provided as input
    if Dx0 is not None:
        obj.Dx0 = Dx0
        obj.Dy0 = Dy0
    else:
        obj.Dx0 = obj.Dx0 * np.logical_not(noDataMask)
        obj.Dy0 = obj.Dy0 * np.logical_not(noDataMask)

    # replace the nodata value with zero
    obj.xGrid[noDataMask] = 0
    obj.yGrid[noDataMask] = 0
    obj.Dx0[noDataMask] = 0
    obj.Dy0[noDataMask] = 0

    # convert azimuth offset to vertical offset as used in autoRIFT convention
    if optflag == 0:
        obj.Dy0 = -1 * obj.Dy0

    # preprocessing
    t1 = time.time()
    print("Pre-process Start!!!")
    obj.preprocess_filt_hps()
    print("Pre-process Done!!!")
    print(time.time()-t1)

    t1 = time.time()
    obj.uniform_data_type()
    print("Uniform Data Type Done!!!")
    print(time.time()-t1)

    t1 = time.time()
    print("AutoRIFT Start!!!")
    obj.runAutorift()
    print("AutoRIFT Done!!!")
    print(time.time()-t1)

    kernel = np.ones((3,3),np.uint8)
    noDataMask = cv2.dilate(noDataMask.astype(np.uint8),kernel,iterations = 1)
    noDataMask = noDataMask.astype(np.bool)

    return obj.Dx, obj.Dy, obj.InterpMask, obj.ChipSizeX, obj.ScaleChipSizeY, \
           obj.SearchLimitX, obj.SearchLimitY, obj.origSize, noDataMask


def main():
    '''
    Main driver.
    '''
    inps = cmdLineParse()
    
    if inps.optical_flag == 1:
        data_m = loadProductOptical(inps.indir_m)
        data_s = loadProductOptical(inps.indir_s)
    else:
        data_m = loadProduct(inps.indir_m)
        data_s = loadProduct(inps.indir_s)



    xGrid = None
    yGrid = None
    Dx0 = None
    Dy0 = None
    noDataMask = None
    nodata = None
    
    if inps.grid_location is not None:
        ds = gdal.Open(inps.grid_location)
        tran = ds.GetGeoTransform()
        proj = ds.GetProjection()
        srs = ds.GetSpatialRef()
        band = ds.GetRasterBand(1)
        nodata = band.GetNoDataValue()
        xGrid = band.ReadAsArray()
        noDataMask = (xGrid == nodata)
        band = ds.GetRasterBand(2)
        yGrid = band.ReadAsArray()
        band=None
        ds=None
    
    if inps.init_offset is not None:
        ds = gdal.Open(inps.init_offset)
        band = ds.GetRasterBand(1)
        Dx0 = band.ReadAsArray()
        band = ds.GetRasterBand(2)
        Dy0 = band.ReadAsArray()
        band=None
        ds=None

    Dx, Dy, InterpMask, ChipSizeX, ScaleChipSizeY, SearchLimitX, SearchLimitY, origSize, noDataMask = runAutorift(
        data_m, data_s, xGrid, yGrid, Dx0, Dy0, noDataMask, inps.optical_flag, nodata
    )

    if inps.optical_flag == 0:
        Dy = -Dy

    DX = np.zeros(origSize,dtype=np.float32) * np.nan
    DY = np.zeros(origSize,dtype=np.float32) * np.nan
    INTERPMASK = np.zeros(origSize,dtype=np.float32)
    CHIPSIZEX = np.zeros(origSize,dtype=np.float32)
    SEARCHLIMITX = np.zeros(origSize,dtype=np.float32)
    SEARCHLIMITY = np.zeros(origSize,dtype=np.float32)
    
    DX[0:Dx.shape[0],0:Dx.shape[1]] = Dx
    DY[0:Dy.shape[0],0:Dy.shape[1]] = Dy
    INTERPMASK[0:InterpMask.shape[0],0:InterpMask.shape[1]] = InterpMask
    CHIPSIZEX[0:ChipSizeX.shape[0],0:ChipSizeX.shape[1]] = ChipSizeX
    SEARCHLIMITX[0:SearchLimitX.shape[0],0:SearchLimitX.shape[1]] = SearchLimitX
    SEARCHLIMITY[0:SearchLimitY.shape[0],0:SearchLimitY.shape[1]] = SearchLimitY

    DX[noDataMask] = np.nan
    DY[noDataMask] = np.nan
    INTERPMASK[noDataMask] = 0
    CHIPSIZEX[noDataMask] = 0
    SEARCHLIMITX[noDataMask] = 0
    SEARCHLIMITY[noDataMask] = 0

    sio.savemat('offset.mat',{'Dx':DX,'Dy':DY,'InterpMask':INTERPMASK,'ChipSizeX':CHIPSIZEX})

    if inps.grid_location is not None:

        t1 = time.time()
        print("Write Outputs Start!!!")

        # Create the GeoTiff
        driver = gdal.GetDriverByName('GTiff')

        outRaster = driver.Create("offset.tif", int(xGrid.shape[1]), int(xGrid.shape[0]), 4, gdal.GDT_Float32)
        outRaster.SetGeoTransform(tran)
        outRaster.SetProjection(proj)
        outband = outRaster.GetRasterBand(1)
        outband.WriteArray(DX)
        outband.FlushCache()
        outband = outRaster.GetRasterBand(2)
        outband.WriteArray(DY)
        outband.FlushCache()
        outband = outRaster.GetRasterBand(3)
        outband.WriteArray(INTERPMASK)
        outband.FlushCache()
        outband = outRaster.GetRasterBand(4)
        outband.WriteArray(CHIPSIZEX)
        outband.FlushCache()

        if inps.offset2vx is not None:
            ds = gdal.Open(inps.offset2vx)
            band = ds.GetRasterBand(1)
            offset2vx_1 = band.ReadAsArray()
            band = ds.GetRasterBand(2)
            offset2vx_2 = band.ReadAsArray()
            band=None
            ds=None

            ds = gdal.Open(inps.offset2vy)
            band = ds.GetRasterBand(1)
            offset2vy_1 = band.ReadAsArray()
            band = ds.GetRasterBand(2)
            offset2vy_2 = band.ReadAsArray()
            band=None
            ds=None

            VX = offset2vx_1 * DX + offset2vx_2 * DY
            VY = offset2vy_1 * DX + offset2vy_2 * DY
            VX = VX.astype(np.float32)
            VY = VY.astype(np.float32)

            outRaster = driver.Create("velocity.tif", int(xGrid.shape[1]), int(xGrid.shape[0]), 2, gdal.GDT_Float32)
            outRaster.SetGeoTransform(tran)
            outRaster.SetProjection(proj)
            outband = outRaster.GetRasterBand(1)
            outband.WriteArray(VX)
            outband.FlushCache()
            outband = outRaster.GetRasterBand(2)
            outband.WriteArray(VY)
            outband.FlushCache()
            
            # netCDF packaging for Sentinel and Landsat dataset; can add other sensor format as well
            if inps.nc_sensor == "S":
                
                rangePixelSize = float(str.split(runCmd('fgrep "Range:" testGeogrid.txt'))[2])
                prf = float(str.split(runCmd('fgrep "Azimuth:" testGeogrid.txt'))[2])
                dt = float(str.split(runCmd('fgrep "Repeat Time:" testGeogrid.txt'))[2])
                epsg = float(str.split(runCmd('fgrep "EPSG:" testGeogrid.txt'))[1])
                satv = np.array([float(str.split(runCmd('fgrep "Center Satellite Velocity:" testGeogrid.txt'))[3]),
                                 float(str.split(runCmd('fgrep "Center Satellite Velocity:" testGeogrid.txt'))[4]),
                                 float(str.split(runCmd('fgrep "Center Satellite Velocity:" testGeogrid.txt'))[5])])
                azimuthPixelSize = np.sqrt(np.sum(satv**2)) / prf

                runCmd('topsinsar_filename.py')
                conts = sio.loadmat('topsinsar_filename.mat')
                master_filename = conts['master_filename'][0]
                slave_filename = conts['slave_filename'][0]
                master_split = str.split(master_filename,'_')
                slave_split = str.split(slave_filename,'_')

                version = '1.0.4'
                pair_type = 'radar'
                detection_method = 'feature'
                coordinates = 'radar'
                out_nc_filename = master_filename[0:-4]+'_'+slave_filename[0:-4]+'.nc'
                out_nc_filename = './' + out_nc_filename
                roi_valid_percentage = np.sum(CHIPSIZEX!=0)/np.sum(SEARCHLIMITX!=0)*100.0
                CHIPSIZEY = CHIPSIZEX * ScaleChipSizeY

                d0 = date(np.int(master_split[5][0:4]),np.int(master_split[5][4:6]),np.int(master_split[5][6:8]))
                d1 = date(np.int(slave_split[5][0:4]),np.int(slave_split[5][4:6]),np.int(slave_split[5][6:8]))
                date_dt_base = d1 - d0
                date_dt = np.float64(np.abs(date_dt_base.days))
                if date_dt_base.days < 0:
                    date_ct = d1 + (d0 - d1)/2
                    date_center = date_ct.strftime("%Y%m%d")
                else:
                    date_ct = d0 + (d1 - d0)/2
                    date_center = date_ct.strftime("%Y%m%d")
            
                IMG_INFO_DICT = {'mission_img1':master_split[0][0],
                                 'sensor_img1':'C',
                                 'satellite_img1':master_split[0][1:3],
                                 'acquisition_img1':master_split[5][0:8],
                                 'absolute_orbit_number_img1':master_split[7],
                                 'mission_data_take_ID_img1':master_split[8],
                                 'product_unique_ID_img1':master_split[9][0:4],
                                 'mission_img2':slave_split[0][0],
                                 'sensor_img2':'C',
                                 'satellite_img2':slave_split[0][1:3],
                                 'acquisition_img2':slave_split[5][0:8],
                                 'absolute_orbit_number_img2':slave_split[7],
                                 'mission_data_take_ID_img2':slave_split[8],
                                 'product_unique_ID_img2':slave_split[9][0:4],
                                 'date_dt':date_dt,
                                 'date_center':date_center,
                                 'roi_valid_percentage':roi_valid_percentage,
                                 'autoRIFT_software_version':version}

                no.netCDF_packaging(
                    VX, VY, DX, DY, INTERPMASK, CHIPSIZEX, CHIPSIZEY, rangePixelSize, azimuthPixelSize,
                    dt, epsg, srs, tran, out_nc_filename, pair_type, detection_method, coordinates, IMG_INFO_DICT
                )

            elif inps.nc_sensor == "L":
                
                XPixelSize = np.abs(float(str.split(runCmd('fgrep "X-direction coordinate:" testGeogrid.txt'))[3]))
                YPixelSize = np.abs(float(str.split(runCmd('fgrep "Y-direction coordinate:" testGeogrid.txt'))[3]))
                epsg = float(str.split(runCmd('fgrep "EPSG:" testGeogrid.txt'))[1])
                
                master_filename = inps.indir_m
                slave_filename = inps.indir_s
                master_split = str.split(master_filename,'_')
                slave_split = str.split(slave_filename,'_')
                
                version = '1.0.4'
                pair_type = 'optical'
                detection_method = 'feature'
                coordinates = 'map'
                out_nc_filename = master_filename[0:-4]+'_'+slave_filename[0:-4]+'.nc'
                out_nc_filename = './' + out_nc_filename
                roi_valid_percentage = np.sum(CHIPSIZEX!=0)/np.sum(SEARCHLIMITX!=0)*100.0
                CHIPSIZEY = CHIPSIZEX * ScaleChipSizeY

                d0 = date(np.int(master_split[3][0:4]),np.int(master_split[3][4:6]),np.int(master_split[3][6:8]))
                d1 = date(np.int(slave_split[3][0:4]),np.int(slave_split[3][4:6]),np.int(slave_split[3][6:8]))
                date_dt_base = d1 - d0
                date_dt = np.float64(np.abs(date_dt_base.days))
                if date_dt_base.days < 0:
                    date_ct = d1 + (d0 - d1)/2
                    date_center = date_ct.strftime("%Y%m%d")
                else:
                    date_ct = d0 + (d1 - d0)/2
                    date_center = date_ct.strftime("%Y%m%d")

                IMG_INFO_DICT = {'mission_img1':master_split[0][0],
                                 'sensor_img1':master_split[0][1],
                                 'satellite_img1':np.float64(master_split[0][2:4]),
                                 'correction_level_img1':master_split[1],
                                 'path_img1':np.float64(master_split[2][0:3]),
                                 'row_img1':np.float64(master_split[2][3:6]),
                                 'acquisition_date_img1':master_split[3][0:8],
                                 'processing_date_img1':master_split[4][0:8],
                                 'collection_number_img1':np.float64(master_split[5]),
                                 'collection_category_img1':master_split[6],
                                 'mission_img2':slave_split[0][0],
                                 'sensor_img2':slave_split[0][1],
                                 'satellite_img2':np.float64(slave_split[0][2:4]),
                                 'correction_level_img2':slave_split[1],
                                 'path_img2':np.float64(slave_split[2][0:3]),
                                 'row_img2':np.float64(slave_split[2][3:6]),
                                 'acquisition_date_img2':slave_split[3][0:8],
                                 'processing_date_img2':slave_split[4][0:8],
                                 'collection_number_img2':np.float64(slave_split[5]),
                                 'collection_category_img2':slave_split[6],
                                 'date_dt':date_dt,
                                 'date_center':date_center,
                                 'roi_valid_percentage':roi_valid_percentage,
                                 'autoRIFT_software_version':version}
                
                no.netCDF_packaging(
                    VX, VY, DX, DY, INTERPMASK, CHIPSIZEX, CHIPSIZEY, XPixelSize, YPixelSize,
                    None, epsg, srs, tran, out_nc_filename, pair_type, detection_method, coordinates, IMG_INFO_DICT
                )

            elif inps.nc_sensor is None:
                print('netCDF packaging not performed')

            else:
                raise Exception('netCDF packaging not supported for the type "{0}"'.format(inps.nc_sensor))

        print("Write Outputs Done!!!")
        print(time.time()-t1)


if __name__ == '__main__':
    main()
