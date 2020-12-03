"""
Package for processing with autoRIFT ICSE
"""

import argparse
import glob
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from secrets import token_hex

import numpy as np
import requests
from hyp3lib.execute import execute
from hyp3lib.fetch import download_file
from hyp3lib.file_subroutines import mkdir_p
from hyp3lib.get_orb import downloadSentinelOrbitFile
from hyp3lib.makeAsfBrowse import makeAsfBrowse
from hyp3lib.scene import get_download_url
from osgeo import gdal

from hyp3_autorift import geometry
from hyp3_autorift import io

log = logging.getLogger(__name__)

SEARCH_URL = 'https://earth-search.aws.element84.com/v0/collections/sentinel-s2-l2a-cogs/items'


def get_s2_metadata(scene_name):
    response = requests.get(f'{SEARCH_URL}/{scene_name}')
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
    response = requests.post(SEARCH_URL, json=payload)
    response.raise_for_status()
    print(response.json())
    if response.json()['numberReturned'] == 0:
        raise ValueError(f'Scene could not be found: {scene_name}')
    print(response.json())
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
        return datetime.strptime(scene_name[10:18], '%Y%m%d')
    if scene_name.startswith('L'):
        return datetime.strptime(scene_name[17:25], '%Y%m%d')

    raise ValueError(f'Unsupported scene format: {scene_name}')


def get_product_name(reference_name, secondary_name, orbit_files=None, pixel_spacing=240, band=None):
    mission = reference_name[0:2]
    plat1 = reference_name[2]
    plat2 = secondary_name[2]

    ref_datetime = get_datetime(reference_name)
    sec_datetime = get_datetime(secondary_name)
    days = abs((ref_datetime - sec_datetime).days)

    if reference_name.startswith('S1'):
        polarization1 = reference_name[15:16]
        polarization2 = secondary_name[15:16]
        orbit = least_precise_orbit_of(orbit_files)
        misc = polarization1 + polarization2 + orbit
    else:
        misc = band

    product_id = token_hex(2).upper()

    return f'{mission}{plat1}{plat2}_{datetime1}_{datetime2}_{misc}{days:03}_VEL{pixel_spacing}_A_{product_id}'


