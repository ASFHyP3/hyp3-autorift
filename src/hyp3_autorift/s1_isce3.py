import copy
import glob
import math
import os
import shutil
import subprocess
from datetime import timedelta

import numpy as np
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


def process_sentinel1_burst_isce3(reference, secondary, static_files_bucket, use_static_files):
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
            swaths,
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
):
    swath = int(granule_ref.split('_')[2][2])
    lat_limits, lon_limits = bounding_box(safe_ref, orbit_ref, False, swaths=[swath])
    scene_poly = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = utils.find_jpl_parameter_info(scene_poly, parameter_file=DEFAULT_PARAMETER_FILE)

    download_dem(
        dem=parameter_info['geogrid']['dem'],
        bounds=[lon_limits[0], lat_limits[0], lon_limits[1], lat_limits[1]],
    )

    if use_static_files:
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

    meta_r = loadMetadata(safe_ref, orbit_ref, swath=swath)
    meta_temp = loadMetadata(safe_sec, orbit_sec, swath=swath)
    meta_s = copy.copy(meta_r)
    meta_s.sensingStart = meta_temp.sensingStart
    meta_s.sensingStop = meta_temp.sensingStop

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

    return netcdf_file


def process_sentinel1_slc_isce3(slc_ref, slc_sec, static_files_bucket, use_static_files):
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
    swaths=(1, 2, 3),
):
    lat_limits, lon_limits = bounding_box(safe_ref, orbit_ref, True, swaths=swaths)
    scene_poly = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = utils.find_jpl_parameter_info(scene_poly, parameter_file=DEFAULT_PARAMETER_FILE)
    burst_ids = list(set(burst_ids_sec) & set(burst_ids_ref))
    pol = getPol(safe_ref, orbit_ref)

    download_dem(
        dem=parameter_info['geogrid']['dem'],
        bounds=[lon_limits[0], lat_limits[0], lon_limits[1], lat_limits[1]],
    )

    for burst_id in burst_ids:
        swath = int(burst_id.split('_')[-1][-1])
        burst = s1reader.load_bursts(safe_ref, orbit_ref, swath, pol, burst_ids=[burst_id])[0]

        if use_static_files:
            retrieval_bucket = static_files_bucket if static_files_bucket else S3_BUCKET
            has_static_layer = get_static_layer(burst_id, retrieval_bucket)
            do_static_upload = not has_static_layer and static_files_bucket
        else:
            has_static_layer = False
            do_static_upload = False

        write_yaml(
            safe=safe_ref,
            orbit_file=orbit_ref,
            burst_id=burst_id,
            is_ref=True,
            use_static_layer=use_static_files and has_static_layer,
        )
        s1_cslc.run('s1_cslc.yaml', 'radar')

        write_yaml(
            safe=safe_sec,
            orbit_file=orbit_sec,
            burst_id=burst_id,
            use_static_layer=use_static_files and has_static_layer,
        )
        s1_cslc.run('s1_cslc.yaml', 'radar')

        if do_static_upload and (topo_correction_file := create_static_layer(burst_id, burst=burst)):
            upload_static_nc_to_s3(topo_correction_file, burst_id, static_files_bucket)
            topo_correction_file.unlink()

        if has_static_layer:
            shutil.rmtree(STATIC_DIR / burst_id)

    slc_shape = merge_swaths(safe_ref, orbit_ref, swaths=swaths)
    meta_r = loadMetadataSlc(safe_ref, orbit_ref, swaths=swaths, slc_shape=slc_shape)
    meta_temp = loadMetadataSlc(safe_sec, orbit_sec, swaths=swaths)
    meta_s = copy.copy(meta_r)
    meta_s.sensingStart = meta_temp.sensingStart
    meta_s.sensingStop = meta_temp.sensingStop

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

    return netcdf_file


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


