"""
Package for processing with autoRIFT
"""

import argparse
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from secrets import token_hex
from typing import Tuple

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

S2_SEARCH_URL = 'https://earth-search.aws.element84.com/v0/collections/sentinel-s2-l1c/items'
LC2_SEARCH_URL = 'https://landsatlook.usgs.gov/sat-api/collections/landsat-c2l1/items'

DEFAULT_PARAMETER_FILE = '/vsicurl/http://its-live-data.jpl.nasa.gov.s3.amazonaws.com/' \
                         'autorift_parameters/v001/autorift_landice_0120m.shp'


def get_lc2_metadata(scene_name):
    response = requests.get(f'{LC2_SEARCH_URL}/{scene_name}')
    response.raise_for_status()
    return response.json()


def get_s2_metadata(scene_name):
    response = requests.get(f'{S2_SEARCH_URL}/{scene_name}')
    try:
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError:
        if response.status_code != 404:
            raise

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


def get_s1_primary_polarization(granule_name):
    polarization = granule_name[14:16]
    if polarization in ['SV', 'DV']:
        return 'vv'
    if polarization in ['SH', 'DH']:
        return 'hh'
    raise ValueError(f'Cannot determine co-polarization of granule {granule_name}')


def process(reference: str, secondary: str, parameter_file: str = DEFAULT_PARAMETER_FILE,
            naming_scheme: str = 'ITS_LIVE_OD', band: str = 'B08') -> Tuple[Path, Path]:
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
        reference_state_vec, reference_provider = downloadSentinelOrbitFile(reference, directory=orbits)
        log.info(f'Downloaded orbit file {reference_state_vec} from {reference_provider}')
        secondary_state_vec, secondary_provider = downloadSentinelOrbitFile(secondary, directory=orbits)
        log.info(f'Downloaded orbit file {secondary_state_vec} from {secondary_provider}')

        polarization = get_s1_primary_polarization(reference)
        lat_limits, lon_limits = geometry.bounding_box(f'{reference}.zip', polarization=polarization, orbits=orbits)

    elif platform == 'S2':
        gdal.SetConfigOption('GDAL_DISABLE_READDIR_ON_OPEN', 'EMPTY_DIR')
        gdal.SetConfigOption('AWS_REQUEST_PAYER', 'requester')
        gdal.SetConfigOption('AWS_REGION', 'eu-central-1')

        reference_metadata = get_s2_metadata(reference)
        reference_path = reference_metadata['assets'][band]['href'].replace('s3://', '/vsis3/')

        secondary_metadata = get_s2_metadata(secondary)
        secondary_path = secondary_metadata['assets'][band]['href'].replace('s3://', '/vsis3/')

        bbox = reference_metadata['bbox']
        lat_limits = (bbox[1], bbox[3])
        lon_limits = (bbox[0], bbox[2])

    elif platform == 'L':
        gdal.SetConfigOption('GDAL_DISABLE_READDIR_ON_OPEN', 'EMPTY_DIR')
        gdal.SetConfigOption('AWS_REQUEST_PAYER', 'requester')
        gdal.SetConfigOption('AWS_REGION', 'us-west-2')

        if band == 'B08':
            band = 'B8'
        reference_metadata = get_lc2_metadata(reference)
        reference_path = reference_metadata['assets'][f'{band}.TIF']['href']
        reference_path = reference_path.replace('https://landsatlook.usgs.gov/data/', '/vsis3/usgs-landsat/')

        secondary_metadata = get_lc2_metadata(secondary)
        secondary_path = secondary_metadata['assets'][f'{band}.TIF']['href']
        secondary_path = secondary_path.replace('https://landsatlook.usgs.gov/data/', '/vsis3/usgs-landsat/')

        bbox = reference_metadata['bbox']
        lat_limits = (bbox[1], bbox[3])
        lon_limits = (bbox[0], bbox[2])

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
        meta_r = loadMetadata('reference')
        meta_s = loadMetadata('secondary')
        geogrid_info = runGeogrid(meta_r, meta_s, epsg=parameter_info['epsg'], **parameter_info['geogrid'])

        # NOTE: After Geogrid is run, all drivers are no longer registered.
        #       I've got no idea why, or if there are other affects...
        gdal.AllRegister()

        from hyp3_autorift.vend.testautoRIFT_ISCE import generateAutoriftProduct
        netcdf_file = generateAutoriftProduct(
            reference_path, secondary_path, nc_sensor=platform[0], optical_flag=False, ncname=None,
            geogrid_run_info=geogrid_info, **parameter_info['autorift'],
            parameter_file=parameter_file.replace('/vsicurl/', ''),
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
            parameter_file=parameter_file.replace('/vsicurl/', ''),
        )

    if netcdf_file is None:
        raise Exception('Processing failed! Output netCDF file not found')

    if naming_scheme == 'ITS_LIVE_PROD':
        product_file = Path(netcdf_file)
    elif naming_scheme == 'ASF':
        product_name = get_product_name(
            reference, secondary, orbit_files=(reference_state_vec, secondary_state_vec),
            band=band, pixel_spacing=parameter_info['xsize'],
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
    parser.add_argument('-b', '--band', default='B08',
                        help='Band to process for Sentinel-2 or Landsat-8 Collection 2 scenes')
    args = parser.parse_args()

    process(**args.__dict__)


if __name__ == "__main__":
    main()
