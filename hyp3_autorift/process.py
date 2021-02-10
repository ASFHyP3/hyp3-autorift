"""
Package for processing with autoRIFT
"""

import argparse
import glob
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from secrets import token_hex
from typing import Optional

import numpy as np
import requests
from hyp3lib.execute import execute
from hyp3lib.fetch import download_file
from hyp3lib.file_subroutines import mkdir_p
from hyp3lib.get_orb import downloadSentinelOrbitFile
from hyp3lib.scene import get_download_url
from netCDF4 import Dataset

from hyp3_autorift import geometry
from hyp3_autorift import image
from hyp3_autorift import io

log = logging.getLogger(__name__)

S2_SEARCH_URL = 'https://earth-search.aws.element84.com/v0/collections/sentinel-s2-l1c/items'
LC2_SEARCH_URL = 'https://landsatlook.usgs.gov/sat-api/collections/landsat-c2l1/items'

DEFAULT_PARAMETER_FILE = '/vsicurl/http://its-live-data.jpl.nasa.gov.s3.amazonaws.com/' \
                         'autorift_parameters/v001/autorift_parameters.shp'


def get_lc2_metadata(scene_name):
    response = requests.get(f'{LC2_SEARCH_URL}/{scene_name}')
    response.raise_for_status()
    return response.json()


def get_s2_metadata(scene_name):
    response = requests.get(f'{S2_SEARCH_URL}/{scene_name}')
    response.raise_for_status()

    if response.json().get('code') != 404:
        return response.json()

    payload = {
        'query': {
            'sentinel:product_id': {
                'eq': scene_name,
            }
        }
    }
    response = requests.post(S2_SEARCH_URL, json=payload)
    response.raise_for_status()
    if not response.json().get('numberReturned'):
        raise ValueError(f'Scene could not be found: {scene_name}')
    return response.json()['features'][0]


def least_precise_orbit_of(orbits):
    if any([orb is None for orb in orbits]):
        return 'O'
    if any(['RESORB' in orb for orb in orbits]):
        return 'R'
    return 'P'


def get_datetime(scene_name):
    if scene_name.startswith('S1'):
        return datetime.strptime(scene_name[17:32], '%Y%m%dT%H%M%S')
    if scene_name.startswith('S2') and len(scene_name) > 24:  # ESA
        return datetime.strptime(scene_name[11:26], '%Y%m%dT%H%M%S')
    if scene_name.startswith('S2'):  # COG
        return datetime.strptime(scene_name.split('_')[2], '%Y%m%d')
    if scene_name.startswith('L'):
        return datetime.strptime(scene_name[17:25], '%Y%m%d')

    raise ValueError(f'Unsupported scene format: {scene_name}')


def get_product_name(reference_name, secondary_name, orbit_files=None, pixel_spacing=240, band=None):
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
        misc = band.ljust(3, '-')

    product_id = token_hex(2).upper()

    return f'{mission}{plat1}{plat2}_{datetime1}_{datetime2}_{misc}{days:03}_VEL{pixel_spacing}_A_{product_id}'


def get_platform(scene: str) -> str:
    if scene.startswith('S1') or scene.startswith('S2'):
        return scene[0:2]
    elif scene.startswith('L'):
        return scene[0]
    else:
        raise NotImplementedError(f'autoRIFT processing not available for this platform. {scene}')


def get_bucket(platform: str) -> Optional[str]:
    if platform == 'S2':
        return 'sentinel-s2-l1c'
    elif platform == 'L':
        return 'usgs-landsat'
    return


def get_s1_primary_polarization(granule_name):
    polarization = granule_name[14:16]
    if polarization in ['SV', 'DV']:
        return 'vv'
    if polarization in ['SH', 'DH']:
        return 'hh'
    raise ValueError(f'Cannot determine co-polarization of granule {granule_name}')


