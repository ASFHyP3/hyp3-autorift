"""Helper io utilities for autoRIFT"""

import argparse
import logging
import os
import textwrap

import boto3
from hyp3lib import DemError
from isce.applications.topsApp import TopsInSAR
from osgeo import gdal
from osgeo import ogr
from scipy.io import savemat

from hyp3_autorift.geometry import flip_point_coordinates

log = logging.getLogger(__name__)

_s3_client = boto3.client('s3')


def find_jpl_parameter_info(polygon: ogr.Geometry, parameter_file: str) -> dict:
    driver = ogr.GetDriverByName('ESRI Shapefile')
    shapes = driver.Open(parameter_file, gdal.GA_ReadOnly)

    parameter_info = None
    centroid = flip_point_coordinates(polygon.Centroid())
    for feature in shapes.GetLayer(0):
        if feature.geometry().Contains(centroid):
            parameter_info = {
                'name': f'{feature["name"]}',
                'epsg': feature['epsg'],
                'geogrid': {
                    'dem': f"/vsicurl/{feature['h']}",
                    'ssm': f"/vsicurl/{feature['StableSurfa']}",
                    'dhdx': f"/vsicurl/{feature['dhdx']}",
                    'dhdy': f"/vsicurl/{feature['dhdy']}",
                    'vx': f"/vsicurl/{feature['vx0']}",
                    'vy': f"/vsicurl/{feature['vy0']}",
                    'srx': f"/vsicurl/{feature['vxSearchRan']}",
                    'sry': f"/vsicurl/{feature['vySearchRan']}",
                    'csminx': f"/vsicurl/{feature['xMinChipSiz']}",
                    'csminy': f"/vsicurl/{feature['yMinChipSiz']}",
                    'csmaxx': f"/vsicurl/{feature['xMaxChipSiz']}",
                    'csmaxy': f"/vsicurl/{feature['yMaxChipSiz']}",
                },
                'autorift': {
                    'grid_location': 'window_location.tif',
                    'init_offset': 'window_offset.tif',
                    'search_range': 'window_search_range.tif',
                    'chip_size_min': 'window_chip_size_min.tif',
                    'chip_size_max': 'window_chip_size_max.tif',
                    'offset2vx': 'window_rdr_off2vel_x_vec.tif',
                    'offset2vy': 'window_rdr_off2vel_y_vec.tif',
                    'stable_surface_mask': 'window_stable_surface_mask.tif',
                    'mpflag': 0,
                }
            }
            break

    if parameter_info is None:
        raise DemError('Could not determine appropriate DEM for:\n'
                       f'    centroid: {centroid}'
                       f'    using: {parameter_file}')

    dem_transform = gdal.Info(parameter_info['geogrid']['dem'], format='json')['geoTransform']
    parameter_info['xsize'] = abs(dem_transform[1])
    parameter_info['ysize'] = abs(dem_transform[-1])

    return parameter_info


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
