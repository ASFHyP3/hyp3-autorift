"""Helper io utilities for autoRIFT"""

import argparse
import logging
import os
import textwrap
from pathlib import Path
from typing import List, Union

import boto3
from hyp3lib import DemError
from isce.applications.topsApp import TopsInSAR
from osgeo import gdal
from osgeo import ogr
from osgeo import osr
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


def find_jpl_dem(polygon: ogr.Geometry) -> dict:
    shape_file = f'/vsicurl/http://{ITS_LIVE_BUCKET}.s3.amazonaws.com/{AUTORIFT_PREFIX}/autorift_parameters.shp'
    driver = ogr.GetDriverByName('ESRI Shapefile')
    shapes = driver.Open(shape_file, gdal.GA_ReadOnly)

    centroid = polygon.Centroid()
    for feature in shapes.GetLayer(0):
        if feature.geometry().Contains(centroid):
            dem_info = {
                'name': f'{feature["name"]}_0240m',
                'epsg': feature['epsg'],
                'tifs': {
                    'h': f"/vsicurl/{feature['h']}",
                    'StableSurface': f"/vsicurl/{feature['StableSurfa']}",
                    'dhdx': f"/vsicurl/{feature['dhdx']}",
                    'dhdy': f"/vsicurl/{feature['dhdy']}",
                    'dhdxs': f"/vsicurl/{feature['dhdxs']}",
                    'dhdys': f"/vsicurl/{feature['dhdys']}",
                    'vx0': f"/vsicurl/{feature['vx0']}",
                    'vy0': f"/vsicurl/{feature['vy0']}",
                    'vxSearchRange': f"/vsicurl/{feature['vxSearchRan']}",
                    'vySearchRange': f"/vsicurl/{feature['vySearchRan']}",
                    'xMinChipSize': f"/vsicurl/{feature['xMinChipSiz']}",
                    'yMinChipSize': f"/vsicurl/{feature['yMinChipSiz']}",
                    'xMaxChipSize': f"/vsicurl/{feature['xMaxChipSiz']}",
                    'yMaxChipSize': f"/vsicurl/{feature['yMaxChipSiz']}",
                    'sp': f"/vsicurl/{feature['sp']}",
                },
            }
            return dem_info

    raise DemError('Could not determine appropriate DEM for:\n'
                   f'    centroid: {centroid}'
                   f'    using: {shape_file}')


def subset_jpl_tifs(polygon: ogr.Geometry, buffer: float = 0.15, target_dir: Union[str, Path] = '.'):
    dem_info = find_jpl_dem(polygon)
    log.info(f'Subsetting {dem_info["name"]} tifs from s3://{ITS_LIVE_BUCKET}/{AUTORIFT_PREFIX}/')

    in_srs = osr.SpatialReference()
    in_srs.ImportFromEPSG(4326)

    out_srs = osr.SpatialReference()
    out_srs.ImportFromEPSG(dem_info['epsg'])

    transformation = osr.CoordinateTransformation(in_srs, out_srs)
    transformed_poly = ogr.Geometry(wkb=polygon.ExportToWkb())
    transformed_poly = transformed_poly.Buffer(buffer)
    transformed_poly.Transform(transformation)

    lon_min, lon_max, lat_min, lat_max = transformed_poly.GetEnvelope()
    output_bounds = (lon_min, lat_min, lon_max, lat_max)
    log.debug(f'Subset bounds: {output_bounds}')

    subset_tifs = {}
    for key, tif in dem_info['tifs'].items():
        out_path = os.path.join(target_dir, os.path.basename(tif))

        # FIXME: shouldn't need to do after next autoRIFT upgrade
        if out_path.endswith('_sp.tif'):
            out_path = out_path.replace('_sp.tif', '_masks.tif')

        subset_tifs[key] = out_path

        gdal.Warp(
            out_path, tif, outputBounds=output_bounds,
            xRes=240, yRes=240, targetAlignedPixels=True,
        )

    return subset_tifs


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
