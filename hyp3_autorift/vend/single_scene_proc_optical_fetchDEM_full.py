#!/usr/bin/env python3

########
#Yang Lei, Jet Propulsion Laboratory
#November 2017

import xml.etree.ElementTree as ET
from numpy import *
import scipy.io as sio
##import commands
import subprocess
import os
import time
import argparse
import pdb
import os
import isce
import shelve
import string
import sys
from osgeo import osr,gdal
import re

def cmdLineParse():
    '''
    Command line parser.
    '''
    parser = argparse.ArgumentParser(description="Single-pair InSAR processing of Sentinel-1 data using ISCE modules")
    
    parser.add_argument('-m', '--reference', dest='reference', type=str, required=True,
                        help='Optical reference filename')
    parser.add_argument('-s', '--secondary', dest='secondary', type=str, required=True,
                        help='Optical secondary filename')
    parser.add_argument('-f', '--foldername', dest='foldername', type=str, required=True,
                        help='Output foldername')

    return parser.parse_args()


def runCmd(cmd):
    out = subprocess.getoutput(cmd)
    return out



if __name__ == '__main__':
    
        inps = cmdLineParse()
        
        print (time.strftime("%H:%M:%S"))
#        pdb.set_trace()

        ##########################      DEM preparation      ######################
        
#        foldername = os.path.split(inps.reference)[1][:-4] + '_' + os.path.split(inps.secondary)[1][:-4]
        foldername = inps.foldername
        reference_name_list = inps.reference
        secondary_name_list = inps.secondary
        
        cmd = 'mkdir ' + foldername
        runCmd(cmd)
        os.chdir(foldername)

        # START: fetch appropriate DEM from DEM archive
        DEM_Directory_Dict = ['http://its-live-data.jpl.nasa.gov.s3.amazonaws.com/isce_autoRIFT/GRE240m_','http://its-live-data.jpl.nasa.gov.s3.amazonaws.com/isce_autoRIFT/ANT240m_']

        flag = 0

        for dem_directory in DEM_Directory_Dict:

            demname = '{0}h.tif'.format(dem_directory)
            cmd = 'gdalsrsinfo -o epsg /vsicurl/{0}'.format(demname)
            epsgstr = subprocess.check_output(cmd, shell=True)
            epsgstr = re.findall("EPSG:(\d+)", str(epsgstr))[0]
            if not epsgstr:  #Empty string
                raise Exception('Could not auto-identify epsg code')
            epsgDem = int(epsgstr)

            cmd = 'gdalsrsinfo -o epsg /vsicurl/{0}'.format(inps.reference)
            epsgstr = subprocess.check_output(cmd, shell=True)
            epsgstr = re.findall("EPSG:(\d+)", str(epsgstr))[0]
            if not epsgstr:  #Empty string
                raise Exception('Could not auto-identify epsg code')
            epsgDat = int(epsgstr)

#            from components.contrib.geo_autoRIFT.geogrid import GeogridOptical
            from geogrid import GeogridOptical
            
            obj = GeogridOptical()
            x1a, y1a, xsize1, ysize1, x2a, y2a, xsize2, ysize2, trans = obj.coregister(inps.reference, inps.secondary, 1)
            obj.startingX = trans[0]
            obj.startingY = trans[3]
            obj.XSize = trans[1]
            obj.YSize = trans[5]
            obj.numberOfLines = ysize1
            obj.numberOfSamples = xsize1
            obj.epsgDat = epsgDat
            obj.epsgDem = epsgDem

            obj.determineBbox()

            xlim = obj._xlim
            ylim = obj._ylim

            demDS = gdal.Open('/vsicurl/%s' %(demname))
            geoTrans = demDS.GetGeoTransform()
            demXSize = demDS.RasterXSize
            demYSize = demDS.RasterYSize

            if ((xlim[0]>geoTrans[0])&(xlim[0]<(geoTrans[0]+(demXSize-1)*geoTrans[1]))&(ylim[1]<geoTrans[3])&(ylim[0]>(geoTrans[3]+(demYSize-1)*geoTrans[5]))):
                demDS = None
                flag = 1
                break

        if not flag:
            raise Exception("Existing DEM's in the database do not cover or at least do not fully cover the image data!")

        dhdxname = '{0}dhdx.tif'.format(dem_directory)
        dhdyname = '{0}dhdy.tif'.format(dem_directory)
        vxname = '{0}vx0.tif'.format(dem_directory)
        vyname = '{0}vy0.tif'.format(dem_directory)
        srxname = '{0}vxSearchRange.tif'.format(dem_directory)
        sryname = '{0}vySearchRange.tif'.format(dem_directory)
        csmaxxname = '{0}xMaxChipSize.tif'.format(dem_directory)
        csmaxyname = '{0}yMaxChipSize.tif'.format(dem_directory)
        csminxname = '{0}xMinChipSize.tif'.format(dem_directory)
        csminyname = '{0}yMinChipSize.tif'.format(dem_directory)
        ssmname = '{0}StableSurface.tif'.format(dem_directory)

        import re
        DS = gdal.Open('/vsicurl/%s' %(inps.reference))

        if re.findall("L8",DS.GetDescription()).__len__() > 0:
            sensor = 'L'
        elif re.findall("S2",DS.GetDescription()).__len__() > 0:
            sensor = 'S2'
        else:
            raise Exception('Optical data NOT supported yet!')

        # END: fetch appropriate DEM from DEM archive
        print("Initialization Done!")
        print (time.strftime("%H:%M:%S"))


        ##########################      Geogrid and autoRIFT run      ######################

        cmd = 'testGeogridOptical.py -m ' + inps.reference + ' -s ' + inps.secondary + ' -d ' + demname + ' -sx ' + dhdxname + ' -sy ' + dhdyname + ' -vx ' + vxname + ' -vy ' + vyname + ' -srx ' + srxname + ' -sry ' + sryname + ' -csminx ' + csminxname + ' -csminy ' + csminyname + ' -csmaxx ' + csmaxxname + ' -csmaxy ' + csmaxyname + ' -ssm ' + ssmname + ' -urlflag 1 | tee testGeogrid.txt'

        runCmd(cmd)

        print("Geogrid Done!")
        print (time.strftime("%H:%M:%S"))

        cmd = 'testautoRIFT.py -m ' + inps.reference + ' -s ' + inps.secondary + ' -g window_location.tif -o window_offset.tif -vx window_rdr_off2vel_x_vec.tif -vy window_rdr_off2vel_y_vec.tif -sr window_search_range.tif -csmin window_chip_size_min.tif -csmax window_chip_size_max.tif -ssm window_stable_surface_mask.tif -nc {0} -fo 1 -urlflag 1 | tee testautoRIFT.txt'.format(sensor)

        runCmd(cmd)
        
        print("autoRIFT Done!")
        print (time.strftime("%H:%M:%S"))
        


        print("Single pair of ###" + foldername + "### Done !!!")

        print(time.strftime("%H:%M:%S"))
        
        print("\n")

        os.chdir('..')

        

