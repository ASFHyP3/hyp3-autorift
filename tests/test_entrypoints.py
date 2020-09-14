def test_hyp3_autorift(script_runner):
    ret = script_runner.run('autorift', '+h')
    assert ret.success


def test_autorift_passthought(script_runner):
    ret = script_runner.run('autorift', '--version')
    assert ret.success
    assert 'autorift_isce v' in ret.stdout
    assert 'hyp3lib v' in ret.stdout
    assert 'hyp3proclib v' in ret.stdout


def test_autorift_passthough_v2(script_runner):
    ret = script_runner.run(
        'autorift', '++entrypoint', 'hyp3_autorift_v2', '--help')
    assert ret.success
    assert 'autorift_v2' in ret.stdout
    assert '--bucket-prefix' in ret.stdout


def test_autorift_proc_pair(script_runner):
    ret = script_runner.run('autorift_proc_pair', '-h')
    assert ret.success


def test_testautorift_isce(script_runner):
    ret = script_runner.run('testautoRIFT_ISCE.py', '-h')
    assert ret.success


def test_testgeogrid_isce(script_runner):
    ret = script_runner.run('testGeogrid_ISCE.py', '-h')
    assert ret.success


def test_topsinsar_filename(script_runner):
    ret = script_runner.run('topsinsar_filename.py', '-h')
    assert ret.success
