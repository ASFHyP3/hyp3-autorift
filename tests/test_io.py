from io import BytesIO

import pytest
from hyp3lib import DemError

from hyp3_autorift import geometry, io


def test_download_s3_file_requester_pays(tmp_path, s3_stub):
    s3_stub.add_response(
        'get_object',
        expected_params={
            'Bucket': 'myBucket',
            'Key': 'foobar.txt',
            'RequestPayer': 'requester',
        },
        service_response={
            'Body': BytesIO(b'123'),
        },
    )
    file = io.download_s3_file_requester_pays(tmp_path / 'foobar.txt', 'myBucket', 'foobar.txt')
    assert (tmp_path / 'foobar.txt').exists()
    assert (tmp_path / 'foobar.txt').read_text() == '123'
    assert tmp_path / 'foobar.txt' == file


def test_find_jpl_dem():
    polygon = geometry.polygon_from_bbox(lat_limits=(55, 56), lon_limits=(40, 41))
    dem_info = io.find_jpl_dem(polygon)
    assert dem_info['name'] == 'NPS_0240m'

    polygon = geometry.polygon_from_bbox(lat_limits=(54, 55), lon_limits=(40, 41))
    dem_info = io.find_jpl_dem(polygon)
    assert dem_info['name'] == 'N37_0240m'

    polygon = geometry.polygon_from_bbox(lat_limits=(54, 55), lon_limits=(-40, -41))
    dem_info = io.find_jpl_dem(polygon)
    assert dem_info['name'] == 'N24_0240m'

    polygon = geometry.polygon_from_bbox(lat_limits=(-54, -55), lon_limits=(-40, -41))
    dem_info = io.find_jpl_dem(polygon)
    assert dem_info['name'] == 'S24_0240m'

    polygon = geometry.polygon_from_bbox(lat_limits=(-55, -56), lon_limits=(40, 41))
    dem_info = io.find_jpl_dem(polygon)
    assert dem_info['name'] == 'S37_0240m'

    polygon = geometry.polygon_from_bbox(lat_limits=(-56, -57), lon_limits=(40, 41))
    dem_info = io.find_jpl_dem(polygon)
    assert dem_info['name'] == 'SPS_0240m'

    polygon = geometry.polygon_from_bbox(lat_limits=(-90, -91), lon_limits=(40, 41))
    with pytest.raises(DemError):
        io.find_jpl_dem(polygon)

    polygon = geometry.polygon_from_bbox(lat_limits=(90, 91), lon_limits=(40, 41))
    with pytest.raises(DemError):
        io.find_jpl_dem(polygon)

    polygon = geometry.polygon_from_bbox(lat_limits=(55, 56), lon_limits=(180, 181))
    with pytest.raises(DemError):
        io.find_jpl_dem(polygon)

    polygon = geometry.polygon_from_bbox(lat_limits=(55, 56), lon_limits=(-180, -181))
    with pytest.raises(DemError):
        io.find_jpl_dem(polygon)
