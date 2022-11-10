import pytest
from hyp3lib import DemError

from hyp3_autorift import geometry, io
from hyp3_autorift.process import DEFAULT_PARAMETER_FILE


def test_find_jpl_parameter_info():
    lat_limits = (55, 56)
    lon_limits = (40, 41)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = io.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'NPS'

    lat_limits = (54, 55)
    lon_limits = (40, 41)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = io.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'N37'

    lat_limits = (54, 55)
    lon_limits = (-40, -41)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = io.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'N24'

    lat_limits = (-54, -55)
    lon_limits = (-40, -41)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = io.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'S24'

    lat_limits = (-55, -56)
    lon_limits = (40, 41)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = io.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'S37'

    lat_limits = (-56, -57)
    lon_limits = (40, 41)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = io.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'SPS'

    lat_limits = (-90, -91)
    lon_limits = (40, 41)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    with pytest.raises(DemError):
        io.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)

    lat_limits = (90, 91)
    lon_limits = (40, 41)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    with pytest.raises(DemError):
        io.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)


def test_find_jpl_parameter_info_antimeridian():
    lat_limits = (54, 55)
    lon_limits = (180, 181)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = io.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'N01'

    lat_limits = (54, 55)
    lon_limits = (-180, -181)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = io.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'N60'

    lat_limits = (55, 56)
    lon_limits = (180, 181)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = io.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'NPS'

    lat_limits = (55, 56)
    lon_limits = (-180, -181)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = io.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'NPS'

    lat_limits = (-56, -55)
    lon_limits = (180, 181)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = io.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'S01'

    lat_limits = (-56, -55)
    lon_limits = (-180, -181)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = io.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'S60'

    lat_limits = (-57, -56)
    lon_limits = (180, 181)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = io.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'SPS'

    lat_limits = (-57, -56)
    lon_limits = (-180, -181)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = io.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'SPS'
