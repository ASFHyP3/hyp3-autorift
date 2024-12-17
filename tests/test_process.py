import io
from datetime import datetime
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock, patch

import botocore.exceptions
import pytest
import requests
import responses

from hyp3_autorift import process


def test_get_platform():
    assert process.get_platform('S1B_IW_GRDH_1SSH_20201203T095903_20201203T095928_024536_02EAB3_6D81') == 'S1'
    assert process.get_platform('S1A_IW_SLC__1SDV_20180605T233148_20180605T233215_022228_0267AD_48B2') == 'S1'
    assert process.get_platform('S2A_1UCR_20210124_0_L1C') == 'S2'
    assert process.get_platform('S2B_22WEB_20200913_0_L2A') == 'S2'
    assert process.get_platform('S2A_11UNA_20201203_0_L2A') == 'S2'
    assert process.get_platform('S2B_60CWT_20220130_0_L1C') == 'S2'
    assert process.get_platform('S2B_MSIL2A_20200913T151809_N0214_R068_T22WEB_20200913T180530') == 'S2'
    assert process.get_platform('S2A_MSIL2A_20201203T190751_N0214_R013_T11UNA_20201203T195322') == 'S2'
    assert process.get_platform('LM04_L1GS_025009_19830519_20200903_02_T2') == 'L4'
    assert process.get_platform('LT05_L1TP_091090_20060929_20200831_02_T1') == 'L5'
    assert process.get_platform('LE07_L2SP_233095_20200102_20200822_02_T2') == 'L7'
    assert process.get_platform('LC08_L1TP_009011_20200703_20200913_02_T1') == 'L8'
    assert process.get_platform('LC09_L1GT_024115_20220320_20220322_02_T2') == 'L9'

    with pytest.raises(NotImplementedError):
        process.get_platform('S3B_IW_GRDH_1SSH_20201203T095903_20201203T095928_024536_02EAB3_6D81')

    with pytest.raises(NotImplementedError):
        process.get_platform('LM02_L1GS_113057_19770914_20200907_02_T2')

    with pytest.raises(NotImplementedError):
        process.get_platform('foobar')


def test_get_lc2_stac_json_key():
    expected = (
        'collection02/level-1/standard/oli-tirs/2021/122/028/LC09_L1GT_122028_20211107_20220119_02_T2/'
        'LC09_L1GT_122028_20211107_20220119_02_T2_stac.json'
    )
    assert process.get_lc2_stac_json_key('LC09_L1GT_122028_20211107_20220119_02_T2') == expected

    expected = (
        'collection02/level-1/standard/oli-tirs/2022/060/002/LO09_L1TP_060002_20220316_20220316_02_T1/'
        'LO09_L1TP_060002_20220316_20220316_02_T1_stac.json'
    )
    assert process.get_lc2_stac_json_key('LO09_L1TP_060002_20220316_20220316_02_T1') == expected

    expected = (
        'collection02/level-1/standard/oli-tirs/2022/137/206/LT09_L1GT_137206_20220107_20220123_02_T2/'
        'LT09_L1GT_137206_20220107_20220123_02_T2_stac.json'
    )
    assert process.get_lc2_stac_json_key('LT09_L1GT_137206_20220107_20220123_02_T2') == expected

    expected = (
        'collection02/level-1/standard/oli-tirs/2016/138/039/LC08_L1TP_138039_20161105_20200905_02_T1/'
        'LC08_L1TP_138039_20161105_20200905_02_T1_stac.json'
    )
    assert process.get_lc2_stac_json_key('LC08_L1TP_138039_20161105_20200905_02_T1') == expected

    expected = (
        'collection02/level-1/standard/oli-tirs/2019/157/021/LO08_L1GT_157021_20191221_20200924_02_T2/'
        'LO08_L1GT_157021_20191221_20200924_02_T2_stac.json'
    )
    assert process.get_lc2_stac_json_key('LO08_L1GT_157021_20191221_20200924_02_T2') == expected

    expected = (
        'collection02/level-1/standard/oli-tirs/2015/138/206/LT08_L1GT_138206_20150628_20200925_02_T2/'
        'LT08_L1GT_138206_20150628_20200925_02_T2_stac.json'
    )
    assert process.get_lc2_stac_json_key('LT08_L1GT_138206_20150628_20200925_02_T2') == expected

    expected = (
        'collection02/level-1/standard/etm/2006/024/035/LE07_L1TP_024035_20061119_20200913_02_T1/'
        'LE07_L1TP_024035_20061119_20200913_02_T1_stac.json'
    )
    assert process.get_lc2_stac_json_key('LE07_L1TP_024035_20061119_20200913_02_T1') == expected

    expected = (
        'collection02/level-1/standard/tm/1995/124/064/LT05_L1TP_124064_19950211_20200912_02_T1/'
        'LT05_L1TP_124064_19950211_20200912_02_T1_stac.json'
    )
    assert process.get_lc2_stac_json_key('LT05_L1TP_124064_19950211_20200912_02_T1') == expected

    expected = (
        'collection02/level-1/standard/mss/1995/098/068/LM05_L1GS_098068_19950831_20200823_02_T2/'
        'LM05_L1GS_098068_19950831_20200823_02_T2_stac.json'
    )
    assert process.get_lc2_stac_json_key('LM05_L1GS_098068_19950831_20200823_02_T2') == expected

    expected = (
        'collection02/level-1/standard/tm/1988/183/062/LT04_L1TP_183062_19880706_20200917_02_T1/'
        'LT04_L1TP_183062_19880706_20200917_02_T1_stac.json'
    )
    assert process.get_lc2_stac_json_key('LT04_L1TP_183062_19880706_20200917_02_T1') == expected

    expected = (
        'collection02/level-1/standard/mss/1983/117/071/LM04_L1GS_117071_19830609_20200903_02_T2/'
        'LM04_L1GS_117071_19830609_20200903_02_T2_stac.json'
    )
    assert process.get_lc2_stac_json_key('LM04_L1GS_117071_19830609_20200903_02_T2') == expected


