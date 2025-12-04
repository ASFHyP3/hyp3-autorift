"""Helper utilities for autoRIFT"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Tuple, Union

import boto3
import numpy as np
from hyp3lib import DemError
from hyp3lib.aws import get_content_type, get_tag_set
from netCDF4 import Dataset
from osgeo import gdal, ogr, osr

from hyp3_autorift.geometry import fix_point_for_antimeridian, flip_point_coordinates


log = logging.getLogger(__name__)


def upload_file_to_s3_with_publish_access_keys(
    path_to_file: Path, bucket: str, prefix: str = '', s3_name: str | None = None
):
    try:
        access_key_id = os.environ['PUBLISH_ACCESS_KEY_ID']
        access_key_secret = os.environ['PUBLISH_SECRET_ACCESS_KEY']
    except KeyError:
        raise ValueError(
            'Please provide S3 Bucket upload access key credentials via the '
            'PUBLISH_ACCESS_KEY_ID and PUBLISH_SECRET_ACCESS_KEY environment variables'
        )

    s3_client = boto3.client('s3', aws_access_key_id=access_key_id, aws_secret_access_key=access_key_secret)

    if s3_name is None:
        s3_name = path_to_file.name
    key = str(Path(prefix) / s3_name)

    extra_args = {'ContentType': get_content_type(key)}

    logging.info(f'Uploading s3://{bucket}/{key}')
    s3_client.upload_file(str(path_to_file), bucket, key, extra_args)

    tag_set = get_tag_set(path_to_file.name)

    s3_client.put_object_tagging(Bucket=bucket, Key=key, Tagging=tag_set)


def find_jpl_parameter_info(polygon: ogr.Geometry, parameter_file: str, flip_point: bool = True) -> dict:
    driver = ogr.GetDriverByName('ESRI Shapefile')
    shapes = driver.Open(parameter_file, gdal.GA_ReadOnly)

    parameter_info = None

    if flip_point:
        centroid = flip_point_coordinates(polygon.Centroid())
    else:
        centroid = polygon.Centroid()

    centroid = fix_point_for_antimeridian(centroid)
    for feature in shapes.GetLayer(0):
        if feature.geometry().Contains(centroid):
            parameter_info = {
                'name': f'{feature["name"]}',
                'epsg': feature['epsg'],
                'geogrid': {
                    'dem': f'/vsicurl/{feature["h"]}',
                    'ssm': f'/vsicurl/{feature["StableSurfa"]}',
                    'dhdx': f'/vsicurl/{feature["dhdx"]}',
                    'dhdy': f'/vsicurl/{feature["dhdy"]}',
                    'vx': f'/vsicurl/{feature["vx0"]}',
                    'vy': f'/vsicurl/{feature["vy0"]}',
                    'srx': f'/vsicurl/{feature["vxSearchRan"]}',
                    'sry': f'/vsicurl/{feature["vySearchRan"]}',
                    'csminx': f'/vsicurl/{feature["xMinChipSiz"]}',
                    'csminy': f'/vsicurl/{feature["yMinChipSiz"]}',
                    'csmaxx': f'/vsicurl/{feature["xMaxChipSiz"]}',
                    'csmaxy': f'/vsicurl/{feature["yMaxChipSiz"]}',
                    'sp': f'/vsicurl/{feature["sp"]}',
                    'dhdxs': f'/vsicurl/{feature["dhdxs"]}',
                    'dhdys': f'/vsicurl/{feature["dhdys"]}',
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
                },
            }
            break

    if parameter_info is None:
        raise DemError(f'Could not determine appropriate DEM for:\n    centroid: {centroid}    using: {parameter_file}')

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


def write_geospatial(
    outfile: str, data, transform, projection, nodata, driver: str = 'GTiff', dtype: int = gdal.GDT_Float64
) -> str:
    driver_object = gdal.GetDriverByName(driver)

    rows, cols = data.shape
    ds = driver_object.Create(outfile, cols, rows, 1, dtype)
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

    gdal.Warp(
        reprojected_reference,
        str(reference_path),
        dstSRS=f'EPSG:{ref_epsg}',
        xRes=ref_info['geoTransform'][1],
        yRes=ref_info['geoTransform'][5],
        resampleAlg='lanczos',
        targetAlignedPixels=True,
    )
    gdal.Warp(
        reprojected_secondary,
        str(secondary_path),
        dstSRS=f'EPSG:{ref_epsg}',
        xRes=ref_info['geoTransform'][1],
        yRes=ref_info['geoTransform'][5],
        resampleAlg='lanczos',
        targetAlignedPixels=True,
    )

    return reprojected_reference, reprojected_secondary


def nullable_string(argument_string: str) -> str | None:
    argument_string = argument_string.replace('None', '').strip()
    return argument_string if argument_string else None


def nullable_granule_list(granule_string: str) -> list[str]:
    granule_string = granule_string.replace('None', '').strip()
    granule_list = [granule for granule in granule_string.split(' ') if granule]
    return granule_list


def sort_ref_sec(reference: list[str], secondary: list[str]) -> tuple[list[str], list[str]]:
    if get_datetime(reference[0]) > get_datetime(secondary[0]):
        return secondary, reference
    return reference, secondary


def get_lat_lon_from_ncfile(ncfile: Path) -> Tuple[float, float]:
    with Dataset(ncfile) as ds:
        var = ds.variables['img_pair_info']
        return var.latitude, var.longitude


def point_to_region(lat: float, lon: float) -> str:
    """
    Returns a string (for example, N78W124) of a region name based on
    granule center point lat,lon
    """
    nw_hemisphere = 'N' if lat >= 0.0 else 'S'
    ew_hemisphere = 'E' if lon >= 0.0 else 'W'

    region_lat = int(10 * np.trunc(np.abs(lat / 10.0)))
    if region_lat == 90:  # if you are exactly at a pole, put in lat = 80 bin
        region_lat = 80

    region_lon = int(10 * np.trunc(np.abs(lon / 10.0)))

    if region_lon >= 180:  # if you are at the dateline, back off to the 170 bin
        region_lon = 170

    return f'{nw_hemisphere}{region_lat:02d}{ew_hemisphere}{region_lon:03d}'


def get_opendata_prefix(file: Path) -> str:
    # filenames have form GRANULE1_X_GRANULE2
    scene = file.name.split('_X_')[0]

    platform_shortname = get_platform(scene)
    lat, lon = get_lat_lon_from_ncfile(file)
    region = point_to_region(lat, lon)

    return '/'.join(['velocity_image_pair', PLATFORM_SHORTNAME_LONGNAME_MAPPING[platform_shortname], 'v02', region])


def save_publication_info(bucket: str, prefix: str, name: str) -> Path:
    publish_info_file = Path.cwd() / 'publish_info.json'
    publish_info_file.write_text(
        json.dumps(
            {
                'bucket': bucket,
                'prefix': prefix,
                'name': name,
            }
        )
    )
    return publish_info_file


PLATFORM_SHORTNAME_LONGNAME_MAPPING = {
    'S1-SLC': 'sentinel1',
    'S1-BURST': 'sentinel1',
    'S2': 'sentinel2',
    'L4': 'landsatOLI',
    'L5': 'landsatOLI',
    'L7': 'landsatOLI',
    'L8': 'landsatOLI',
    'L9': 'landsatOLI',
}


def get_datetime(scene_name):
    if 'BURST' in scene_name:
        return datetime.strptime(scene_name[14:29], '%Y%m%dT%H%M%S')
    if scene_name.startswith('S1'):
        return datetime.strptime(scene_name[17:32], '%Y%m%dT%H%M%S')
    if scene_name.startswith('S2') and len(scene_name) > 25:  # ESA
        return datetime.strptime(scene_name[11:26], '%Y%m%dT%H%M%S')
    if scene_name.startswith('S2'):  # COG
        return datetime.strptime(scene_name.split('_')[2], '%Y%m%d')
    if scene_name.startswith('L'):
        return datetime.strptime(scene_name[17:25], '%Y%m%d')
    if scene_name.startswith('N'):
        return datetime.strptime(scene_name.split('_')[11][:8], '%Y%m%d')
    raise ValueError(f'Unsupported scene format: {scene_name}')


def get_platform(scene: str) -> str:
    if scene.startswith('S1'):
        if 'BURST' in scene:
            return 'S1-BURST'
        return 'S1-SLC'
    if scene.startswith('S2'):
        return scene[0:2]
    if scene.startswith('L') and scene[3] in ('4', '5', '7', '8', '9'):
        return scene[0] + scene[3]
    if scene.startswith('NISAR'):
        return 'NISAR'
    raise NotImplementedError(f'autoRIFT processing not available for this platform. {scene}')
