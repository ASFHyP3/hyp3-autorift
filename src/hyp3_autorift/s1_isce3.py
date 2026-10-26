import copy
import glob
import logging
import math
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import asf_search
import netCDF4
import numpy as np
import s1_orbits
import s1reader
from burst2safe.burst2safe import burst2safe
from compass import s1_cslc
from hyp3lib.fetch import download_file
from hyp3lib.scene import get_download_url
from osgeo import gdal
from s1reader import s1_info
from s1reader.s1_orbit import retrieve_orbit_file

import hyp3_autorift
from hyp3_autorift import geometry, utils
from hyp3_autorift.process import DEFAULT_PARAMETER_FILE
from hyp3_autorift.s1_rdr_static_files import (
    S3_BUCKET,
    STATIC_DIR,
    create_static_layer,
    get_static_layer,
    upload_static_nc_to_s3,
)
from hyp3_autorift.vend.testGeogrid import getPol, loadMetadata, loadMetadataSlc, runGeogrid
from hyp3_autorift.vend.testautoRIFT import generateAutoriftProduct


log = logging.getLogger(__name__)


def process_sentinel1_burst_isce3(
    reference,
    secondary,
    static_files_bucket,
    use_static_files,
    frame_id,
    regenerate_static_files: bool = False,
    chip_size: int | None = None,
    search_range: int | None = None,
):
    safe_ref = download_burst(reference)
    safe_sec = download_burst(secondary)

    orbit_ref = retrieve_orbit_file(str(safe_ref), orbit_dir='.', concatenate=True)
    orbit_sec = retrieve_orbit_file(str(safe_sec), orbit_dir='.', concatenate=True)

    if isinstance(reference, list) and len(reference) > 1:
        burst_ids_ref = [get_burst_id(safe_ref, g, orbit_ref) for g in reference]
        burst_ids_sec = [get_burst_id(safe_sec, g, orbit_sec) for g in secondary]

        swaths = sorted(list(set([int(g.split('_')[2][2]) for g in reference])))

        return process_slc(
            safe_ref,
            safe_sec,
            orbit_ref,
            orbit_sec,
            burst_ids_ref,
            burst_ids_sec,
            static_files_bucket,
            use_static_files,
            frame_id,
            swaths,
            regenerate_static_files,
            chip_size,
            search_range,
            reference[0],
        )

    reference = reference[0]
    secondary = secondary[0]

    burst_id_ref = get_burst_id(safe_ref, reference, orbit_ref)
    burst_id_sec = get_burst_id(safe_sec, secondary, orbit_sec)

    return process_burst(
        safe_ref,
        safe_sec,
        orbit_ref,
        orbit_sec,
        reference,
        burst_id_ref,
        burst_id_sec,
        static_files_bucket,
        use_static_files,
        regenerate_static_files,
        chip_size,
        search_range,
        reference,
    )


