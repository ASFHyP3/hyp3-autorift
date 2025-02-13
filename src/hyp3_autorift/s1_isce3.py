import copy
import glob
import math
import netrc
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from platform import system
from typing import Tuple

import numpy as np
import rasterio
import s1reader
from burst2safe.burst2safe import burst2safe
from compass import s1_cslc
from dem_stitcher import stitch_dem
from hyp3lib.fetch import download_file
from hyp3lib.get_orb import downloadSentinelOrbitFile
from hyp3lib.scene import get_download_url
from osgeo import gdal
from s1reader import s1_info

import hyp3_autorift
from hyp3_autorift import geometry, utils
from hyp3_autorift.process import DEFAULT_PARAMETER_FILE
from hyp3_autorift.vend.testGeogrid_ISCE import getPol, loadMetadata, loadMetadataSlc, runGeogrid
from hyp3_autorift.vend.testautoRIFT import generateAutoriftProduct

ESA_HOST = 'dataspace.copernicus.eu'


def process_sentinel1_burst_isce3(burst_granule_ref, burst_granule_sec, is_opera=False):
    esa_username, esa_password = get_esa_credentials()
    esa_credentials = (esa_username, esa_password)

    safe_ref = download_burst(burst_granule_ref)
    safe_sec = download_burst(burst_granule_sec)
    safe_granule_ref = os.path.basename(safe_ref).split('.')[0]
    safe_granule_sec = os.path.basename(safe_sec).split('.')[0]
    orbit_ref, _ = downloadSentinelOrbitFile(safe_granule_ref, esa_credentials=esa_credentials)
    orbit_sec, _ = downloadSentinelOrbitFile(safe_granule_sec, esa_credentials=esa_credentials)
    burst_id_ref = get_burst_id(safe_ref, burst_granule_ref, orbit_ref)
    burst_id_sec = get_burst_id(safe_sec, burst_granule_sec, orbit_sec)

    return process_burst(
        safe_ref,
        safe_sec, 
        orbit_ref,
        orbit_sec,
        burst_granule_ref,
        burst_id_ref,
        burst_id_sec
    )


def process_sentinel1_slc_isce3(slc_ref, slc_sec):
    esa_username, esa_password = get_esa_credentials()
    esa_credentials = (esa_username, esa_password)

    for scene in [slc_ref, slc_sec]:
        scene_url = get_download_url(scene)
        download_file(scene_url, chunk_size=5242880)

    safe_ref = sorted(glob.glob('./*.zip'))[0]
    safe_sec = sorted(glob.glob('./*.zip'))[1]
    orbit_ref, _ = downloadSentinelOrbitFile(slc_ref, esa_credentials=esa_credentials)
    orbit_sec, _ = downloadSentinelOrbitFile(slc_sec, esa_credentials=esa_credentials)
    burst_ids_ref = get_burst_ids(safe_ref, orbit_ref)
    burst_ids_sec = get_burst_ids(safe_sec, orbit_sec)

    get_dem_for_safes(safe_ref, safe_sec)

    return process_slc(
        safe_ref,
        safe_sec,
        orbit_ref,
        orbit_sec,
        burst_ids_ref,
        burst_ids_sec
    )


def process_burst(
    safe_ref,
    safe_sec, 
    orbit_ref,
    orbit_sec,
    granule_ref,
    burst_id_ref,
    burst_id_sec
):
    write_yaml(safe_ref, orbit_ref)
    s1_cslc.run('s1_cslc.yaml', 'radar')
    ref = convert2isce(burst_id_ref)

    write_yaml(safe_sec, orbit_sec, burst_id_sec)
    s1_cslc.run('s1_cslc.yaml', 'radar')
    sec = convert2isce(burst_id_sec, ref=False)

    swath = int(granule_ref.split('_')[2][2])
    meta_r = loadMetadata(safe_ref, orbit_ref, swath=swath)
    meta_temp = loadMetadata(safe_sec, orbit_sec, swath=swath)
    meta_s = copy.copy(meta_r)
    meta_s.sensingStart = meta_temp.sensingStart
    meta_s.sensingStop = meta_temp.sensingStop

    lat_limits, lon_limits = bounding_box(safe_ref, orbit_ref, swath=swath)

    download_dem([lon_limits[0], lat_limits[0], lon_limits[1], lat_limits[1]])

    scene_poly = geometry.polygon_from_bbox(x_limits=np.array(lat_limits), y_limits=np.array(lon_limits))
    parameter_info = utils.find_jpl_parameter_info(scene_poly, parameter_file=DEFAULT_PARAMETER_FILE)

    geogrid_info = runGeogrid(meta_r, meta_s, epsg=parameter_info['epsg'], **parameter_info['geogrid'])

    from osgeo import gdal
    gdal.AllRegister()

    netcdf_file = generateAutoriftProduct(
            ref, sec, nc_sensor='S1', optical_flag=False, ncname=None,
            geogrid_run_info=geogrid_info, **parameter_info['autorift'],
            parameter_file=DEFAULT_PARAMETER_FILE.replace('/vsicurl/', ''),
        )

    return netcdf_file


