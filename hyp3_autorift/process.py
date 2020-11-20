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

_PRODUCT_LIST = [
    'offset.tif',
    'velocity.tif',
    'velocity_browse.tif',
    'velocity_browse.kmz',
    'velocity_browse.png',
    'velocity_browse.png.aux.xml',
    'window_chip_size_max.tif',
    'window_chip_size_min.tif',
    'window_location.tif',
    'window_offset.tif',
    'window_rdr_off2vel_x_vec.tif',
    'window_rdr_off2vel_y_vec.tif',
    'window_search_range.tif',
    'window_stable_surface_mask.tif',
]


def get_s2_metadata(scene_name):
    search_url = 'https://earth-search.aws.element84.com/v0/collections/sentinel-s2-l2a-cogs/items'
    payload = {
        'query': {
            'sentinel:product_id': {
                'eq': scene_name,
            }
        }
    }
    response = requests.post(search_url, json=payload)
    response.raise_for_status()
    return response.json()['features'][0]


def least_precise_orbit_of(orbits):
    if any([orb is None for orb in orbits]):
        return 'O'
    if any(['RESORB' in orb for orb in orbits]):
        return 'R'
    return 'P'


def get_product_name(reference_name, secondary_name, orbit_files, pixel_spacing=240):
    mission = reference_name[0:2]
    plat1 = reference_name[2]
    plat2 = secondary_name[2]

    datetime1 = reference_name[17:32]
    datetime2 = secondary_name[17:32]

    ref_datetime = datetime.strptime(datetime1, '%Y%m%dT%H%M%S')
    sec_datetime = datetime.strptime(datetime2, '%Y%m%dT%H%M%S')
    days = abs((ref_datetime - sec_datetime).days)

    pol1 = reference_name[15:16]
    pol2 = secondary_name[15:16]
    orb = least_precise_orbit_of(orbit_files)
    product_id = token_hex(2).upper()

    return f'{mission}{plat1}{plat2}_{datetime1}_{datetime2}_{pol1}{pol2}{orb}{days:03}_VEL{pixel_spacing}' \
           f'_A_{product_id}'


def process(reference: str, secondary: str, polarization: str = 'hh', band: str = 'B03') -> Path:
    """Process a Sentinel-1, Sentinel-2, or Landsat image pair

    Args:
        reference: Name of the reference Sentinel-1, Sentinel-2, or Landsat scene
        secondary: Name of the secondary Sentinel-1, Sentinel-2, or Landsat scene
        polarization: Polarization to process for Sentinel-1 scenes, one of 'hh', 'hv', 'vv', or 'vh'
        band: Band to process for Landsat scenes
    """

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

        reference_url = reference_metadata['assets'][band]['href']
        secondary_url = get_s2_metadata(secondary)['assets'][band]['href']

        bbox = reference_metadata['bbox']
        lat_limits = (bbox[1], bbox[3])
        lon_limits = (bbox[0], bbox[2])

    dem = geometry.find_jpl_dem(lat_limits, lon_limits)
    if reference.startswith('S1'):
        dem_dir = os.path.join(os.getcwd(), 'DEM')
        mkdir_p(dem_dir)
        io.fetch_jpl_tifs(ice_sheet=dem[:3], target_dir=dem_dir)
        dem_file = os.path.join(dem_dir, dem)
    else:
        dem_file = f'http://{io.ITS_LIVE_BUCKET}.s3.amazonaws.com/{io.AUTORIFT_PREFIX}/{dem}'  # TODO move this to find_jpl_dem?

    in_file_base = dem_file.replace('_h.tif', '')
    geogrid_parameters = f'-d {dem_file} -ssm {in_file_base}_StableSurface.tif ' \
                         f'-sx {in_file_base}_dhdx.tif -sy {in_file_base}_dhdy.tif ' \
                         f'-vx {in_file_base}_vx0.tif -vy {in_file_base}_vy0.tif ' \
                         f'-srx {in_file_base}_vxSearchRange.tif -sry {in_file_base}_vySearchRange.tif ' \
                         f'-csminx {in_file_base}_xMinChipSize.tif -csminy {in_file_base}_yMinChipSize.tif ' \
                         f'-csmaxx {in_file_base}_xMaxChipSize.tif -csmaxy {in_file_base}_yMaxChipSize.tif'
    autorift_parameters = '-g window_location.tif -o window_offset.tif -sr window_search_range.tif ' \
                          '-csmin window_chip_size_min.tif -csmax window_chip_size_max.tif ' \
                          '-vx window_rdr_off2vel_x_vec.tif -vy window_rdr_off2vel_y_vec.tif ' \
                          '-ssm window_stable_surface_mask.tif'

    if reference.startswith('S1'):
        isce_dem = geometry.prep_isce_dem(dem_file, lat_limits, lon_limits)

        io.format_tops_xml(reference, secondary, polarization, isce_dem, orbits)

        with open('topsApp.txt', 'w') as f:
            cmd = '${ISCE_HOME}/applications/topsApp.py topsApp.xml --steps --end=mergebursts'
            execute(cmd, logfile=f, uselogging=True)

        m_slc = os.path.join(os.getcwd(), 'merged', 'reference.slc.full')
        s_slc = os.path.join(os.getcwd(), 'merged', 'secondary.slc.full')

        with open('createImages.txt', 'w') as f:
            for slc in [m_slc, s_slc]:
                cmd = f'gdal_translate -of ENVI {slc}.vrt {slc}'
                execute(cmd, logfile=f, uselogging=True)

        with open('testGeogrid.txt', 'w') as f:
            cmd = f'testGeogrid_ISCE.py -r reference -s secondary {geogrid_parameters}'
            execute(cmd, logfile=f, uselogging=True)

        with open('testautoRIFT.txt', 'w') as f:
            cmd = f'testautoRIFT_ISCE.py -r {m_slc} -s {s_slc} {autorift_parameters} -nc S'
            execute(cmd, logfile=f, uselogging=True)

    else:
        with open('testGeogrid.txt', 'w') as f:
            cmd = f'testGeogridOptical.py -m {reference_url} -s {secondary_url} {geogrid_parameters} -urlflag 1'
            execute(cmd, logfile=f, uselogging=True)

        with open('testautoRIFT.txt', 'w') as f:
            cmd = f'testautoRIFT.py -m {reference_url} -s {secondary_url} {autorift_parameters} -nc S2 -fo 1 -url'
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

    product_name = get_product_name(reference, secondary, (reference_state_vec, secondary_state_vec))  # TODO fix for S2
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
