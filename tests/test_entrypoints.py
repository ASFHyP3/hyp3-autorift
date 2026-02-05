def test_hyp3_autorift(script_runner):
    ret = script_runner.run(['hyp3_autorift', '-h'])
    assert ret.success


def test_crop_netcdf_product(script_runner):
    ret = script_runner.run(['crop_netcdf_product', '-h'])
    assert ret.success


def test_bulk_crop_netcdf_product(script_runner):
    ret = script_runner.run(['bulk_crop_netcdf_product', '-h'])
    assert ret.success