def process_slc(
    safe_ref,
    safe_sec,
    orbit_ref,
    orbit_sec,
    burst_ids_ref,
    burst_ids_sec
):
    write_yaml(safe_ref, orbit_ref)
    s1_cslc.run('s1_cslc.yaml', 'radar')
    print('Bursts ref', burst_ids_ref)
    print('Bursts sec', burst_ids_sec)
    burst_ids = list(set(burst_ids_sec) & set(burst_ids_ref))

    for burst_id_sec in burst_ids:
        print('Burst', burst_id_sec)
        write_yaml(safe_sec, orbit_sec, burst_id_sec)
        s1_cslc.run('s1_cslc.yaml', 'radar')

    merge_swaths(ref=False)
    merge_swaths()

    meta_r = loadMetadataSlc(safe_ref, orbit_ref)
    meta_temp = loadMetadataSlc(safe_sec, orbit_sec)
    meta_s = copy.copy(meta_r)
    meta_s.sensingStart = meta_temp.sensingStart
    meta_s.sensingStop = meta_temp.sensingStop

    lat_limits, lon_limits = bounding_box(safe_ref, orbit_ref)

    scene_poly = geometry.polygon_from_bbox(x_limits=np.array(lat_limits), y_limits=np.array(lon_limits))
    parameter_info = utils.find_jpl_parameter_info(scene_poly, parameter_file=DEFAULT_PARAMETER_FILE)

    geogrid_info = runGeogrid(meta_r, meta_s, epsg=parameter_info['epsg'], **parameter_info['geogrid'])

    from osgeo import gdal
    gdal.AllRegister()

    ref = 'reference.slc'
    sec = 'secondary.slc'

    netcdf_file = generateAutoriftProduct(
            ref, sec, nc_sensor='S1', optical_flag=False, ncname=None,
            geogrid_run_info=geogrid_info, **parameter_info['autorift'],
            parameter_file=DEFAULT_PARAMETER_FILE.replace('/vsicurl/', ''),
        )

    return netcdf_file