def process(reference: str, secondary: str, parameter_file: str = DEFAULT_PARAMETER_FILE,
            naming_scheme: str = 'ITS_LIVE_OD', band: str = 'B08') -> Path:
    """Process a Sentinel-1, Sentinel-2, or Landsat-8 image pair

    Args:
        reference: Name of the reference Sentinel-1, Sentinel-2, or Landsat-8 Collection 2 scene
        secondary: Name of the secondary Sentinel-1, Sentinel-2, or Landsat-8 Collection 2 scene
        parameter_file: Shapefile for determining the correct search parameters by geographic location
        naming_scheme: Naming scheme to use for product files
        band: Band to process for Sentinel-2 or Landsat-8 Collection 2 scenes
    """

    orbits = None
    polarization = None
    reference_path = None
    secondary_path = None
    reference_state_vec = None
    secondary_state_vec = None
    lat_limits, lon_limits = None, None
    platform = get_platform(reference)
    bucket = get_bucket(platform)

    if platform == 'S1':
        for scene in [reference, secondary]:
            scene_url = get_download_url(scene)
            download_file(scene_url, chunk_size=5242880)

        orbits = Path('Orbits').resolve()
        mkdir_p(orbits)
        reference_state_vec, reference_provider = downloadSentinelOrbitFile(reference, directory=orbits)
        log.info(f'Downloaded orbit file {reference_state_vec} from {reference_provider}')
        secondary_state_vec, secondary_provider = downloadSentinelOrbitFile(secondary, directory=orbits)
        log.info(f'Downloaded orbit file {secondary_state_vec} from {secondary_provider}')

        polarization = get_s1_primary_polarization(reference)
        lat_limits, lon_limits = geometry.bounding_box(f'{reference}.zip', polarization=polarization, orbits=orbits)

    elif platform == 'S2':
        reference_metadata = get_s2_metadata(reference)
        reference = reference_metadata['properties']['sentinel:product_id']
        reference_url = reference_metadata['assets'][band]['href']
        # FIXME: This is only because autoRIFT can't handle /vsis3/
        reference_url = reference_url.replace(f's3://{bucket}/', '')
        reference_path = Path.cwd() / f'{reference}_{Path(reference_url).name}'  # file names are just band.jp2
        io.download_s3_file_requester_pays(reference_path, bucket, reference_url)

        secondary_metadata = get_s2_metadata(secondary)
        secondary = secondary_metadata['properties']['sentinel:product_id']
        secondary_url = secondary_metadata['assets'][band]['href']
        # FIXME: This is only because autoRIFT can't handle /vsis3/
        secondary_url = secondary_url.replace(f's3://{bucket}/', '')  # file names are just band.jp2
        secondary_path = Path.cwd() / f'{secondary}_{Path(secondary_url).name}'
        io.download_s3_file_requester_pays(secondary_path, bucket, secondary_url)

        bbox = reference_metadata['bbox']
        lat_limits = (bbox[1], bbox[3])
        lon_limits = (bbox[0], bbox[2])

    elif platform == 'L':
        if band == 'B08':
            band = 'B8'
        reference_metadata = get_lc2_metadata(reference)
        reference_url = reference_metadata['assets'][f'{band}.TIF']['href']
        # FIXME: This is only because autoRIFT can't handle /vsis3/
        reference_url = reference_url.replace('https://landsatlook.usgs.gov/data/', '')
        reference_path = Path.cwd() / Path(reference_url).name
        io.download_s3_file_requester_pays(reference_path, bucket, reference_url)

        secondary_metadata = get_lc2_metadata(secondary)
        secondary_url = secondary_metadata['assets'][f'{band}.TIF']['href']
        # FIXME: This is only because autoRIFT can't handle /vsis3/
        secondary_url = secondary_url.replace('https://landsatlook.usgs.gov/data/', '')
        secondary_path = Path.cwd() / Path(secondary_url).name
        io.download_s3_file_requester_pays(secondary_path, bucket, secondary_url)

        bbox = reference_metadata['bbox']
        lat_limits = (bbox[1], bbox[3])
        lon_limits = (bbox[0], bbox[2])

    scene_poly = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    tifs = io.subset_jpl_tifs(scene_poly, parameter_file, target_dir=Path.cwd())

    geogrid_parameters = f'-d {tifs["h"]} -ssm {tifs["StableSurface"]} ' \
                         f'-sx {tifs["dhdx"]} -sy {tifs["dhdy"]} ' \
                         f'-vx {tifs["vx0"]} -vy {tifs["vy0"]} ' \
                         f'-srx {tifs["vxSearchRange"]} -sry {tifs["vySearchRange"]} ' \
                         f'-csminx {tifs["xMinChipSize"]} -csminy {tifs["yMinChipSize"]} ' \
                         f'-csmaxx {tifs["xMaxChipSize"]} -csmaxy {tifs["yMaxChipSize"]}'
    autorift_parameters = '-g window_location.tif -o window_offset.tif -sr window_search_range.tif ' \
                          '-csmin window_chip_size_min.tif -csmax window_chip_size_max.tif ' \
                          '-vx window_rdr_off2vel_x_vec.tif -vy window_rdr_off2vel_y_vec.tif ' \
                          '-ssm window_stable_surface_mask.tif'

    if platform == 'S1':
        isce_dem = geometry.prep_isce_dem(tifs["h"], lat_limits, lon_limits)

        io.format_tops_xml(reference, secondary, polarization, isce_dem, orbits)

        with open('topsApp.txt', 'w') as f:
            cmd = '${ISCE_HOME}/applications/topsApp.py topsApp.xml --end=mergebursts'
            execute(cmd, logfile=f, uselogging=True)

        r_slc = os.path.join(os.getcwd(), 'merged', 'reference.slc.full')
        s_slc = os.path.join(os.getcwd(), 'merged', 'secondary.slc.full')

        with open('createImages.txt', 'w') as f:
            for slc in [r_slc, s_slc]:
                cmd = f'gdal_translate -of ENVI {slc}.vrt {slc}'
                execute(cmd, logfile=f, uselogging=True)

        with open('testGeogrid.txt', 'w') as f:
            cmd = f'testGeogrid_ISCE.py -r reference -s secondary {geogrid_parameters}'
            execute(cmd, logfile=f, uselogging=True)

        with open('testautoRIFT.txt', 'w') as f:
            cmd = f'testautoRIFT_ISCE.py -r {r_slc} -s {s_slc} {autorift_parameters} -nc S'
            execute(cmd, logfile=f, uselogging=True)

    else:
        with open('testGeogrid.txt', 'w') as f:
            cmd = f'testGeogridOptical.py -r {reference_path.name} -s {secondary_path.name} {geogrid_parameters} ' \
                  f'-urlflag 0'
            execute(cmd, logfile=f, uselogging=True)

        with open('testautoRIFT.txt', 'w') as f:
            cmd = f'testautoRIFT.py -r {reference_path.name} -s {secondary_path.name} {autorift_parameters} ' \
                  f'-nc {platform} -fo 1 -urlflag 0'
            execute(cmd, logfile=f, uselogging=True)

    netcdf_files = glob.glob('*.nc')
    if not netcdf_files:
        raise Exception('Processing failed! Output netCDF file not found')
    if len(netcdf_files) > 1:
        log.warning(f'Too many netCDF files found; using first:\n    {netcdf_files}')

    if naming_scheme == 'ITS_LIVE_PROD':
        product_file = Path(netcdf_files[0]).resolve()
    elif naming_scheme == 'ASF':
        product_name = get_product_name(
            reference, secondary, orbit_files=(reference_state_vec, secondary_state_vec), band=band
        )
        product_file = Path(f'{product_name}.nc').resolve()
        shutil.move(netcdf_files[0], str(product_file))
    else:
        product_file = Path(netcdf_files[0].replace('.nc', '_IL_ASF_OD.nc')).resolve()
        shutil.move(netcdf_files[0], str(product_file))

    with Dataset(product_file) as nc:
        velocity = nc.variables['v']
        data = np.ma.masked_values(velocity, -32767.).filled(0)
    image.make_browse(product_file.with_suffix('.png'), data)

    return product_file


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
    parser.add_argument('-b', '--band', default='B08',
                        help='Band to process for Sentinel-2 or Landsat-8 Collection 2 scenes')
    args = parser.parse_args()

    process(**args.__dict__)


if __name__ == "__main__":
    main()
