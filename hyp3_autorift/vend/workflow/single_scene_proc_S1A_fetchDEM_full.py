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

    parser.add_argument('-m', '--reference', dest='reference', type=str, required=True, nargs='+',
                        help='Sentinel-1 safe zipped filename')
    parser.add_argument('-s', '--secondary', dest='secondary', type=str, required=True, nargs='+',
                        help='Sentinel-1 safe zipped filename')
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
        reference_name_list = ''
        secondary_name_list = ''
        for ii in range(inps.reference.__len__()):
            if reference_name_list is '':
                reference_name_list = reference_name_list + inps.reference[ii]
            else:
                reference_name_list = reference_name_list + "','" + inps.reference[ii]
        for ii in range(inps.secondary.__len__()):
            if secondary_name_list is '':
                secondary_name_list = secondary_name_list + inps.secondary[ii]
            else:
                secondary_name_list = secondary_name_list + "','" + inps.secondary[ii]

        cmd = 'mkdir ' + foldername
        runCmd(cmd)
        os.chdir(foldername)


        bbox_S = 100000.0
        bbox_N = -100000.0
        bbox_W = 100000.0
        bbox_E = -100000.0

        for ii in range(inps.reference.__len__()):
            cmd = 'bbox_dem_trunc.py -i ' + inps.reference[ii] + ' | tee bbox.txt'
            runCmd(cmd)
            bbox_S = min(float(str.split(runCmd('fgrep "Latitude limits" bbox.txt'))[2]),bbox_S)
            bbox_N = max(float(str.split(runCmd('fgrep "Latitude limits" bbox.txt'))[3]),bbox_N)
            bbox_W = min(float(str.split(runCmd('fgrep "Longitude limits" bbox.txt'))[2]),bbox_W)
            bbox_E = max(float(str.split(runCmd('fgrep "Longitude limits" bbox.txt'))[3]),bbox_E)

        print("bbox Done!")
        print (time.strftime("%H:%M:%S"))


        # START: fetch appropriate DEM from DEM archive
        DEM_Directory_Dict = ['/Volumes/shinyblue/CRYO/DEM/GRE240m_new','/Volumes/shinyblue/CRYO/DEM/ANT240m_new']

        flag = 0

        for dem_directory in DEM_Directory_Dict:

            cmd = 'find {0} -name "*h.tif"'.format(dem_directory)
            demname = subprocess.check_output(cmd, shell=True)
            demname = str(demname)[2:-3]

            cmd = 'gdalsrsinfo -o epsg {0}'.format(demname)
            epsgstr = subprocess.check_output(cmd, shell=True)
            epsgstr = re.findall("EPSG:(\d+)", str(epsgstr))[0]
            if not epsgstr:  #Empty string
                raise Exception('Could not auto-identify epsg code')
            epsgcode = int(epsgstr)

            lonlat = osr.SpatialReference()
            lonlat.ImportFromEPSG(4326)

            coord = osr.SpatialReference()
            coord.ImportFromEPSG(epsgcode)

            trans = osr.CoordinateTransformation(lonlat, coord)

            xyzs = []

            for lat in [bbox_N, bbox_S]:
                for lon in [bbox_W, bbox_E]:
                    for z in [-200,4000]:
                        if gdal.__version__[0] == '2':
                            x,y,z = trans.TransformPoint(lon, lat, z)
                        else:
                            x,y,z = trans.TransformPoint(lat, lon, z)
                        xyzs.append([x,y,z])

            xyzs = array(xyzs)

            xlim = [min(xyzs[:,0]), max(xyzs[:,0])]
            ylim = [min(xyzs[:,1]), max(xyzs[:,1])]

            demDS = gdal.Open(demname, gdal.GA_ReadOnly)
            geoTrans = demDS.GetGeoTransform()
            demXSize = demDS.RasterXSize
            demYSize = demDS.RasterYSize

            if ((xlim[0]>geoTrans[0])&(xlim[0]<(geoTrans[0]+(demXSize-1)*geoTrans[1]))&(ylim[1]<geoTrans[3])&(ylim[0]>(geoTrans[3]+(demYSize-1)*geoTrans[5]))):
                demDS = None
                flag = 1
                break

        if not flag:
            raise Exception("Existing DEM's in the database do not cover or at least do not fully cover the image data!")

        cmd = 'find {0} -name "*dhdx.tif"'.format(dem_directory)
        dhdxname = subprocess.check_output(cmd, shell=True)
        dhdxname = str(dhdxname)[2:-3]
        cmd = 'find {0} -name "*dhdy.tif"'.format(dem_directory)
        dhdyname = subprocess.check_output(cmd, shell=True)
        dhdyname = str(dhdyname)[2:-3]
        cmd = 'find {0} -name "*vx0.tif"'.format(dem_directory)
        vxname = subprocess.check_output(cmd, shell=True)
        vxname = str(vxname)[2:-3]
        cmd = 'find {0} -name "*vy0.tif"'.format(dem_directory)
        vyname = subprocess.check_output(cmd, shell=True)
        vyname = str(vyname)[2:-3]
        cmd = 'find {0} -name "*vxSearchRange.tif"'.format(dem_directory)
        srxname = subprocess.check_output(cmd, shell=True)
        srxname = str(srxname)[2:-3]
        cmd = 'find {0} -name "*vySearchRange.tif"'.format(dem_directory)
        sryname = subprocess.check_output(cmd, shell=True)
        sryname = str(sryname)[2:-3]
        cmd = 'find {0} -name "*xMaxChipSize.tif"'.format(dem_directory)
        csmaxxname = subprocess.check_output(cmd, shell=True)
        csmaxxname = str(csmaxxname)[2:-3]
        cmd = 'find {0} -name "*yMaxChipSize.tif"'.format(dem_directory)
        csmaxyname = subprocess.check_output(cmd, shell=True)
        csmaxyname = str(csmaxyname)[2:-3]
        cmd = 'find {0} -name "*xMinChipSize.tif"'.format(dem_directory)
        csminxname = subprocess.check_output(cmd, shell=True)
        csminxname = str(csminxname)[2:-3]
        cmd = 'find {0} -name "*yMinChipSize.tif"'.format(dem_directory)
        csminyname = subprocess.check_output(cmd, shell=True)
        csminyname = str(csminyname)[2:-3]
        cmd = 'find {0} -name "*StableSurface.tif"'.format(dem_directory)
        ssmname = subprocess.check_output(cmd, shell=True)
        ssmname = str(ssmname)[2:-3]
        # END: fetch appropriate DEM from DEM archive