def merge_swaths(safe, orbit, is_ref=True, swaths=[1, 2, 3]):
    safe_date = datetime.strptime(safe.split('_')[5], '%Y%m%dT%H%M%S')
    orbit_date =  datetime.strptime(orbit.split('_')[6], 'V%Y%m%dT%H%M%S')
    path = os.path.abspath(safe)
    orbit_path = os.path.abspath(orbit)
    burst_ids = get_burst_ids(path, orbit_path)
    product_path = './product/*' if is_ref else './product_sec/*'
    output_path = 'reference.slc' if is_ref else 'secondary.slc'
    burst_files = sorted(glob.glob(product_path))

    # Check against metadata
    if len(burst_ids) != len(burst_files):
        print('Warning : Not all the bursts were processed')

    bursts = []
    sensing_starts = []
    total_rng_samples = 0
    rng_offsets = [0]
    sensing_start = None
    sensing_stop = None
    az_time_interval = None
    pol = getPol(safe, orbit)

    for swath in swaths:
        merge_bursts_in_swath(swath, is_ref)

        bursts_from_swath = s1reader.load_bursts(safe, orbit, swath, pol)

        num_az_samples, num_rng_samples = bursts_from_swath.shape
        total_rng_samples += num_rng_samples

        az_time_interval = bursts_from_swath[0].azimuth_time_interval
        burst_length = timedelta(seconds=az_time_interval * (num_az_samples-1))
        burst_sensing_start = bursts_from_swath[0].sensing_start
        burst_sensing_stop = sensing_start + burst_length
        burst_start_rng = bursts_from_swath[0].starting_range

        bursts.extend(bursts_from_swath)
        sensing_starts.append(burst_sensing_start)

        # TODO: min(swaths) was previously 1
        #       Does this intentially not support passing something like swaths=[2, 3]? 
        if swath == min(swaths):
            sensing_start = burst_sensing_start
            az_time_interval = bursts[-1].azimuth_time_interval
            sensing_stop = burst_sensing_stop

        if sensing_start > burst_sensing_start:
            sensing_start = burst_sensing_start

        if sensing_stop < burst_sensing_stop:
            sensing_stop = burst_sensing_stop

        # TODO: min(swaths) was previously 1
        #       Does this intentially not support passing something like swaths=[2, 3]? 
        if swath > min(swaths):
            rng_offset = (burst_start_rng - bursts[0].starting_range) / bursts[0].range_pixel_spacing
            rng_offsets.append(int(np.round(rng_offset)))

    first_start_rng = bursts[0].starting_range
    last_start_rng = bursts[-1].starting_range
    last_rng_samples = bursts[-1].shape[1]
    rng_pixel_spacing = bursts[0].range_pixel_spacing

    total_rng_samples = last_rng_samples + int(np.round(
        (last_start_rng - first_start_rng) / rng_pixel_spacing
    ))

    total_az_samples = 1 + int(np.round(
        (sensing_stop - sensing_start).total_seconds() / az_time_interval
    ))

    merged_array = np.zeros((total_az_samples, total_rng_samples), dtype=complex)
    for swath in swaths:
        az_offset = int(np.round(
            (sensing_starts[swath-1]-sensing_start).total_seconds() / az_time_interval
        ))
        rng_offset = rng_offsets[swath-1]

        print('Offsets', rng_offset, az_offset)

        slc = 'swath_iw'+str(swath)+'.slc'
        ds = gdal.Open(slc)
        band = ds.GetRasterBand(1)
        if swath == 1:
            tran = ds.GetGeoTransform()
            proj = ds.GetProjection()
        slc_array = band.ReadAsArray()
        del band, ds

        az_end_index = az_offset+slc_array.shape[0]
        rng_end_index = rng_offset+slc_array.shape[1]
        if swath == 1:
            merged_array[az_offset:az_end_index, rng_offset:rng_end_index] = slc_array
        else:
            temp = merged_array[az_offset:az_end_index, rng_offset:rng_end_index]
            cond = np.logical_and(np.abs(temp) == 0, np.logical_not(np.abs(slc_array) == 0))
            merged_array[az_offset:az_end_index, rng_offset:rng_end_index][cond] = slc_array[cond]
            temp = None

    nodata = 0
    driver = gdal.GetDriverByName('ENVI')
    out_raster = driver.Create(output_path, total_rng_samples, total_az_samples, 1, gdal.GDT_CFloat32)
    out_raster.SetGeoTransform(tran)
    out_raster.SetProjection(proj)
    out_band = out_raster.GetRasterBand(1)
    out_band.SetNoDataValue(nodata)
    out_band.WriteArray(merged_array)
    out_band.FlushCache()
    del out_raster
    subprocess.call('rm -rf swath_*iw*', shell=True)


