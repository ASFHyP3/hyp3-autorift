"""Geometry routines for working Geogrid"""

import logging
import os
from typing import Tuple
import numpy as np

from osgeo import gdal
from osgeo import ogr
from osgeo import osr

log = logging.getLogger(__name__)


def polygon_from_bbox(x_limits: Tuple[float, float], y_limits: Tuple[float, float],
                      epsg_code: int = 4326) -> ogr.Geometry:
    ring = ogr.Geometry(ogr.wkbLinearRing)
    ring.AddPoint_2D(x_limits[0], y_limits[1])
    ring.AddPoint_2D(x_limits[1], y_limits[1])
    ring.AddPoint_2D(x_limits[1], y_limits[0])
    ring.AddPoint_2D(x_limits[0], y_limits[0])
    ring.AddPoint_2D(x_limits[0], y_limits[1])
    polygon = ogr.Geometry(ogr.wkbPolygon)
    polygon.AddGeometry(ring)

    srs = osr.SpatialReference()
    srs.ImportFromEPSG(epsg_code)
    polygon.AssignSpatialReference(srs)

    return polygon


def poly_bounds_in_proj(polygon: ogr.Geometry, out_epsg: int):
    in_srs = polygon.GetSpatialReference()
    if in_srs is None:
        log.warning('Polygon does not have an assigned spatial reference; assuming EPSG:4326.')
        in_srs = osr.SpatialReference()
        in_srs.ImportFromEPSG(4326)

    out_srs = osr.SpatialReference()
    out_srs.ImportFromEPSG(out_epsg)

    transformation = osr.CoordinateTransformation(in_srs, out_srs)
    out_poly = ogr.Geometry(wkb=polygon.ExportToWkb())
    out_poly.Transform(transformation)

    return out_poly.GetEnvelope()


def flip_point_coordinates(point: ogr.Geometry):
    if not point.GetGeometryName() == 'POINT':
        raise ValueError('Can only flip POINT geometries')

    flipped = ogr.Geometry(ogr.wkbPoint)
    flipped.AddPoint_2D(point.GetY(), point.GetX())

    return flipped


def fix_point_for_antimeridian(point: ogr.Geometry):
    if not point.GetGeometryName() == 'POINT':
        raise ValueError('Can only fix POINT geometries')

    def fix(n):
        return (n + 180) % 360 - 180

    fixed = ogr.Geometry(ogr.wkbPoint)
    fixed.AddPoint_2D(fix(point.GetX()), fix(point.GetY()))
    return fixed



