from hyp3_autorift import geometry


def test_polygon_from_bbox():
    lat_limits = (1, 2)
    lon_limits = (3, 4)
    assert geometry.polygon_from_bbox(lat_limits, lon_limits).ExportToWkt() \
           == 'POLYGON ((3 1 0,4 1 0,4 2 0,3 2 0,3 1 0))'