@responses.activate
def test_get_lc2_metadata():
    responses.add(
        responses.GET,
        f'{process.LC2_SEARCH_URL}/LC08_L1TP_009011_20200703_20200913_02_T1',
        body='{"foo": "bar"}',
        status=200,
    )

    assert process.get_lc2_metadata('LC08_L1TP_009011_20200703_20200913_02_T1') == {'foo': 'bar'}


@responses.activate
def test_get_lc2_metadata_fallback(s3_stubber):
    responses.add(responses.GET, f'{process.LC2_SEARCH_URL}/LC08_L1TP_009011_20200703_20200913_02_T1', status=404)
    params = {
        'Bucket': process.LANDSAT_BUCKET,
        'Key': 'foo.json',
        'RequestPayer': 'requester',
    }
    s3_response = {'Body': io.StringIO('{"foo": "bar"}')}
    s3_stubber.add_response(method='get_object', expected_params=params, service_response=s3_response)

    with mock.patch('hyp3_autorift.process.get_lc2_stac_json_key', return_value='foo.json'):
        assert process.get_lc2_metadata('LC08_L1TP_009011_20200703_20200913_02_T1') == {'foo': 'bar'}


def test_get_lc2_path():
    metadata = {'id': 'L--5', 'assets': {'B2.TIF': {'href': 'foo'}}}
    assert process.get_lc2_path(metadata) == 'foo'

    metadata = {'id': 'L--5', 'assets': {'green': {'href': 'foo'}}}
    assert process.get_lc2_path(metadata) == 'foo'

    metadata = {'id': 'L--8', 'assets': {'B8.TIF': {'href': 'foo'}}}
    assert process.get_lc2_path(metadata) == 'foo'

    metadata = {'id': 'L--8', 'assets': {'pan': {'href': 'foo'}}}
    assert process.get_lc2_path(metadata) == 'foo'


@responses.activate
@patch('hyp3_autorift.process.get_raster_bbox')
@patch('hyp3_autorift.process.get_s2_path')
def test_get_s2_metadata(mock_get_s2_path: MagicMock, mock_get_raster_bbox: MagicMock):
    mock_get_s2_path.return_value = 's2 path'
    mock_get_raster_bbox.return_value = [0, 0, 1, 1]

    expected = {
        'path': 's2 path',
        'bbox': [0, 0, 1, 1],
        'id': 'S2A_MSIL1C_20160616T112217_N0204_R137_T29QKF_20160617T193500',
        'properties': {
            'datetime': '2016-06-16T11:22:17Z',
        },
    }
    assert process.get_s2_metadata('S2A_MSIL1C_20160616T112217_N0204_R137_T29QKF_20160617T193500') == expected

    mock_get_s2_path.assert_called_once_with('S2A_MSIL1C_20160616T112217_N0204_R137_T29QKF_20160617T193500')
    mock_get_raster_bbox.assert_called_once_with('s2 path')


