"""Geometry routines for working Geogrid"""

import glob
import logging
import os

import isce  # noqa: F401
import isceobj
import numpy as np
from contrib.demUtils import createDemStitcher
from contrib.geo_autoRIFT.geogrid import Geogrid
from isceobj.Orbit.Orbit import Orbit
from isceobj.Sensor.TOPS.Sentinel1 import Sentinel1
from osgeo import gdal
from osgeo import osr

from hyp3_autorift.io import fetch_jpl_tifs

log = logging.getLogger(__name__)


class GeometryException(Exception):
    pass


def bounding_box(safe, priority='reference', polarization='hh', orbits='Orbits', aux='Orbits', epsg=4326):
    """Determine the geometric bounding box of a Sentinel-1 image

    :param safe: Path to the Sentinel-1 SAFE zip archive
    :param priority: Image priority, either 'reference' (default) or 'secondary'
    :param polarization: Image polarization (default: 'hh')
    :param orbits: Path to the orbital files (default: './Orbits')
    :param aux: Path to the auxiliary orbital files (default: './Orbits')
    :param epsg: Projection EPSG code (default: 4326)

    :return: lat_limits (list), lon_limits (list)
        lat_limits: list containing the [minimum, maximum] latitudes
        lat_limits: list containing the [minimum, maximum] longitudes
    """
    frames = []
    for swath in range(1, 4):
        rdr = Sentinel1()
        rdr.configure()
        rdr.safe = [os.path.abspath(safe)]
        rdr.output = priority
        rdr.orbitDir = os.path.abspath(orbits)
        rdr.auxDir = os.path.abspath(aux)
        rdr.swathNumber = swath
        rdr.polarization = polarization
        rdr.parse()
        frames.append(rdr.product)

    first_burst = frames[0].bursts[0]
    sensing_start = min([x.sensingStart for x in frames])
    sensing_stop = max([x.sensingStop for x in frames])
    starting_range = min([x.startingRange for x in frames])
    far_range = max([x.farRange for x in frames])
    range_pixel_size = first_burst.rangePixelSize
    prf = 1.0 / first_burst.azimuthTimeInterval

    orb = Orbit()
    orb.configure()

    for state_vector in first_burst.orbit:
        orb.addStateVector(state_vector)

    for frame in frames:
        for burst in frame.bursts:
            for state_vector in burst.orbit:
                if state_vector.time < orb.minTime or state_vector.time > orb.maxTime:
                    orb.addStateVector(state_vector)

    obj = Geogrid()
    obj.configure()

    obj.startingRange = starting_range
    obj.rangePixelSize = range_pixel_size
    obj.sensingStart = sensing_start
    obj.prf = prf
    obj.lookSide = -1
    obj.numberOfLines = int(np.round((sensing_stop - sensing_start).total_seconds() * prf))
    obj.numberOfSamples = int(np.round((far_range - starting_range)/range_pixel_size))
    obj.orbit = orb
    obj.epsg = epsg

    obj.determineBbox()

    if gdal.__version__[0] == '2':
        lat_limits = obj._ylim
        lon_limits = obj._xlim
    else:
        lat_limits = obj._xlim
        lon_limits = obj._ylim

    log.info(f'Latitude limits [min, max]: {lat_limits}')
    log.info(f'Longitude limits [min, max]: {lon_limits}')

    return lat_limits, lon_limits


def find_jpl_dem(lat_limits, lon_limits, z_limits=(-200, 4000), dem_dir='DEM', download=False):

    if download:
        fetch_jpl_tifs(dem_dir=dem_dir, match='_h.tif')

    dems = glob.glob(os.path.join(dem_dir, '*_h.tif'))

    bounding_dem = None
    for dem in dems:
        log.info(f'Checking DEM: {dem}')
        dem_ds = gdal.Open(dem, gdal.GA_ReadOnly)
        dem_sr = dem_ds.GetSpatialRef()
        log.debug(f'DEM projection: {dem_sr}')

        latlon = osr.SpatialReference()
        latlon.ImportFromEPSG(4326)

        trans = osr.CoordinateTransformation(latlon, dem_sr)

        # NOTE: This is probably unnecessary and just the lower-left and upper-right could be used,
        #       but this does cover the case of skewed bounding boxes
        all_xyz = []
        for lat in lat_limits:
            for lon in lon_limits:
                for zed in z_limits:
                    if gdal.__version__[0] == '2':
                        xyz = trans.TransformPoint(lon, lat, zed)
                    else:
                        xyz = trans.TransformPoint(lat, lon, zed)

                    all_xyz.append(xyz)

        x, y, _ = zip(*all_xyz)

        x_limits = (min(x), max(x))
        y_limits = (min(y), max(y))

        log.info(f'Image X limits: {x_limits}')
        log.info(f'Image Y limits: {y_limits}')

        dem_geo_trans = dem_ds.GetGeoTransform()
        dem_x_limits = (dem_geo_trans[0], dem_geo_trans[0] + dem_ds.RasterXSize * dem_geo_trans[1])
        dem_y_limits = (dem_geo_trans[3] + dem_ds.RasterYSize * dem_geo_trans[5], dem_geo_trans[3])

        log.info(f'DEM X limits: {dem_x_limits}')
        log.info(f'DEM Y limits: {dem_y_limits}')

        if x_limits[0] > dem_x_limits[0] and x_limits[1] < dem_x_limits[1] \
           and y_limits[0] > dem_y_limits[0] and y_limits[1] < dem_y_limits[1]:
            bounding_dem = os.path.abspath(dem)
            break

    if bounding_dem is None:
        raise GeometryException('Existing DEMs do not (fully) cover the image data')

    log.info(f'Bounding DEM is: {bounding_dem}')
    return bounding_dem


def prep_isce_dem(input_dem, lat_limits, lon_limits, isce_dem=None):

    if isce_dem is None:
        seamstress = createDemStitcher()
        isce_dem = seamstress.defaultName([*lat_limits, *lon_limits])

    isce_dem = os.path.abspath(isce_dem + '.wgs84')
    log.info(f'ISCE dem is: {isce_dem}')

    in_ds = gdal.OpenShared(input_dem, gdal.GA_ReadOnly)
    warp_options = gdal.WarpOptions(
        format='ENVI', outputType=gdal.GDT_Int16, resampleAlg='cubic',
        xRes=0.001, yRes=0.001, dstSRS='EPSG:4326', dstNodata=0,
        outputBounds=[lon_limits[0], lat_limits[0], lon_limits[1], lat_limits[1]]
    )
    gdal.Warp(isce_dem, in_ds, options=warp_options)

    del in_ds

    isce_ds = gdal.Open(isce_dem, gdal.GA_ReadOnly)
    isce_trans = isce_ds.GetGeoTransform()

    img = isceobj.createDemImage()
    img.width = isce_ds.RasterXSize
    img.length = isce_ds.RasterYSize
    img.bands = 1
    img.dataType = 'SHORT'
    img.scheme = 'BIL'
    img.setAccessMode('READ')
    img.filename = isce_dem

    img.firstLongitude = isce_trans[0] + 0.5 * isce_trans[1]
    img.deltaLongitude = isce_trans[1]

    img.firstLatitude = isce_trans[3] + 0.5 * isce_trans[5]
    img.deltaLatitude = isce_trans[5]
    img.renderHdr()

    return isce_dem
