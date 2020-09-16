"""Helper io utilities for autoRIFT"""

import argparse
import logging
import os
import textwrap
from multiprocessing.dummy import Pool

import requests
from hyp3lib.file_subroutines import mkdir_p
from isce.applications.topsApp import TopsInSAR
from scipy.io import savemat

log = logging.getLogger(__name__)

_FILE_LIST = [
    'ANT240m_dhdx.tif',
    'ANT240m_dhdy.tif',
    'ANT240m_h.tif',
    'ANT240m_StableSurface.tif',
    'ANT240m_vx0.tif',
    'ANT240m_vxSearchRange.tif',
    'ANT240m_vy0.tif',
    'ANT240m_vySearchRange.tif',
    'ANT240m_xMaxChipSize.tif',
    'ANT240m_xMinChipSize.tif',
    'ANT240m_yMaxChipSize.tif',
    'ANT240m_yMinChipSize.tif',
    'GRE240m_dhdx.tif',
    'GRE240m_dhdy.tif',
    'GRE240m_h.tif',
    'GRE240m_StableSurface.tif',
    'GRE240m_vx0.tif',
    'GRE240m_vxSearchRange.tif',
    'GRE240m_vy0.tif',
    'GRE240m_vySearchRange.tif',
    'GRE240m_xMaxChipSize.tif',
    'GRE240m_xMinChipSize.tif',
    'GRE240m_yMaxChipSize.tif',
    'GRE240m_yMinChipSize.tif',
]


def _request_file(url_file_map):
    url, path = url_file_map
    if not os.path.exists(path):
        response = requests.get(url)
        if response.status_code == 200:
            with open(path, 'wb') as f:
                for chunk in response:
                    f.write(chunk)
    return path


def fetch_jpl_tifs(dem_dir='DEM', endpoint_url='http://jpl.nasa.gov.s3.amazonaws.com/',
                   bucket='its-live-data', prefix='isce_autoRIFT', match=None):
    log.info("Downloading tifs from JPL's AWS bucket")
    mkdir_p(dem_dir)

    if match:
        file_list = [file for file in _FILE_LIST if match in file]
    else:
        file_list = _FILE_LIST

    url_file_map = [
        (endpoint_url.replace('http://', f'http://{bucket}.') + f'{prefix}/{file}',
         os.path.join(dem_dir, file)) for file in file_list
    ]

    pool = Pool(5)
    fetched = pool.imap_unordered(_request_file, url_file_map)
    pool.close()
    pool.join()

    log.info(f'Downloaded: {fetched}')


def format_tops_xml(reference, secondary, polarization, dem, orbits, aux, xml_file='topsApp.xml'):
    xml_template = f"""    <?xml version="1.0" encoding="UTF-8"?>
    <topsApp>
        <component name="topsinsar">
            <component name="reference">
                <property name="orbit directory">{orbits}</property>
                <property name="auxiliary data directory">{aux}</property>
                <property name="output directory">reference</property>
                <property name="safe">['{reference}']</property>
                <property name="polarization">{polarization}</property>
            </component>
            <component name="secondary">
                <property name="orbit directory">{orbits}</property>
                <property name="auxiliary data directory">{aux}</property>
                <property name="output directory">secondary</property>
                <property name="safe">['{secondary}']</property>
                <property name="polarization">hh</property>
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
    reference_filename = os.path.basename(insar.reference.safe[0])
    secondary_filename = os.path.basename(insar.secondary.safe[0])

    log.info(f'reference: {reference_filename}')
    log.info(f'secondary: {secondary_filename}')

    savemat(
        'topsinsar_filename.mat', {'reference_filename': reference_filename, 'secondary_filename': secondary_filename}
    )


def topsinsar_mat():
    parser = argparse.ArgumentParser(
        prog=os.path.basename(__file__),
        description='Save the TopsApp InSAR configuration dictionary into a MATLAB file',
    )

    # just get a help option
    _ = parser.parse_args()

    save_topsinsar_mat()
