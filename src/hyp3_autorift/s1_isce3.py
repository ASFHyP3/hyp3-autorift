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

import asf_search
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
from hyp3_autorift import geometry, process, utils
from hyp3_autorift.process import DEFAULT_PARAMETER_FILE
from hyp3_autorift.vend.testGeogridOptical import coregisterLoadMetadata
from hyp3_autorift.vend.testGeogrid_ISCE import getPol, loadMetadata, loadMetadataSlc, runGeogrid
from hyp3_autorift.vend.testautoRIFT import generateAutoriftProduct

ESA_HOST = 'dataspace.copernicus.eu'


def process_burst_sentinel1_with_isce3(burst_granule_ref, burst_granule_sec):
    esa_username, esa_password = get_esa_credentials()
    esa_credentials = (esa_username, esa_password)

    safe_ref = download_burst(burst_granule_ref)
    safe_sec = download_burst(burst_granule_sec)

    granule_ref = os.path.basename(safe_ref).split('.')[0]
    granule_sec = os.path.basename(safe_sec).split('.')[0]

    lon1min, lat1min, lon1max, lat1max = get_bounds_dem(safe_ref)
    lon2min, lat2min, lon2max, lat2max = get_bounds_dem(safe_sec)
    lon_min, lat_min = np.min([lon1min, lon2min]), np.min([lat1min, lat2min])
    lon_max, lat_max = np.max([lon1max, lon2max]), np.max([lat1max, lat2max])

    bounds = [lon_min, lat_min, lon_max, lat_max]
    download_dem(bounds)

    orbit_file, prov = downloadSentinelOrbitFile(granule_ref, esa_credentials)
    orbit_file_ref = orbit_file
    orbit_file, prov = downloadSentinelOrbitFile(granule_sec, esa_credentials)
    orbit_file_sec = orbit_file

    burst_ids_ref = get_burst_ids(safe_ref, burst_granule_ref, orbit_file_ref)
    burst_ids_sec = get_burst_ids(safe_sec, burst_granule_sec, orbit_file_sec)

    write_yaml(safe_ref, orbit_file_ref, burst_ids_ref)
    run_rtc()
    ref = correct_geocode_slc(safe_ref, burst_granule_ref, orbit_file_ref)
    remove_temp_files(only_rtc=True)

    write_yaml(safe_sec, orbit_file_sec, burst_ids_sec)
    run_rtc()
    sec = correct_geocode_slc(safe_sec, burst_granule_sec, orbit_file_sec)

    remove_temp_files()

    bbox = process.get_raster_bbox(ref)
    y_limits = (bbox[1], bbox[3])
    x_limits = (bbox[0], bbox[2])

    scene_poly = geometry.polygon_from_bbox(x_limits, y_limits)
    parameter_info = utils.find_jpl_parameter_info(scene_poly, parameter_file=DEFAULT_PARAMETER_FILE)

    meta_r, meta_s = coregisterLoadMetadata(ref, sec)

    geogrid_info = runGeogrid(meta_r, meta_s, epsg=parameter_info['epsg'], **parameter_info['geogrid'])

    generateAutoriftProduct(
            ref, sec, nc_sensor='GS1', optical_flag=True, ncname=None,
            geogrid_run_info=geogrid_info, **parameter_info['autorift'],
            parameter_file=DEFAULT_PARAMETER_FILE.replace('/vsicurl/', ''),
        )