def test_get_s2_safe_url():
    expected = (
        'https://storage.googleapis.com/gcp-public-data-sentinel-2/tiles/29/Q/KF/'
        'S2A_MSIL1C_20160616T112217_N0204_R137_T29QKF_20160617T193500.SAFE'
    )
    assert process.get_s2_safe_url('S2A_MSIL1C_20160616T112217_N0204_R137_T29QKF_20160617T193500') == expected

    expected = (
        'https://storage.googleapis.com/gcp-public-data-sentinel-2/tiles/38/E/MQ/'
        'S2B_MSIL1C_20200419T060719_N0209_R105_T38EMQ_20200419T091056.SAFE'
    )
    assert process.get_s2_safe_url('S2B_MSIL1C_20200419T060719_N0209_R105_T38EMQ_20200419T091056') == expected


@responses.activate
def test_get_s2_manifest():
    url = (
        'https://storage.googleapis.com/gcp-public-data-sentinel-2/tiles/29/Q/KF/'
        'S2A_MSIL1C_20160616T112217_N0204_R137_T29QKF_20160617T193500.SAFE/manifest.safe'
    )
    responses.add(responses.GET, url, body='foo', status=200)

    assert process.get_s2_manifest('S2A_MSIL1C_20160616T112217_N0204_R137_T29QKF_20160617T193500') == 'foo'


@patch('hyp3_autorift.process.s3_object_is_accessible')
def test_get_s2_path_aws(mock_s3_object_is_accessible: MagicMock):
    mock_s3_object_is_accessible.return_value = True
    assert process.get_s2_path('foo') == '/vsis3/its-live-project/s2-cache/foo_B08.jp2'

    mock_s3_object_is_accessible.assert_called_once_with('its-live-project', 's2-cache/foo_B08.jp2')


@patch('hyp3_autorift.process.s3_object_is_accessible')
@patch('hyp3_autorift.process.get_s2_manifest')
def test_get_s2_path_google_old_manifest(
    mock_get_s2_manifest: MagicMock,
    mock_s3_object_is_accessible: MagicMock,
    test_data_directory: Path,
):
    manifest = test_data_directory / 'S2A_MSIL1C_20160616T112217_N0204_R137_T29QKF_20160617T193500.manifest.safe'
    mock_get_s2_manifest.return_value = manifest.read_text()
    mock_s3_object_is_accessible.return_value = False

    path = process.get_s2_path('S2A_MSIL1C_20160616T112217_N0204_R137_T29QKF_20160617T193500')
    assert (
        path == '/vsicurl/https://storage.googleapis.com/gcp-public-data-sentinel-2/tiles/29/Q/KF/'
        'S2A_MSIL1C_20160616T112217_N0204_R137_T29QKF_20160617T193500.SAFE/./GRANULE'
        '/S2A_OPER_MSI_L1C_TL_SGS__20160616T181414_A005139_T29QKF_N02.04/IMG_DATA'
        '/S2A_OPER_MSI_L1C_TL_SGS__20160616T181414_A005139_T29QKF_B08.jp2'
    )

    mock_get_s2_manifest.assert_called_once_with('S2A_MSIL1C_20160616T112217_N0204_R137_T29QKF_20160617T193500')
    mock_s3_object_is_accessible.assert_called_once_with(
        'its-live-project',
        's2-cache/S2A_MSIL1C_20160616T112217_N0204_R137_T29QKF_20160617T193500_B08.jp2',
    )


@patch('hyp3_autorift.process.s3_object_is_accessible')
@patch('hyp3_autorift.process.get_s2_manifest')
def test_get_s2_path_google_new_manifest(
    mock_get_s2_manifest: MagicMock,
    mock_s3_object_is_accessible: MagicMock,
    test_data_directory,
):
    manifest = test_data_directory / 'S2B_MSIL1C_20200419T060719_N0209_R105_T38EMQ_20200419T091056.manifest.safe'
    mock_get_s2_manifest.return_value = manifest.read_text()
    mock_s3_object_is_accessible.return_value = False

    path = process.get_s2_path('S2B_MSIL1C_20200419T060719_N0209_R105_T38EMQ_20200419T091056')
    assert (
        path == '/vsicurl/https://storage.googleapis.com/gcp-public-data-sentinel-2/tiles/38/E/MQ/'
        'S2B_MSIL1C_20200419T060719_N0209_R105_T38EMQ_20200419T091056.SAFE/./GRANULE'
        '/L1C_T38EMQ_A016290_20200419T060719/IMG_DATA/T38EMQ_20200419T060719_B08.jp2'
    )

    mock_get_s2_manifest.assert_called_once_with('S2B_MSIL1C_20200419T060719_N0209_R105_T38EMQ_20200419T091056')
    mock_s3_object_is_accessible.assert_called_once_with(
        'its-live-project',
        's2-cache/S2B_MSIL1C_20200419T060719_N0209_R105_T38EMQ_20200419T091056_B08.jp2',
    )


