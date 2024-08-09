"""Helper utilities for autoRIFT"""

import logging
import os
from pathlib import Path
from typing import Tuple, Union

import boto3
from hyp3lib import DemError
from hyp3lib.aws import get_content_type, get_tag_set
from osgeo import gdal, ogr, osr

from hyp3_autorift.geometry import fix_point_for_antimeridian, flip_point_coordinates


log = logging.getLogger(__name__)


def upload_file_to_s3_with_publish_access_keys(path_to_file: Path, bucket: str, prefix: str = ''):
    try:
        access_key_id = os.environ['PUBLISH_ACCESS_KEY_ID']
        access_key_secret = os.environ['PUBLISH_SECRET_ACCESS_KEY']
    except KeyError:
        raise ValueError(
            'Please provide S3 Bucket upload access key credentials via the '
            'PUBLISH_ACCESS_KEY_ID and PUBLISH_SECRET_ACCESS_KEY environment variables'
        )

    s3_client = boto3.client('s3', aws_access_key_id=access_key_id, aws_secret_access_key=access_key_secret)
    key = str(Path(prefix) / path_to_file.name)
    extra_args = {'ContentType': get_content_type(key)}

    logging.info(f'Uploading s3://{bucket}/{key}')
    s3_client.upload_file(str(path_to_file), bucket, key, extra_args)

    tag_set = get_tag_set(path_to_file.name)

    s3_client.put_object_tagging(Bucket=bucket, Key=key, Tagging=tag_set)


def find_jpl_parameter_info(polygon: ogr.Geometry, parameter_file: str) -> dict:
    driver = ogr.GetDriverByName('ESRI Shapefile')
    shapes = driver.Open(parameter_file, gdal.GA_ReadOnly)

    parameter_info = None
    centroid = flip_point_coordinates(polygon.Centroid())
    centroid = fix_point_for_antimeridian(centroid)
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
                    'sp': f"/vsicurl/{feature['sp']}",
                    'dhdxs': f"/vsicurl/{feature['dhdxs']}",
                    'dhdys': f"/vsicurl/{feature['dhdys']}",
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
                    'scale_factor': 'window_scale_factor.tif',
                    'mpflag': 0,
                }
            }
            break

    if parameter_info is None:
        raise DemError('Could not determine appropriate DEM for:\n'
                       f'    centroid: {centroid}'
                       f'    using: {parameter_file}')

    dem_geotransform = gdal.Info(parameter_info['geogrid']['dem'], format='json')['geoTransform']
    parameter_info['xsize'] = abs(dem_geotransform[1])
    parameter_info['ysize'] = abs(dem_geotransform[5])

    return parameter_info


def load_geospatial(infile: str, band: int = 1):
    ds = gdal.Open(infile, gdal.GA_ReadOnly)

    data = ds.GetRasterBand(band).ReadAsArray()
    nodata = ds.GetRasterBand(band).GetNoDataValue()

    transform = ds.GetGeoTransform()
    projection = ds.GetProjection()
    srs = ds.GetSpatialRef()

    del ds
    return data, transform, projection, srs, nodata


def write_geospatial(outfile: str, data, transform, projection, nodata,
                     driver: str = 'GTiff', dtype: int = gdal.GDT_Float64) -> str:
    driver = gdal.GetDriverByName(driver)

    rows, cols = data.shape
    ds = driver.Create(outfile, cols, rows, 1, dtype)
    ds.SetGeoTransform(transform)
    ds.SetProjection(projection)

    if nodata is not None:
        ds.GetRasterBand(1).SetNoDataValue(nodata)
    ds.GetRasterBand(1).WriteArray(data)
    del ds
    return outfile


def get_epsg_code(info: dict) -> int:
    """Get the EPSG code from a GDAL Info dictionary
    Args:
        info: The dictionary returned by a gdal.Info call
    Returns:
        epsg_code: The integer EPSG code
    """
    proj = osr.SpatialReference(info['coordinateSystem']['wkt'])
    epsg_code = int(proj.GetAttrValue('AUTHORITY', 1))
    return epsg_code


def ensure_same_projection(reference_path: Union[str, Path], secondary_path: Union[str, Path]) -> Tuple[str, str]:
    reprojection_dir = Path('reprojected')
    reprojection_dir.mkdir(exist_ok=True)

    ref_info = gdal.Info(str(reference_path), format='json')
    ref_epsg = get_epsg_code(ref_info)

    reprojected_reference = str(reprojection_dir / Path(reference_path).name)
    reprojected_secondary = str(reprojection_dir / Path(secondary_path).name)

    gdal.Warp(reprojected_reference, str(reference_path), dstSRS=f'EPSG:{ref_epsg}',
              xRes=ref_info['geoTransform'][1], yRes=ref_info['geoTransform'][5],
              resampleAlg='lanczos', targetAlignedPixels=True)
    gdal.Warp(reprojected_secondary, str(secondary_path), dstSRS=f'EPSG:{ref_epsg}',
              xRes=ref_info['geoTransform'][1], yRes=ref_info['geoTransform'][5],
              resampleAlg='lanczos', targetAlignedPixels=True)

    return reprojected_reference, reprojected_secondary