def process_burst_sentinel1_with_isce3_radar(burst_granule_ref, burst_granule_sec):
    esa_username, esa_password = get_esa_credentials()
    esa_credentials = (esa_username, esa_password)

    safe_ref = download_burst(burst_granule_ref)
    safe_sec = download_burst(burst_granule_sec)

    granule_ref = os.path.basename(safe_ref).split('.')[0]
    granule_sec = os.path.basename(safe_sec).split('.')[0]

    lon1min, lat1min, lon1max, lat1max = get_bounds_dem(safe_ref)
    lon2min, lat2min, lon2max, lat2max = get_bounds_dem(safe_sec)
    lon_min, lat_min = np.min([lon1min, lon2min]), np.min([lat1min, lat2min])
    lon_max, lat_max = np.max([lon1max, lon2max]), np.max([lat1max, lat2max])

    bounds = [lon_min, lat_min, lon_max, lat_max]
    download_dem(bounds)

    orbit_file, prov = downloadSentinelOrbitFile(granule_ref, esa_credentials=esa_credentials)
    orbit_file_ref = orbit_file
    orbit_file, prov = downloadSentinelOrbitFile(granule_sec, esa_credentials=esa_credentials)
    orbit_file_sec = orbit_file

    burst_id_ref = get_burst_id(safe_ref, burst_granule_ref, orbit_file_ref)
    burst_id_sec = get_burst_id(safe_sec, burst_granule_sec, orbit_file_sec)

    write_yaml_radar(safe_ref, orbit_file_ref)
    s1_cslc.run('s1_cslc.yaml', 'radar')
    ref = convert2isce(burst_id_ref)

    write_yaml_radar(safe_sec, orbit_file_sec, burst_id_sec)
    s1_cslc.run('s1_cslc.yaml', 'radar')
    sec = convert2isce(burst_id_sec, ref=False)

    swath = int(burst_granule_ref.split('_')[2][2])
    meta_r = loadMetadata(safe_ref, orbit_file_ref, swath=swath)
    meta_temp = loadMetadata(safe_sec, orbit_file_sec, swath=swath)
    meta_s = copy.copy(meta_r)
    meta_s.sensingStart = meta_temp.sensingStart
    meta_s.sensingStop = meta_temp.sensingStop

    lat_limits, lon_limits = bounding_box(safe_ref, orbit_file_ref, swath=swath)

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


def process_sentinel1_with_isce3_slc(slc_ref, slc_sec):
    esa_username, esa_password = get_esa_credentials()
    esa_credentials = (esa_username, esa_password)

    for scene in [slc_ref, slc_sec]:
        scene_url = get_download_url(scene)
        download_file(scene_url, chunk_size=5242880)

    safe_ref = sorted(glob.glob('./*.zip'))[0]
    safe_sec = sorted(glob.glob('./*.zip'))[1]

    lon1min, lat1min, lon1max, lat1max = get_bounds_dem(safe_ref)
    lon2min, lat2min, lon2max, lat2max = get_bounds_dem(safe_sec)
    lon_min, lat_min = np.min([lon1min, lon2min]), np.min([lat1min, lat2min])
    lon_max, lat_max = np.max([lon1max, lon2max]), np.max([lat1max, lat2max])

    bounds = [lon_min, lat_min, lon_max, lat_max]
    download_dem(bounds)

    orbit_file_ref, _ = downloadSentinelOrbitFile(slc_ref, esa_credentials=esa_credentials)
    orbit_file_sec, _ = downloadSentinelOrbitFile(slc_sec, esa_credentials=esa_credentials)

    burst_ids_ref = get_burst_ids(safe_ref, orbit_file_ref)
    burst_ids_sec = get_burst_ids(safe_sec, orbit_file_sec)

    write_yaml_radar(safe_ref, orbit_file_ref)
    s1_cslc.run('s1_cslc.yaml', 'radar')
    print('Bursts ref', burst_ids_ref)
    print('Bursts sec', burst_ids_sec)
    burst_ids = list(set(burst_ids_sec) & set(burst_ids_ref))

    for burst_id_sec in burst_ids:
        print('Burst', burst_id_sec)
        write_yaml_radar(safe_sec, orbit_file_sec, burst_id_sec)
        s1_cslc.run('s1_cslc.yaml', 'radar')

    mergeSwaths(ref=False)
    mergeSwaths()

    meta_r = loadMetadataSlc(safe_ref, orbit_file_ref)
    meta_temp = loadMetadataSlc(safe_sec, orbit_file_sec)
    meta_s = copy.copy(meta_r)
    meta_s.sensingStart = meta_temp.sensingStart
    meta_s.sensingStop = meta_temp.sensingStop

    lat_limits, lon_limits = bounding_box(safe_ref, orbit_file_ref)

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