def merge_swaths(safe_ref: str, orbit_ref: str, swaths=(1, 2, 3)) -> tuple[int, ...]:
    """Merges the bursts within the provided swath(s) and then merges the swaths.
       The secondary image is merged according to the reference image's metadata.

    Args:
        safe_ref: The filename of the reference safe. The secondary must be coregistered to this.
        orbit_ref: The filename of the orbit file for the reference image.
        swaths: Ascending sorted list containing the desired swath(s) to merge. Swaths must be adjacent.
    """
    safe_path_ref = os.path.abspath(safe_ref)
    orbit_path_ref = os.path.abspath(orbit_ref)

    burst_ids_ref = get_burst_ids(safe_path_ref, orbit_path_ref)

    product_path_ref = './product/*'
    product_path_sec = './product_sec/*'

    burst_files_ref = sorted(glob.glob(product_path_ref))
    burst_files_sec = sorted(glob.glob(product_path_sec))

    # Check against metadata
    if len(burst_ids_ref) != len(burst_files_ref):
        print('Warning : Not all the bursts were processed')

    bursts = []
    sensing_starts = []
    rng_offsets = [0]
    sensing_start = None
    sensing_stop = None
    az_time_interval = None
    pol = getPol(safe_ref, orbit_ref)

    for swath in swaths:
        ref_bursts = s1reader.load_bursts(safe_ref, orbit_ref, swath, pol)
        ref_burst_files = [b for b in burst_files_ref if f'iw{swath}' in b]
        sec_burst_files = [b for b in burst_files_sec if f'iw{swath}' in b]

        burst_az_samples, num_rng_samples = merge_bursts_in_swath(ref_bursts, ref_burst_files, sec_burst_files, swath)

        az_time_interval = ref_bursts[0].azimuth_time_interval
        burst_length = timedelta(seconds=az_time_interval * (burst_az_samples - 1))
        burst_sensing_start = ref_bursts[0].sensing_start
        burst_sensing_stop = ref_bursts[-1].sensing_start + burst_length
        burst_start_rng = ref_bursts[0].starting_range

        bursts.extend(ref_bursts)
        sensing_starts.append(burst_sensing_start)

        if swath == min(swaths):
            sensing_start = burst_sensing_start
            az_time_interval = bursts[-1].azimuth_time_interval
            sensing_stop = burst_sensing_stop
            last_rng_samples = num_rng_samples

        if sensing_start > burst_sensing_start:
            sensing_start = burst_sensing_start

        if sensing_stop < burst_sensing_stop:
            sensing_stop = burst_sensing_stop

        if swath > min(swaths):
            rng_offset = (burst_start_rng - bursts[0].starting_range) / bursts[0].range_pixel_spacing
            rng_offsets.append(int(np.floor(rng_offset)))
            last_rng_samples = num_rng_samples

    first_start_rng = bursts[0].starting_range
    last_start_rng = bursts[-1].starting_range
    rng_pixel_spacing = bursts[0].range_pixel_spacing

    assert sensing_start and sensing_stop and rng_pixel_spacing

    num_rng_pixels = int(np.floor((last_start_rng - first_start_rng) / rng_pixel_spacing))
    sensing_time = (sensing_stop - sensing_start).total_seconds()
    total_rng_samples = last_rng_samples + num_rng_pixels
    total_az_samples = 1 + int(np.round(sensing_time / az_time_interval))

    for slc in ['ref', 'sec']:
        swath_index = 0
        merged_arr = np.zeros((total_az_samples, total_rng_samples), dtype=np.float32)

        for swath in swaths:
            print(f'Merging Swath {swath}')

            slc_path = slc + '_swath_iw' + str(swath) + '.tif'
            slc_array = read_slc_gdal(slc_path)
            slc_rows = slc_array.shape[0]

            bursts = s1reader.load_bursts(safe_ref, orbit_ref, swath, pol)

            first_rng_sample = bursts[0].first_valid_sample
            last_rng_sample = bursts[0].last_valid_sample
            az_offset = int(np.floor((sensing_starts[swath_index] - sensing_start).total_seconds() / az_time_interval))
            rng_offset = rng_offsets[swath_index] + first_rng_sample
            rng_end_index = rng_offset + (last_rng_sample - first_rng_sample)
            invalid_pixel_buffer = 64 if swath != max(swaths) else 0
            slc_az_start_index = bursts[0].first_valid_line

            if len(bursts) > 1:
                slc_az_end_index = -bursts[-1].last_valid_line
                merged_az_end_index = az_offset + slc_rows + (slc_az_end_index - slc_az_start_index)
            else:
                slc_az_end_index = bursts[0].last_valid_line
                merged_az_end_index = az_offset + (slc_az_end_index - slc_az_start_index)

            merged_az_slice = slice(az_offset, merged_az_end_index)
            merged_rng_slice = slice(rng_offset, rng_end_index - invalid_pixel_buffer)
            slc_az_slice = slice(slc_az_start_index, slc_az_end_index)
            slc_rng_slice = slice(first_rng_sample, last_rng_sample - invalid_pixel_buffer)

            cond = np.logical_and(
                merged_arr[merged_az_slice, merged_rng_slice] == 0, slc_array[slc_az_slice, slc_rng_slice] != 0
            )

            merged_arr[merged_az_slice, merged_rng_slice][cond] = slc_array[slc_az_slice, slc_rng_slice][cond]

            swath_index += 1

        write_slc_gdal(merged_arr, 'reference.tif' if slc == 'ref' else 'secondary.tif')

    subprocess.call('rm -rf ref_swath_*iw* sec_swath_*iw*', shell=True)

    return merged_arr.shape


