import logging
import os
import sys
import textwrap
from pathlib import Path

import numpy as np
from hyp3lib.fetch import download_file
from hyp3lib.scene import get_download_url
from osgeo import gdal
from s1_orbits import fetch_for_scene

from hyp3_autorift import geometry, utils
from hyp3_autorift.s1 import get_s1_primary_polarization

log = logging.getLogger(__name__)


def process_sentinel1_with_isce2(reference, secondary, parameter_file):
    import isce  # noqa
    from topsApp import TopsInSAR
    from hyp3_autorift.vend.testGeogrid_ISCE import loadMetadata, runGeogrid
    from hyp3_autorift.vend.testautoRIFT_ISCE import generateAutoriftProduct

    for scene in [reference, secondary]:
        scene_url = get_download_url(scene)
        download_file(scene_url, chunk_size=5242880)

    orbits = Path('Orbits').resolve()
    orbits.mkdir(parents=True, exist_ok=True)

    reference_state_vec = fetch_for_scene(reference, dir=orbits)
    log.info(f'Downloaded orbit file {reference_state_vec} from s1-orbits')

    secondary_state_vec = fetch_for_scene(secondary, dir=orbits)
    log.info(f'Downloaded orbit file {secondary_state_vec} from s1-orbits')

    polarization = get_s1_primary_polarization(reference)
    lat_limits, lon_limits = bounding_box(f'{reference}.zip', polarization=polarization, orbits=str(orbits))

    scene_poly = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = utils.find_jpl_parameter_info(scene_poly, parameter_file)

    isce_dem = prep_isce_dem(parameter_info['geogrid']['dem'], lat_limits, lon_limits)
    format_tops_xml(reference, secondary, polarization, isce_dem, orbits)

    insar = TopsInSAR(name='topsApp', cmdline=['topsApp.xml', '--end=mergebursts'])
    insar.configure()
    insar.run()

    reference_path = os.path.join(os.getcwd(), 'merged', 'reference.slc.full')
    secondary_path = os.path.join(os.getcwd(), 'merged', 'secondary.slc.full')

    for slc in [reference_path, secondary_path]:
        gdal.Translate(slc, f'{slc}.vrt', format='ENVI')

    meta_r = loadMetadata('fine_coreg')
    meta_s = loadMetadata('secondary')
    geogrid_info = runGeogrid(meta_r, meta_s, epsg=parameter_info['epsg'], **parameter_info['geogrid'])

    # NOTE: After Geogrid is run, all drivers are no longer registered.
    #       I've got no idea why, or if there are other affects...
    gdal.AllRegister()

    netcdf_file = generateAutoriftProduct(
            reference_path, secondary_path, nc_sensor='S1', optical_flag=False, ncname=None,
            geogrid_run_info=geogrid_info, **parameter_info['autorift'],
            parameter_file=parameter_file.replace('/vsicurl/', ''),
        )
    return netcdf_file


class SysArgvManager:
    """Context manager to clear and reset sys.argv

    A bug in the ISCE2 Application class causes sys.argv to always be parsed when
    no options are proved, even when setting `cmdline=[]`, preventing programmatic use.
    """
    def __init__(self):
        self.argv = sys.argv.copy()

    def __enter__(self):
        sys.argv = sys.argv[:1]

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.argv = self.argv


def get_topsinsar_config():
    from isce.applications.topsApp import TopsInSAR
    with SysArgvManager():
        insar = TopsInSAR(name="topsApp")
        insar.configure()

    config_data = {}
    for name in ['reference', 'secondary']:
        scene = insar.__getattribute__(name)

        sensing_times = []
        for swath in range(1, 4):
            scene.configure()
            scene.swathNumber = swath
            scene.parse()
            sensing_times.append(
                (scene.product.sensingStart, scene.product.sensingStop)
            )

        sensing_start = min([sensing_time[0] for sensing_time in sensing_times])
        sensing_stop = max([sensing_time[1] for sensing_time in sensing_times])

        sensing_dt = (sensing_stop - sensing_start) / 2 + sensing_start

        config_data[f'{name}_filename'] = Path(scene.safe[0]).name
        config_data[f'{name}_dt'] = sensing_dt.strftime("%Y%m%dT%H:%M:%S.%f").rstrip('0')

    return config_data


