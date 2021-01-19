import pytest
from hyp3lib import DemError

from hyp3_autorift import geometry


def test_polygon_from_bbox():
    lat_limits = (1, 2)
    lon_limits = (3, 4)
    assert geometry.polygon_from_bbox(lat_limits, lon_limits).ExportToWkt() \
           == 'POLYGON ((3 1 0,4 1 0,4 2 0,3 2 0,3 1 0))'


def test_find_jpl_dem():
    polygon = geometry.polygon_from_bbox(lat_limits=(55, 56), lon_limits=(40, 41))
    assert geometry.find_jpl_dem(polygon) == 'NPS_0240m'

    polygon = geometry.polygon_from_bbox(lat_limits=(54, 55), lon_limits=(40, 41))
    assert geometry.find_jpl_dem(polygon) == 'N37_0240m'

    polygon = geometry.polygon_from_bbox(lat_limits=(54, 55), lon_limits=(-40, -41))
    assert geometry.find_jpl_dem(polygon) == 'N24_0240m'

    polygon = geometry.polygon_from_bbox(lat_limits=(-54, -55), lon_limits=(-40, -41))
    assert geometry.find_jpl_dem(polygon) == 'S24_0240m'

    polygon = geometry.polygon_from_bbox(lat_limits=(-55, -56), lon_limits=(40, 41))
    assert geometry.find_jpl_dem(polygon) == 'S37_0240m'

    polygon = geometry.polygon_from_bbox(lat_limits=(-56, -57), lon_limits=(40, 41))
    assert geometry.find_jpl_dem(polygon) == 'SPS_0240m'

    polygon = geometry.polygon_from_bbox(lat_limits=(-90, -91), lon_limits=(40, 41))
    with pytest.raises(DemError):
        geometry.find_jpl_dem(polygon)

    polygon = geometry.polygon_from_bbox(lat_limits=(90, 91), lon_limits=(40, 41))
    with pytest.raises(DemError):
        geometry.find_jpl_dem(polygon)

    polygon = geometry.polygon_from_bbox(lat_limits=(55, 56), lon_limits=(180, 181))
    with pytest.raises(DemError):
        geometry.find_jpl_dem(polygon)

    polygon = geometry.polygon_from_bbox(lat_limits=(55, 56), lon_limits=(-180, -181))
    with pytest.raises(DemError):
        geometry.find_jpl_dem(polygon)
