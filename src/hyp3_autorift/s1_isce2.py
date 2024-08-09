import copy
import logging
import os
import sys
import textwrap
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

import numpy as np
from autoRIFT import __version__ as version
from hyp3lib.fetch import download_file
from hyp3lib.scene import get_download_url
from netCDF4 import Dataset
from osgeo import gdal, osr
from s1_orbits import fetch_for_scene

from hyp3_autorift import geometry, utils
from hyp3_autorift.process import DEFAULT_PARAMETER_FILE

log = logging.getLogger(__name__)


def get_s1_primary_polarization(granule_name):
    polarization = granule_name[14:16]
    if polarization in ['SV', 'DV']:
        return 'vv'
    if polarization in ['SH', 'DH']:
        return 'hh'
    raise ValueError(f'Cannot determine co-polarization of granule {granule_name}')


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


def write_conversion_file(
        *,
        file_name: str,
        srs: osr.SpatialReference,
        epsg: int,
        tran: List[float],
        x: np.ndarray,
        y: np.ndarray,
        M11: np.ndarray,
        M12: np.ndarray,
        dr_2_vr_factor: float,
        ChunkSize: List[int],
        NoDataValue: int = -32767,
        noDataMask: np.ndarray,
        parameter_file: str
) -> str:

    nc_outfile = Dataset(file_name, 'w', clobber=True, format='NETCDF4')

    nc_outfile.setncattr('GDAL_AREA_OR_POINT', 'Area')
    nc_outfile.setncattr('Conventions', 'CF-1.8')
    nc_outfile.setncattr('date_created', datetime.now().strftime("%d-%b-%Y %H:%M:%S"))
    nc_outfile.setncattr('title', 'autoRIFT S1 Corrections')
    nc_outfile.setncattr('autoRIFT_software_version', version)
    nc_outfile.setncattr('autoRIFT_parameter_file', parameter_file)

    nc_outfile.createDimension('x', len(x))
    nc_outfile.createDimension('y', len(y))

    var = nc_outfile.createVariable('x', np.dtype('float64'), 'x', fill_value=None)
    var.setncattr('standard_name', 'projection_x_coordinate')
    var.setncattr('description', 'x coordinate of projection')
    var.setncattr('units', 'm')
    var[:] = x

    var = nc_outfile.createVariable('y', np.dtype('float64'), 'y', fill_value=None)
    var.setncattr('standard_name', 'projection_y_coordinate')
    var.setncattr('description', 'y coordinate of projection')
    var.setncattr('units', 'm')
    var[:] = y

    mapping_var_name = 'mapping'
    var = nc_outfile.createVariable(mapping_var_name, 'U1', (), fill_value=None)
    if srs.GetAttrValue('PROJECTION') == 'Polar_Stereographic':
        var.setncattr('grid_mapping_name', 'polar_stereographic')
        var.setncattr('straight_vertical_longitude_from_pole', srs.GetProjParm('central_meridian'))
        var.setncattr('false_easting', srs.GetProjParm('false_easting'))
        var.setncattr('false_northing', srs.GetProjParm('false_northing'))
        var.setncattr('latitude_of_projection_origin', np.sign(srs.GetProjParm('latitude_of_origin')) * 90.0)
        var.setncattr('latitude_of_origin', srs.GetProjParm('latitude_of_origin'))
        var.setncattr('semi_major_axis', float(srs.GetAttrValue('GEOGCS|SPHEROID', 1)))
        var.setncattr('scale_factor_at_projection_origin', 1)
        var.setncattr('inverse_flattening', float(srs.GetAttrValue('GEOGCS|SPHEROID', 2)))
        var.setncattr('spatial_ref', srs.ExportToWkt())
        var.setncattr('crs_wkt', srs.ExportToWkt())
        var.setncattr('proj4text', srs.ExportToProj4())
        var.setncattr('spatial_epsg', epsg)
        var.setncattr('GeoTransform', ' '.join(str(x) for x in tran))

    elif srs.GetAttrValue('PROJECTION') == 'Transverse_Mercator':
        var.setncattr('grid_mapping_name', 'universal_transverse_mercator')
        zone = epsg - np.floor(epsg / 100) * 100
        var.setncattr('utm_zone_number', zone)
        var.setncattr('longitude_of_central_meridian', srs.GetProjParm('central_meridian'))
        var.setncattr('false_easting', srs.GetProjParm('false_easting'))
        var.setncattr('false_northing', srs.GetProjParm('false_northing'))
        var.setncattr('latitude_of_projection_origin', srs.GetProjParm('latitude_of_origin'))
        var.setncattr('semi_major_axis', float(srs.GetAttrValue('GEOGCS|SPHEROID', 1)))
        var.setncattr('scale_factor_at_central_meridian', srs.GetProjParm('scale_factor'))
        var.setncattr('inverse_flattening', float(srs.GetAttrValue('GEOGCS|SPHEROID', 2)))
        var.setncattr('spatial_ref', srs.ExportToWkt())
        var.setncattr('crs_wkt', srs.ExportToWkt())
        var.setncattr('proj4text', srs.ExportToProj4())
        var.setncattr('spatial_epsg', epsg)
        var.setncattr('GeoTransform', ' '.join(str(x) for x in tran))
    else:
        raise Exception(f'Projection {srs.GetAttrValue("PROJECTION")} not recognized for this program')

    var = nc_outfile.createVariable('M11', np.dtype('int16'), ('y', 'x'), fill_value=NoDataValue,
                                    zlib=True, complevel=2, shuffle=True, chunksizes=ChunkSize)
    var.setncattr('standard_name', 'conversion_matrix_element_11')
    var.setncattr(
        'description',
        'conversion matrix element (1st row, 1st column) that can be multiplied with vx to give range pixel '
        'displacement dr (see Eq. A18 in https://www.mdpi.com/2072-4292/13/4/749)'
    )
    var.setncattr('units', 'pixel/(meter/year)')
    var.setncattr('grid_mapping', mapping_var_name)
    var.setncattr('dr_to_vr_factor', dr_2_vr_factor)
    var.setncattr('dr_to_vr_factor_description', 'multiplicative factor that converts slant range '
                                                 'pixel displacement dr to slant range velocity vr')

    x1 = np.nanmin(M11[:])
    x2 = np.nanmax(M11[:])
    y1 = -50
    y2 = 50

    C = [(y2 - y1) / (x2 - x1), y1 - x1 * (y2 - y1) / (x2 - x1)]
    var.setncattr('scale_factor', np.float32(1 / C[0]))
    var.setncattr('add_offset', np.float32(-C[1] / C[0]))

    M11[noDataMask] = NoDataValue * np.float32(1 / C[0]) + np.float32(-C[1] / C[0])
    var[:] = M11

    var = nc_outfile.createVariable('M12', np.dtype('int16'), ('y', 'x'), fill_value=NoDataValue,
                                    zlib=True, complevel=2, shuffle=True, chunksizes=ChunkSize)
    var.setncattr('standard_name', 'conversion_matrix_element_12')
    var.setncattr(
        'description',
        'conversion matrix element (1st row, 2nd column) that can be multiplied with vy to give range pixel '
        'displacement dr (see Eq. A18 in https://www.mdpi.com/2072-4292/13/4/749)'
    )
    var.setncattr('units', 'pixel/(meter/year)')
    var.setncattr('grid_mapping', mapping_var_name)
    var.setncattr('dr_to_vr_factor', dr_2_vr_factor)
    var.setncattr('dr_to_vr_factor_description',
                  'multiplicative factor that converts slant range pixel displacement dr to slant range velocity vr')

    x1 = np.nanmin(M12[:])
    x2 = np.nanmax(M12[:])
    y1 = -50
    y2 = 50

    C = [(y2 - y1) / (x2 - x1), y1 - x1 * (y2 - y1) / (x2 - x1)]
    var.setncattr('scale_factor', np.float32(1 / C[0]))
    var.setncattr('add_offset', np.float32(-C[1] / C[0]))

    M12[noDataMask] = NoDataValue * np.float32(1 / C[0]) + np.float32(-C[1] / C[0])
    var[:] = M12

    nc_outfile.sync()
    nc_outfile.close()

    return file_name


