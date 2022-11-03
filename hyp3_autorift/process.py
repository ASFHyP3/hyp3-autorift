"""
Package for processing with autoRIFT
"""

import argparse
import json
import logging
import os
import shutil
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from secrets import token_hex
from typing import Tuple

import boto3
import botocore.exceptions
import numpy as np
import requests
from hyp3lib.fetch import download_file
from hyp3lib.get_orb import downloadSentinelOrbitFile
from hyp3lib.scene import get_download_url
from netCDF4 import Dataset
from osgeo import gdal

from hyp3_autorift import geometry
from hyp3_autorift import image
from hyp3_autorift import io

log = logging.getLogger(__name__)

gdal.UseExceptions()

S3_CLIENT = boto3.client('s3')
S2_GRANULE_DIR = 'https://storage.googleapis.com/gcp-public-data-sentinel-2/tiles'

LC2_SEARCH_URL = 'https://landsatlook.usgs.gov/stac-server/collections/landsat-c2l1/items'
LANDSAT_BUCKET = 'usgs-landsat'
LANDSAT_SENSOR_MAPPING = {
    'L9': {'C': 'oli-tirs', 'O': 'oli-tirs', 'T': 'oli-tirs'},
    'L8': {'C': 'oli-tirs', 'O': 'oli-tirs', 'T': 'oli-tirs'},
    'L7': {'E': 'etm'},
    'L5': {'T': 'tm', 'M': 'mss'},
    'L4': {'T': 'tm', 'M': 'mss'},
}

DEFAULT_PARAMETER_FILE = '/vsicurl/http://its-live-data.s3.amazonaws.com/' \
                         'autorift_parameters/v001/autorift_landice_0120m.shp'


def get_lc2_stac_json_key(scene_name: str) -> str:
    platform = get_platform(scene_name)
    year = scene_name[17:21]
    path = scene_name[10:13]
    row = scene_name[13:16]

    sensor = LANDSAT_SENSOR_MAPPING[platform][scene_name[1]]

    return f'collection02/level-1/standard/{sensor}/{year}/{path}/{row}/{scene_name}/{scene_name}_stac.json'


def get_lc2_metadata(scene_name):
    response = requests.get(f'{LC2_SEARCH_URL}/{scene_name}')
    try:
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError:
        if response.status_code != 404:
            raise

    key = get_lc2_stac_json_key(scene_name)
    obj = S3_CLIENT.get_object(Bucket=LANDSAT_BUCKET, Key=key, RequestPayer='requester')
    return json.load(obj['Body'])


def get_lc2_path(metadata):
    if metadata['id'][3] in ('4', '5'):
        band = metadata['assets'].get('B2.TIF')
        if band is None:
            band = metadata['assets']['green']
    elif metadata['id'][3] in ('7', '8', '9'):
        band = metadata['assets'].get('B8.TIF')
        if band is None:
            band = metadata['assets']['pan']

    return band['href'].replace('https://landsatlook.usgs.gov/data/', f'/vsis3/{LANDSAT_BUCKET}/')


def get_s2_path(manifest_text: str, scene_name: str) -> str:
    root = ET.fromstring(manifest_text)
    elements = root.findall(".//fileLocation[@locatorType='URL'][@href]")
    hrefs = [element.attrib['href'] for element in elements if
             element.attrib['href'].endswith('_B08.jp2') and '/IMG_DATA/' in element.attrib['href']]
    if len(hrefs) == 1:
        # post-2016-12-06 scene; only one tile
        file_path = hrefs[0]
    else:
        # pre-2016-12-06 scene; choose the requested tile
        tile_token = scene_name.split('_')[5]
        file_path = [href for href in hrefs if href.endswith(f'_{tile_token}_B08.jp2')][0]
    return f'/vsicurl/{S2_GRANULE_DIR}/{file_path}'


def get_raster_bbox(path: str):
    info = gdal.Info(path, format='json')
    coordinates = info['wgs84Extent']['coordinates'][0]
    lons = [coord[0] for coord in coordinates]
    lats = [coord[1] for coord in coordinates]
    if max(lons) >= 170 and min(lons) <= -170:
        lons = [lon - 360 if lon >= 170 else lon for lon in lons]
    return [
        min(lons),
        min(lats),
        max(lons),
        max(lats),
    ]