def process_burst(
    safe_ref,
    safe_sec,
    orbit_ref,
    orbit_sec,
    granule_ref,
    burst_id_ref,
    burst_id_sec,
    static_files_bucket,
    use_static_files,
    regenerate_static_files: bool = False,
    chip_size: int | None = None,
    search_range: int | None = None,
    ref_burst: str | None = None,
):
    swath = int(granule_ref.split('_')[2][2])
    lat_limits, lon_limits = bounding_box(safe_ref, orbit_ref, False, swaths=[swath])
    scene_poly = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = utils.find_jpl_parameter_info(scene_poly, parameter_file=DEFAULT_PARAMETER_FILE)

    download_dem(
        dem=parameter_info['geogrid']['dem'],
        bounds=[lon_limits[0], lat_limits[0], lon_limits[1], lat_limits[1]],
    )

    if regenerate_static_files:
        has_static_layer = False
        do_static_upload = True
    elif use_static_files:
        retrieval_bucket = static_files_bucket if static_files_bucket else S3_BUCKET
        has_static_layer = get_static_layer(burst_id_ref, retrieval_bucket)
        do_static_upload = not has_static_layer and static_files_bucket
    else:
        has_static_layer = False
        do_static_upload = False

    pol = getPol(safe_ref, orbit_ref)
    burst = s1reader.load_bursts(safe_ref, orbit_ref, swath, pol, burst_ids=[burst_id_ref])[0]

    write_yaml(
        safe=safe_ref,
        orbit_file=orbit_ref,
        burst_id=burst_id_ref,
        is_ref=True,
        use_static_layer=use_static_files and has_static_layer,
    )
    s1_cslc.run('s1_cslc.yaml', 'radar')
    convert2isce(burst_id_ref)

    if do_static_upload and (topo_correction_file := create_static_layer(burst_id_ref, burst=burst)):
        upload_static_nc_to_s3(topo_correction_file, burst_id_ref, bucket=static_files_bucket)
        topo_correction_file.unlink()

    write_yaml(
        safe=safe_sec,
        orbit_file=orbit_sec,
        burst_id=burst_id_sec,
        use_static_layer=use_static_files and has_static_layer,
    )
    s1_cslc.run('s1_cslc.yaml', 'radar')
    convert2isce(burst_id_sec, ref=False)

    if use_static_files:
        burst = get_burst_info(burst_id_ref)
        assert ref_burst
        static_orbit_path = get_orbit_for_static(ref_burst, str(burst.sensing_start))
        meta_r = loadMetadataSlc(safe_ref, static_orbit_path, pol, swaths=[swath], bursts=[burst])
        meta_s = loadMetadataSlc(safe_sec, static_orbit_path, pol, swaths=[swath], bursts=[burst])
    else:
        meta_r = loadMetadataSlc(safe_ref, orbit_ref, pol, swaths=[swath])
        meta_temp = loadMetadataSlc(safe_sec, orbit_sec, swaths=[swath])
        meta_s = copy.copy(meta_r)
        meta_s.sensingStart = meta_temp.sensingStart
        meta_s.sensingStop = meta_temp.sensingStop

    if chip_size is not None:
        log.info(f'Overriding chip size with user-defined value: {chip_size}')  # Add this log

        # Modify geogrid params (sends ChipSizeX to runGeogrid)
        parameter_info['geogrid']['ChipSizeX'] = chip_size
        parameter_info['geogrid']['ChipSizeY'] = chip_size

        # Modify autorift params (sends ChipSizeX to generateAutoriftProduct/runAutorift)
        parameter_info['autorift']['ChipSizeX'] = chip_size
        parameter_info['autorift']['ChipSizeY'] = chip_size
        parameter_info['autorift']['chip_size_min'] = None
        parameter_info['autorift']['chip_size_max'] = None

    if search_range is not None:
        log.info(f'Overriding search range with user-defined value: {search_range}')
        # Inject user-specified search_range into 'autorift' dictionary
        parameter_info['autorift']['SearchLimitX'] = search_range
        parameter_info['autorift']['SearchLimitY'] = search_range
        # Nullify Reference Velocity for non-glacier applications
        parameter_info['autorift']['NullReferenceVelocity'] = True

    geogrid_info = runGeogrid(
        info=meta_r,
        info1=meta_s,
        optical_flag=0,
        epsg=parameter_info['epsg'],
        **parameter_info['geogrid'],
    )

    # Geogrid seems to De-register Drivers
    gdal.AllRegister()

    netcdf_file = generateAutoriftProduct(
        'reference.tif',
        'secondary.tif',
        nc_sensor='S1',
        optical_flag=False,
        ncname=None,
        geogrid_run_info=geogrid_info,
        **parameter_info['autorift'],
        parameter_file=DEFAULT_PARAMETER_FILE.replace('/vsicurl/', ''),
    )

    with netCDF4.Dataset(netcdf_file, 'a', clobber=True, format='NETCDF4') as ds:
        var = ds.variables['img_pair_info']
        var.setncattr('frame_img1', burst_id_ref[1:])
        var.setncattr('frame_img2', burst_id_sec[1:])

    return netcdf_file


def process_sentinel1_slc_isce3(
    slc_ref,
    slc_sec,
    static_files_bucket,
    use_static_files,
    regenerate_static_files: bool = False,
    chip_size: int | None = None,
    search_range: int | None = None,
):
    safe_ref = download_file(get_download_url(slc_ref), chunk_size=5242880)
    safe_sec = download_file(get_download_url(slc_sec), chunk_size=5242880)

    orbit_ref = retrieve_orbit_file(safe_ref, orbit_dir='.', concatenate=True)
    orbit_sec = retrieve_orbit_file(safe_sec, orbit_dir='.', concatenate=True)

    burst_ids_ref = get_burst_ids(safe_ref, orbit_ref)
    burst_ids_sec = get_burst_ids(safe_sec, orbit_sec)

    return process_slc(
        safe_ref,
        safe_sec,
        orbit_ref,
        orbit_sec,
        burst_ids_ref,
        burst_ids_sec,
        static_files_bucket,
        use_static_files,
        frame_id='N/A',
        chip_size=chip_size,
        search_range=search_range,
        regenerate_static_files=regenerate_static_files,
    )