def mergeSwaths(ref=True, swath=None):
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
    burst_ids = get_burst_ids(path, orbit_path)
    if ref:
        fileList = sorted(glob.glob('./product/*'))
        output = 'reference.slc'
    else:
        fileList = sorted(glob.glob('./product_sec/*'))
        output = 'secondary.slc'

    # Check against metadata
    if len(burst_ids) != len(fileList):
        print('Warning : Not all the bursts were processed')

    bursts = []
    total_width = 0
    starts = []
    offsx = [0]

    if swath is None:
        swaths = [1, 2, 3]
    else:
        swaths = [swath]

    pol = getPol(safe, orbit_file)

    for swath in swaths:
        mergeBurstsSwath(swath, ref)
        burstst = s1reader.load_bursts(safe, orbit_file, swath, pol)
        total_width += burstst[0].shape[1]
        bursts += burstst
        dt = burstst[0].azimuth_time_interval
        sensingStopt = burstst[-1].sensing_start + timedelta(seconds=(burstst[0].shape[0]-1) * dt)
        starts.append(burstst[0].sensing_start)
        sensingStartt = burstst[0].sensing_start
        if swath == 1:
            sensingStart = sensingStartt
            dt = bursts[-1].azimuth_time_interval
            sensingStop = sensingStopt
        if sensingStart > sensingStartt:
            sensingStart = sensingStartt
        if sensingStop < sensingStopt:
            sensingStop = sensingStopt
        if swath > 1:
            offsx.append(int(np.round((burstst[0].starting_range-bursts[0].starting_range) /
                             bursts[0].range_pixel_spacing)))

    total_width = int(np.round((bursts[-1].starting_range-bursts[0].starting_range) /
                      bursts[0].range_pixel_spacing))+bursts[-1].shape[1]
    nLines = int(np.round((sensingStop - sensingStart).total_seconds() / dt)) + 1
    outArray = np.zeros((nLines, total_width), dtype=complex)
    for swath in swaths:
        offy = int(np.round((starts[swath-1]-sensingStart).total_seconds() / dt))
        offx = offsx[swath-1]
        slc = 'swath_iw'+str(swath)+'.slc'
        ds = gdal.Open(slc)
        band = ds.GetRasterBand(1)
        if swath == 1:
            tran = ds.GetGeoTransform()
            proj = ds.GetProjection()
        current = band.ReadAsArray()
        band = None
        ds = None
        print('Offsets', offx, offy)
        if swath == 1:
            outArray[offy:offy+current.shape[0], offx:offx+current.shape[1]] = current
        else:
            temp = outArray[offy:offy+current.shape[0], offx:offx+current.shape[1]]
            cond = np.logical_and(np.abs(temp) == 0, np.logical_not(np.abs(current) == 0))
            outArray[offy:offy+current.shape[0], offx:offx+current.shape[1]][cond] = current[cond]
            temp = None
            del temp

    nodata = 0
    driver = gdal.GetDriverByName('ENVI')
    outRaster = driver.Create(output, total_width, nLines, 1, gdal.GDT_CFloat32)
    outRaster.SetGeoTransform(tran)
    outRaster.SetProjection(proj)
    outband = outRaster.GetRasterBand(1)
    outband.SetNoDataValue(nodata)
    outband.WriteArray(outArray)
    outband.FlushCache()
    del outRaster
    subprocess.call('rm -rf swath_*iw*', shell=True)


def mergeBurstsSwath(swath, ref=True, outfile='output.slc', method='top'):
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


