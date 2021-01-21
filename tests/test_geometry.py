import numpy as np

from hyp3_autorift import geometry


def test_polygon_from_bbox():
    lat_limits = (1, 2)
    lon_limits = (3, 4)
    assert geometry.polygon_from_bbox(lat_limits, lon_limits).ExportToWkt() \
           == 'POLYGON ((3 1 0,4 1 0,4 2 0,3 2 0,3 1 0))'


def test_pol_bounds_in_proj():
    polygon = geometry.polygon_from_bbox(lat_limits=(55, 56), lon_limits=(40, 41))
    assert np.allclose(
        geometry.poly_bounds_in_proj(polygon, in_epsg=4326, out_epsg=3413),  # NPS
        (3776365.5697414433, 3899644.3388010086, -340706.3423259673, -264432.19003121805)
    )

    polygon = geometry.polygon_from_bbox(lat_limits=(-58, -57), lon_limits=(40, 41))
    assert np.allclose(
        geometry.poly_bounds_in_proj(polygon, in_epsg=4326, out_epsg=3031),  # SPS
        (2292512.6214329866, 2416952.768825992, 2691684.1770189586, 2822144.2827928355)
    )

    polygon = geometry.polygon_from_bbox(lat_limits=(22, 23), lon_limits=(40, 41))
    assert np.allclose(
        geometry.poly_bounds_in_proj(polygon, in_epsg=4326, out_epsg=32637),
        (602485.1663686256, 706472.0593133729, 2433164.428653589, 2544918.1043369616)
    )

    polygon = geometry.polygon_from_bbox(lat_limits=(-23, -22), lon_limits=(40, 41))
    assert np.allclose(
        geometry.poly_bounds_in_proj(polygon, in_epsg=4326, out_epsg=32737),
        (602485.1663686256, 706472.0593133729, 7455081.895663038, 7566835.5713464115)
    )
