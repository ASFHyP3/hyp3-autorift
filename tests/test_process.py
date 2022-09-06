import io
from datetime import datetime
from re import match
from unittest import mock

import botocore.exceptions
import pytest
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
    expected = 'collection02/level-1/standard/oli-tirs/2019/041/001/LC08_L1TP_041001_20191005_20200825_02_T1/' \
               'LC08_L1TP_041001_20191005_20200825_02_T1_stac.json'
    assert process.get_lc2_stac_json_key('LC08_L1TP_041001_20191005_20200825_02_T1') == expected

    expected = 'collection02/level-1/standard/oli-tirs/2020/226/012/LO08_L1TP_226012_20201108_20201120_02_T2/' \
               'LO08_L1TP_226012_20201108_20201120_02_T2_stac.json'
    assert process.get_lc2_stac_json_key('LO08_L1TP_226012_20201108_20201120_02_T2') == expected


@responses.activate
def test_get_lc2_metadata():
    responses.add(
        responses.GET, f'{process.LC2_SEARCH_URL}/LC08_L1TP_009011_20200703_20200913_02_T1',
        body='{"foo": "bar"}', status=200,
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
    s3_response = {
        'Body': io.StringIO('{"foo": "bar"}')
    }
    s3_stubber.add_response(method='get_object', expected_params=params, service_response=s3_response)

    with mock.patch('hyp3_autorift.process.get_lc2_stac_json_key', return_value='foo.json'):
        assert process.get_lc2_metadata('LC08_L1TP_009011_20200703_20200913_02_T1') == {'foo': 'bar'}


def test_get_lc2_path():
    metadata = {'id': 'L--5',
                'assets':
                    {'B2.TIF': {'href': 'foo'}}}
    assert process.get_lc2_path(metadata) == 'foo'

    metadata = {'id': 'L--5',
                'assets': {'red': {'href': 'foo'}}}
    assert process.get_lc2_path(metadata) == 'foo'

    metadata = {'id': 'L--8',
                'assets': {'B8.TIF': {'href': 'foo'}}}
    assert process.get_lc2_path(metadata) == 'foo'

    metadata = {'id': 'L--8',
                'assets': {'pan': {'href': 'foo'}}}
    assert process.get_lc2_path(metadata) == 'foo'


@responses.activate
def test_get_s2_metadata_not_found():
    responses.add(responses.GET, f'{process.S2_SEARCH_URL}/foo', status=404)
    responses.add(
        responses.POST, process.S2_SEARCH_URL,
        body='{"numberReturned": 0}', status=200,
    )
    with pytest.raises(ValueError):
        process.get_s2_metadata('foo')


@responses.activate
def test_get_s2_metadata_cog_id():
    responses.add(
        responses.GET, f'{process.S2_SEARCH_URL}/2FS2B_22WEB_20200913_0_L2A',
        body='{"foo": "bar"}', status=200,
    )

    assert process.get_s2_metadata('2FS2B_22WEB_20200913_0_L2A') == {'foo': 'bar'}


@responses.activate
def test_get_s2_metadata_esa_id():
    responses.add(
        responses.GET, f'{process.S2_SEARCH_URL}/S2B_MSIL2A_20200913T151809_N0214_R068_T22WEB_20200913T180530',
        status=404,
    )
    responses.add(
        responses.POST, process.S2_SEARCH_URL,
        body='{"numberReturned": 1, "features": [{"foo": "bar"}]}', status=200,
    )

    assert process.get_s2_metadata('S2B_MSIL2A_20200913T151809_N0214_R068_T22WEB_20200913T180530') == {"foo": "bar"}


@responses.activate
def test_get_s2_metadata_json():
    responses.add(responses.GET, f'{process.S2_SEARCH_URL}/S2B_60CWT_20220130_0_L1C', status=404)

    responses.add(
        responses.POST, process.S2_SEARCH_URL,
        body='{"numberReturned": 0}', status=200,
    )

    s3_path = process.get_s2_metadata('S2B_60CWT_20220130_0_L1C')['assets']['B08']['href']
    assert s3_path == 's3://sentinel-s2-l1c/tiles/60/C/WT/2022/1/30/0/B08.jp2'


def test_s3_object_is_accessible(s3_stubber):
    bucket = 'MyBucket'
    key = 'MyKey'

    params = {
        'Bucket': bucket,
        'Key': key
    }

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


def test_get_s2_paths(monkeypatch):
    ref_s3_url = 's3://sentinel-s2-l1c/foo/bar.jp2'
    sec_s3_url = 's3://sentinel-s2-l1c/fiz/buz.jp2'

    with monkeypatch.context() as m:
        m.setattr(process, 's3_object_is_accessible', lambda **kwargs: True)
        paths = process.get_s2_paths(ref_s3_url, sec_s3_url)
        assert paths == ('/vsis3/s2-l1c-us-west-2/foo/bar.jp2', '/vsis3/s2-l1c-us-west-2/fiz/buz.jp2')

    with monkeypatch.context() as m:
        m.setattr(process, 's3_object_is_accessible', lambda **kwargs: False)
        paths = process.get_s2_paths(ref_s3_url, sec_s3_url)
        assert paths == ('/vsis3/sentinel-s2-l1c/foo/bar.jp2', '/vsis3/sentinel-s2-l1c/fiz/buz.jp2')

    with monkeypatch.context() as m:
        m.setattr(process, 's3_object_is_accessible', lambda **kwargs: kwargs['key'] == 'foo/bar.jp2')
        paths = process.get_s2_paths(ref_s3_url, sec_s3_url)
        assert paths == ('/vsis3/sentinel-s2-l1c/foo/bar.jp2', '/vsis3/sentinel-s2-l1c/fiz/buz.jp2')

    with monkeypatch.context() as m:
        m.setattr(process, 's3_object_is_accessible', lambda **kwargs: kwargs['key'] == 'fiz/buz.jp2')
        paths = process.get_s2_paths(ref_s3_url, sec_s3_url)
        assert paths == ('/vsis3/sentinel-s2-l1c/foo/bar.jp2', '/vsis3/sentinel-s2-l1c/fiz/buz.jp2')


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


def test_get_product_name():
    payload = {
        'reference_name': 'S1A_IW_SLC__1SSV_20160527T014319_20160527T014346_011438_011694_26B0',
        'secondary_name': 'S1A_IW_SLC__1SSV_20160714T014322_20160714T014349_012138_012CE7_96A0',
        'orbit_files': [
            'S1A_OPER_AUX_POEORB_OPOD_20160616T121500_V20160526T225943_20160528T005943.EOF',
            'S1A_OPER_AUX_POEORB_OPOD_20160616T121500_V20160526T225943_20160528T005943.EOF',
        ],
        'pixel_spacing': 240,
    }
    name = process.get_product_name(**payload)
    assert match(r'S1AA_20160527T014319_20160714T014322_VVP049_VEL240_A_[0-9A-F]{4}$', name)

    payload = {
        'reference_name': 'S1B_IW_SLC__1SDH_20200918T073646_20200918T073716_023426_02C7FC_6374',
        'secondary_name': 'S1A_IW_SLC__1SDH_20200906T073646_20200906T073716_023251_02C278_AE75',
        'orbit_files': [
            'S1B_OPER_AUX_RESORB_OPOD_20200907T115242_V20200906T042511_20200906T074241.EOF',
            'S1A_OPER_AUX_POEORB_OPOD_20160616T121500_V20160526T225943_20160528T005943.EOF',
        ],
        'pixel_spacing': 40
    }
    name = process.get_product_name(**payload)
    assert match(r'S1BA_20200918T073646_20200906T073646_HHR012_VEL40_A_[0-9A-F]{4}$', name)

    payload = {
        'reference_name': 'S1A_IW_SLC__1SSV_20150101T230038_20150101T230114_003984_004CC1_0481',
        'secondary_name': 'S1B_IW_SLC__1SDV_20200924T005722_20200924T005750_023510_02CA91_4873',
        'orbit_files': [
            'S1B_OPER_AUX_RESORB_OPOD_20200907T115242_V20200906T042511_20200906T074241.EOF',
            None,
        ],
        'pixel_spacing': 40
    }
    name = process.get_product_name(**payload)
    assert match(r'S1AB_20150101T230038_20200924T005722_VVO2093_VEL40_A_[0-9A-F]{4}$', name)

    payload = {
        'reference_name': 'S2B_MSIL2A_20200903T151809_N0214_R068_T22WEB_20200903T194353',
        'secondary_name': 'S2B_MSIL2A_20200913T151809_N0214_R068_T22WEB_20200913T180530',
        'pixel_spacing': 40,
    }
    name = process.get_product_name(**payload)
    assert match(r'S2BB_20200903T151809_20200913T151809_B08010_VEL40_A_[0-9A-F]{4}$', name)

    payload = {
        'reference_name': 'LC08_L1TP_009011_20200703_20200913_02_T1',
        'secondary_name': 'LC08_L1TP_009011_20200820_20200905_02_T1',
        'pixel_spacing': 40,
    }
    name = process.get_product_name(**payload)
    assert match(r'LC88_20200703T000000_20200820T000000_B08048_VEL40_A_[0-9A-F]{4}$', name)


def test_get_s1_primary_polarization():
    assert process.get_s1_primary_polarization(
        'S1B_WV_SLC__1SSV_20200923T184541_20200923T185150_023506_02CA71_AABB') == 'vv'
    assert process.get_s1_primary_polarization(
        'S1B_IW_GRDH_1SDV_20200924T092954_20200924T093026_023515_02CABC_6C62') == 'vv'
    assert process.get_s1_primary_polarization(
        'S1B_IW_GRDH_1SSH_20200924T112903_20200924T112932_023516_02CAC7_D003') == 'hh'
    assert process.get_s1_primary_polarization(
        'S1B_IW_OCN__2SDH_20200924T090450_20200924T090519_023515_02CAB8_917B') == 'hh'

    with pytest.raises(ValueError):
        process.get_s1_primary_polarization('S1A_EW_GRDM_1SHH_20150513T080355_20150513T080455_005900_007994_35D2')
    with pytest.raises(ValueError):
        process.get_s1_primary_polarization('S1A_EW_GRDM_1SHV_20150509T230833_20150509T230912_005851_00787D_3BE5')
    with pytest.raises(ValueError):
        process.get_s1_primary_polarization('S1A_IW_SLC__1SVH_20150706T015744_20150706T015814_006684_008EF7_9B69')
    with pytest.raises(ValueError):
        process.get_s1_primary_polarization('S1A_IW_GRDH_1SVV_20150706T015720_20150706T015749_006684_008EF7_54BA')