def process_slc(
    safe_ref,
    safe_sec,
    orbit_ref,
    orbit_sec,
    burst_ids_ref,
    burst_ids_sec,
    static_files_bucket,
    use_static_files,
    frame_id,
    swaths=(1, 2, 3),
    regenerate_static_files: bool = False,
    chip_size: int | None = None,
    search_range: int | None = None,
    ref_burst: str | None = None,
):
    lat_limits, lon_limits = bounding_box(safe_ref, orbit_ref, True, swaths=swaths)
    scene_poly = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = utils.find_jpl_parameter_info(scene_poly, parameter_file=DEFAULT_PARAMETER_FILE)
    burst_ids = sorted(list(set(burst_ids_sec) & set(burst_ids_ref)))
    pol = getPol(safe_ref, orbit_ref)

    download_dem(
        dem=parameter_info['geogrid']['dem'],
        bounds=[lon_limits[0], lat_limits[0], lon_limits[1], lat_limits[1]],
    )

    orbit_direction = None
    for burst_id in burst_ids:
        swath = int(burst_id.split('_')[-1][-1])
        burst = s1reader.load_bursts(safe_ref, orbit_ref, swath, pol, burst_ids=[burst_id])[0]
        if not orbit_direction:
            orbit_direction = burst.orbit_direction

        if regenerate_static_files:
            has_static_layer = False
            do_static_upload = True
        elif use_static_files:
            retrieval_bucket = static_files_bucket if static_files_bucket else S3_BUCKET
            has_static_layer = get_static_layer(burst_id, retrieval_bucket)
            do_static_upload = not has_static_layer and static_files_bucket
        else:
            has_static_layer = False
            do_static_upload = False

        if use_static_files:
            assert has_static_layer

        write_yaml(
            safe=safe_ref,
            orbit_file=orbit_ref,
            burst_id=burst_id,
            is_ref=True,
            use_static_layer=use_static_files,
        )
        s1_cslc.run('s1_cslc.yaml', 'radar')

        write_yaml(
            safe=safe_sec,
            orbit_file=orbit_sec,
            burst_id=burst_id,
            use_static_layer=use_static_files,
        )
        s1_cslc.run('s1_cslc.yaml', 'radar')

        if do_static_upload and (topo_correction_file := create_static_layer(burst_id, burst=burst)):
            upload_static_nc_to_s3(topo_correction_file, burst_id, static_files_bucket)
            topo_correction_file.unlink()

    slc_shape = merge_bursts(
        safe=safe_ref,
        orbit=orbit_ref,
        pol=pol,
        burst_ids=burst_ids,
        out_path='reference.tif',
        swaths=swaths,
        isce_path_prefix='product',
        use_static_files=use_static_files,
    )

    if use_static_files:
        bursts = [get_burst_info(burst_id) for burst_id in burst_ids]
        assert ref_burst
        static_orbit_path = get_orbit_for_static(ref_burst, str(bursts[0].sensing_start))
        meta_r = loadMetadataSlc(
            safe_ref,
            orbit_ref,
            pol,
            static_orbit_path=static_orbit_path,
            swaths=swaths,
            slc_shape=slc_shape,
            bursts=bursts,
        )
        meta_s = loadMetadataSlc(
            safe_sec, orbit_sec, pol, static_orbit_path=static_orbit_path, swaths=swaths, bursts=bursts
        )
    else:
        meta_r = loadMetadataSlc(safe_ref, orbit_ref, pol, swaths=swaths, slc_shape=slc_shape)
        meta_temp = loadMetadataSlc(safe_sec, orbit_sec, pol, swaths=swaths)
        meta_s = copy.copy(meta_r)
        meta_s.sensingStart = meta_temp.sensingStart
        meta_s.sensingStop = meta_temp.sensingStop
        meta_s.sensingDt = meta_temp.sensingDt

    meta_r.sceneName = safe_ref
    meta_s.sceneName = safe_sec
    meta_r.orbitDirection = orbit_direction
    meta_s.orbitDirection = orbit_direction
    meta_r.platformID = str(safe_ref)[3]
    meta_s.platformID = str(safe_sec)[3]

    shutil.rmtree('product/')

    _ = merge_bursts(
        safe=safe_ref,
        orbit=orbit_ref,
        pol=pol,
        burst_ids=burst_ids,
        out_path='secondary.tif',
        isce_path_prefix='product_sec',
        swaths=swaths,
        use_static_files=use_static_files,
    )

    if use_static_files:
        shutil.rmtree('static_topo_corrections/')
    shutil.rmtree('product_sec/')

    if chip_size is not None:
        log.info(f'Overriding chip size with user-defined value: {chip_size}')  # Add this log

        # Modify geogrid params (sends ChipSizeX to runGeogrid)
        parameter_info['geogrid']['ChipSizeX'] = chip_size
        parameter_info['geogrid']['ChipSizeY'] = chip_size

        # Modify autorift params (sends ChipSizeX to generateAutoriftProduct/runAutorift)
        parameter_info['autorift']['ChipSizeX'] = chip_size
        parameter_info['autorift']['ChipSizeY'] = chip_size
        parameter_info['autorift']['chip_size_min'] = None
        parameter_info['autorift']['chip_size_max'] = None

    if search_range is not None:
        log.info(f'Overriding search range with user-defined value: {search_range}')
        # Inject user-specified search_range into 'autorift' dictionary
        parameter_info['autorift']['SearchLimitX'] = search_range
        parameter_info['autorift']['SearchLimitY'] = search_range
        # Nullify Reference Velocity for non-glacier applications
        parameter_info['autorift']['NullReferenceVelocity'] = True

    ref_time = s1reader.load_bursts(safe_ref, orbit_ref, min(swaths), pol)[0].sensing_start
    sec_time = s1reader.load_bursts(safe_sec, orbit_sec, min(swaths), pol)[0].sensing_start
    repeat_time = (sec_time - ref_time).total_seconds()

    geogrid_info = runGeogrid(
        info=meta_r,
        info1=meta_s,
        optical_flag=0,
        epsg=parameter_info['epsg'],
        dt=repeat_time,
        **parameter_info['geogrid'],
    )

    # Geogrid seems to De-register Drivers
    gdal.AllRegister()

    netcdf_file = generateAutoriftProduct(
        'reference.tif',
        'secondary.tif',
        nc_sensor='S1',
        optical_flag=False,
        ncname=None,
        geogrid_run_info=geogrid_info,
        **parameter_info['autorift'],
        parameter_file=DEFAULT_PARAMETER_FILE.replace('/vsicurl/', ''),
        meta_r=meta_r,
        meta_s=meta_s,
    )

    with netCDF4.Dataset(netcdf_file, 'a', clobber=True, format='NETCDF4') as ds:
        var = ds.variables['img_pair_info']
        var.setncattr('frame_img1', str(frame_id))
        var.setncattr('frame_img2', str(frame_id))

    return netcdf_file


