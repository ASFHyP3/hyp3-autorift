from io import BytesIO

from hyp3_autorift import io


def test_list_s3_files(s3_stub):
    s3_stub.add_response(
        'list_objects_v2',
        expected_params={
            'Bucket': 'myBucket',
            'Prefix': 'myPrefix',
        },
        service_response={
            'Contents': [
                {
                    'Key': 'myPrefix/foo',
                },
                {
                    'Key': 'myPrefix/bar',
                },
            ]
        },
    )
    assert io._list_s3_files('myBucket', 'myPrefix') == ['myPrefix/foo', 'myPrefix/bar']


def test_download_s3_files(tmp_path, s3_stub):
    keys = ['foo', 'bar']
    for key in keys:
        s3_stub.add_response(
            'head_object',
            expected_params={
                'Bucket': 'myBucket',
                'Key': key,
            },
            service_response={
                'ContentLength': 3,
            },
        )
        s3_stub.add_response(
            'get_object',
            expected_params={
                'Bucket': 'myBucket',
                'Key': key,
            },
            service_response={
                'Body': BytesIO(b'123'),
            },
        )
    io._download_s3_files(tmp_path, 'myBucket', keys)
    for key in keys:
        assert (tmp_path / key).exists()
        with open(tmp_path / key, 'r') as f:
            assert f.read() == '123'
