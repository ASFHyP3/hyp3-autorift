#!/usr/bin/env python3

def cmdLineParse():
    '''
    Command line parser.
    '''
    import argparse

    parser = argparse.ArgumentParser(description='determine bbox for truncating DEM')
    parser.add_argument('-i', '--input', dest='indir', type=str, required=True,
            help='Sentinel-1 safe zipped filename')
    

    return parser.parse_args()

class Dummy(object):
    pass





def getMergedOrbit(product):
    import isce
    from isceobj.Orbit.Orbit import Orbit

    ###Create merged orbit
    orb = Orbit()
    orb.configure()

    burst = product[0].bursts[0]
    #Add first burst orbit to begin with
    for sv in burst.orbit:
        orb.addStateVector(sv)

#    import pdb
#    pdb.set_trace()


    for pp in product:
        ##Add all state vectors
        for bb in pp.bursts:
            for sv in bb.orbit:
                if (sv.time< orb.minTime) or (sv.time > orb.maxTime):
                    orb.addStateVector(sv)
    return orb




def loadParsedata(indir):
    '''
    Input file.
    '''
    import os
    import numpy as np
    import isce
    from isceobj.Sensor.TOPS.Sentinel1 import Sentinel1
    

    frames = []
    for swath in range(1,4):
        rdr=Sentinel1()
        rdr.configure()
#        rdr.safe=['./S1A_IW_SLC__1SDH_20180401T100057_20180401T100124_021272_024972_8CAF.zip']
        rdr.safe=[indir]
        rdr.output='master'
        rdr.orbitDir='/Users/yanglei/orbit/S1A/precise'
        rdr.auxDir='/Users/yanglei/orbit/S1A/aux'
        rdr.swathNumber=swath
        rdr.polarization='hh'
        rdr.parse()
        frames.append(rdr.product)
    
    info = Dummy()
    info.sensingStart = min([x.sensingStart for x in frames])
    info.sensingStop = max([x.sensingStop for x in frames])
    info.startingRange = min([x.startingRange for x in frames])
    info.farRange = max([x.farRange for x in frames])
    info.prf = 1.0 / frames[0].bursts[0].azimuthTimeInterval
    info.rangePixelSize = frames[0].bursts[0].rangePixelSize
    info.lookSide = -1
    info.numberOfLines = int( np.round( (info.sensingStop - info.sensingStart).total_seconds() * info.prf))
    info.numberOfSamples = int( np.round( (info.farRange - info.startingRange)/info.rangePixelSize))
    info.orbit = getMergedOrbit(frames)
    
    return info

def runGeogrid(info):
    '''
    Wire and run geogrid.
    '''

    import isce
    from components.contrib.geo_autoRIFT.geogrid import Geogrid
    from osgeo import gdal

    obj = Geogrid()
    obj.configure()

    obj.startingRange = info.startingRange
    obj.rangePixelSize = info.rangePixelSize
    obj.sensingStart = info.sensingStart
    obj.prf = info.prf
    obj.lookSide = info.lookSide
    obj.numberOfLines = info.numberOfLines
    obj.numberOfSamples = info.numberOfSamples
    obj.orbit = info.orbit
#    obj.demname = dem
    obj.epsg = 4326

#    obj.geogrid()
    obj.determineBbox()
    if gdal.__version__[0] == '2':
        print('Latitude limits: %f %f'%(obj._ylim[0],obj._ylim[1]))
        print('Longitude limits: %f %f'%(obj._xlim[0],obj._xlim[1]))
    else:
        print('Longitude limits: %f %f'%(obj._ylim[0],obj._ylim[1]))
        print('Latitude limits: %f %f'%(obj._xlim[0],obj._xlim[1]))


if __name__ == '__main__':
    '''
    Main driver.
    '''

    inps = cmdLineParse()

#    metadata = loadMetadata(inps.indir)
#
#    runGeogrid(metadata, inps.demfile)
    parsedata = loadParsedata(inps.indir)
#    import pdb
#    pdb.set_trace()
    runGeogrid(parsedata)
