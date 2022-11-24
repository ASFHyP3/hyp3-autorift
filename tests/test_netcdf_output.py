from hyp3_autorift.vend.netcdf_output import get_satellite_attribute


def test_get_satellite_attribute():
    info_dict = {
        'mission_img1': 'L',
        'satellite_img1': '8',
        'mission_img2': 'L',
        'satellite_img2': '8',
    }
    assert get_satellite_attribute(info_dict) == 'Landsat 8'

    info_dict = {
        'mission_img1': 'S',
        'satellite_img1': '2',
        'mission_img2': 'S',
        'satellite_img2': '2',
    }
    assert get_satellite_attribute(info_dict) == 'Sentinel-2'

    info_dict = {
        'mission_img1': 'L',
        'satellite_img1': '4',
        'mission_img2': 'S',
        'satellite_img2': '1',
    }
    assert get_satellite_attribute(info_dict) == 'Landsat 4 and Sentinel-1'

    info_dict = {
        'mission_img1': 'S',
        'satellite_img1': '1',
        'mission_img2': 'S',
        'satellite_img2': '2',
    }
    assert get_satellite_attribute(info_dict) == 'Sentinel-1 and Sentinel-2'