def merge_bursts_in_swath(swath, ref=True, outfile='output.slc', method='top'):
    '''
    Merge burst products into single file.
    Simple numpy based stitching
    '''
    safes = glob.glob('*.zip')
    orbits = glob.glob('*.EOF')
    dates_safes = [datetime.strptime(safe.split('_')[5], '%Y%m%dT%H%M%S') for safe in safes]
    dates_orbits = [datetime.strptime(orbit.split('_')[6], 'V%Y%m%dT%H%M%S') for orbit in orbits]
    argmin_safe = np.argsort(dates_safes)
    argmin_orbit = np.argsort(dates_orbits)

    safe = safes[argmin_safe[0]]
    orbit_file = orbits[argmin_orbit[0]]

    path = os.path.abspath(safe)
    orbit_path = os.path.abspath(orbit_file)

    pol = getPol(safe, orbit_path)

    burst_idst = get_burst_ids(path, orbit_path)
    burst_ids = [burst_id for burst_id in burst_idst if 'iw'+str(swath) in burst_id]
    if ref:
        fileList = sorted(glob.glob('./product/*_iw'+str(swath)))
    else:
        fileList = sorted(glob.glob('./product_sec/*_iw'+str(swath)))

    # Check against metadata
    if len(burst_ids) != len(fileList):
        print('Warning : Not all the bursts were processed')

    bursts = s1reader.load_bursts(safe, orbit_file, swath, pol)

    dt = bursts[0].azimuth_time_interval
    length, width = bursts[-1].shape

    #######
    tstart = bursts[0].sensing_start
    tstartLast = bursts[-1].sensing_start
    tend = (tstartLast + timedelta(seconds=(length-1.0) * dt))
    nLines = int(np.round((tend - tstart).total_seconds() / dt)) + 1
    print('Expected total nLines: ', nLines)

    azReferenceOff = []
    for index in range(len(burst_ids)):
        burst = bursts[index]
        soff = burst.sensing_start + timedelta(seconds=(burst.first_valid_line*dt))
        start = int(np.round((soff - tstart).total_seconds() / dt))
        end = start + (burst.last_valid_line - burst.first_valid_line) + 1

        azReferenceOff.append([start, end])

        print('Burst: ', index, [start, end])

        if index == 0:
            linecount = start

    outArray = np.zeros((nLines, width), dtype=complex)

    for index in range(len(burst_ids)):
        curBurst = bursts[index]
        curLimit = azReferenceOff[index]

        folder = glob.glob(fileList[index]+'/*')[0]
        slc = glob.glob(folder+'/*.slc')[0]
        ds = gdal.Open(slc)
        if index == 0:
            tran = ds.GetGeoTransform()
            proj = ds.GetProjection()
        band = ds.GetRasterBand(1)
        curMap = band.ReadAsArray()
        band = None
        ds = None

        # If middle burst
        if index > 0:
            topBurst = bursts[index-1]
            folder = glob.glob(fileList[index-1]+'/*')[0]
            slc = glob.glob(folder+'/*.slc')[0]
            ds = gdal.Open(slc)
            band = ds.GetRasterBand(1)
            topMap = band.ReadAsArray()
            band = None
            ds = None
            topLimit = azReferenceOff[index-1]

            olap = topLimit[1] - curLimit[0]

            print("olap: ", olap)

            if olap <= 0:
                raise Exception('No Burst Overlap')

            topData = topMap[topBurst.first_valid_line:topBurst.last_valid_line+1, :]

            curData = curMap[curBurst.first_valid_line:curBurst.last_valid_line+1, :]

            im1 = topData[-olap:, :]
            im2 = curData[:olap, :]

            if method == 'avg':
                data = 0.5*(im1 + im2)
            elif method == 'top':
                data = im1
            elif method == 'bot':
                data = im2
            else:
                raise Exception('Method should be top/bot/avg')

            outArray[linecount:linecount+olap, :] = data

            tlim = olap
        else:
            tlim = 0

        linecount += tlim

        if index != (len(burst_ids)-1):
            botLimit = azReferenceOff[index+1]

            olap = curLimit[1] - botLimit[0]

            if olap < 0:
                raise Exception('No Burst Overlap')

            blim = botLimit[0] - curLimit[0]
        else:
            blim = curBurst.last_valid_line - curBurst.first_valid_line + 1

        lineout = blim - tlim

        curData = curMap[curBurst.first_valid_line:curBurst.last_valid_line+1, :]
        outArray[linecount:linecount+lineout, :] = curData[tlim:blim, :]

        linecount += lineout

    driver = gdal.GetDriverByName('ENVI')
    outRaster = driver.Create("swath_iw"+str(swath)+".slc", width, nLines, 1, gdal.GDT_CFloat32)
    outRaster.SetGeoTransform(tran)
    outRaster.SetProjection(proj)
    outband = outRaster.GetRasterBand(1)
    outband.WriteArray(outArray)
    outband.FlushCache()
    del outRaster, outband