def process(reference: str, secondary: str, polarization: str = 'hh', band: str = 'B08') -> Path:
    """Process a Sentinel-1, Sentinel-2, or Landsat image pair

    Args:
        reference: Name of the reference Sentinel-1, Sentinel-2, or Landsat 8 scene
        secondary: Name of the secondary Sentinel-1, Sentinel-2, or Landsat 8 scene
        polarization: Polarization to process for Sentinel-1 scenes, one of 'hh', 'hv', 'vv', or 'vh'
        band: Band to process for Sentinel-2 or Landsat 8 scenes
    """

    orbits = None
    reference_url = None
    secondary_url = None
    reference_state_vec = None
    secondary_state_vec = None

    if reference.startswith('S1'):
        for scene in [reference, secondary]:
            scene_url = get_download_url(scene)
            download_file(scene_url, chunk_size=5242880)

        orbits = Path('Orbits').resolve()
        mkdir_p(orbits)
        reference_state_vec, reference_provider = downloadSentinelOrbitFile(reference, directory=orbits)
        log.info(f'Downloaded orbit file {reference_state_vec} from {reference_provider}')
        secondary_state_vec, secondary_provider = downloadSentinelOrbitFile(secondary, directory=orbits)
        log.info(f'Downloaded orbit file {secondary_state_vec} from {secondary_provider}')

        lat_limits, lon_limits = geometry.bounding_box(f'{reference}.zip', orbits=orbits)

    else:
        reference_metadata = get_s2_metadata(reference)
        reference = reference_metadata['properties']['sentinel:product_id']
        reference_url = reference_metadata['assets'][band]['href']

        secondary_metadata = get_s2_metadata(secondary)
        secondary = secondary_metadata['properties']['sentinel:product_id']
        secondary_url = secondary_metadata['assets'][band]['href']

        bbox = reference_metadata['bbox']
        lat_limits = (bbox[1], bbox[3])
        lon_limits = (bbox[0], bbox[2])

    dem = geometry.find_jpl_dem(lat_limits, lon_limits)
    if reference.startswith('S1'):
        dem_dir = os.path.join(os.getcwd(), 'DEM')
        mkdir_p(dem_dir)
        io.fetch_jpl_tifs(dem=dem, target_dir=dem_dir)
        dem_prefix = os.path.join(dem_dir, dem)
    else:
        # TODO move this to find_jpl_dem?
        dem_prefix = f'http://{io.ITS_LIVE_BUCKET}.s3.amazonaws.com/{io.AUTORIFT_PREFIX}/{dem}'

    geogrid_parameters = f'-d {dem_prefix}_h.tif -ssm {dem_prefix}_StableSurface.tif ' \
                         f'-sx {dem_prefix}_dhdx.tif -sy {dem_prefix}_dhdy.tif ' \
                         f'-vx {dem_prefix}_vx0.tif -vy {dem_prefix}_vy0.tif ' \
                         f'-srx {dem_prefix}_vxSearchRange.tif -sry {dem_prefix}_vySearchRange.tif ' \
                         f'-csminx {dem_prefix}_xMinChipSize.tif -csminy {dem_prefix}_yMinChipSize.tif ' \
                         f'-csmaxx {dem_prefix}_xMaxChipSize.tif -csmaxy {dem_prefix}_yMaxChipSize.tif'
    autorift_parameters = '-g window_location.tif -o window_offset.tif -sr window_search_range.tif ' \
                          '-csmin window_chip_size_min.tif -csmax window_chip_size_max.tif ' \
                          '-vx window_rdr_off2vel_x_vec.tif -vy window_rdr_off2vel_y_vec.tif ' \
                          '-ssm window_stable_surface_mask.tif'

    if reference.startswith('S1'):
        isce_dem = geometry.prep_isce_dem(f'{dem_prefix}_h.tif', lat_limits, lon_limits)

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
            cmd = f'testGeogridOptical.py -r {reference_url} -s {secondary_url} {geogrid_parameters} -urlflag 1'
            execute(cmd, logfile=f, uselogging=True)

        with open('testautoRIFT.txt', 'w') as f:
            cmd = f'testautoRIFT.py -r {reference_url} -s {secondary_url} {autorift_parameters} -nc S2 -fo 1 -urlflag 1'
            execute(cmd, logfile=f, uselogging=True)

    velocity_tif = gdal.Open('velocity.tif')
    x_velocity = np.ma.masked_invalid(velocity_tif.GetRasterBand(1).ReadAsArray())
    y_velocity = np.ma.masked_invalid(velocity_tif.GetRasterBand(2).ReadAsArray())
    velocity = np.sqrt(x_velocity**2 + y_velocity**2)

    browse_file = Path('velocity_browse.tif')
    driver = gdal.GetDriverByName('GTiff')
    browse_tif = driver.Create(
        str(browse_file), velocity.shape[1], velocity.shape[0], 1, gdal.GDT_Byte, ['COMPRESS=LZW']
    )
    browse_tif.SetProjection(velocity_tif.GetProjection())
    browse_tif.SetGeoTransform(velocity_tif.GetGeoTransform())
    velocity_band = browse_tif.GetRasterBand(1)
    velocity_band.WriteArray(velocity)

    del velocity_band, browse_tif, velocity_tif

    product_name = get_product_name(reference, secondary, orbit_files=(reference_state_vec, secondary_state_vec),
                                    band=band)
    makeAsfBrowse(str(browse_file), product_name)

    netcdf_files = glob.glob('*.nc')
    if not netcdf_files:
        raise Exception('Processing failed! Output netCDF file not found')
    if len(netcdf_files) > 1:
        log.warning(f'Too many netCDF files found; using first:\n    {netcdf_files}')

    product_file = Path(f'{product_name}.nc').resolve()
    shutil.move(netcdf_files[0], f'{product_name}.nc')

    return product_file


def main():
    """Main entrypoint"""
    parser = argparse.ArgumentParser(
        prog=os.path.basename(__file__),
        description=__doc__,
    )
    parser.add_argument('reference', type=os.path.abspath,
                        help='Reference Sentinel-1 SAFE zip archive')
    parser.add_argument('secondary', type=os.path.abspath,
                        help='Secondary Sentinel-1 SAFE zip archive')
    parser.add_argument('-p', '--polarization', default='hh',
                        help='Polarization of the Sentinel-1 scenes')
    args = parser.parse_args()

    process(**args.__dict__)


if __name__ == "__main__":
    main()