def geocode_burst_temp(burst_granule_ref, index):
    esa_username, esa_password = get_esa_credentials()

    safe_ref = sorted(glob.glob('./*.SAFE'))[index]
    granule_ref = os.path.basename(safe_ref).split('.')[0]

    orbit_file_ref, provider_ref = downloadSentinelOrbitFile(granule_ref, esa_credentials=(esa_username, esa_password))

    str_burst_ids_ref = get_burst_ids(safe_ref, burst_granule_ref, orbit_file_ref)

    write_yaml(safe_ref, orbit_file_ref, str_burst_ids_ref)
    run_rtc()
    correct_geocode_slc(safe_ref, burst_granule_ref, orbit_file_ref)


def geocode_burst(burst_granule):
    esa_username, esa_password = get_esa_credentials()

    download_bursts(burst_granule)
    safe = glob.glob('./*.SAFE')[0]

    bounds = get_bounds_dem(safe)
    download_dem(bounds)
    granule = os.path.basename(safe).split('.')[0]
    orbit_file, provider = downloadSentinelOrbitFile(granule, esa_credentials=(esa_username, esa_password))

    str_burst_ids = get_burst_ids(safe, burst_granule, orbit_file)
    write_yaml(safe, orbit_file, str_burst_ids)
    run_rtc()
    correct_geocode_slc(safe, burst_granule, orbit_file)

    remove_temp_files()


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


# def download_bursts(burst_granule):
#     start = (datetime.strptime(burst_granule.split('_')[3], '%Y%m%dT%H%M%S')-timedelta(days=1)).strftime('%Y-%m-%d')
#     end = (datetime.strptime(burst_granule.split('_')[3], '%Y%m%dT%H%M%S')+timedelta(days=1)).strftime('%Y-%m-%d')
#     pol = burst_granule.split('_')[4]
#     results = asf_search.search(product_list=[burst_granule])
#     burst_id = results[0].properties['burst']['fullBurstID']
#     if burst_id[-1] == '1':
#         burst_id1 = burst_id.replace('IW1', 'IW2')
#         results = asf_search.search(fullBurstID=burst_id1, start=start, end=end, polarization=pol)
#         burst_add1 = results[0].properties['fileID']
#         burst_id2 = burst_id.replace('IW1', 'IW3')
#         results = asf_search.search(fullBurstID=burst_id2, start=start, end=end, polarization=pol)
#         burst_add2 = results[0].properties['fileID']
#         bursts = [burst_granule, burst_add1, burst_add2]
#     elif burst_id[-1] == '2':
#         burst_id1 = burst_id.replace('IW2', 'IW1')
#         results = asf_search.search(fullBurstID=burst_id1, start=start, end=end, polarization=pol)
#         burst_add1 = results[0].properties['fileID']
#         burst_id2 = burst_id.replace('IW2', 'IW3')
#         results = asf_search.search(fullBurstID=burst_id2, start=start, end=end, polarization=pol)
#         burst_add2 = results[0].properties['fileID']
#         bursts = [burst_add1, burst_granule, burst_add2]
#     elif burst_id[-1] == '3':
#         burst_id1 = burst_id.replace('IW3', 'IW1')
#         results = asf_search.search(fullBurstID=burst_id1, start=start, end=end, polarization=pol)
#         burst_add1 = results[0].properties['fileID']
#         burst_id2 = burst_id.replace('IW3', 'IW2')
#         results = asf_search.search(fullBurstID=burst_id2, start=start, end=end, polarization=pol)
#         burst_add2 = results[0].properties['fileID']
#         bursts = [burst_add1, burst_add2, burst_granule]
#     else:
#         raise Exception('The name of the granule is not valid')

#     subprocess.call('burst2safe '+' '.join(bursts), shell=True)


def get_burst(safe, burst_granule, orbit_file):
    abspath = os.path.abspath(safe)
    swath = burst_granule.split('_')[2]
    swath_number = int(swath[2])
    pol = burst_granule.split('_')[4]
    bursts = s1reader.load_bursts(abspath, orbit_file, swath_number, pol)

    return bursts[0]


