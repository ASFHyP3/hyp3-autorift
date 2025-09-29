from datetime import datetime
from pathlib import Path

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
            utils.upload_file_to_s3_with_publish_access_keys(Path('file.zip'), 'myBucket')

    with monkeypatch.context() as m:
        m.setenv('PUBLISH_ACCESS_KEY_ID', 'publish_access_key_id')
        m.delenv('PUBLISH_SECRET_ACCESS_KEY', raising=False)
        msg = 'Please provide.*'
        with pytest.raises(ValueError, match=msg):
            utils.upload_file_to_s3_with_publish_access_keys(Path('file.zip'), 'myBucket')


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


def test_get_datetime():
    granule = 'S1B_IW_GRDH_1SSH_20201203T095903_20201203T095928_024536_02EAB3_6D81'
    assert utils.get_datetime(granule) == datetime(year=2020, month=12, day=3, hour=9, minute=59, second=3)

    granule = 'S1A_IW_SLC__1SDV_20180605T233148_20180605T233215_022228_0267AD_48B2'
    assert utils.get_datetime(granule) == datetime(year=2018, month=6, day=5, hour=23, minute=31, second=48)

    granule = 'S2A_1UCR_20210124_0_L1C'
    assert utils.get_datetime(granule) == datetime(year=2021, month=1, day=24)

    granule = 'S2B_22WEB_20200913_0_L2A'
    assert utils.get_datetime(granule) == datetime(year=2020, month=9, day=13)

    granule = 'S2B_22XEQ_20190610_11_L1C'
    assert utils.get_datetime(granule) == datetime(year=2019, month=6, day=10)

    granule = 'S2A_11UNA_20201203_0_L2A'
    assert utils.get_datetime(granule) == datetime(year=2020, month=12, day=3)

    granule = 'S2B_MSIL2A_20200913T151809_N0214_R068_T22WEB_20200913T180530'
    assert utils.get_datetime(granule) == datetime(year=2020, month=9, day=13, hour=15, minute=18, second=9)

    granule = 'S2A_MSIL2A_20201203T190751_N0214_R013_T11UNA_20201203T195322'
    assert utils.get_datetime(granule) == datetime(year=2020, month=12, day=3, hour=19, minute=7, second=51)

    granule = 'LM04_L1GS_025009_19830519_20200903_02_T2'
    assert utils.get_datetime(granule) == datetime(year=1983, month=5, day=19)

    granule = 'LT05_L1TP_091090_20060929_20200831_02_T1'
    assert utils.get_datetime(granule) == datetime(year=2006, month=9, day=29)

    granule = 'LE07_L2SP_233095_20200102_20200822_02_T2'
    assert utils.get_datetime(granule) == datetime(year=2020, month=1, day=2)

    granule = 'LC08_L1TP_009011_20200703_20200913_02_T1'
    assert utils.get_datetime(granule) == datetime(year=2020, month=7, day=3)

    with pytest.raises(ValueError):
        utils.get_datetime('AB_adsflafjladsf')

    with pytest.raises(ValueError):
        utils.get_datetime('S3_adsflafjladsf')


def test_get_platform():
    assert utils.get_platform('S1_191569_IW1_20170703T204652_HV_1093-BURST') == 'S1-BURST'
    assert utils.get_platform('S1A_IW_SLC__1SDV_20180605T233148_20180605T233215_022228_0267AD_48B2') == 'S1-SLC'
    assert utils.get_platform('S2A_1UCR_20210124_0_L1C') == 'S2'
    assert utils.get_platform('S2B_22WEB_20200913_0_L2A') == 'S2'
    assert utils.get_platform('S2A_11UNA_20201203_0_L2A') == 'S2'
    assert utils.get_platform('S2B_60CWT_20220130_0_L1C') == 'S2'
    assert utils.get_platform('S2B_MSIL2A_20200913T151809_N0214_R068_T22WEB_20200913T180530') == 'S2'
    assert utils.get_platform('S2A_MSIL2A_20201203T190751_N0214_R013_T11UNA_20201203T195322') == 'S2'
    assert utils.get_platform('LM04_L1GS_025009_19830519_20200903_02_T2') == 'L4'
    assert utils.get_platform('LT05_L1TP_091090_20060929_20200831_02_T1') == 'L5'
    assert utils.get_platform('LE07_L2SP_233095_20200102_20200822_02_T2') == 'L7'
    assert utils.get_platform('LC08_L1TP_009011_20200703_20200913_02_T1') == 'L8'
    assert utils.get_platform('LC09_L1GT_024115_20220320_20220322_02_T2') == 'L9'

    with pytest.raises(NotImplementedError):
        utils.get_platform('S3B_IW_GRDH_1SSH_20201203T095903_20201203T095928_024536_02EAB3_6D81')

    with pytest.raises(NotImplementedError):
        utils.get_platform('LM02_L1GS_113057_19770914_20200907_02_T2')

    with pytest.raises(NotImplementedError):
        utils.get_platform('foobar')


def test_point_to_prefix():
    assert utils.point_to_region(63.0, 128.0) == 'N60E120'
    assert utils.point_to_region(-63.0, 128.0) == 'S60E120'
    assert utils.point_to_region(63.0, -128.0) == 'N60W120'
    assert utils.point_to_region(-63.0, -128.0) == 'S60W120'
    assert utils.point_to_region(0.0, 128.0) == 'N00E120'
    assert utils.point_to_region(0.0, -128.0) == 'N00W120'
    assert utils.point_to_region(63.0, 0.0) == 'N60E000'
    assert utils.point_to_region(-63.0, 0.0) == 'S60E000'
    assert utils.point_to_region(0.0, 0.0) == 'N00E000'


def test_get_lat_lon_from_ncfile():
    file = Path(
        'tests/data/'
        'LT05_L1GS_219121_19841206_20200918_02_T2_X_LT05_L1GS_226120_19850124_20200918_02_T2_G0120V02_P000.nc'
    )
    assert utils.get_lat_lon_from_ncfile(file) == (-81.49, -128.28)


def test_get_opendata_prefix():
    file = Path(
        'tests/data/'
        'LT05_L1GS_219121_19841206_20200918_02_T2_X_LT05_L1GS_226120_19850124_20200918_02_T2_G0120V02_P000.nc'
    )
    assert utils.get_opendata_prefix(file) == 'velocity_image_pair/landsatOLI/v02/S80W120'


@pytest.mark.parametrize(
    'argument_string,expected',
    [
        ('', None),
        ('None', None),
        ('none', 'none'),
        ('foobar', 'foobar'),
    ],
)
def test_nullable_string(argument_string, expected):
    assert utils.nullable_string(argument_string) == expected


@pytest.mark.parametrize(
    'granule_string,expected',
    [
        ('', []),
        ('None', []),
        ('None None', []),
        ('none', ['none']),
        ('foobar', ['foobar']),
        ('fizz buzz', ['fizz', 'buzz']),
        ('a b c d', ['a', 'b', 'c', 'd']),
    ],
)
def test_nullable_granule_list(granule_string, expected):
    assert utils.nullable_granule_list(granule_string) == expected
