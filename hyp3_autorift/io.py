"""Helper io utilities for autoRIFT"""

import argparse
import logging
import os
import textwrap

import boto3
from boto3.s3.transfer import TransferConfig
from hyp3lib.file_subroutines import mkdir_p
from isce.applications.topsApp import TopsInSAR
from scipy.io import savemat

log = logging.getLogger(__name__)
s3_client = boto3.client('s3')


def _list_s3_files(bucket, prefix):
    response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    keys = [item['Key'] for item in response['Contents']]
    return keys


def _download_s3_files(target_dir, bucket, keys, chunk_size=50*1024*1024):
    transfer_config = TransferConfig(multipart_threshold=chunk_size, multipart_chunksize=chunk_size)
    for key in keys:
        filename = os.path.join(target_dir, os.path.basename(key))
        log.info(f'Downloading s3://{bucket}/{key} to {filename}')
        s3_client.download_file(Bucket=bucket, Key=key, Filename=filename, Config=transfer_config)


def fetch_jpl_tifs(ice_sheet='GRE', target_dir='DEM', bucket='its-live-data.jpl.nasa.gov', prefix='isce_autoRIFT'):
    log.info(f"Downloading {ice_sheet} tifs from JPL's AWS bucket")
    mkdir_p(target_dir)

    for logger in ('botocore', 's3transfer'):
        logging.getLogger(logger).setLevel(logging.WARNING)

    full_prefix = f'{prefix}/{ice_sheet}'
    keys = _list_s3_files(bucket, full_prefix)
    _download_s3_files(target_dir, bucket, keys)


def format_tops_xml(reference, secondary, polarization, dem, orbits, aux, xml_file='topsApp.xml'):
    xml_template = f"""    <?xml version="1.0" encoding="UTF-8"?>
    <topsApp>
        <component name="topsinsar">
            <component name="reference">
                <property name="orbit directory">{orbits}</property>
                <property name="auxiliary data directory">{aux}</property>
                <property name="output directory">reference</property>
                <property name="safe">['{reference}']</property>
                <property name="polarization">{polarization}</property>
            </component>
            <component name="secondary">
                <property name="orbit directory">{orbits}</property>
                <property name="auxiliary data directory">{aux}</property>
                <property name="output directory">secondary</property>
                <property name="safe">['{secondary}']</property>
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
    reference_filename = os.path.basename(insar.reference.safe[0])
    secondary_filename = os.path.basename(insar.secondary.safe[0])

    reference_sensing_times = []
    secondary_sensing_times = []
    for swath in range(1, 4):
        insar.reference.configure()
        insar.reference.swathNumber = swath
        insar.reference.parse()
        reference_sensing_times.append(
            (insar.reference.product.sensingStart, insar.reference.product.sensingStop)
        )

        insar.secondary.configure()
        insar.secondary.swathNumber = swath
        insar.secondary.parse()
        secondary_sensing_times.append(
            (insar.secondary.product.sensingStart, insar.secondary.product.sensingStop)
        )

    reference_start = min([sensing_time[0] for sensing_time in reference_sensing_times])
    reference_stop = min([sensing_time[1] for sensing_time in reference_sensing_times])

    secondary_start = min([sensing_time[0] for sensing_time in secondary_sensing_times])
    secondary_stop = min([sensing_time[1] for sensing_time in secondary_sensing_times])

    reference_dt = (reference_stop - reference_start) / 2 + reference_start
    secondary_dt = (secondary_stop - secondary_start) / 2 + secondary_start

    savemat(
        'topsinsar_filename.mat', {
            'reference_filename': reference_filename, 'secondary_filename': secondary_filename,
            'reference_dt': reference_dt.strftime("%Y%m%dT%H:%M:%S"), 'secondary_dt': secondary_dt.strftime("%Y%m%dT%H:%M:%S"),
        }
    )


def topsinsar_mat():
    parser = argparse.ArgumentParser(
        prog=os.path.basename(__file__),
        description='Save the TopsApp InSAR configuration dictionary into a MATLAB file',
    )

    # just get a help option
    _ = parser.parse_args()

    save_topsinsar_mat()
