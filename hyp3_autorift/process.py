#!/usr/bin/env python3
"""
Package for processing with autoRIFT ICSE
"""

import argparse
import glob
import logging
import os
import shutil
import zipfile

from hyp3lib.execute import execute
from hyp3lib.file_subroutines import mkdir_p
from hyp3lib.get_orb import downloadSentinelOrbitFile
from lxml import etree

from hyp3_autorift import geometry
from hyp3_autorift import io

log = logging.getLogger(__name__)

_PRODUCT_LIST = [
    'offset.tif',
    'velocity.tif',
    'window_location.tif',
    'window_offset.tif',
    'window_rdr_off2vel_x_vec.tif',
    'window_rdr_off2vel_y_vec.tif',
]


def process(master, slave, download=False, polarization='hh', orbits=None, aux=None, process_dir=None, product=False):
    """Process a Sentinel-1 image pair

    Args:
        master: Path to master Sentinel-1 SAFE zip archive
        slave: Path to slave Sentinel-1 SAFE zip archive
        download: If True, try and download the granules from ASF to the
            current working directory (default: False)
        polarization: Polarization of Sentinel-1 scene (default: 'hh')
        orbits: Path to the orbital files, otherwise, fetch them from ASF
            (default: None)
        aux: Path to the auxiliary orbital files, otherwise, assume same as orbits
            (default: None)
        process_dir: Path to a directory for processing inside
            (default: None; use current working directory)
        product: Create a product directory in the current working directory with
            copies of the product-level files (no intermediate files; default: False)
    """

    # Ensure we have absolute paths
    master = os.path.abspath(master)
    slave = os.path.abspath(slave)

    product_dir = os.path.join(os.getcwd(), 'PRODUCT')

    if not os.path.isfile(master) or not os.path.isfile(slave) and download:
        log.info('Downloading Sentinel-1 image pair')
        dl_file_list = 'download_list.csv'
        with open('download_list.csv', 'w') as f:
            f.write(f'{os.path.basename(master)}\n'
                    f'{os.path.basename(slave)}\n')

        execute(f'get_asf.py {dl_file_list}')
        os.rmdir('download')  # Really, get_asf.py should do this...

    if orbits is None:
        orbits = os.path.abspath('Orbits')
        mkdir_p(orbits)
        master_state_vec, master_provider = downloadSentinelOrbitFile(master, directory=orbits)
        log.info(f'Downloaded orbit file {master_state_vec} from {master_provider}')
        slave_state_vec, slave_provider = downloadSentinelOrbitFile(slave, directory=orbits)
        log.info(f'Downloaded orbit file {slave_state_vec} from {slave_provider}')

    if aux is None:
        aux = orbits

    lat_limits, lon_limits = geometry.bounding_box(
        master, slave, orbits=orbits, aux=aux, polarization=polarization
    )

    # FIXME: Should integrate this functionality into hyp3lib.get_dem
    dem = geometry.find_jpl_dem(lat_limits, lon_limits, download=download)

    if process_dir:
        mkdir_p(process_dir)
        os.chdir(process_dir)

    dhdx = dem.replace('_h.tif', '_dhdx.tif')
    dhdy = dem.replace('_h.tif', '_dhdy.tif')
    vx = dem.replace('_h.tif', '_vx0.tif')
    vy = dem.replace('_h.tif', '_vy0.tif')

    isce_dem = geometry.prep_isce_dem(dem, lat_limits, lon_limits)

    io.format_tops_xml(master, slave, polarization, isce_dem, orbits, aux)

    with open('topsApp.txt', 'w') as f:
        cmd = '${ISCE_HOME}/applications/topsApp.py topsApp.xml --end=mergebursts'
        execute(cmd, logfile=f, uselogging=True)

    m_slc = os.path.join(os.getcwd(), 'merged', 'master.slc.full')
    s_slc = os.path.join(os.getcwd(), 'merged', 'slave.slc.full')

    with open('createImages.txt', 'w') as f:
        for slc in [m_slc, s_slc]:
            cmd = f'gdal_translate -of ENVI {slc}.vrt {slc}'
            execute(cmd, logfile=f, uselogging=True)

    with open('testGeogrid.txt', 'w') as f:
        cmd = f'testGeogrid_ISCE.py -m master -s slave -d {dem} -sx {dhdx} -sy {dhdy} -vx {vx} -vy {vy}'
        execute(cmd, logfile=f, uselogging=True)

    with open('testautoRIFT.txt', 'w') as f:
        cmd = f'testautoRIFT_ISCE.py ' \
              f'-m {m_slc} -s {s_slc} -g window_location.tif -o window_offset.tif ' \
              f'-vx window_rdr_off2vel_x_vec.tif -vy window_rdr_off2vel_y_vec.tif  -nc S'
        execute(cmd, logfile=f, uselogging=True)

    if product:
        mkdir_p(product_dir)
        for f in _PRODUCT_LIST:
            shutil.copyfile(f, os.path.join(product_dir, f))

        for f in glob.iglob('*.nc'):
            shutil.copyfile(f, os.path.join(product_dir, f))

        # NOTE: Not sure we need to get all this info...
        # with zipfile.ZipFile(master) as master_safe:
        #     annotation = [f for f in master_safe.namelist() if f.endswith('001.xml') and 'calibration' not in f][0]
        #     with master_safe.open(annotation) as xml:
        #         heading = float(etree.parse(xml).findtext('.//platformHeading'))
        #
        # with open('isce.log') as isce_log:
        #     for line in isce_log.readlines():
        #         FIXME: not in isce.log for autoRIFT
        #         if "subset.Overlap" in line and "start time" in line:
        #             # FIXME: Too many steps here and re module is overkill
        #             t = re.split('=', line)
        #             t = t[1].strip()
        #             print("Found utctime %s" % t)
        #             t = re.split(' ', t)
        #             s = re.split(":", t[1])
        #             utctime = ((int(s[0]) * 60 + int(s[1])) * 60) + float(s[2])
        #         FIXME: all three subswaths are found for autoRIFT, so need to handle that
        #         if "Bperp at midrange for first common burst" in line:
        #             t = re.split('=', line)
        #             baseline = t[1].strip()
        #             print("Found baseline %s" % baseline)
        #         FIXME: not in isce.log for autoRIFT
        #         if "geocode.Azimuth looks" in line:
        #             t = re.split('=', line)
        #             az_looks = t[1].strip()
        #             print("Found azimuth looks %s" % az_looks)
        #         FIXME: not in isce.log for autoRIFT
        #         if "geocode.Range looks" in line:
        #             t = re.split('=', line)
        #             rg_looks = t[1].strip()
        #             print("Found range looks %s" % rg_looks)


