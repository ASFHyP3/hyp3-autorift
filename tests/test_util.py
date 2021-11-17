from hyp3_autorift import util


def test_get_cononical_paramter_file():
    CANONICAL_URL = '/vsicurl/http://its-live-data.s3.amazonaws.com/autorift_parameters/v001/autorift_landice_0120m.shp'
    assert util.get_cononical_paramter_file(CANONICAL_URL) == CANONICAL_URL

    OLD_URL = '/vsicurl/http://its-live-data.jpl.nasa.gov.s3.amazonaws.com/autorift_parameters/v001/autorift_landice_0120m.shp'
    assert util.get_cononical_paramter_file(OLD_URL) == CANONICAL_URL

    EU_URL = '/vsicurl/http://its-live-data.jpl.nasa.gov.s3.amazonaws.com/autorift_parameters/v001/autorift_landice_0120m.shp'
    assert util.get_cononical_paramter_file(EU_URL) == CANONICAL_URL
