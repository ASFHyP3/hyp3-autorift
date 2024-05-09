def test_hyp3_autorift(script_runner):
    ret = script_runner.run(['hyp3_autorift', '-h'])
    assert ret.success


def test_autorift_proc_pair(script_runner):
    ret = script_runner.run(['s1_correction', '-h'])
    assert ret.success
