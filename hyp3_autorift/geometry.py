"""Geometry routines for working Geogrid"""

import logging
import os
from typing import Tuple

import isce  # noqa: F401
import isceobj
import numpy as np
from contrib.demUtils import createDemStitcher
from contrib.geo_autoRIFT.geogrid import Geogrid
from isceobj.Orbit.Orbit import Orbit
from isceobj.Sensor.TOPS.Sentinel1 import Sentinel1
from osgeo import gdal
from osgeo import ogr
from osgeo import osr

log = logging.getLogger(__name__)


def bounding_box(safe, priority='reference', polarization='hh', orbits='Orbits', epsg=4326):
    """Determine the geometric bounding box of a Sentinel-1 image

    :param safe: Path to the Sentinel-1 SAFE zip archive
    :param priority: Image priority, either 'reference' (default) or 'secondary'
    :param polarization: Image polarization (default: 'hh')
    :param orbits: Path to the orbital files (default: './Orbits')
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
        rdr.auxDir = os.path.abspath(orbits)
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

    lat_limits = obj._xlim
    lon_limits = obj._ylim

    log.info(f'Latitude limits [min, max]: {lat_limits}')
    log.info(f'Longitude limits [min, max]: {lon_limits}')

    return lat_limits, lon_limits


def polygon_from_bbox(lat_limits: Tuple[float, float], lon_limits: Tuple[float, float]) -> ogr.Geometry:
    ring = ogr.Geometry(ogr.wkbLinearRing)
    ring.AddPoint(lon_limits[0], lat_limits[0])
    ring.AddPoint(lon_limits[1], lat_limits[0])
    ring.AddPoint(lon_limits[1], lat_limits[1])
    ring.AddPoint(lon_limits[0], lat_limits[1])
    ring.AddPoint(lon_limits[0], lat_limits[0])
    polygon = ogr.Geometry(ogr.wkbPolygon)
    polygon.AddGeometry(ring)
    return polygon


def poly_bounds_in_proj(polygon: ogr.Geometry, in_epsg: int, out_epsg: int):
    in_srs = osr.SpatialReference()
    in_srs.ImportFromEPSG(in_epsg)

    out_srs = osr.SpatialReference()
    out_srs.ImportFromEPSG(out_epsg)

    transformation = osr.CoordinateTransformation(in_srs, out_srs)
    ring = ogr.Geometry(ogr.wkbLinearRing)
    for point in polygon.GetBoundary().GetPoints():
        try:
            lon, lat = point
        except ValueError:
            # buffered polygons only have (X, Y) while unbuffered have (X, Y, Z)
            lon, lat, _ = point
        ring.AddPoint(*transformation.TransformPoint(lat, lon))

    return ring.GetEnvelope()


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
