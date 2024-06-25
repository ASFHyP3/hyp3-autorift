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
from dem_stitcher import stitch_dem
from hyp3lib.get_orb import downloadSentinelOrbitFile
from s1reader import s1_info

import hyp3_autorift
from hyp3_autorift import geometry, process, utils
from hyp3_autorift.process import DEFAULT_PARAMETER_FILE
from hyp3_autorift.vend.testGeogridOptical import coregisterLoadMetadata
from hyp3_autorift.vend.testGeogridOptical import runGeogrid
from hyp3_autorift.vend.testautoRIFT import generateAutoriftProduct


ESA_HOST = 'dataspace.copernicus.eu'


def process_burst_sentinel1_with_isce3(burst_granule_ref, burst_granule_sec):
    esa_username, esa_password = get_esa_credentials()
    esa_credentials = (esa_username, esa_password)

    download_bursts(burst_granule_ref)
    download_bursts(burst_granule_sec)

    safe_ref = sorted(glob.glob('./*.SAFE'))[0]
    safe_sec = sorted(glob.glob('./*.SAFE'))[1]

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


def download_bursts(burst_granule):
    start = (datetime.strptime(burst_granule.split('_')[3], '%Y%m%dT%H%M%S')-timedelta(days=1)).strftime('%Y-%m-%d')
    end = (datetime.strptime(burst_granule.split('_')[3], '%Y%m%dT%H%M%S')+timedelta(days=1)).strftime('%Y-%m-%d')
    pol = burst_granule.split('_')[4]
    results = asf_search.search(product_list=[burst_granule])
    burst_id = results[0].properties['burst']['fullBurstID']
    if burst_id[-1] == '1':
        burst_id1 = burst_id.replace('IW1', 'IW2')
        results = asf_search.search(fullBurstID=burst_id1, start=start, end=end, polarization=pol)
        burst_add1 = results[0].properties['fileID']
        burst_id2 = burst_id.replace('IW1', 'IW3')
        results = asf_search.search(fullBurstID=burst_id2, start=start, end=end, polarization=pol)
        burst_add2 = results[0].properties['fileID']
        bursts = [burst_granule, burst_add1, burst_add2]
    elif burst_id[-1] == '2':
        burst_id1 = burst_id.replace('IW2', 'IW1')
        results = asf_search.search(fullBurstID=burst_id1, start=start, end=end, polarization=pol)
        burst_add1 = results[0].properties['fileID']
        burst_id2 = burst_id.replace('IW2', 'IW3')
        results = asf_search.search(fullBurstID=burst_id2, start=start, end=end, polarization=pol)
        burst_add2 = results[0].properties['fileID']
        bursts = [burst_add1, burst_granule, burst_add2]
    elif burst_id[-1] == '3':
        burst_id1 = burst_id.replace('IW3', 'IW1')
        results = asf_search.search(fullBurstID=burst_id1, start=start, end=end, polarization=pol)
        burst_add1 = results[0].properties['fileID']
        burst_id2 = burst_id.replace('IW3', 'IW2')
        results = asf_search.search(fullBurstID=burst_id2, start=start, end=end, polarization=pol)
        burst_add2 = results[0].properties['fileID']
        bursts = [burst_add1, burst_add2, burst_granule]
    else:
        raise Exception('The name of the granule is not valid')

    subprocess.call('burst2safe '+' '.join(bursts), shell=True)


def get_burst_ids(safe, burst_granule, orbit_file):
    abspath = os.path.abspath(safe)
    swath = burst_granule.split('_')[2]
    swath_number = int(swath[2])
    pol = burst_granule.split('_')[4]
    bursts = s1reader.load_bursts(abspath, orbit_file, swath_number, pol)
    str_burst_ids = ', '.join(['t'+str(int(x.burst_id.track_number)).zfill(3)
                               + '_'+str(x.burst_id.esa_burst_id).zfill(6)+'_'
                               + x.burst_id.subswath.lower() for x in bursts])

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


def download_dem(bounds):
    X, p = stitch_dem(bounds,
                      dem_name='glo_30',  # Global Copernicus 30 meter resolution DEM
                      dst_ellipsoidal_height=False,
                      dst_area_or_point='Point')

    with rasterio.open('dem.tif', 'w', **p) as ds:
        ds.write(X, 1)
        ds.update_tags(AREA_OR_POINT='Point')


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