def create_conversion_matrices(
        *,
        scene: str,
        grid_location: str = 'window_location.tif',
        offset2vx: str = 'window_rdr_off2vel_x_vec.tif',
        offset2vy: str = 'window_rdr_off2vel_y_vec.tif',
        scale_factor: str = 'window_scale_factor.tif',
        epsg: int = 4326,
        parameter_file: str = DEFAULT_PARAMETER_FILE,
        **kwargs,
) -> Path:
    xGrid, tran, _, srs, nodata = utils.load_geospatial(grid_location, band=1)

    offset2vy_1, _, _, _, _ = utils.load_geospatial(offset2vy, band=1)
    offset2vy_1[offset2vy_1 == nodata] = np.nan

    offset2vy_2, _, _, _, _ = utils.load_geospatial(offset2vy, band=2)
    offset2vy_2[offset2vy_2 == nodata] = np.nan

    offset2vx_1, _, _, _, _ = utils.load_geospatial(offset2vx, band=1)
    offset2vx_1[offset2vx_1 == nodata] = np.nan

    offset2vx_2, _, _, _, _ = utils.load_geospatial(offset2vx, band=2)
    offset2vx_2[offset2vx_2 == nodata] = np.nan

    offset2vr, _, _, _, _ = utils.load_geospatial(offset2vx, band=3)
    offset2vr[offset2vr == nodata] = np.nan

    scale_factor_1, _, _, _, _ = utils.load_geospatial(scale_factor, band=1)
    scale_factor_1[scale_factor_1 == nodata] = np.nan

    # GDAL using upper-left of pixel -> netCDF using center of pixel
    tran = [tran[0] + tran[1] / 2, tran[1], 0.0, tran[3] + tran[5] / 2, 0.0, tran[5]]

    dimidY, dimidX = xGrid.shape
    noDataMask = xGrid == nodata

    y = np.arange(tran[3], tran[3] + tran[5] * dimidY, tran[5])
    x = np.arange(tran[0], tran[0] + tran[1] * dimidX, tran[1])

    chunk_lines = np.min([np.ceil(8192 / dimidY) * 128, dimidY])
    ChunkSize = [chunk_lines, dimidX]

    M11 = offset2vy_2 / (offset2vx_1 * offset2vy_2 - offset2vx_2 * offset2vy_1) / scale_factor_1
    M12 = -offset2vx_2 / (offset2vx_1 * offset2vy_2 - offset2vx_2 * offset2vy_1) / scale_factor_1

    dr_2_vr_factor = np.median(offset2vr[np.logical_not(np.isnan(offset2vr))])

    conversion_nc = write_conversion_file(
        file_name='conversion_matrices.nc', srs=srs, epsg=epsg, tran=tran, x=x, y=y, M11=M11, M12=M12,
        dr_2_vr_factor=dr_2_vr_factor, ChunkSize=ChunkSize, noDataMask=noDataMask, parameter_file=parameter_file,
    )

    return Path(conversion_nc)


