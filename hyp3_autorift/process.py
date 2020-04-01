#!/usr/bin/env python3
"""
Package for processing with autoRIFT ICSE
"""

import argparse
import logging
import os

from hyp3lib.execute import execute
from hyp3lib.file_subroutines import mkdir_p

from hyp3_autorift import geometry
from hyp3_autorift import io

log = logging.getLogger(__name__)


def process(master, slave, download=False, polarization='hh', orbits=None, aux=None, process_dir=None):
    """Process a Sentinel-1 image pair

    Args:
        master: Path to master Sentinel-1 SAFE zip archive
        slave: Path to slave Sentinel-1 SAFE zip archive
        download: If True, try and download the granules from ASF to the
            current working directory (default: False)
        polarization: Polarization of Sentinel-1 scene (default: 'hh')
        orbits: Path to the orbital files, otherwise, fetch them from ASF
            (default: None)
        aux: Path to the auxiliary orbital files, otherwise, fetch them from ASF
            (default: None)
        process_dir: Path to a directory for processing inside
            (default: None; use current working directory)
    """
    
    # Ensure we have absolute paths
    master = os.path.abspath(master)
    slave = os.path.abspath(slave)

    if not os.path.isfile(master) or not os.path.isfile(slave) and download:
        log.info('Downloading Sentinel-1 image pair')
        dl_file_list = 'download_list.csv'
        with open('download_list.csv', 'w') as f:
            f.write(f'{os.path.basename(master)}\n'
                    f'{os.path.basename(slave)}\n')

        execute(f'get_asf.py {dl_file_list}')
        os.rmdir('download')  # Really, get_asf.py should do this...

    # TODO: Fetch orbit and aux files

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
    args = parser.parse_args()

    process(**args.__dict__)


if __name__ == "__main__":
    main()
