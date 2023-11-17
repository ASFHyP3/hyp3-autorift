import pytest

from hyp3_autorift.utils import ESA_HOST, get_esa_credentials


def test_get_esa_credentials_env(tmp_path, monkeypatch):
    with monkeypatch.context() as m:
        m.setenv('ESA_USERNAME', 'foo')
        m.setenv('ESA_PASSWORD', 'bar')
        m.setenv('HOME', str(tmp_path))
        (tmp_path / '.netrc').write_text(f'machine {ESA_HOST} login netrc_username password netrc_password')

        username, password = get_esa_credentials()
        assert username == 'foo'
        assert password == 'bar'


def test_get_esa_credentials_netrc(tmp_path, monkeypatch):
    with monkeypatch.context() as m:
        m.delenv('ESA_USERNAME', raising=False)
        m.delenv('ESA_PASSWORD', raising=False)
        m.setenv('HOME', str(tmp_path))
        (tmp_path / '.netrc').write_text(f'machine {ESA_HOST} login foo password bar')

        username, password = get_esa_credentials()
        assert username == 'foo'
        assert password == 'bar'


def test_get_esa_credentials_missing(tmp_path, monkeypatch):
    with monkeypatch.context() as m:
        m.delenv('ESA_USERNAME', raising=False)
        m.setenv('ESA_PASSWORD', 'env_password')
        m.setenv('HOME', str(tmp_path))
        (tmp_path / '.netrc').write_text('')
        msg = 'Please provide.*'
        with pytest.raises(ValueError, match=msg):
            get_esa_credentials()

    with monkeypatch.context() as m:
        m.setenv('ESA_USERNAME', 'env_username')
        m.delenv('ESA_PASSWORD', raising=False)
        m.setenv('HOME', str(tmp_path))
        (tmp_path / '.netrc').write_text('')
        msg = 'Please provide.*'
        with pytest.raises(ValueError, match=msg):
            get_esa_credentials()