def get_topsinsar_config():
    '''
    Input file.
    '''
    import os
    import numpy as np
    from datetime import datetime, timedelta
    from s1reader import load_bursts
    import glob
    orbits = glob.glob('*.EOF')
    fechas_orbits = [datetime.strptime(os.path.basename(file).split('_')[6], 'V%Y%m%dT%H%M%S') for file in orbits]
    safes = glob.glob('*.SAFE')
    if not len(safes) == 0:
        fechas_safes = [datetime.strptime(os.path.basename(file).split('_')[5], '%Y%m%dT%H%M%S') for file in safes]
    else:
        safes = glob.glob('*.zip')
        fechas_safes = [datetime.strptime(os.path.basename(file).split('_')[5], '%Y%m%dT%H%M%S') for file in safes]

    safe_ref = safes[np.argmin(fechas_safes)]
    orbit_path_ref = orbits[np.argmin(fechas_orbits)]

    safe_sec = safes[np.argmax(fechas_safes)]
    orbit_path_sec = orbits[np.argmax(fechas_orbits)]

    if len(glob.glob('*_ref*.slc')) > 0:
        swath = int(os.path.basename(glob.glob('*_ref*.slc')[0]).split('_')[2][2])
    else:
        swath = 1

    pol = getPol(safe_ref, orbit_path_ref)

    config_data = {}
    for name in ['reference', 'secondary']:
        if name == 'reference':
            burst = load_bursts(safe_ref, orbit_path_ref, swath, pol)[0]
            safe = safe_ref
        else:
            burst = load_bursts(safe_sec, orbit_path_sec, swath, pol)[0]
            safe = safe_sec

        sensing_start = burst.sensing_start
        length, width = burst.shape
        prf = 1 / burst.azimuth_time_interval

        sensing_stop = (sensing_start + timedelta(seconds=(length-1.0)/prf))

        sensing_dt = (sensing_stop - sensing_start) / 2 + sensing_start

        config_data[f'{name}_filename'] = Path(safe).name
        config_data[f'{name}_dt'] = sensing_dt.strftime("%Y%m%dT%H:%M:%S.%f").rstrip('0')

    return config_data


def bounding_box(safe, orbit_file, swath=0, epsg=4326):
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

    if swath > 0:
        info = loadMetadata(safe, orbit_file, swath=swath)
    else:
        info = loadMetadataSlc(safe, orbit_file)

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
    if ref:
        fol = glob.glob('./product/'+burst_id+'/*')[0]
        slc = glob.glob(fol+'/*.slc')[0]
        ds = gdal.Open(slc)
        ds = gdal.Translate('burst_ref_'+str(burst_id.split('_')[2])+'.slc', ds, options="-of ISCE")
        ds = None
        return 'burst_ref_'+str(burst_id.split('_')[2])+'.slc'
    else:
        fol = glob.glob('./product_sec/'+burst_id+'/*')[0]
        slc = glob.glob(fol+'/*.slc')[0]
        ds = gdal.Open(slc)
        ds = gdal.Translate('burst_sec_'+str(burst_id.split('_')[2])+'.slc', ds, options="-of ISCE")
        ds = None
        subprocess.call('rm -rf scratch scratch_sec product product_sec output output_sec', shell=True)
        return 'burst_sec_'+str(burst_id.split('_')[2])+'.slc'


def get_esa_credentials() -> Tuple[str, str]:
    netrc_name = '_netrc' if system().lower() == 'windows' else '.netrc'
    netrc_file = Path.home() / netrc_name

    if "ESA_USERNAME" in os.environ and "ESA_PASSWORD" in os.environ:
        username = os.environ["ESA_USERNAME"]
        password = os.environ["ESA_PASSWORD"]
        return username, password

    if netrc_file.exists():
        netrc_credentials = netrc.netrc(netrc_file)
        if ESA_HOST in netrc_credentials.hosts:
            username = netrc_credentials.hosts[ESA_HOST][0]
            password = netrc_credentials.hosts[ESA_HOST][2]
            return username, password

    raise ValueError(
        "Please provide Copernicus Data Space Ecosystem (CDSE) credentials via the "
        "ESA_USERNAME and ESA_PASSWORD environment variables, or your netrc file."
    )


def download_burst(burst_granule, all_anns=True):
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
        burst_id_x = str(x.burst_id.esa_burst_id).zfill(6)+'_'+x.burst_id.subswath.lower()
        orbit_id = orbit_number.lower()+'_'+swath.lower()
        if burst_id_x == orbit_id:
            str_burst_id = 't'+str(int(x.burst_id.track_number)).zfill(3)+'_'+burst_id_x

    if str_burst_id is None:
        raise Exception('The burst id from ' + burst_granule + ' was not found in ' + safe)

    return str_burst_id