@responses.activate
@patch('hyp3_autorift.process.s3_object_is_accessible')
def test_get_s2_path_not_found(mock_s3_object_is_accessible: MagicMock):
    mock_s3_object_is_accessible.return_value = False

    url = 'https://storage.googleapis.com/gcp-public-data-sentinel-2/tiles////foo.SAFE/manifest.safe'
    responses.add(responses.GET, url, status=404)

    with pytest.raises(requests.exceptions.HTTPError) as http_error:
        process.get_s2_path('foo')
    assert http_error.value.response.status_code == 404


def test_get_raster_bbox(test_data_directory):
    bbox = process.get_raster_bbox(str(test_data_directory / 'T60CWU_20160414T200612_B08.jp2'))
    assert bbox == [-183.0008956, -78.4606571, -178.0958227, -77.438842]
    bbox = process.get_raster_bbox(str(test_data_directory / 'T55XEE_20200911T034541_B08.jp2'))
    assert bbox == [146.999228, 75.5641782, 151.2301741, 76.5810287]


def test_s3_object_is_accessible(s3_stubber):
    bucket = 'MyBucket'
    key = 'MyKey'

    params = {'Bucket': bucket, 'Key': key}

    s3_stubber.add_response(method='head_object', expected_params=params, service_response={})
    assert process.s3_object_is_accessible(bucket, key)

    s3_stubber.add_client_error(
        method='head_object', expected_params=params, service_error_code='404', http_status_code=404
    )
    assert not process.s3_object_is_accessible(bucket, key)

    s3_stubber.add_client_error(
        method='head_object', expected_params=params, service_error_code='403', http_status_code=403
    )
    assert not process.s3_object_is_accessible(bucket, key)

    s3_stubber.add_client_error(
        method='head_object', expected_params=params, service_error_code='500', http_status_code=500
    )
    with pytest.raises(botocore.exceptions.ClientError):
        process.s3_object_is_accessible(bucket, key)


def test_parse_s3_url():
    assert process.parse_s3_url('s3://sentinel-s2-l1c/foo/bar.jp2') == ('sentinel-s2-l1c', 'foo/bar.jp2')
    assert process.parse_s3_url('s3://s2-l1c-us-west/hello.jp2') == ('s2-l1c-us-west', 'hello.jp2')


def test_get_datetime():
    granule = 'S1B_IW_GRDH_1SSH_20201203T095903_20201203T095928_024536_02EAB3_6D81'
    assert process.get_datetime(granule) == datetime(year=2020, month=12, day=3, hour=9, minute=59, second=3)

    granule = 'S1A_IW_SLC__1SDV_20180605T233148_20180605T233215_022228_0267AD_48B2'
    assert process.get_datetime(granule) == datetime(year=2018, month=6, day=5, hour=23, minute=31, second=48)

    granule = 'S2A_1UCR_20210124_0_L1C'
    assert process.get_datetime(granule) == datetime(year=2021, month=1, day=24)

    granule = 'S2B_22WEB_20200913_0_L2A'
    assert process.get_datetime(granule) == datetime(year=2020, month=9, day=13)

    granule = 'S2B_22XEQ_20190610_11_L1C'
    assert process.get_datetime(granule) == datetime(year=2019, month=6, day=10)

    granule = 'S2A_11UNA_20201203_0_L2A'
    assert process.get_datetime(granule) == datetime(year=2020, month=12, day=3)

    granule = 'S2B_MSIL2A_20200913T151809_N0214_R068_T22WEB_20200913T180530'
    assert process.get_datetime(granule) == datetime(year=2020, month=9, day=13, hour=15, minute=18, second=9)

    granule = 'S2A_MSIL2A_20201203T190751_N0214_R013_T11UNA_20201203T195322'
    assert process.get_datetime(granule) == datetime(year=2020, month=12, day=3, hour=19, minute=7, second=51)

    granule = 'LM04_L1GS_025009_19830519_20200903_02_T2'
    assert process.get_datetime(granule) == datetime(year=1983, month=5, day=19)

    granule = 'LT05_L1TP_091090_20060929_20200831_02_T1'
    assert process.get_datetime(granule) == datetime(year=2006, month=9, day=29)

    granule = 'LE07_L2SP_233095_20200102_20200822_02_T2'
    assert process.get_datetime(granule) == datetime(year=2020, month=1, day=2)

    granule = 'LC08_L1TP_009011_20200703_20200913_02_T1'
    assert process.get_datetime(granule) == datetime(year=2020, month=7, day=3)

    with pytest.raises(ValueError):
        process.get_datetime('AB_adsflafjladsf')

    with pytest.raises(ValueError):
        process.get_datetime('S3_adsflafjladsf')


