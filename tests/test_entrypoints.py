def test_hyp3_autorift(script_runner):
    ret = script_runner.run(['hyp3_autorift', '-h'])
    assert ret.success
