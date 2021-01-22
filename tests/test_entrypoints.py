def test_hyp3_autorift(script_runner):
    ret = script_runner.run('hyp3_autorift', '-h')
    assert ret.success


def test_autorift_proc_pair(script_runner):
    ret = script_runner.run('autorift_proc_pair', '-h')
    assert ret.success


def test_testautorift_isce(script_runner):
    ret = script_runner.run('testautoRIFT_ISCE.py', '-h')
    assert ret.success


def test_testgeogrid_isce(script_runner):
    ret = script_runner.run('testGeogrid_ISCE.py', '-h')
    assert ret.success


def test_testautorift(script_runner):
    ret = script_runner.run('testautoRIFT.py', '-h')
    assert ret.success


def test_testgeogridoptical(script_runner):
    ret = script_runner.run('testGeogridOptical.py', '-h')
    assert ret.success


def test_topsinsar_filename(script_runner):
    ret = script_runner.run('topsinsar_filename.py', '-h')
    assert ret.success