def get_orbit_for_static(scene: str, static_date: str):
    stack = asf_search.stack_from_id(scene)
    results = [res for res in stack if res.properties['startTime'][:10] == static_date[:10]]
    assert len(results) == 1

    group_id = results[0].properties['groupID']
    slcs = asf_search.search(groupID=group_id, processingLevel=asf_search.PRODUCT_TYPE.SLC)
    assert len(slcs) == 1

    slc_name = slcs[0].properties['sceneName']
    orbit_path = s1_orbits.fetch_for_scene(slc_name)
    assert orbit_path

    return str(orbit_path)


def read_slc_gdal(slc_path: str):
    ds = gdal.Open(slc_path)
    band = ds.GetRasterBand(1)
    slc_arr = np.abs(band.ReadAsArray()).astype(np.float32)
    del band, ds
    return slc_arr


def write_slc_gdal(data: np.ndarray, out_path: str):
    num_az_samples, num_rng_samples = data.shape
    nodata = 0
    driver = gdal.GetDriverByName('GTIFF')
    out_raster = driver.Create(out_path, num_rng_samples, num_az_samples, 1, gdal.GDT_Float32)
    out_band = out_raster.GetRasterBand(1)
    out_band.SetNoDataValue(nodata)
    out_band.WriteArray(data)
    out_band.FlushCache()
    del out_raster