def get_azimuth_reference_offsets(bursts: list):
    """Calculate the azimuth offsets and valid burst indexes

    Args:
        bursts: List of burst objects

    Returns:
        az_reference_offsets: The azimuth offsets
        start_index: The starting index for merging
    """
    az_reference_offsets = []
    sensing_start = bursts[0].sensing_start
    az_time_interval = bursts[0].azimuth_time_interval

    for index in range(len(bursts)):
        burst = bursts[index]
        az_offset = burst.sensing_start + timedelta(seconds=(burst.first_valid_line * az_time_interval))
        burst_start_index = int(np.round((az_offset - sensing_start).total_seconds() / az_time_interval))
        burst_end_index = burst_start_index + (burst.last_valid_line - burst.first_valid_line) + 1
        az_reference_offsets.append([burst_start_index, burst_end_index])

    return az_reference_offsets


def get_burst_path(burst_filename: str):
    return glob.glob(glob.glob(burst_filename + '/*')[0] + '/*.slc.tif')[0]


def merge_bursts_in_swath(ref_bursts: list, ref_burst_files: list[str], sec_burst_files: list[str], swath: int):
    """Merges the bursts within the provided swath.
       The secondary bursts are merged according to the reference bursts' metadata.

    Args:
        ref_bursts: List of the reference burst objects
        ref_burst_files: List of the filenames of the reference burst slcs
        sec_burst_files: List of the filenames of the secondary burst slcs
        swath: The swath containing the bursts to merge.

    Returns:
        num_az_samples: Merged image size in the azimuth direction
        num_rng_samples: Merged image size in the range direction
    """
    print(f'Merging Bursts in Swath {swath}')

    num_bursts = len(ref_bursts)
    az_time_interval = ref_bursts[0].azimuth_time_interval
    burst_arr = read_slc_gdal(get_burst_path(ref_burst_files[0]))
    num_az_samples, num_rng_samples = burst_arr.shape

    ref_output_path = 'ref_swath_iw' + str(swath) + '.tif'
    sec_output_path = 'sec_swath_iw' + str(swath) + '.tif'

    if num_bursts == 1:
        write_slc_gdal(burst_arr, ref_output_path)
        burst_arr = read_slc_gdal(get_burst_path(sec_burst_files[0]))
        write_slc_gdal(burst_arr, sec_output_path)
        return num_az_samples, num_rng_samples

    last_burst_sensing_start = ref_bursts[-1].sensing_start
    burst_length = timedelta(seconds=(num_az_samples - 1.0) * az_time_interval)
    sensing_start = ref_bursts[0].sensing_start
    sensing_end = last_burst_sensing_start + burst_length
    num_az_lines = 1 + int(np.round((sensing_end - sensing_start).total_seconds() / az_time_interval))
    az_reference_offsets = get_azimuth_reference_offsets(ref_bursts)

    ref_merged_arr = np.zeros((num_az_lines, num_rng_samples), dtype=np.float32)
    sec_merged_arr = np.zeros((num_az_lines, num_rng_samples), dtype=np.float32)
    for index in range(num_bursts):
        burst = ref_bursts[index]
        burst_limit = az_reference_offsets[index]
        burst_arr_ref = read_slc_gdal(get_burst_path(ref_burst_files[index]))
        burst_arr_sec = read_slc_gdal(get_burst_path(sec_burst_files[index]))

        # Merge the bursts in the azimuth direction such that the beginning of 1 burst is halfway
        # through the overlap with the previous burst. This avoids any invalid pixels from resampling in ISCE3.
        if index == 0:
            next_burst_limit = az_reference_offsets[index + 1]
            burst_start_index = burst.first_valid_line
            burst_end_index = 1 + burst.last_valid_line - (burst_limit[1] - next_burst_limit[0]) // 2
            merge_start_index = burst_limit[0]
            merge_end_index = burst_limit[1] - (burst_limit[1] - next_burst_limit[0]) // 2

        elif index != num_bursts - 1:
            prev_burst_limit = az_reference_offsets[index - 1]
            next_burst_limit = az_reference_offsets[index + 1]
            burst_start_index = burst.first_valid_line + (prev_burst_limit[1] - burst_limit[0]) // 2
            burst_end_index = 1 + burst.last_valid_line - (burst_limit[1] - next_burst_limit[0]) // 2
            merge_start_index = burst_limit[0] + (prev_burst_limit[1] - burst_limit[0]) // 2
            merge_end_index = burst_limit[1] - (burst_limit[1] - next_burst_limit[0]) // 2

        else:
            prev_burst_limit = az_reference_offsets[index - 1]
            burst_start_index = burst.first_valid_line + (prev_burst_limit[1] - burst_limit[0]) // 2
            burst_end_index = 1 + burst.last_valid_line
            merge_start_index = burst_limit[0] + (prev_burst_limit[1] - burst_limit[0]) // 2
            merge_end_index = burst_limit[1]

        rng_slice = slice(burst.first_valid_sample, burst.last_valid_sample)

        merge_az_slice = slice(merge_start_index, merge_end_index)
        burst_az_slice = slice(burst_start_index, burst_end_index)

        print(
            f'IW{swath}[{merge_start_index}:{merge_end_index}] = burst_{index}[{burst_start_index}:{burst_end_index}]'
        )

        burst_arr_ref = burst_arr_ref[burst_az_slice, rng_slice]
        burst_arr_sec = burst_arr_sec[burst_az_slice, rng_slice]

        ref_merged_arr[merge_az_slice, rng_slice] = burst_arr_ref
        sec_merged_arr[merge_az_slice, rng_slice] = burst_arr_sec

    write_slc_gdal(ref_merged_arr, ref_output_path)
    write_slc_gdal(sec_merged_arr, sec_output_path)

    return num_az_lines, num_rng_samples


# FIXME: Docstring; is_slc could be handled by swaths?
def bounding_box(safe, orbit_file, is_slc, swaths=(1, 2, 3), epsg=4326):
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
    from geogrid import GeogridRadar

    if not is_slc:
        info = loadMetadata(safe, orbit_file, swath=swaths[0])
    else:
        info = loadMetadataSlc(safe, orbit_file, swaths=swaths)

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
