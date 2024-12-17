import numpy as np
from osgeo import ogr

from hyp3_autorift import geometry


def test_polygon_from_bbox():
    lat_limits = (1, 2)
    lon_limits = (3, 4)

    polygon = geometry.polygon_from_bbox(lat_limits, lon_limits)
    assert str(polygon) == 'POLYGON ((1 4,2 4,2 3,1 3,1 4))'
    srs = polygon.GetSpatialReference()
    assert srs.GetAttrValue('AUTHORITY', 0) == 'EPSG'
    assert srs.GetAttrValue('AUTHORITY', 1) == '4326'

    polygon = geometry.polygon_from_bbox(lat_limits, lon_limits, epsg_code=3413)
    assert str(polygon) == 'POLYGON ((1 4,2 4,2 3,1 3,1 4))'
    srs = polygon.GetSpatialReference()
    assert srs.GetAttrValue('AUTHORITY', 0) == 'EPSG'
    assert srs.GetAttrValue('AUTHORITY', 1) == '3413'


def test_pol_bounds_in_proj():
    lat_limits = (55, 56)
    lon_limits = (40, 41)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    assert np.allclose(
        geometry.poly_bounds_in_proj(polygon, out_epsg=3413),  # NPS
        (3776365.5697414433, 3899644.3388010086, -340706.3423259673, -264432.19003121805),
    )

    lat_limits = (-58, -57)
    lon_limits = (40, 41)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    assert np.allclose(
        geometry.poly_bounds_in_proj(polygon, out_epsg=3031),  # SPS
        (2292512.6214329866, 2416952.768825992, 2691684.1770189586, 2822144.2827928355),
    )

    lat_limits = (22, 23)
    lon_limits = (40, 41)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    assert np.allclose(
        geometry.poly_bounds_in_proj(polygon, out_epsg=32637),
        (602485.1663686256, 706472.0593133729, 2433164.428653589, 2544918.1043369616),
    )

    lat_limits = (-23, -22)
    lon_limits = (40, 41)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    assert np.allclose(
        geometry.poly_bounds_in_proj(polygon, out_epsg=32737),
        (602485.1663686256, 706472.0593133729, 7455081.895663038, 7566835.5713464115),
    )


def test_flip_point_coordinates():
    point = ogr.Geometry(ogr.wkbPoint)
    point.AddPoint_2D(0, 1)
    assert str(geometry.flip_point_coordinates(point)) == 'POINT (1 0)'

    point = ogr.Geometry(ogr.wkbPoint)
    point.AddPoint(2, 3, 4)
    assert str(geometry.flip_point_coordinates(point)) == 'POINT (3 2)'


def test_fix_point_for_antimeridian():
    point = ogr.Geometry(ogr.wkbPoint)
    point.AddPoint_2D(5, 10)
    assert str(geometry.fix_point_for_antimeridian(point)) == 'POINT (5 10)'

    point = ogr.Geometry(ogr.wkbPoint)
    point.AddPoint_2D(-100, -60)
    assert str(geometry.fix_point_for_antimeridian(point)) == 'POINT (-100 -60)'

    point = ogr.Geometry(ogr.wkbPoint)
    point.AddPoint(-180, 180)
    assert str(geometry.fix_point_for_antimeridian(point)) == 'POINT (-180 -180)'

    point = ogr.Geometry(ogr.wkbPoint)
    point.AddPoint(181, -181)
    assert str(geometry.fix_point_for_antimeridian(point)) == 'POINT (-179 179)'
