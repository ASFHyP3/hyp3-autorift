#!/usr/bin/env python3

from osgeo import gdal,osr
import argparse
import isce
import os
#import numpy as np


def cmdLineParse():
    '''
    Command line parser.
    '''

    parser = argparse.ArgumentParser(description='Generate Antarctic DEM for given bbox')
    parser.add_argument('-i', '--in', dest='infile', type=str, default=None,
                        help='Source DEM file')
    parser.add_argument('-b', '--bbox', dest='bbox', type=float, nargs=4,
                        required=True, help='Bounding box in SNWE format')
    parser.add_argument('-o', '--out', dest='outfile', type=str, default=None,
                        help='File to download to')
    parser.add_argument('-c', '--correct', dest='correct', type=str, default=None,
                        help='Correct the DEM to ellipsoid height')
    
    vals =  parser.parse_args()

    if vals.bbox[1] <= vals.bbox[0]:
        raise Exception('N < S for bbox')

    if vals.bbox[2] >= vals.bbox[3]:
        raise Exception('E < W for bbox')

    return vals


def getFilename(snwe):
    '''
    Get ISCE convention DEM filename.
    '''

    from contrib.demUtils import createDemStitcher
    
    ds = createDemStitcher()
    fname = ds.defaultName(snwe)
    return fname

def extractSubset(srcfile, bbox, outfile, correct=None):
    '''
    Extract DEM using GDAL.
    '''
    import isceobj

#    srcfile = os.path.join( '/vsizip', os.path.dirname(__file__), 'bedmap2.zip','bedmap2_surface.tif')
#    geoidfile = os.path.join( '/vsizip', os.path.dirname(__file__), 'bedmap2.zip', 'gl04c_geiod_to_WGS84.tif')
#    import pdb
#    pdb.set_trace()
#    srcfile = '../GRE240m/GRE240m_DEM.tif'
#    cmd = 'gdalwarp -of ENVI -ot Int16 -r cubic -tr 0.001 0.001 -t_srs "EPSG:4326" -dstnodata 0 -te {0} {1} {2} {3} {4} {5}'.format(
#                bbox[2], bbox[0], bbox[3], bbox[1], srcfile, outfile)
#    status = os.system(cmd)
#    if status:
#        raise Exception('{0} command failed'.format(cmd))

    inds = gdal.OpenShared(srcfile, gdal.GA_ReadOnly)
    warpOptions = gdal.WarpOptions(format='ENVI',
                                   outputType=gdal.GDT_Int16,
                                   resampleAlg='cubic',
                                   xRes=0.001, yRes=0.001,
                                   dstSRS='EPSG:4326',
                                   dstNodata=0,
                                   outputBounds=(bbox[2], bbox[0], bbox[3], bbox[1])
                                   )
    gdal.Warp(outfile, inds, options=warpOptions)
    


    inds = None


    if correct:
#        cmd = 'gdalwarp -of ENVI -ot Int16 -r cubic -tr 0.001 0.001 -t_srs "EPSG:4326" -dstnodata 0 -te {0} {1} {2} {3} {4} {5}'.format(
#                bbox[2], bbox[0], bbox[3], bbox[1], geoidfile, outfile+'.gl04c')
#
#        status = os.system(cmd)
#        if status:
#            raise Exception('{0} command failed'.format(cmd))

        inds = gdal.OpenShared(correct, gdal.GA_ReadOnly)
        warpOptions = gdal.WarpOptions(format='ENVI',
                                       outputType=gdal.GDT_Int16,
                                       resampleAlg='cubic',
                                       xRes=0.001, yRes=0.001,
                                       dstSRS='EPSG:4326',
                                       dstNodata=0,
                                       outputBounds=(bbox[2], bbox[0], bbox[3], bbox[1])
                                       )
        gdal.Warp(outfile+'.crt', inds, options=warpOptions)
        
        ds = gdal.Open(outfile, gdal.GA_Update)
        arr = ds.GetRasterBand(1).ReadAsArray()
        

        adj = gdal.Open(outfile + '.crt', gdal.GA_ReadOnly)
        off = adj.GetRasterBand(1).ReadAsArray()
        adj = None

        arr += off
        ds.GetRasterBand(1).WriteArray(arr)

        adj = None
        arr = None
        ds = None
        inds = None


    ds = gdal.Open(outfile, gdal.GA_ReadOnly)
    trans = ds.GetGeoTransform()

#    import pdb
#    pdb.set_trace()

    img = isceobj.createDemImage()
    img.width = ds.RasterXSize
    img.length = ds.RasterYSize
    img.bands = 1
    img.dataType = 'SHORT'
    img.scheme = 'BIL'
    img.setAccessMode('READ')
    img.filename = outfile

    img.firstLongitude = trans[0] + 0.5 * trans[1]
    img.deltaLongitude = trans[1]

    img.firstLatitude = trans[3] + 0.5 * trans[5]
    img.deltaLatitude = trans[5]
    img.renderHdr()





if __name__ == '__main__':
    '''
    Main driver.
    '''
    
    inps = cmdLineParse()

    ###Create output file name if not provided
    if inps.outfile is None:
        inps.outfile = getFilename(inps.bbox)

#    if inps.correct:
#        inps.outfile += '.wgs84'
    inps.outfile += '.wgs84'

    print('Output file: {0}'.format(inps.outfile))

    ###Extract using DEM
    extractSubset(inps.infile, inps.bbox, inps.outfile, inps.correct)

