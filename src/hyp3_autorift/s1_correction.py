import argparse
import copy
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple

import numpy as np
from autoRIFT import __version__ as version
from hyp3lib.aws import upload_file_to_s3
from netCDF4 import Dataset
from osgeo import gdal, osr
from s1_orbits import fetch_for_scene

from hyp3_autorift import geometry, utils
from hyp3_autorift.process import DEFAULT_PARAMETER_FILE
from hyp3_autorift.s1 import get_s1_primary_polarization
from hyp3_autorift.s1_isce2 import _get_safe, bounding_box, format_tops_xml, prep_isce_dem


log = logging.getLogger(__name__)


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
    parameter_file: str,
) -> str:
    nc_outfile = Dataset(file_name, 'w', clobber=True, format='NETCDF4')

    nc_outfile.setncattr('GDAL_AREA_OR_POINT', 'Area')
    nc_outfile.setncattr('Conventions', 'CF-1.8')
    nc_outfile.setncattr('date_created', datetime.now().strftime('%d-%b-%Y %H:%M:%S'))
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

    var = nc_outfile.createVariable(
        'M11',
        np.dtype('float32'),
        ('y', 'x'),
        fill_value=NoDataValue,
        zlib=True,
        complevel=2,
        shuffle=True,
        chunksizes=ChunkSize,
    )
    var.setncattr('standard_name', 'conversion_matrix_element_11')
    var.setncattr(
        'description',
        'conversion matrix element (1st row, 1st column) that can be multiplied with vx to give range pixel '
        'displacement dr (see Eq. A18 in https://www.mdpi.com/2072-4292/13/4/749)',
    )
    var.setncattr('units', 'pixel/(meter/year)')
    var.setncattr('grid_mapping', mapping_var_name)
    var.setncattr('dr_to_vr_factor', dr_2_vr_factor)
    var.setncattr(
        'dr_to_vr_factor_description',
        'multiplicative factor that converts slant range pixel displacement dr to slant range velocity vr',
    )

    M11[noDataMask] = NoDataValue
    var[:] = M11

    var = nc_outfile.createVariable(
        'M12',
        np.dtype('float32'),
        ('y', 'x'),
        fill_value=NoDataValue,
        zlib=True,
        complevel=2,
        shuffle=True,
        chunksizes=ChunkSize,
    )
    var.setncattr('standard_name', 'conversion_matrix_element_12')
    var.setncattr(
        'description',
        'conversion matrix element (1st row, 2nd column) that can be multiplied with vy to give range pixel '
        'displacement dr (see Eq. A18 in https://www.mdpi.com/2072-4292/13/4/749)',
    )
    var.setncattr('units', 'pixel/(meter/year)')
    var.setncattr('grid_mapping', mapping_var_name)
    var.setncattr('dr_to_vr_factor', dr_2_vr_factor)
    var.setncattr(
        'dr_to_vr_factor_description',
        'multiplicative factor that converts slant range pixel displacement dr to slant range velocity vr',
    )

    M12[noDataMask] = NoDataValue
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
        file_name='conversion_matrices.nc',
        srs=srs,
        epsg=epsg,
        tran=tran,
        x=x,
        y=y,
        M11=M11,
        M12=M12,
        dr_2_vr_factor=dr_2_vr_factor,
        ChunkSize=ChunkSize,
        noDataMask=noDataMask,
        parameter_file=parameter_file,
    )

    return Path(conversion_nc)


def generate_correction_data(
    scene: str,
    buffer: int = 0,
    parameter_file: str = DEFAULT_PARAMETER_FILE,
) -> Tuple[dict, Path]:
    from hyp3_autorift.vend.testGeogrid_ISCE import loadParsedata, runGeogrid

    scene_safe = _get_safe(scene)

    orbits = Path('Orbits').resolve()
    orbits.mkdir(parents=True, exist_ok=True)

    state_vec = fetch_for_scene(scene_safe.stem, dir=orbits)
    log.info(f'Downloaded orbit file {state_vec} from s1-orbits')

    polarization = get_s1_primary_polarization(scene_safe.stem)

    swaths = [int(scene.split('_')[2][-1])] if scene.endswith('-BURST') else [1, 2, 3]
    lat_limits, lon_limits = bounding_box(str(scene_safe), polarization=polarization, orbits=str(orbits), swaths=swaths)

    scene_poly = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = utils.find_jpl_parameter_info(scene_poly, parameter_file)

    isce_dem = prep_isce_dem(parameter_info['geogrid']['dem'], lat_limits, lon_limits)
    format_tops_xml(scene_safe, scene_safe, polarization, isce_dem, orbits, swaths)

    reference_meta = loadParsedata(str(scene_safe), orbit_dir=orbits, aux_dir=orbits, buffer=buffer)

    secondary_meta = copy.deepcopy(reference_meta)
    spoof_dt = timedelta(days=1)
    secondary_meta.sensingStart += spoof_dt
    secondary_meta.sensingStop += spoof_dt

    geogrid_info = runGeogrid(reference_meta, secondary_meta, epsg=parameter_info['epsg'], **parameter_info['geogrid'])

    # NOTE: After Geogrid is run, all drivers are no longer registered.
    #       I've got no idea why, or if there are other affects...
    gdal.AllRegister()

    conversion_nc = create_conversion_matrices(
        scene=scene, epsg=parameter_info['epsg'], parameter_file=parameter_file, **parameter_info['autorift']
    )

    return geogrid_info, conversion_nc


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--bucket', help='AWS bucket to upload product files to')
    parser.add_argument('--bucket-prefix', default='', help='AWS prefix (location in bucket) to add to product files')
    parser.add_argument('--buffer', type=int, default=0, help='Number of pixels to buffer each edge of the input scene')
    parser.add_argument(
        '--parameter-file',
        default=DEFAULT_PARAMETER_FILE,
        help='Shapefile for determining the correct search parameters by geographic location. '
        'Path to shapefile must be understood by GDAL',
    )
    parser.add_argument(
        'granule',
        help='Reference Sentinel-1 or Sentinel-1 Burst granule (scene) to process'
    )
    args = parser.parse_args()

    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.INFO
    )

    _, conversion_nc = generate_correction_data(args.granule, buffer=args.buffer)

    if args.bucket:
        upload_file_to_s3(conversion_nc, args.bucket, args.bucket_prefix)
        for geotiff in Path.cwd().glob('*.tif'):
            upload_file_to_s3(geotiff, args.bucket, args.bucket_prefix)