def get_burst_id(safe, burst_granule, orbit_file):
    abspath = os.path.abspath(safe)
    orbit_number = burst_granule.split('_')[1]
    swath = burst_granule.split('_')[2]
    swath_number = int(swath[2])
    pol = burst_granule.split('_')[4]
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


def get_burst_ids(safe, orbit_file):
    abspath = os.path.abspath(safe)
    bursts = []
    pol = getPol(safe, orbit_file)

    for swath_number in [1, 2, 3]:
        bursts += s1reader.load_bursts(abspath, orbit_file, swath_number, pol)
    str_burst_ids = ['t'+str(int(x.burst_id.track_number)).zfill(3) + '_' +
                     str(x.burst_id.esa_burst_id).zfill(6) + '_' +
                     x.burst_id.subswath.lower() for x in bursts]

    return str_burst_ids


def get_beta(safe, burst_granule, orbit_file):
    abspath = os.path.abspath(safe)
    swath = burst_granule.split('_')[2]
    swath_number = int(swath[2])
    pol = burst_granule.split('_')[4]
    bursts = s1reader.load_bursts(abspath, orbit_file, swath_number, pol)
    rad = str(bursts[0].burst_calibration.beta_naught)

    return rad


def get_bounds_dem(safe):
    bounds = s1_info.get_frame_bounds(os.path.basename(safe))
    bounds = [int(bounds[0])-1, int(bounds[1]), math.ceil(bounds[2])+1, math.ceil(bounds[3])]

    return bounds


def get_bounds_dem1(safe):
    bounds = s1_info.get_frame_bounds(os.path.basename(safe))
    bounds = [bounds[0]-0.1, bounds[1], bounds[2]+0.1, bounds[3]]

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


def write_yaml(safe, orbit_file, burst_id):
    abspath = os.path.abspath(safe)
    yaml_folder = os.path.dirname(hyp3_autorift.__file__)+'/schemas'
    yaml = open(f'{yaml_folder}/rtc_s1_template.yaml', 'r')
    lines = yaml.readlines()
    yaml.close()

    yaml = open('rtc_s1.yaml', 'w')
    newstring = ''
    for line in lines:
        if 's1_rtc_image' in line:
            newstring += line.replace('s1_rtc_image', abspath)
        elif 's1_orbit_file' in line:
            orbit = os.path.abspath(orbit_file)
            newstring += line.replace('s1_orbit_file', orbit)
        elif 'burst_ids' in line:
            newstring += line.replace('burst_ids', burst_id)
        else:
            newstring = line
        yaml.write(newstring)
    yaml.close()


def write_yaml_radar(safe, orbit_file, burst_id=None):
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


def write_yaml_burst(safe, orbit_file, burst_id_ref, burst_id=None):
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
                newstring += line.replace('burst_ids', '[\''+burst_id_ref+'\']')
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


def run_rtc():
    subprocess.call('rtc_s1_single_job.py rtc_s1.yaml', shell=True)


def correct_geocode_slc(safe, burst_granule, orbit_file):
    granule = os.path.basename(safe).split('.')[0]
    rtc = glob.glob('./output_dir/OPERA*.tif')[0]

    rad = get_beta(safe, burst_granule, orbit_file)

    output = 'GS1_OPERA_BURST'+granule.split('IW_SLC')[1]+'.tif'
    subprocess.call(f"gdal_calc.py --type=UInt16 -A {rtc} --calc='numpy.sqrt(A)*{rad}' --outfile={output}", shell=True)

    return output


def remove_temp_files(only_rtc=False):
    if only_rtc:
        subprocess.call('rm -rf output_dir scratch_dir rtc.log rtc_s1.yaml', shell=True)
    else:
        subprocess.call('rm -rf output_dir *SAFE *EOF scratch_dir dem.tif rtc.log rtc_s1.yaml', shell=True)