class MockBurstInfo:
    def __init__(
        self,
        burst_id,
        azimuth_time_interval,
        sensing_start,
        sensing_start_delta,
        reference_epoch,
        starting_range,
        range_pixel_spacing,
        wavelength,
        length,
        width,
        first_valid_sample,
        last_valid_sample,
        first_valid_line,
        last_valid_line,
    ):
        self.burst_id = burst_id
        self.azimuth_time_interval = azimuth_time_interval
        self.sensing_start = sensing_start
        self.sensing_start_delta = sensing_start_delta
        self.reference_epoch = reference_epoch
        self.starting_range = starting_range
        self.range_pixel_spacing = range_pixel_spacing
        self.wavelength = wavelength
        self.length = length
        self.width = width
        self.shape = (length, width)
        self.first_valid_sample = first_valid_sample
        self.last_valid_sample = last_valid_sample
        self.first_valid_line = first_valid_line
        self.last_valid_line = last_valid_line


def get_valid_bounds(slc):
    ds = gdal.Open(slc)
    band = ds.GetRasterBand(1)
    arr = band.ReadAsArray()

    valid = arr != 0 + 0j

    lines, samples = np.where(valid)

    if len(lines) == 0:
        return None

    return {
        'first_valid_line': int(lines.min()),
        'last_valid_line': int(lines.max()),
        'first_valid_sample': int(samples.min()),
        'last_valid_sample': int(samples.max()),
    }


def get_burst_info(burst_id, isce_path_prefix='product'):
    info_path = f'./static_topo_corrections/{burst_id}/{burst_id}_static_rdr.nc'
    ds = gdal.Open(info_path)
    metadata = ds.GetMetadata()
    ds = None

    ref_epoch = datetime.strptime(metadata['NC_GLOBAL#ref_epoch'][:-3], '%Y-%m-%dT%H:%M:%S.%f')
    sensing_start_delta = timedelta(seconds=int(metadata['NC_GLOBAL#sensing_start']))
    sensing_start = ref_epoch + sensing_start_delta

    valid_data = get_valid_bounds(get_burst_path(str(Path(isce_path_prefix) / burst_id)))

    return MockBurstInfo(
        burst_id,
        float(metadata['NC_GLOBAL#azimuth_time_interval']),
        sensing_start,
        float(sensing_start_delta.total_seconds()),
        ref_epoch,
        float(metadata['NC_GLOBAL#starting_range']),
        float(metadata['NC_GLOBAL#range_pixel_spacing']),
        float(metadata['NC_GLOBAL#wavelength']),
        int(metadata['NC_GLOBAL#length']),
        int(metadata['NC_GLOBAL#width']),
        valid_data['first_valid_sample'],
        valid_data['last_valid_sample'],
        valid_data['first_valid_line'],
        valid_data['last_valid_line'],
    )


def merge_bursts(
    safe: str,
    orbit: str,
    pol: str,
    burst_ids: list,
    out_path: str,
    isce_path_prefix='product',
    swaths=(1, 2, 3),
    use_static_files=False,
):
    bursts = []
    if use_static_files:
        bursts = [get_burst_info(burst_id, isce_path_prefix=isce_path_prefix) for burst_id in burst_ids]
    else:
        for swath in swaths:
            bursts.extend(s1reader.load_bursts(safe, orbit, swath, pol))

    sensing_starts = sorted([burst.sensing_start for burst in bursts])
    sensing_start = min(sensing_starts)
    sensing_end = max(sensing_starts) + timedelta(seconds=bursts[-1].azimuth_time_interval * bursts[-1].length)
    sensing_time = sensing_end - sensing_start
    az_interval = bursts[0].azimuth_time_interval
    min_range = bursts[0].starting_range
    max_range = bursts[-1].starting_range + bursts[-1].range_pixel_spacing * bursts[-1].width
    total_range = max_range - min_range
    max_lines = int(np.round((sensing_time / az_interval).total_seconds()))
    max_samples = int(np.round(total_range / bursts[0].range_pixel_spacing))

    grid: np.ndarray = np.ndarray((max_lines, max_samples), dtype=np.float32)

    print(f'Sensing Start: {sensing_start}')
    print(f'Sensing Stop: {sensing_end}')
    print(f'Sensing Time: {sensing_time}')
    print(f'Azimuth Time Interval: {az_interval}')
    print(f'Start Range: {min_range}')
    print(f'Stop Range: {max_range}')
    print(f'Total Azimuth Pixels: {max_lines}')
    print(f'Total Range Pixels: {max_samples}')

    for burst in bursts:
        burst_id = str(burst.burst_id)
        print(f'Merging {burst_id} from {isce_path_prefix} to {out_path}')

        file = get_burst_path(str(Path(isce_path_prefix) / burst_id))
        ds = gdal.Open(file)
        band = ds.GetRasterBand(1)
        arr = np.abs(band.ReadAsArray()).astype(np.float32)

        start_range = int((burst.starting_range - min_range) / burst.range_pixel_spacing)
        end_range = int(start_range + burst.width)
        start_az = int(np.floor(((burst.sensing_start - sensing_start) / burst.azimuth_time_interval).total_seconds()))
        end_az = start_az + burst.length

        print(f'Azimuth: {start_az}, {end_az}')
        print(f'Range: {start_range}, {end_range}')

        valid_data = get_valid_bounds(file)

        buffer_lines = 8

        valid_az = slice(valid_data['first_valid_line'] + buffer_lines, valid_data['last_valid_line'] - buffer_lines)
        valid_rng = slice(
            valid_data['first_valid_sample'] + buffer_lines, valid_data['last_valid_sample'] - buffer_lines
        )

        print(f'Valid Azimuth: {valid_az}')
        print(f'Valid Range: {valid_rng}')

        grid[slice(start_az, end_az), slice(start_range, end_range)][valid_az, valid_rng] = arr[valid_az, valid_rng]

    write_slc_gdal(grid, out_path)

    return grid.shape