def format_tops_xml(reference, secondary, polarization, dem, orbits, xml_file='topsApp.xml'):
    xml_template = f"""    <?xml version="1.0" encoding="UTF-8"?>
    <topsApp>
        <component name="topsinsar">
            <component name="reference">
                <property name="orbit directory">{orbits}</property>
                <property name="auxiliary data directory">{orbits}</property>
                <property name="output directory">reference</property>
                <property name="safe">['{reference}.zip']</property>
                <property name="polarization">{polarization}</property>
            </component>
            <component name="secondary">
                <property name="orbit directory">{orbits}</property>
                <property name="auxiliary data directory">{orbits}</property>
                <property name="output directory">secondary</property>
                <property name="safe">['{secondary}.zip']</property>
                <property name="polarization">{polarization}</property>
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


def bounding_box(safe, priority='reference', polarization='hh', orbits='Orbits', epsg=4326):
    """Determine the geometric bounding box of a Sentinel-1 image

    :param safe: Path to the Sentinel-1 SAFE zip archive
    :param priority: Image priority, either 'reference' (default) or 'secondary'
    :param polarization: Image polarization (default: 'hh')
    :param orbits: Path to the orbital files (default: './Orbits')
    :param epsg: Projection EPSG code (default: 4326)

    :return: lat_limits (list), lon_limits (list)
        lat_limits: list containing the [minimum, maximum] latitudes
        lat_limits: list containing the [minimum, maximum] longitudes
    """
    import isce  # noqa: F401
    from contrib.geo_autoRIFT.geogrid import Geogrid
    from isceobj.Orbit.Orbit import Orbit
    from isceobj.Sensor.TOPS.Sentinel1 import Sentinel1
    frames = []
    for swath in range(1, 4):
        rdr = Sentinel1()
        rdr.configure()
        rdr.safe = [os.path.abspath(safe)]
        rdr.output = priority
        rdr.orbitDir = os.path.abspath(orbits)
        rdr.auxDir = os.path.abspath(orbits)
        rdr.swathNumber = swath
        rdr.polarization = polarization
        rdr.parse()
        frames.append(rdr.product)

    first_burst = frames[0].bursts[0]
    sensing_start = min([x.sensingStart for x in frames])
    sensing_stop = max([x.sensingStop for x in frames])
    starting_range = min([x.startingRange for x in frames])
    far_range = max([x.farRange for x in frames])
    range_pixel_size = first_burst.rangePixelSize
    prf = 1.0 / first_burst.azimuthTimeInterval

    orb = Orbit()
    orb.configure()

    for state_vector in first_burst.orbit:
        orb.addStateVector(state_vector)

    for frame in frames:
        for burst in frame.bursts:
            for state_vector in burst.orbit:
                if state_vector.time < orb.minTime or state_vector.time > orb.maxTime:
                    orb.addStateVector(state_vector)

    obj = Geogrid()
    obj.configure()

    obj.startingRange = starting_range
    obj.rangePixelSize = range_pixel_size
    obj.sensingStart = sensing_start
    obj.prf = prf
    obj.lookSide = -1
    obj.numberOfLines = int(np.round((sensing_stop - sensing_start).total_seconds() * prf))
    obj.numberOfSamples = int(np.round((far_range - starting_range)/range_pixel_size))
    obj.orbit = orb
    obj.epsg = epsg

    obj.determineBbox()

    lat_limits = obj._xlim
    lon_limits = obj._ylim

    log.info(f'Latitude limits [min, max]: {lat_limits}')
    log.info(f'Longitude limits [min, max]: {lon_limits}')

    return lat_limits, lon_limits


def prep_isce_dem(input_dem, lat_limits, lon_limits, isce_dem=None):
    import isce  # noqa: F401
    import isceobj
    from contrib.demUtils import createDemStitcher

    if isce_dem is None:
        seamstress = createDemStitcher()
        isce_dem = seamstress.defaultName([*lat_limits, *lon_limits])

    isce_dem = os.path.abspath(isce_dem + '.wgs84')
    log.info(f'ISCE dem is: {isce_dem}')

    in_ds = gdal.OpenShared(input_dem, gdal.GA_ReadOnly)
    warp_options = gdal.WarpOptions(
        format='ENVI', outputType=gdal.GDT_Int16, resampleAlg='cubic',
        xRes=0.001, yRes=0.001, dstSRS='EPSG:4326', dstNodata=0,
        outputBounds=[lon_limits[0], lat_limits[0], lon_limits[1], lat_limits[1]]
    )
    gdal.Warp(isce_dem, in_ds, options=warp_options)

    del in_ds

    isce_ds = gdal.Open(isce_dem, gdal.GA_ReadOnly)
    isce_trans = isce_ds.GetGeoTransform()

    img = isceobj.createDemImage()
    img.width = isce_ds.RasterXSize
    img.length = isce_ds.RasterYSize
    img.bands = 1
    img.dataType = 'SHORT'
    img.scheme = 'BIL'
    img.setAccessMode('READ')
    img.filename = isce_dem

    img.firstLongitude = isce_trans[0] + 0.5 * isce_trans[1]
    img.deltaLongitude = isce_trans[1]

    img.firstLatitude = isce_trans[3] + 0.5 * isce_trans[5]
    img.deltaLatitude = isce_trans[5]
    img.renderHdr()

    return isce_dem
