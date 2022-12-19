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
        'satellite_img1': '2A',
        'mission_img2': 'S',
        'satellite_img2': '2A',
    }
    assert get_satellite_attribute(info_dict) == 'Sentinel-2A'

    info_dict = {
        'mission_img1': 'L',
        'satellite_img1': '5',
        'mission_img2': 'L',
        'satellite_img2': '4',
    }
    assert get_satellite_attribute(info_dict) == 'Landsat 5 and Landsat 4'

    info_dict = {
        'mission_img1': 'S',
        'satellite_img1': '1A',
        'mission_img2': 'S',
        'satellite_img2': '1B',
    }
    assert get_satellite_attribute(info_dict) == 'Sentinel-1A and Sentinel-1B'