def get_isce3_burst_id(burst):
    track_number = 't' + str(int(burst.burst_id.track_number)).zfill(3)
    esa_burst_id = str(burst.burst_id.esa_burst_id).zfill(6)
    subswath = burst.burst_id.subswath.lower()
    return '_'.join([
        track_number,
        esa_burst_id,
        subswath
    ])


def get_burst_ids(safe, orbit_file):
    abspath = os.path.abspath(safe)
    bursts = []
    pol = getPol(safe, orbit_file)

    for swath_number in [1, 2, 3]:
        bursts += s1reader.load_bursts(abspath, orbit_file, swath_number, pol)

    return [get_isce3_burst_id(x) for x in bursts]


def get_dem_for_safes(safe_ref, safe_sec):
    lon1min, lat1min, lon1max, lat1max = get_bounds_dem(safe_ref)
    lon2min, lat2min, lon2max, lat2max = get_bounds_dem(safe_sec)
    lon_min, lat_min = np.min([lon1min, lon2min]), np.min([lat1min, lat2min])
    lon_max, lat_max = np.max([lon1max, lon2max]), np.max([lat1max, lat2max])
    bounds = [lon_min, lat_min, lon_max, lat_max]
    download_dem(bounds)


def get_bounds_dem(safe):
    bounds = s1_info.get_frame_bounds(os.path.basename(safe))
    bounds = [int(bounds[0])-1, int(bounds[1]), math.ceil(bounds[2])+1, math.ceil(bounds[3])]
    return bounds


def download_dem(bounds):
    X, p = stitch_dem(bounds,
                      dem_name='glo_30',  # Global Copernicus 30 meter resolution DEM
                      dst_ellipsoidal_height=False,
                      dst_area_or_point='Point')

    with rasterio.open('dem_temp.tif', 'w', **p) as ds:
        ds.write(X, 1)
        ds.update_tags(AREA_OR_POINT='Point')
    ds = None
    ds = gdal.Open('dem_temp.tif')
    ds = gdal.Translate('dem.tif', ds, options="-ot Int16")
    ds = None
    subprocess.call('rm -rf dem_temp.tif', shell=True)


def write_yaml(safe, orbit_file, burst_id=None):
    abspath = os.path.abspath(safe)
    yaml_folder = os.path.dirname(hyp3_autorift.__file__)+'/schemas'
    yaml = open(f'{yaml_folder}/s1_cslc_template.yaml', 'r')
    lines = yaml.readlines()
    yaml.close()

    if burst_id is None:
        ref = ''
    else:
        ref = glob.glob('./product/'+burst_id+'/*')[0]
        ref = os.path.abspath(ref)

    yaml = open('s1_cslc.yaml', 'w')
    newstring = ''
    for line in lines:
        if 's1_image' in line:
            newstring += line.replace('s1_image', abspath)
        elif 's1_orbit_file' in line:
            orbit = os.path.abspath(orbit_file)
            newstring += line.replace('s1_orbit_file', orbit)
        elif 'burst_ids' in line:
            if burst_id is None:
                newstring += line.replace('burst_ids', '')
            else:
                newstring += line.replace('burst_ids', '[\''+burst_id+'\']')
        elif 'bool_reference' in line:
            if burst_id is None:
                newstring += line.replace('bool_reference', 'True')
            else:
                newstring += line.replace('bool_reference', 'False')
        elif 's1_ref_file' in line:
            if burst_id is None:
                newstring += line.replace('s1_ref_file', '')
            else:
                newstring += line.replace('s1_ref_file', ref)
        elif 'product_folder' in line:
            if burst_id is None:
                newstring += line.replace('product_folder', './product')
            else:
                newstring += line.replace('product_folder', './product_sec')
        elif 'scratch_folder' in line:
            if burst_id is None:
                newstring += line.replace('scratch_folder', './scratch')
            else:
                newstring += line.replace('scratch_folder', './product_sec')
        elif 'output_folder' in line:
            if burst_id is None:
                newstring += line.replace('output_folder', './output')
            else:
                newstring += line.replace('output_folder', './output_sec')
        else:
            newstring = line
        yaml.write(newstring)
    yaml.close()


def remove_temp_files(only_rtc=False):
    if only_rtc:
        subprocess.call('rm -rf output_dir scratch_dir rtc.log rtc_s1.yaml', shell=True)
    else:
        subprocess.call('rm -rf output_dir *SAFE *EOF scratch_dir dem.tif rtc.log rtc_s1.yaml', shell=True)