def main():
    """Main entrypoint"""
    parser = argparse.ArgumentParser(
        prog=os.path.basename(__file__),
        description=__doc__,
    )
    parser.add_argument('master', type=os.path.abspath,
                        help='Master Sentinel-1 SAFE zip archive')
    parser.add_argument('slave', type=os.path.abspath,
                        help='Slave Sentinel-1 SAFE zip archive')
    parser.add_argument('-d', '--download', action='store_true',
                        help='Download the granules from ASF to the current'
                             'working directory')
    parser.add_argument('-p', '--polarization', default='hh',
                        help='Polarization of the Sentinel-1 scenes')
    parser.add_argument('--orbits', type=os.path.abspath,
                        help='Path to the Sentinel-1 orbital files. If this argument'
                             'is not give, process will try and download them from ASF')
    parser.add_argument('--aux', type=os.path.abspath,
                        help='Path to the Sentinel-1 auxiliary orbital files. If this argument'
                             'is not give, process will try and download them from ASF')
    parser.add_argument('--process-dir', type=os.path.abspath,
                        help='If given, do processing inside this directory, otherwise, '
                             'use the current working directory')
    parser.add_argument('--product', action='store_true',
                        help='Create a product directory in the current working directory '
                             'with copies of the product-level files (no intermediate files)')
    args = parser.parse_args()

    process(**args.__dict__)


if __name__ == "__main__":
    main()