def get_s2_metadata(scene_name):
    tile = f'{scene_name[39:41]}/{scene_name[41:42]}/{scene_name[42:44]}'
    tile_path = f'{tile}/{scene_name}.SAFE'

    manifest_url = f'{S2_GRANULE_DIR}/{tile_path}/manifest.safe'
    response = requests.get(manifest_url)
    response.raise_for_status()

    path = get_s2_path(response.text, scene_name)
    bbox = get_s2_bbox(path)

    acquisition_start = datetime.strptime(scene_name.split('_')[2], '%Y%m%dT%H%M%S')

    return {
        'path': path,
        'bbox': bbox,
        'id': scene_name,
        'properties': {
            'datetime': acquisition_start.isoformat(timespec='seconds') + 'Z',
        },
    }


def s3_object_is_accessible(bucket, key):
    try:
        S3_CLIENT.head_object(Bucket=bucket, Key=key)
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] in ['403', '404']:
            return False
        raise
    return True


def parse_s3_url(s3_url: str) -> Tuple[str, str]:
    s3_location = s3_url.replace('s3://', '').split('/')
    bucket = s3_location[0]
    key = '/'.join(s3_location[1:])
    return bucket, key


def least_precise_orbit_of(orbits):
    if any([orb is None for orb in orbits]):
        return 'O'
    if any(['RESORB' in orb for orb in orbits]):
        return 'R'
    return 'P'


def get_datetime(scene_name):
    if scene_name.startswith('S1'):
        return datetime.strptime(scene_name[17:32], '%Y%m%dT%H%M%S')
    if scene_name.startswith('S2') and len(scene_name) > 25:  # ESA
        return datetime.strptime(scene_name[11:26], '%Y%m%dT%H%M%S')
    if scene_name.startswith('S2'):  # COG
        return datetime.strptime(scene_name.split('_')[2], '%Y%m%d')
    if scene_name.startswith('L'):
        return datetime.strptime(scene_name[17:25], '%Y%m%d')

    raise ValueError(f'Unsupported scene format: {scene_name}')


def get_product_name(reference_name, secondary_name, orbit_files=None, pixel_spacing=240):
    mission = reference_name[0:2]
    plat1 = reference_name.split('_')[0][-1]
    plat2 = secondary_name.split('_')[0][-1]

    ref_datetime = get_datetime(reference_name)
    sec_datetime = get_datetime(secondary_name)
    days = abs((ref_datetime - sec_datetime).days)

    datetime1 = ref_datetime.strftime('%Y%m%dT%H%M%S')
    datetime2 = sec_datetime.strftime('%Y%m%dT%H%M%S')

    if reference_name.startswith('S1'):
        polarization1 = reference_name[15:16]
        polarization2 = secondary_name[15:16]
        orbit = least_precise_orbit_of(orbit_files)
        misc = polarization1 + polarization2 + orbit
    else:
        misc = 'B08'

    product_id = token_hex(2).upper()

    return f'{mission}{plat1}{plat2}_{datetime1}_{datetime2}_{misc}{days:03}_VEL{pixel_spacing}_A_{product_id}'


def get_platform(scene: str) -> str:
    if scene.startswith('S1') or scene.startswith('S2'):
        return scene[0:2]
    elif scene.startswith('L') and scene[3] in ('4', '5', '7', '8', '9'):
        return scene[0] + scene[3]
    else:
        raise NotImplementedError(f'autoRIFT processing not available for this platform. {scene}')


def get_s1_primary_polarization(granule_name):
    polarization = granule_name[14:16]
    if polarization in ['SV', 'DV']:
        return 'vv'
    if polarization in ['SH', 'DH']:
        return 'hh'
    raise ValueError(f'Cannot determine co-polarization of granule {granule_name}')


def create_fft_filepath(path: str):
    parent = (Path.cwd() / 'fft').resolve()
    parent.mkdir(exist_ok=True)

    out_path = parent / Path(path).name
    return str(out_path)


def apply_fft_filter(array: np.ndarray, nodata: int):
    from autoRIFT.autoRIFT import _fft_filter, _wallis_filter
    valid_domain = array != nodata
    array[~valid_domain] = 0
    array = array.astype(float)

    wallis = _wallis_filter(array, filter_width=5)
    wallis[~valid_domain] = 0

    filtered = _fft_filter(wallis, valid_domain, power_threshold=500)
    filtered[~valid_domain] = 0

    return filtered


