"""Helper io uilities for autoRIFT"""

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
    'ANT240m_vx0.tif',
    'ANT240m_vy0.tif',
    'GRE240m_dhdx.tif',
    'GRE240m_dhdy.tif',
    'GRE240m_h.tif',
    'GRE240m_vx0.tif',
    'GRE240m_vy0.tif',
]


def _request_file(url_file_map):
    url, path = url_file_map
    if not os.path.exists(path):
        response = requests.get(url)
        if response.status_code == 200:
            with open(path, 'wb') as f:
                for chunck in response:
                    f.write(chunck)
    return path


def fetch_jpl_tifs(dem_dir='DEM', endpoint_url='http://jpl.nasa.gov.s3.amazonaws.com/',
                   bucket='its-live-data', prefix='isce_autoRIFT'):
    # FIXME: Can't figure out how to get these tifs with boto3, so using requests
    # import boto3
    # from botocore import UNSIGNED
    # from botocore.client import Config
    # s3 = boto3.client('s3', endpoint_url=endpoint_url, config=Config(signature_version=UNSIGNED))
    # with open('ANT240m_landice.tif', 'wb') as f:
    #     s3.download_fileobj('its-live-data', 'isce_autoRIFT/ANT240m_landice.tif', f)

    log.info("Downloading tifs from JPL's AWS bucket")
    mkdir_p(dem_dir)
    url_file_map = [
        (endpoint_url.replace('http://', f'http://{bucket}.') + f'{prefix}/{file}',
         os.path.join(dem_dir, file)) for file in _FILE_LIST
    ]

    pool = Pool(5)
    fetched = pool.imap_unordered(_request_file, url_file_map)
    pool.close()
    pool.join()

    log.info(f'Downloaded: {fetched}')


def format_tops_xml(master, slave, polarization, dem, orbits, aux, xml_file='topsApp.xml'):
    xml_template = f"""    <?xml version="1.0" encoding="UTF-8"?>
    <topsApp>
        <component name="topsinsar">
            <component name="master">
                <property name="orbit directory">{orbits}</property>
                <property name="auxiliary data directory">{aux}</property>
                <property name="output directory">master</property>
                <property name="safe">['{master}']</property>
                <property name="polarization">{polarization}</property>
            </component>
            <component name="slave">
                <property name="orbit directory">{orbits}</property>
                <property name="auxiliary data directory">{aux}</property>
                <property name="output directory">slave</property>
                <property name="safe">['{slave}']</property>
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
    master_filename = os.path.basename(insar.master.safe[0])
    slave_filename = os.path.basename(insar.slave.safe[0])

    log.info(f'master: {master_filename}')
    log.info(f'slave: {slave_filename}')

    savemat(
        'topsinsar_filename.mat', {'master_filename': master_filename, 'slave_filename': slave_filename}
    )
