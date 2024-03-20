import logging
import netrc
import os
from pathlib import Path
from platform import system
from typing import Tuple

import boto3
from hyp3lib.aws import get_content_type, get_tag_set


ESA_HOST = 'dataspace.copernicus.eu'


def get_esa_credentials() -> Tuple[str, str]:
    netrc_name = '_netrc' if system().lower() == 'windows' else '.netrc'
    netrc_file = Path.home() / netrc_name

    if "ESA_USERNAME" in os.environ and "ESA_PASSWORD" in os.environ:
        username = os.environ["ESA_USERNAME"]
        password = os.environ["ESA_PASSWORD"]
        return username, password

    if netrc_file.exists():
        netrc_credentials = netrc.netrc(netrc_file)
        if ESA_HOST in netrc_credentials.hosts:
            username = netrc_credentials.hosts[ESA_HOST][0]
            password = netrc_credentials.hosts[ESA_HOST][2]
            return username, password

    raise ValueError(
        "Please provide Copernicus Data Space Ecosystem (CDSE) credentials via the "
        "ESA_USERNAME and ESA_PASSWORD environment variables, or your netrc file."
    )


def upload_file_to_s3_with_upload_access_keys(path_to_file: Path, bucket: str, prefix: str = ''):
    if 'UPLOAD_ACCESS_KEY_ID' in os.environ and 'UPLOAD_ACCESS_KEY_SECRET' in os.environ:
        access_key_id = os.environ['UPLOAD_ACCESS_KEY_ID']
        access_key_secret = os.environ['UPLOAD_ACCESS_KEY_SECRET']
    else:
        raise ValueError(
            'Please provide S3 Bucket upload access key credentials via the '
            'UPLOAD_ACCESS_KEY_ID and UPLOAD_ACCESS_KEY_SECRET environment variables'
        )

    s3_client = boto3.client('s3', aws_access_key_id=access_key_id, aws_secret_access_key=access_key_secret)
    key = str(Path(prefix) / path_to_file.name)
    extra_args = {'ContentType': get_content_type(key)}

    logging.info(f'Uploading s3://{bucket}/{key}')
    s3_client.upload_file(str(path_to_file), bucket, key, extra_args)

    tag_set = get_tag_set(path_to_file.name)

    s3_client.put_object_tagging(Bucket=bucket, Key=key, Tagging=tag_set)