#        pdb.set_trace()


        cmd = 'prepDEM.py -i ' + demname + ' -b ' + str(bbox_S) + ' ' + str(bbox_N) + ' ' + str(bbox_W) + ' ' + str(bbox_E) + ' | tee prepDEM.txt'

        runCmd(cmd)

        cmd = 'find `pwd` -name "dem*.dem.wgs84"'

        dempath = runCmd(cmd)

        print("DEM Done!")
        print (time.strftime("%H:%M:%S"))

        ##########################      topsApp.xml generation      ######################

#        cmd = 'format_tops_xml.py -m ' + inps.reference + ' -s ' + inps.secondary + ' -d ' + dempath + ' | tee topsxml.txt'

        cmd = 'format_tops_xml.py -m "' + reference_name_list + '" -s "' + secondary_name_list + '" -d ' + dempath + ' | tee topsxml.txt'
        runCmd(cmd)

        print("topsApp xml Done!")
        print (time.strftime("%H:%M:%S"))

        ##########################      ISCE topsApp run      ######################

        cmd = 'topsApp.py topsApp.xml --end=mergebursts | tee topsApp.txt'

        runCmd(cmd)

        #### Determine appropriate filenames
        mf = 'reference.slc.full'
        sf = 'secondary.slc.full'

        reference = os.path.join('./merged/', mf)
        secondary = os.path.join('./merged/', sf)

        #### For this module currently, we need to create an actual file on disk
        for infile in [reference,secondary]:
            if os.path.isfile(infile):
                continue
            cmd = 'gdal_translate -of ENVI {0}.vrt {0} | tee createImages.txt'.format(infile)
            status = os.system(cmd)
            if status:
                raise Exception('{0} could not be executed'.format(status))

#        #### test dense ampcor (needs to be commented out when doing the AWS run)
#        cmd = 'topsApp.py topsApp.xml --start=filter | tee topsApp.txt'
#
#        runCmd(cmd)

        print("topsApp Done!")
        print (time.strftime("%H:%M:%S"))

        ##########################      Geogrid and autoRIFT run      ######################

        cmd = 'testGeogrid_ISCE.py -m fine_coreg -s secondary -d '+ demname + ' -sx ' + dhdxname + ' -sy ' + dhdyname + ' -vx ' + vxname + ' -vy ' + vyname + ' -srx ' + srxname + ' -sry ' + sryname + ' -csminx ' + csminxname + ' -csminy ' + csminyname + ' -csmaxx ' + csmaxxname + ' -csmaxy ' + csmaxyname + ' -ssm ' + ssmname + ' | tee testGeogrid.txt'

        runCmd(cmd)

        print("Geogrid Done!")
        print (time.strftime("%H:%M:%S"))

        cmd = 'testautoRIFT_ISCE.py -m merged/reference.slc.full -s merged/secondary.slc.full -g window_location.tif -o window_offset.tif -vx window_rdr_off2vel_x_vec.tif -vy window_rdr_off2vel_y_vec.tif -sr window_search_range.tif -csmin window_chip_size_min.tif -csmax window_chip_size_max.tif -ssm window_stable_surface_mask.tif -nc S | tee testautoRIFT.txt'

        runCmd(cmd)

        print("autoRIFT Done!")
        print (time.strftime("%H:%M:%S"))



        print("Single pair of ###" + foldername + "### Done !!!")

        print(time.strftime("%H:%M:%S"))

        print("\n")

        os.chdir('../../../_test/workflow107')