def process(reference: str, secondary: str, parameter_file: str = DEFAULT_PARAMETER_FILE,
            naming_scheme: str = 'ITS_LIVE_OD') -> Tuple[Path, Path]:
    """Process a Sentinel-1, Sentinel-2, or Landsat-8 image pair

    Args:
        reference: Name of the reference Sentinel-1, Sentinel-2, or Landsat-8 Collection 2 scene
        secondary: Name of the secondary Sentinel-1, Sentinel-2, or Landsat-8 Collection 2 scene
        parameter_file: Shapefile for determining the correct search parameters by geographic location
        naming_scheme: Naming scheme to use for product files
    """
    orbits = None
    polarization = None
    reference_path = None
    secondary_path = None
    reference_metadata = None
    secondary_metadata = None
    reference_state_vec = None
    secondary_state_vec = None
    lat_limits, lon_limits = None, None

    platform = get_platform(reference)
    if platform == 'S1':
        for scene in [reference, secondary]:
            scene_url = get_download_url(scene)
            download_file(scene_url, chunk_size=5242880)

        orbits = Path('Orbits').resolve()
        orbits.mkdir(parents=True, exist_ok=True)
        reference_state_vec, reference_provider = downloadSentinelOrbitFile(reference, directory=str(orbits))
        log.info(f'Downloaded orbit file {reference_state_vec} from {reference_provider}')
        secondary_state_vec, secondary_provider = downloadSentinelOrbitFile(secondary, directory=str(orbits))
        log.info(f'Downloaded orbit file {secondary_state_vec} from {secondary_provider}')

        polarization = get_s1_primary_polarization(reference)
        lat_limits, lon_limits = geometry.bounding_box(f'{reference}.zip', polarization=polarization, orbits=orbits)

    elif platform == 'S2':
        # Set config and env for new CXX threads in Geogrid/autoRIFT
        gdal.SetConfigOption('GDAL_DISABLE_READDIR_ON_OPEN', 'EMPTY_DIR')
        os.environ['GDAL_DISABLE_READDIR_ON_OPEN'] = 'EMPTY_DIR'

        gdal.SetConfigOption('AWS_REGION', 'us-west-2')
        os.environ['AWS_REGION'] = 'us-west-2'

        reference_metadata = get_s2_metadata(reference)
        secondary_metadata = get_s2_metadata(secondary)
        reference_path = reference_metadata['path']
        secondary_path = secondary_metadata['path']
        bbox = reference_metadata['bbox']
        lat_limits = (bbox[1], bbox[3])
        lon_limits = (bbox[0], bbox[2])

    elif 'L' in platform:
        # Set config and env for new CXX threads in Geogrid/autoRIFT
        gdal.SetConfigOption('GDAL_DISABLE_READDIR_ON_OPEN', 'EMPTY_DIR')
        os.environ['GDAL_DISABLE_READDIR_ON_OPEN'] = 'EMPTY_DIR'

        gdal.SetConfigOption('AWS_REGION', 'us-west-2')
        os.environ['AWS_REGION'] = 'us-west-2'

        gdal.SetConfigOption('AWS_REQUEST_PAYER', 'requester')
        os.environ['AWS_REQUEST_PAYER'] = 'requester'

        reference_metadata = get_lc2_metadata(reference)
        reference_path = get_lc2_path(reference_metadata)

        secondary_metadata = get_lc2_metadata(secondary)
        secondary_path = get_lc2_path(secondary_metadata)

        bbox = reference_metadata['bbox']
        lat_limits = (bbox[1], bbox[3])
        lon_limits = (bbox[0], bbox[2])

        if platform in ('L4', 'L5'):
            print('Running FFT')

            ref_array, ref_transform, ref_projection, ref_nodata = io.load_geospatial(reference_path)
            ref_filtered = apply_fft_filter(ref_array, ref_nodata)
            ref_new_path = create_fft_filepath(reference_path)
            reference_path = io.write_geospatial(ref_new_path, ref_filtered, ref_transform, ref_projection, nodata=0)

            sec_array, sec_transform, sec_projection, sec_nodata = io.load_geospatial(secondary_path)
            sec_filtered = apply_fft_filter(sec_array, sec_nodata)
            sec_new_path = create_fft_filepath(secondary_path)
            secondary_path = io.write_geospatial(sec_new_path, sec_filtered, sec_transform, sec_projection, nodata=0)

    log.info(f'Reference scene path: {reference_path}')
    log.info(f'Secondary scene path: {secondary_path}')

    scene_poly = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = io.find_jpl_parameter_info(scene_poly, parameter_file)

    if platform == 'S1':
        isce_dem = geometry.prep_isce_dem(parameter_info['geogrid']['dem'], lat_limits, lon_limits)

        io.format_tops_xml(reference, secondary, polarization, isce_dem, orbits)

        import isce  # noqa
        from topsApp import TopsInSAR
        insar = TopsInSAR(name='topsApp', cmdline=['topsApp.xml', '--end=mergebursts'])
        insar.configure()
        insar.run()

        reference_path = os.path.join(os.getcwd(), 'merged', 'reference.slc.full')
        secondary_path = os.path.join(os.getcwd(), 'merged', 'secondary.slc.full')

        for slc in [reference_path, secondary_path]:
            gdal.Translate(slc, f'{slc}.vrt', format='ENVI')

        from hyp3_autorift.vend.testGeogrid_ISCE import loadMetadata, runGeogrid
        meta_r = loadMetadata('fine_coreg')
        meta_s = loadMetadata('secondary')
        geogrid_info = runGeogrid(meta_r, meta_s, epsg=parameter_info['epsg'], **parameter_info['geogrid'])

        # NOTE: After Geogrid is run, all drivers are no longer registered.
        #       I've got no idea why, or if there are other affects...
        gdal.AllRegister()

        from hyp3_autorift.vend.testautoRIFT_ISCE import generateAutoriftProduct
        netcdf_file = generateAutoriftProduct(
            reference_path, secondary_path, nc_sensor=platform, optical_flag=False, ncname=None,
            geogrid_run_info=geogrid_info, **parameter_info['autorift'],
            parameter_file=DEFAULT_PARAMETER_FILE.replace('/vsicurl/', ''),
        )

    else:
        from hyp3_autorift.vend.testGeogridOptical import coregisterLoadMetadata, runGeogrid
        meta_r, meta_s = coregisterLoadMetadata(
            reference_path, secondary_path,
            reference_metadata=reference_metadata,
            secondary_metadata=secondary_metadata,
        )
        geogrid_info = runGeogrid(meta_r, meta_s, epsg=parameter_info['epsg'], **parameter_info['geogrid'])

        from hyp3_autorift.vend.testautoRIFT import generateAutoriftProduct
        netcdf_file = generateAutoriftProduct(
            reference_path, secondary_path, nc_sensor=platform, optical_flag=True, ncname=None,
            reference_metadata=reference_metadata, secondary_metadata=secondary_metadata,
            geogrid_run_info=geogrid_info, **parameter_info['autorift'],
            parameter_file=DEFAULT_PARAMETER_FILE.replace('/vsicurl/', ''),
        )

    if netcdf_file is None:
        raise Exception('Processing failed! Output netCDF file not found')

    if naming_scheme == 'ITS_LIVE_PROD':
        product_file = Path(netcdf_file)
    elif naming_scheme == 'ASF':
        product_name = get_product_name(
            reference, secondary, orbit_files=(reference_state_vec, secondary_state_vec),
            pixel_spacing=parameter_info['xsize'],
        )
        product_file = Path(f'{product_name}.nc')
        shutil.move(netcdf_file, str(product_file))
    else:
        product_file = Path(netcdf_file.replace('.nc', '_IL_ASF_OD.nc'))
        shutil.move(netcdf_file, str(product_file))

    with Dataset(product_file) as nc:
        velocity = nc.variables['v']
        data = np.ma.masked_values(velocity, -32767.).filled(0)

    browse_file = product_file.with_suffix('.png')
    image.make_browse(browse_file, data)

    return product_file, browse_file


def main():
    """Main entrypoint"""
    parser = argparse.ArgumentParser(
        prog=os.path.basename(__file__),
        description=__doc__,
    )
    parser.add_argument('reference', type=os.path.abspath,
                        help='Reference Sentinel-1, Sentinel-2, or Landsat-8 Collection 2 scene')
    parser.add_argument('secondary', type=os.path.abspath,
                        help='Secondary Sentinel-1, Sentinel-2, or Landsat-8 Collection 2 scene')
    args = parser.parse_args()

    process(**args.__dict__)


if __name__ == "__main__":
    main()
