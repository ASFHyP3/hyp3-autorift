from io import BytesIO

from hyp3_autorift import io


def test_download_s3_file_requester_pays(tmp_path, s3_stub):
    s3_stub.add_response(
        'get_object',
        expected_params={
            'Bucket': 'myBucket',
            'Key': 'foobar.txt',
            'RequestPayer': 'requester',
        },
        service_response={
            'Body': BytesIO(b'123'),
        },
    )
    file = io.download_s3_file_requester_pays(tmp_path / 'foobar.txt', 'myBucket', 'foobar.txt')
    assert (tmp_path / 'foobar.txt').exists()
    assert (tmp_path / 'foobar.txt').read_text() == '123'
    assert tmp_path / 'foobar.txt' == file


def test_get_s3_keys_for_dem():
    expected = [
        'Prefix/GRE240m_h.tif',
        'Prefix/GRE240m_StableSurface.tif',
        'Prefix/GRE240m_dhdx.tif',
        'Prefix/GRE240m_dhdy.tif',
        'Prefix/GRE240m_dhdxs.tif',
        'Prefix/GRE240m_dhdys.tif',
        'Prefix/GRE240m_vx0.tif',
        'Prefix/GRE240m_vy0.tif',
        'Prefix/GRE240m_vxSearchRange.tif',
        'Prefix/GRE240m_vySearchRange.tif',
        'Prefix/GRE240m_xMinChipSize.tif',
        'Prefix/GRE240m_yMinChipSize.tif',
        'Prefix/GRE240m_xMaxChipSize.tif',
        'Prefix/GRE240m_yMaxChipSize.tif',
        'Prefix/GRE240m_sp.tif',
    ]
    assert sorted(io._get_s3_keys_for_dem('Prefix', 'GRE240m')) == sorted(expected)
