import pytest

from hyp3_autorift import s1_isce2


def test_get_s1_primary_polarization():
    assert s1_isce2.get_s1_primary_polarization(
        'S1B_WV_SLC__1SSV_20200923T184541_20200923T185150_023506_02CA71_AABB') == 'vv'
    assert s1_isce2.get_s1_primary_polarization(
        'S1B_IW_GRDH_1SDV_20200924T092954_20200924T093026_023515_02CABC_6C62') == 'vv'
    assert s1_isce2.get_s1_primary_polarization(
        'S1B_IW_GRDH_1SSH_20200924T112903_20200924T112932_023516_02CAC7_D003') == 'hh'
    assert s1_isce2.get_s1_primary_polarization(
        'S1B_IW_OCN__2SDH_20200924T090450_20200924T090519_023515_02CAB8_917B') == 'hh'

    with pytest.raises(ValueError):
        s1_isce2.get_s1_primary_polarization('S1A_EW_GRDM_1SHH_20150513T080355_20150513T080455_005900_007994_35D2')
    with pytest.raises(ValueError):
        s1_isce2.get_s1_primary_polarization('S1A_EW_GRDM_1SHV_20150509T230833_20150509T230912_005851_00787D_3BE5')
    with pytest.raises(ValueError):
        s1_isce2.get_s1_primary_polarization('S1A_IW_SLC__1SVH_20150706T015744_20150706T015814_006684_008EF7_9B69')
    with pytest.raises(ValueError):
        s1_isce2.get_s1_primary_polarization('S1A_IW_GRDH_1SVV_20150706T015720_20150706T015749_006684_008EF7_54BA')
