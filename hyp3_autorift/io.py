"""Helper io utilities for autoRIFT"""

import argparse
import logging
import os
import textwrap
from pathlib import Path
from typing import List, Union

import boto3
from isce.applications.topsApp import TopsInSAR
from osgeo import gdal
from osgeo import ogr
from scipy.io import savemat

log = logging.getLogger(__name__)

ITS_LIVE_BUCKET = 'its-live-data.jpl.nasa.gov'
AUTORIFT_PREFIX = 'autorift_parameters/v001'

_s3_client = boto3.client('s3')


def download_s3_file_requester_pays(target_path: Union[str, Path], bucket: str, key: str) -> Path:
    response = _s3_client.get_object(Bucket=bucket, Key=key, RequestPayer='requester')
    filename = Path(target_path)
    filename.write_bytes(response['Body'].read())
    return filename


def _get_s3_keys_for_dem(prefix: str = AUTORIFT_PREFIX, dem: str = 'GRE240m') -> List[str]:
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
        'sp',
    ]
    keys = [f'{prefix}/{dem}_{tag}.tif' for tag in tags]
    return keys


def subset_jpl_tifs(polygon: ogr.Geometry, buffer: float = 0.15, dem: str = 'NPS_0240m', target_dir: str = 'DEM',
                    bucket: str = ITS_LIVE_BUCKET, prefix: str = AUTORIFT_PREFIX):
    log.info(f'Subsetting {dem} tifs from s3://{bucket}')

    min_x, max_x, min_y, max_y = polygon.Buffer(buffer).GetEnvelope()
    output_bounds = (min_x, min_y, max_x, max_y)

    for key in _get_s3_keys_for_dem(prefix, dem):
        in_file = f'/vsicurl/http://{bucket}.s3.amazonaws.com/{key}'
        out_file = os.path.join(target_dir, os.path.basename(key))

        # FIXME: shouldn't need to do after next autoRIFT upgrade
        if out_file.endswith('_sp.tif'):
            out_file = out_file.replace('_sp.tif', '_masks.tif')

        gdal.Warp(
            out_file, in_file, outputBounds=output_bounds, multithread=True,
            # FIXME: hard coded x-y resolution; required for targetAlignedPixels
            #        could pull this out of a gdal.info call to any one of the tifs
            #        or out of the dem name...
            xRes=240, yRes=240, targetAlignedPixels=True,
        )


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