def get_burst_path(burst_filename: str):
    return glob.glob(glob.glob(burst_filename + '/*')[0] + '/*.slc.tif')[0]


# FIXME: is_slc could be handled by swaths?
def bounding_box(safe, orbit_file, is_slc, pol='HH', swaths=(1, 2, 3), epsg=4326):
    """Determine the geometric bounding box of a Sentinel-1 image

    Args:
        safe: Path to the Sentinel-1 SAFE zip archive
        orbit_file: Path to the Sentinel-1 orbit file
        is_slc: Whether the SAFE archive contains a full SLC product or not
        swaths: Swaths to include in the bounding box
        epsg: Projection EPSG code

    Returns:
        lat_limits: List containing the [minimum, maximum] latitudes
        lon_limits: List containing the [minimum, maximum] longitudes

    """
    from geogrid import GeogridRadar

    if not is_slc:
        info = loadMetadata(safe, orbit_file, swath=swaths[0])
    else:
        info = loadMetadataSlc(safe, orbit_file, pol, swaths=swaths)

    obj = GeogridRadar()

    obj.startingRange = info.startingRange
    obj.rangePixelSize = info.rangePixelSize
    obj.sensingStart = info.sensingStart
    obj.prf = info.prf
    obj.lookSide = info.lookSide
    obj.numberOfLines = info.numberOfLines
    obj.numberOfSamples = info.numberOfSamples
    obj.sensingStop = info.sensingStop
    obj.orbitname = info.orbitname
    obj.orbit = info.orbit
    obj.wavelength = info.wavelength
    obj.aztime = info.aztime
    obj.epsg = epsg

    obj.determineBbox()

    lat_limits = obj._ylim
    lon_limits = obj._xlim

    print(f'Latitude limits [min, max]: {lat_limits}')
    print(f'Longitude limits [min, max]: {lon_limits}')

    return lat_limits, lon_limits


def convert2isce(burst_id, ref=True):
    product_path = './product/' if ref else './product_sec/'
    output_path = 'reference.tif' if ref else 'secondary.tif'

    fol = glob.glob(product_path + burst_id + '/*')[0]
    slc = glob.glob(fol + '/*.slc.tif')[0]
    ds = gdal.Open(slc)
    band = ds.GetRasterBand(1)
    arr = np.abs(band.ReadAsArray()).astype(np.float32)
    write_slc_gdal(arr, output_path)


def download_burst(burst_granule, all_anns=True):
    if isinstance(burst_granule, list):
        pol = burst_granule[0].split('_')[4]
        return burst2safe(burst_granule, polarizations=[pol], all_anns=all_anns)
    return burst2safe([burst_granule], all_anns=all_anns)