def test_apply_landsat_filtering(monkeypatch):
    def mock_apply_filter_function(scene, _):
        if process.get_platform(scene) < 'L7':
            return scene, None
        return scene, 'zero_mask'

    monkeypatch.setattr(process, '_apply_filter_function', mock_apply_filter_function)

    with pytest.raises(NotImplementedError):
        process.apply_landsat_filtering('LC09', 'LC09')
    with pytest.raises(NotImplementedError):
        process.apply_landsat_filtering('LC09', 'LC08')
    with pytest.raises(NotImplementedError):
        process.apply_landsat_filtering('LC09', 'LE07')
    with pytest.raises(NotImplementedError):
        process.apply_landsat_filtering('LC09', 'LT05')
    with pytest.raises(NotImplementedError):
        process.apply_landsat_filtering('LC09', 'LT04')

    with pytest.raises(NotImplementedError):
        process.apply_landsat_filtering('LC08', 'LC09')
    with pytest.raises(NotImplementedError):
        process.apply_landsat_filtering('LC08', 'LC08')
    assert process.apply_landsat_filtering('LC08', 'LE07') == ('LC08', 'zero_mask', 'LE07', 'zero_mask')
    with pytest.raises(NotImplementedError):
        process.apply_landsat_filtering('LC08', 'LT05')
    with pytest.raises(NotImplementedError):
        process.apply_landsat_filtering('LC08', 'LT04')

    with pytest.raises(NotImplementedError):
        process.apply_landsat_filtering('LE07', 'LC09')
    assert process.apply_landsat_filtering('LE07', 'LC08') == ('LE07', 'zero_mask', 'LC08', 'zero_mask')
    assert process.apply_landsat_filtering('LE07', 'LE07') == ('LE07', 'zero_mask', 'LE07', 'zero_mask')
    with pytest.raises(NotImplementedError):
        process.apply_landsat_filtering('LE07', 'LT05')
    with pytest.raises(NotImplementedError):
        process.apply_landsat_filtering('LE07', 'LT04')

    with pytest.raises(NotImplementedError):
        process.apply_landsat_filtering('LT05', 'LC09')
    with pytest.raises(NotImplementedError):
        process.apply_landsat_filtering('LT05', 'LC08')
    with pytest.raises(NotImplementedError):
        process.apply_landsat_filtering('LT05', 'LE07')
    assert process.apply_landsat_filtering('LT05', 'LT05') == ('LT05', None, 'LT05', None)
    assert process.apply_landsat_filtering('LT05', 'LT04') == ('LT05', None, 'LT04', None)

    with pytest.raises(NotImplementedError):
        process.apply_landsat_filtering('LT04', 'LC09')
    with pytest.raises(NotImplementedError):
        process.apply_landsat_filtering('LT04', 'LC08')
    with pytest.raises(NotImplementedError):
        process.apply_landsat_filtering('LT04', 'LE07')
    assert process.apply_landsat_filtering('LT04', 'LT05') == ('LT04', None, 'LT05', None)
    assert process.apply_landsat_filtering('LT04', 'LT04') == ('LT04', None, 'LT04', None)


def test_point_to_prefix():
    assert process.point_to_region(63.0, 128.0) == 'N60E120'
    assert process.point_to_region(-63.0, 128.0) == 'S60E120'
    assert process.point_to_region(63.0, -128.0) == 'N60W120'
    assert process.point_to_region(-63.0, -128.0) == 'S60W120'
    assert process.point_to_region(0.0, 128.0) == 'N00E120'
    assert process.point_to_region(0.0, -128.0) == 'N00W120'
    assert process.point_to_region(63.0, 0.0) == 'N60E000'
    assert process.point_to_region(-63.0, 0.0) == 'S60E000'
    assert process.point_to_region(0.0, 0.0) == 'N00E000'


def test_get_lat_lon_from_ncfile():
    file = Path(
        'tests/data/'
        'LT05_L1GS_219121_19841206_20200918_02_T2_X_LT05_L1GS_226120_19850124_20200918_02_T2_G0120V02_P000.nc'
    )
    assert process.get_lat_lon_from_ncfile(file) == (-81.49, -128.28)


def test_get_opendata_prefix():
    file = Path(
        'tests/data/'
        'LT05_L1GS_219121_19841206_20200918_02_T2_X_LT05_L1GS_226120_19850124_20200918_02_T2_G0120V02_P000.nc'
    )
    assert process.get_opendata_prefix(file) == 'velocity_image_pair/landsatOLI/v02/S80W120'