def generate_correction_data(
    scene: str,
    buffer: int = 0,
    parameter_file: str = DEFAULT_PARAMETER_FILE,
) -> (dict, Path):
    from hyp3_autorift.vend.testGeogrid_ISCE import loadParsedata, runGeogrid
    scene_path = Path(f'{scene}.zip')
    if not scene_path.exists():
        scene_url = get_download_url(scene)
        scene_path = download_file(scene_url, chunk_size=5242880)

    orbits = Path('Orbits').resolve()
    orbits.mkdir(parents=True, exist_ok=True)

    state_vec = fetch_for_scene(scene, dir=orbits)
    log.info(f'Downloaded orbit file {state_vec} from s1-orbits')

    polarization = get_s1_primary_polarization(scene)
    lat_limits, lon_limits = bounding_box(f'{scene}.zip', polarization=polarization, orbits=str(orbits))

    scene_poly = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = utils.find_jpl_parameter_info(scene_poly, parameter_file)

    isce_dem = prep_isce_dem(parameter_info['geogrid']['dem'], lat_limits, lon_limits)
    format_tops_xml(scene, scene, polarization, isce_dem, orbits)

    reference_meta = loadParsedata(str(scene_path), orbit_dir=orbits, aux_dir=orbits, buffer=buffer)

    secondary_meta = copy.deepcopy(reference_meta)
    spoof_dt = timedelta(days=1)
    secondary_meta.sensingStart += spoof_dt
    secondary_meta.sensingStop += spoof_dt

    geogrid_info = runGeogrid(reference_meta, secondary_meta, epsg=parameter_info['epsg'], **parameter_info['geogrid'])

    # NOTE: After Geogrid is run, all drivers are no longer registered.
    #       I've got no idea why, or if there are other effects...
    gdal.AllRegister()

    conversion_nc = create_conversion_matrices(
        scene=scene, epsg=parameter_info['epsg'], parameter_file=parameter_file, **parameter_info['autorift']
    )

    return geogrid_info, conversion_nc


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
