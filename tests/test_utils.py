import pytest
from hyp3lib import DemError

from hyp3_autorift import geometry, utils
from hyp3_autorift.process import DEFAULT_PARAMETER_FILE


def test_upload_file_to_s3_credentials_missing(tmp_path, monkeypatch):
    with monkeypatch.context() as m:
        m.delenv('PUBLISH_ACCESS_KEY_ID', raising=False)
        m.setenv('PUBLISH_SECRET_ACCESS_KEY', 'publish_access_key_secret')
        msg = 'Please provide.*'
        with pytest.raises(ValueError, match=msg):
            utils.upload_file_to_s3_with_publish_access_keys('file.zip', 'myBucket')

    with monkeypatch.context() as m:
        m.setenv('PUBLISH_ACCESS_KEY_ID', 'publish_access_key_id')
        m.delenv('PUBLISH_SECRET_ACCESS_KEY', raising=False)
        msg = 'Please provide.*'
        with pytest.raises(ValueError, match=msg):
            utils.upload_file_to_s3_with_publish_access_keys('file.zip', 'myBucket')


def test_find_jpl_parameter_info():
    lat_limits = (55, 56)
    lon_limits = (40, 41)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = utils.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'NPS'

    lat_limits = (54, 55)
    lon_limits = (40, 41)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = utils.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'N37'

    lat_limits = (54, 55)
    lon_limits = (-40, -41)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = utils.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'N24'

    lat_limits = (-54, -55)
    lon_limits = (-40, -41)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = utils.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'S24'

    lat_limits = (-55, -56)
    lon_limits = (40, 41)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = utils.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'S37'

    lat_limits = (-56, -57)
    lon_limits = (40, 41)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = utils.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'SPS'

    lat_limits = (-90, -91)
    lon_limits = (40, 41)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    with pytest.raises(DemError):
        utils.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)

    lat_limits = (90, 91)
    lon_limits = (40, 41)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    with pytest.raises(DemError):
        utils.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)


def test_find_jpl_parameter_info_antimeridian():
    lat_limits = (54, 55)
    lon_limits = (180, 181)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = utils.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'N01'

    lat_limits = (54, 55)
    lon_limits = (-180, -181)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = utils.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'N60'

    lat_limits = (55, 56)
    lon_limits = (180, 181)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = utils.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'NPS'

    lat_limits = (55, 56)
    lon_limits = (-180, -181)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = utils.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'NPS'

    lat_limits = (-56, -55)
    lon_limits = (180, 181)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = utils.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'S01'

    lat_limits = (-56, -55)
    lon_limits = (-180, -181)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = utils.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'S60'

    lat_limits = (-57, -56)
    lon_limits = (180, 181)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = utils.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'SPS'

    lat_limits = (-57, -56)
    lon_limits = (-180, -181)
    polygon = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = utils.find_jpl_parameter_info(polygon, DEFAULT_PARAMETER_FILE)
    assert parameter_info['name'] == 'SPS'
