"""Helper io utilities for autoRIFT"""

import argparse
import logging
import os
import textwrap

import boto3
from boto3.s3.transfer import TransferConfig
from botocore import UNSIGNED
from botocore.config import Config
from isce.applications.topsApp import TopsInSAR
from scipy.io import savemat

log = logging.getLogger(__name__)

ITS_LIVE_BUCKET = 'its-live-data.jpl.nasa.gov'
AUTORIFT_PREFIX = 'isce_autoRIFT'


def download_s3_files_requester_pays(target_dir, bucket, key):
    s3_client = boto3.client('s3')
    response = s3_client.get_object(Bucket=bucket, Key=key, RequestPayer='requester')
    filename = os.path.join(target_dir, os.path.basename(key))
    with open(filename, 'wb') as f:
        f.write(response['Body'].read())
    return filename


def _download_s3_files(target_dir, bucket, keys, chunk_size=50*1024*1024):
    s3_client = boto3.client('s3', config=Config(signature_version=UNSIGNED))
    transfer_config = TransferConfig(multipart_threshold=chunk_size, multipart_chunksize=chunk_size)
    file_list = []
    for key in keys:
        filename = os.path.join(target_dir, os.path.basename(key))
        if os.path.exists(filename):
            continue
        file_list.append(filename)
        log.info(f'Downloading s3://{bucket}/{key} to {filename}')
        s3_client.download_file(Bucket=bucket, Key=key, Filename=filename, Config=transfer_config)
    return file_list


def _get_s3_keys_for_dem(prefix=AUTORIFT_PREFIX, dem='GRE240m'):
    tags = [
        'h',
        'StableSurface',
        'dhdx',
        'dhdy',
        'dhdxs',
        'dhdys',
        'vx0',
        'vy0',
        'vxSearchRange',
        'vySearchRange',
        'xMinChipSize',
        'yMinChipSize',
        'xMaxChipSize',
        'yMaxChipSize',
        'masks',
    ]
    keys = [f'{prefix}/{dem}_{tag}.tif' for tag in tags]
    return keys


def fetch_jpl_tifs(dem='GRE240m', target_dir='DEM', bucket=ITS_LIVE_BUCKET, prefix=AUTORIFT_PREFIX):
    log.info(f"Downloading {dem} tifs from JPL's AWS bucket")

    for logger in ('botocore', 's3transfer'):
        logging.getLogger(logger).setLevel(logging.WARNING)

    keys = _get_s3_keys_for_dem(prefix, dem)
    _download_s3_files(target_dir, bucket, keys)


def format_tops_xml(reference, secondary, polarization, dem, orbits, xml_file='topsApp.xml'):
    xml_template = f"""    <?xml version="1.0" encoding="UTF-8"?>
    <topsApp>
        <component name="topsinsar">
            <component name="reference">
                <property name="orbit directory">{orbits}</property>
                <property name="auxiliary data directory">{orbits}</property>
                <property name="output directory">reference</property>
                <property name="safe">['{reference}.zip']</property>
                <property name="polarization">{polarization}</property>
            </component>
            <component name="secondary">
                <property name="orbit directory">{orbits}</property>
                <property name="auxiliary data directory">{orbits}</property>
                <property name="output directory">secondary</property>
                <property name="safe">['{secondary}.zip']</property>
                <property name="polarization">{polarization}</property>
            </component>
            <property name="demfilename">{dem}</property>
            <property name="do interferogram">False</property>
            <property name="do dense offsets">True</property>
            <property name="do ESD">False</property>
            <property name="do unwrap">False</property>
            <property name="do unwrap 2 stage">False</property>
            <property name="ampcor skip width">32</property>
            <property name="ampcor skip height">32</property>
            <property name="ampcor search window width">51</property>
            <property name="ampcor search window height">51</property>
            <property name="ampcor window width">32</property>
            <property name="ampcor window height">32</property>
        </component>
    </topsApp>
    """

    with open(xml_file, 'w') as f:
        f.write(textwrap.dedent(xml_template))


def save_topsinsar_mat():
    insar = TopsInSAR(name="topsApp")
    insar.configure()

    mat_data = {}
    for name in ['reference', 'secondary']:
        scene = insar.__getattribute__(name)

        sensing_times = []
        for swath in range(1, 4):
            scene.configure()
            scene.swathNumber = swath
            scene.parse()
            sensing_times.append(
                (scene.product.sensingStart, scene.product.sensingStop)
            )

        sensing_start = min([sensing_time[0] for sensing_time in sensing_times])
        sensing_stop = max([sensing_time[1] for sensing_time in sensing_times])

        sensing_dt = (sensing_stop - sensing_start) / 2 + sensing_start

        mat_data[f'{name}_filename'] = os.path.basename(scene.safe[0])
        mat_data[f'{name}_dt'] = sensing_dt.strftime("%Y%m%dT%H:%M:%S")

    savemat('topsinsar_filename.mat', mat_data)


def topsinsar_mat():
    parser = argparse.ArgumentParser(
        prog=os.path.basename(__file__),
        description='Save the TopsApp InSAR configuration dictionary into a MATLAB file',
    )

    # just get a help option
    _ = parser.parse_args()

    save_topsinsar_mat()