def get_burst_id(safe, burst_granule, orbit_file):
    burst_granule_parts = burst_granule.split('_')
    orbit_number = burst_granule_parts[1]
    swath = burst_granule_parts[2]
    pol = burst_granule_parts[4]
    swath_number = int(swath[2])

    abspath = os.path.abspath(safe)
    bursts = s1reader.load_bursts(abspath, orbit_file, swath_number, pol)

    str_burst_id = None
    for x in bursts:
        burst_id_x = str(x.burst_id.esa_burst_id).zfill(6) + '_' + x.burst_id.subswath.lower()
        orbit_id = orbit_number.lower() + '_' + swath.lower()
        if burst_id_x == orbit_id:
            str_burst_id = 't' + str(int(x.burst_id.track_number)).zfill(3) + '_' + burst_id_x

    if str_burst_id is None:
        raise Exception('The burst id from ' + burst_granule + ' was not found in ' + safe)

    return str_burst_id


def get_isce3_burst_id(burst):
    track_number = 't' + str(int(burst.burst_id.track_number)).zfill(3)
    esa_burst_id = str(burst.burst_id.esa_burst_id).zfill(6)
    subswath = burst.burst_id.subswath.lower()
    return '_'.join([track_number, esa_burst_id, subswath])


def get_burst_ids(safe, orbit_file):
    abspath = os.path.abspath(safe)
    bursts = []
    pol = getPol(safe, orbit_file)

    for swath_number in [1, 2, 3]:
        bursts += s1reader.load_bursts(abspath, orbit_file, swath_number, pol)

    return [get_isce3_burst_id(x) for x in bursts]


def get_bounds_dem(safe):
    bounds = s1_info.get_frame_bounds(os.path.basename(safe))
    bounds = [int(bounds[0]) - 1, int(bounds[1]), math.ceil(bounds[2]) + 1, math.ceil(bounds[3])]
    return bounds


def download_dem(dem, bounds):
    in_ds = gdal.OpenShared(dem, gdal.GA_ReadOnly)
    warp_options = gdal.WarpOptions(
        format='GTIFF',
        outputType=gdal.GDT_Int16,
        resampleAlg='cubic',
        xRes=0.001,
        yRes=0.001,
        dstSRS='EPSG:4326',
        dstNodata=0,
        outputBounds=bounds,
    )
    gdal.Warp('dem.tif', in_ds, options=warp_options)


def write_yaml(safe, orbit_file, burst_id=None, is_ref=False, use_static_layer=False):
    abspath = os.path.abspath(safe)
    yaml_folder = os.path.dirname(hyp3_autorift.__file__) + '/schemas'

    with open(f'{yaml_folder}/s1_cslc_template.yaml') as yaml:
        lines = yaml.readlines()

    if is_ref and not use_static_layer:
        s1_ref_file = ''
        burst_id_str = '[' + burst_id + ']' if burst_id else ''
        bool_reference = 'True'
        product_folder = './product'
        scratch_folder = './scratch'
        output_folder = './output'
    elif use_static_layer:
        s1_ref_file = str((STATIC_DIR / burst_id).absolute())
        burst_id_str = '[' + burst_id + ']'
        bool_reference = 'False'
        product_folder = './product_sec' if not is_ref else './product'
        scratch_folder = './product_sec' if not is_ref else './product'
        output_folder = './output_sec' if not is_ref else './output'
    else:
        s1_ref_file = os.path.abspath(glob.glob('./product/' + burst_id + '/*')[0])
        burst_id_str = '[' + burst_id + ']'
        bool_reference = 'False'
        product_folder = './product_sec'
        scratch_folder = './product_sec'
        output_folder = './output_sec'

    pol = getPol(safe, orbit_file)

    with open('s1_cslc.yaml', 'w') as yaml:
        for line in lines:
            newstring = ''
            if 's1_image' in line:
                newstring += line.replace('s1_image', abspath)
            elif 's1_orbit_file' in line:
                orbit = os.path.abspath(orbit_file)
                newstring += line.replace('s1_orbit_file', orbit)
            elif 'burst_ids' in line:
                newstring += line.replace('burst_ids', burst_id_str)
            elif 'bool_reference' in line:
                newstring += line.replace('bool_reference', bool_reference)
            elif 's1_ref_file' in line:
                newstring += line.replace('s1_ref_file', s1_ref_file)
            elif 'polarization' in line and pol == 'hv':
                newstring += line.replace('co-pol', 'cross-pol')
            elif 'product_folder' in line:
                newstring += line.replace('product_folder', product_folder)
            elif 'scratch_folder' in line:
                newstring += line.replace('scratch_folder', scratch_folder)
            elif 'output_folder' in line:
                newstring += line.replace('output_folder', output_folder)
            else:
                newstring = line
            yaml.write(newstring)
