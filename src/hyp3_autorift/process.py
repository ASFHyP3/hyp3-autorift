"""
Package for processing with autoRIFT
"""

import argparse
import json
import logging
import os
import shutil
import warnings
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Callable, Literal, Optional, Tuple

import boto3
import botocore.exceptions
import numpy as np
import requests
from hyp3lib.aws import upload_file_to_s3
from hyp3lib.image import create_thumbnail
from hyp3lib.util import string_is_true
from netCDF4 import Dataset
from osgeo import gdal

from hyp3_autorift import geometry, image, utils
from hyp3_autorift.crop import crop_netcdf_product
from hyp3_autorift.utils import get_opendata_prefix, get_platform, save_publication_info


log = logging.getLogger(__name__)

gdal.UseExceptions()

S3_CLIENT = boto3.client('s3')

LC2_SEARCH_URL = 'https://landsatlook.usgs.gov/stac-server/collections/landsat-c2l1/items'
LANDSAT_BUCKET = 'usgs-landsat'
LANDSAT_SENSOR_MAPPING = {
    'L9': {'C': 'oli-tirs', 'O': 'oli-tirs', 'T': 'oli-tirs'},
    'L8': {'C': 'oli-tirs', 'O': 'oli-tirs', 'T': 'oli-tirs'},
    'L7': {'E': 'etm'},
    'L5': {'T': 'tm', 'M': 'mss'},
    'L4': {'T': 'tm', 'M': 'mss'},
}

DEFAULT_PARAMETER_FILE = (
    '/vsicurl/https://its-live-data.s3.amazonaws.com/autorift_parameters/v001/autorift_landice_0120m.shp'
)


def get_lc2_stac_json_key(scene_name: str) -> str:
    platform = get_platform(scene_name)
    year = scene_name[17:21]
    path = scene_name[10:13]
    row = scene_name[13:16]

    sensor = LANDSAT_SENSOR_MAPPING[platform][scene_name[1]]

    return f'collection02/level-1/standard/{sensor}/{year}/{path}/{row}/{scene_name}/{scene_name}_stac.json'


def get_lc2_metadata(scene_name: str) -> dict:
    response = requests.get(f'{LC2_SEARCH_URL}/{scene_name}')
    try:
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError:
        if response.status_code != 404:
            raise

    key = get_lc2_stac_json_key(scene_name)
    obj = S3_CLIENT.get_object(Bucket=LANDSAT_BUCKET, Key=key, RequestPayer='requester')
    return json.load(obj['Body'])


def get_lc2_path(metadata: dict) -> str:
    if metadata['id'][3] in ('4', '5'):
        band = metadata['assets'].get('B2.TIF')
        if band is None:
            band = metadata['assets']['green']
    elif metadata['id'][3] in ('7', '8', '9'):
        band = metadata['assets'].get('B8.TIF')
        if band is None:
            band = metadata['assets']['pan']
    else:
        raise NotImplementedError(f'autoRIFT processing not available for this platform. {metadata["id"][:3]}')

    return band['href'].replace('https://landsatlook.usgs.gov/data/', f'/vsis3/{LANDSAT_BUCKET}/')


def get_s2_safe_url(scene_name):
    root_url = 'https://storage.googleapis.com/gcp-public-data-sentinel-2/tiles'
    tile = f'{scene_name[39:41]}/{scene_name[41:42]}/{scene_name[42:44]}'
    return f'{root_url}/{tile}/{scene_name}.SAFE'


def get_s2_manifest(scene_name):
    safe_url = get_s2_safe_url(scene_name)
    manifest_url = f'{safe_url}/manifest.safe'
    response = requests.get(manifest_url)
    response.raise_for_status()
    return response.text


def get_s2_path(scene_name: str) -> str:
    bucket = 'its-live-project'
    key = f's2-cache/{scene_name}_B08.jp2'
    if s3_object_is_accessible(bucket, key):
        return f'/vsis3/{bucket}/{key}'

    manifest_text = get_s2_manifest(scene_name)
    root = ET.fromstring(manifest_text)
    elements = root.findall(".//fileLocation[@locatorType='URL'][@href]")
    hrefs = [
        element.attrib['href']
        for element in elements
        if element.attrib['href'].endswith('_B08.jp2') and '/IMG_DATA/' in element.attrib['href']
    ]
    if len(hrefs) == 1:
        # post-2016-12-06 scene; only one tile
        file_path = hrefs[0]
    else:
        # pre-2016-12-06 scene; choose the requested tile
        tile_token = scene_name.split('_')[5]
        file_path = [href for href in hrefs if href.endswith(f'_{tile_token}_B08.jp2')][0]
    safe_url = get_s2_safe_url(scene_name)
    return f'/vsicurl/{safe_url}/{file_path}'


def get_raster_bbox(path: str):
    info = gdal.Info(path, format='json')
    coordinates = info['wgs84Extent']['coordinates'][0]
    lons = [coord[0] for coord in coordinates]
    lats = [coord[1] for coord in coordinates]
    if max(lons) >= 170 and min(lons) <= -170:
        lons = [lon - 360 if lon >= 170 else lon for lon in lons]
    return [
        min(lons),
        min(lats),
        max(lons),
        max(lats),
    ]


def get_s2_metadata(scene_name):
    path = get_s2_path(scene_name)
    bbox = get_raster_bbox(path)
    acquisition_start = datetime.strptime(scene_name.split('_')[2], '%Y%m%dT%H%M%S')

    return {
        'path': path,
        'bbox': bbox,
        'id': scene_name,
        'properties': {
            'datetime': acquisition_start.isoformat(timespec='seconds') + 'Z',
        },
    }


def _create_mosaic_metadata(metas: list[dict]) -> dict:
    """Creates a union metadata object from a list of granule metadata"""
    log.info(f"Creating union metadata for {len(metas)} granules.")
    
    # Use first granule as base for properties (like projection)
    mosaic_meta = metas[0].copy()
    
    # Create a union of all bounding boxes
    try:
        min_lon = min(m['bbox'][0] for m in metas)
        min_lat = min(m['bbox'][1] for m in metas)
        max_lon = max(m['bbox'][2] for m in metas)
        max_lat = max(m['bbox'][3] for m in metas)
        union_bbox = [min_lon, min_lat, max_lon, max_lat]
    except KeyError:
        # Fallback if 'bbox' isn't present for some reason
        log.warning("Could not find 'bbox' in metadata. Using bbox from first granule only.")
        union_bbox = metas[0].get('bbox', [-180, -90, 180, 90])

    mosaic_meta['bbox'] = union_bbox
    # Overwrite ID to show it's a mosaic
    mosaic_meta['id'] = f"{metas[0].get('id', 'MOSAIC')}_AND_{len(metas)-1}_MORE" 
    
    log.info(f"Mosaic union BBOX: {union_bbox}")
    return mosaic_meta


def s3_object_is_accessible(bucket, key):
    try:
        S3_CLIENT.head_object(Bucket=bucket, Key=key)
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] in ['403', '404']:
            return False
        raise
    except botocore.exceptions.NoCredentialsError:
        warnings.warn('No AWS credentials found')
        return False
    return True


def least_precise_orbit_of(orbits):
    if any([orb is None for orb in orbits]):
        return 'O'
    if any(['RESORB' in orb for orb in orbits]):
        return 'R'
    return 'P'


def create_filtered_filepath(path: str) -> str:
    parent = (Path.cwd() / 'filtered').resolve()
    parent.mkdir(exist_ok=True)

    return str(parent / Path(path).name)


def prepare_array_for_filtering(array: np.ndarray, nodata: int) -> Tuple[np.ndarray, np.ndarray]:
    valid_domain = array != nodata
    array[~valid_domain] = 0
    return array.astype(np.float32), valid_domain


def apply_fft_filter(array: np.ndarray, nodata: int) -> Tuple[np.ndarray, None]:
    from autoRIFT.autoRIFT import _fft_filter, _wallis_filter

    array, valid_domain = prepare_array_for_filtering(array, nodata)
    wallis = _wallis_filter(array, filter_width=5)
    wallis[~valid_domain] = 0

    filtered = _fft_filter(wallis, valid_domain, power_threshold=500)
    filtered[~valid_domain] = 0

    return filtered, None


def apply_wallis_nodata_fill_filter(array: np.ndarray, nodata: int) -> Tuple[np.ndarray, np.ndarray]:
    """
    Wallis filter with nodata infill for L7 SLC Off preprocessing
    """
    from autoRIFT.autoRIFT import _wallis_filter_fill

    array, _ = prepare_array_for_filtering(array, nodata)
    filtered, zero_mask = _wallis_filter_fill(array, filter_width=5, std_cutoff=0.25)
    filtered[zero_mask] = 0

    return filtered, zero_mask


def _apply_filter_function(image_path: str, filter_function: Callable) -> Tuple[str, Optional[str]]:
    image_array, image_transform, image_projection, _, image_nodata = utils.load_geospatial(image_path)
    image_array = image_array.astype(np.float32)

    image_filtered, zero_mask = filter_function(image_array, image_nodata)

    image_new_path = create_filtered_filepath(image_path)
    _ = utils.write_geospatial(
        image_new_path, image_filtered, image_transform, image_projection, nodata=None, dtype=gdal.GDT_Float32
    )

    zero_path = None
    if zero_mask is not None:
        zero_path = create_filtered_filepath(f'{Path(image_new_path).stem}_zeroMask{Path(image_new_path).suffix}')
        _ = utils.write_geospatial(
            zero_path, zero_mask, image_transform, image_projection, nodata=np.iinfo(np.uint8).max, dtype=gdal.GDT_Byte
        )

    return image_new_path, zero_path


def apply_landsat_filtering(reference_path: str, secondary_path: str) -> Tuple[str, Optional[str], str, Optional[str]]:
    reference_platform = get_platform(Path(reference_path).name)
    secondary_platform = get_platform(Path(secondary_path).name)
    if reference_platform > 'L7' and secondary_platform > 'L7':
        raise NotImplementedError(
            f'{reference_platform}+{secondary_platform} pairs should be highpass filtered in autoRIFT instead'
        )

    platform_filter_dispatch = {
        'L4': apply_fft_filter,
        'L5': apply_fft_filter,
        'L7': apply_wallis_nodata_fill_filter,
        'L8': apply_wallis_nodata_fill_filter,  # sometimes paired w/ L7 scenes, so use same filter
    }
    try:
        reference_filter = platform_filter_dispatch[reference_platform]
        secondary_filter = platform_filter_dispatch[secondary_platform]
    except KeyError:
        raise NotImplementedError('Unknown pre-processing filter for satellite platform')

    if reference_filter != secondary_filter:
        raise NotImplementedError('AutoRIFT not available for image pairs with different preprocessing methods')

    reference_path, reference_zero_path = _apply_filter_function(reference_path, reference_filter)
    secondary_path, secondary_zero_path = _apply_filter_function(secondary_path, secondary_filter)

    return reference_path, reference_zero_path, secondary_path, secondary_zero_path


def process(
    reference: list[str],
    secondary: list[str],
    parameter_file: str = DEFAULT_PARAMETER_FILE,
    chip_size: int | None = None,
    search_range: int | None = None,
    naming_scheme: Literal['ITS_LIVE_OD', 'ITS_LIVE_PROD'] = 'ITS_LIVE_OD',
    publish_bucket: str = '',
    use_static_files: bool = True,
    frame_id: str | None = None,
) -> Tuple[Path, Path, Path]:
    """Process a Sentinel-1, Sentinel-2, or Landsat-8 image pair

    Args:
        reference: Name of the reference Sentinel-1 (or list of bursts), Sentinel-2, or Landsat-8 Collection 2 scene
        secondary: Name of the secondary Sentinel-1 (or list of bursts), Sentinel-2, or Landsat-8 Collection 2 scene
        parameter_file: Shapefile for determining the correct search parameters by geographic location
        chip_size: (Optional) Specify a single chip size (e.g., 64). Overrides parameter-file approach and uses a static chip size value.
        search_range: (Optional) Specify a search range in pixels (e.g., 32 or 64). Overrides parameter-file defaults.
        naming_scheme: Naming scheme to use for product files
        publish_bucket: S3 bucket to upload Sentinel-1 static topographic correction files to
        use_static_files: Use pre-generated static topographic correction files if available
        frame_id: OPERA frame ID to record in the img_pair_info variable in the autoRIFT product file

    Returns:
        the autoRIFT product file, browse image, thumbnail image
    """
    reference_path = None
    secondary_path = None
    reference_metadata = None
    secondary_metadata = None
    reference_zero_path = None
    secondary_zero_path = None

    platform = get_platform(reference[0])

    if platform == 'S1-BURST':
        from hyp3_autorift.s1_isce3 import process_sentinel1_burst_isce3

        netcdf_file = process_sentinel1_burst_isce3(reference, secondary, publish_bucket, use_static_files, frame_id, chip_size=chip_size)

    elif platform == 'S1-SLC':
        from hyp3_autorift.s1_isce3 import process_sentinel1_slc_isce3

        netcdf_file = process_sentinel1_slc_isce3(reference[0], secondary[0], publish_bucket, use_static_files, chip_size=chip_size)

    else:
        # Set config and env for new CXX threads in Geogrid/autoRIFT
        gdal.SetConfigOption('GDAL_DISABLE_READDIR_ON_OPEN', 'EMPTY_DIR')
        os.environ['GDAL_DISABLE_READDIR_ON_OPEN'] = 'EMPTY_DIR'

        gdal.SetConfigOption('AWS_REGION', 'us-west-2')
        os.environ['AWS_REGION'] = 'us-west-2'

        # Initialize lists used for mosaicking multiple scenes (if applicable)
        ref_metas = []
        ref_paths = []
        sec_metas = []
        sec_paths = []

        if platform == 'S2':
            log.info(f"Processing {len(reference)} reference S2 granules.")
            for granule in reference:
                meta = get_s2_metadata(granule)
                ref_metas.append(meta)
                ref_paths.append(meta['path'])
            log.info(f"Processing {len(secondary)} secondary S2 granules.")
            for granule in secondary:
                meta = get_s2_metadata(granule)
                sec_metas.append(meta)
                sec_paths.append(meta['path'])

        elif 'L' in platform:
            # Set config and env for new CXX threads in Geogrid/autoRIFT
            gdal.SetConfigOption('AWS_REQUEST_PAYER', 'requester')
            os.environ['AWS_REQUEST_PAYER'] = 'requester'

            log.info(f"Processing {len(reference)} reference Landsat Collection 2 granules.")
            for granule in reference:
                meta = get_lc2_metadata(granule)
                ref_metas.append(meta)
                ref_paths.append(get_lc2_path(meta))
            log.info(f"Processing {len(secondary)} secondary Landsat Collection 2 granules.")
            for granule in secondary:
                meta = get_lc2_metadata(granule)
                sec_metas.append(meta)
                sec_paths.append(get_lc2_path(meta))

        # Handle mosaicking/metadata if multiple scenes were provided, otherwise just get metadata from the single scene        
        if len(ref_paths) > 1:
            reference_path = f'{reference[0]}.vrt'
            log.info(f"Creating VRT mosaic: {reference_path}")
            gdal.BuildVRT(reference_path, ref_paths)
            reference_metadata = _create_mosaic_metadata(ref_metas)
        else:
            reference_path = ref_paths[0]
            reference_metadata = ref_metas[0]
        
        if len(sec_paths) > 1:
            secondary_path = f'{secondary[0]}.vrt'
            log.info(f"Creating VRT mosaic: {secondary_path}")
            gdal.BuildVRT(secondary_path, sec_paths)
            secondary_metadata = _create_mosaic_metadata(sec_metas)
        else:
            secondary_path = sec_paths[0]
            secondary_metadata = sec_metas[0]

        if 'L' in platform:
            filter_platform = min([platform, get_platform(secondary[0])])
            if filter_platform in ('L4', 'L5', 'L7'):
                # Log path here before we transform it
                log.info(f'Reference scene path: {reference_path}')
                log.info(f'Secondary scene path: {secondary_path}')
                reference_path, reference_zero_path, secondary_path, secondary_zero_path = apply_landsat_filtering(
                    reference_path, secondary_path
                )

            if reference_metadata['properties']['proj:epsg'] != secondary_metadata['properties']['proj:epsg']:
                log.info('Reference and secondary projections are different! Reprojecting.')

                # Reproject zero masks if necessary
                if reference_zero_path and secondary_zero_path:
                    _, _ = utils.ensure_same_projection(reference_zero_path, secondary_zero_path)

                reference_path, secondary_path = utils.ensure_same_projection(reference_path, secondary_path)

        assert reference_metadata is not None
        bbox = reference_metadata['bbox']
        lat_limits = (bbox[1], bbox[3])
        lon_limits = (bbox[0], bbox[2])

        log.info(f'Reference scene path: {reference_path}')
        log.info(f'Secondary scene path: {secondary_path}')

        scene_poly = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
        parameter_info = utils.find_jpl_parameter_info(scene_poly, parameter_file)

        if chip_size is not None:
            # Add static chipSize to parameter_info geogrid params
            parameter_info['geogrid']['ChipSizeX'] = chip_size
            parameter_info['geogrid']['ChipSizeY'] = chip_size
            # Add static chipSize to parameter_info autorift params and remove tif-file parameters
            parameter_info['autorift']['ChipSizeX'] = chip_size
            parameter_info['autorift']['ChipSizeY'] = chip_size
            parameter_info['autorift']['chip_size_min'] = None
            parameter_info['autorift']['chip_size_max'] = None

        if search_range is not None:
            log.info(f"Overriding search range with user-defined value: {search_range}")
            # Inject user-specified search_range into 'autorift' dictionary
            parameter_info['autorift']['SearchLimitX'] = search_range
            parameter_info['autorift']['SearchLimitY'] = search_range
            # Nullify Reference Velocity for non-glacier applications
            parameter_info['autorift']['NullReferenceVelocity'] = True

        from hyp3_autorift.vend.testGeogrid import coregisterLoadMetadata, runGeogrid

        meta_r, meta_s = coregisterLoadMetadata(
            reference_path,
            secondary_path,
            reference_metadata=reference_metadata,
            secondary_metadata=secondary_metadata,
        )
        geogrid_info = runGeogrid(meta_r, meta_s, epsg=parameter_info['epsg'], **parameter_info['geogrid'])

        from hyp3_autorift.vend.testautoRIFT import generateAutoriftProduct

        netcdf_file = generateAutoriftProduct(
            reference_path,
            secondary_path,
            nc_sensor=platform,
            optical_flag=True,
            ncname=None,
            reference_metadata=reference_metadata,
            secondary_metadata=secondary_metadata,
            geogrid_run_info=geogrid_info,
            **parameter_info['autorift'],
            parameter_file=DEFAULT_PARAMETER_FILE.replace('/vsicurl/', ''),
        )

    if netcdf_file is None:
        raise Exception('Processing failed! Output netCDF file not found')

    netcdf_file = Path(netcdf_file)
    if naming_scheme == 'ITS_LIVE_OD':
        product_file = netcdf_file.with_stem(f'{netcdf_file.stem}_IL_ASF_OD')
    else:
        product_file = netcdf_file

    log.info(f'Successfully created autoRIFT product: {product_file}')

    if not netcdf_file.name.endswith('_P000.nc'):
        log.info('Cropping product to the valid data extent')
        cropped_file = crop_netcdf_product(netcdf_file)
        netcdf_file.unlink()
        shutil.move(cropped_file, str(product_file))
    else:
        shutil.move(netcdf_file, str(product_file))

    with Dataset(product_file) as nc:
        velocity = nc.variables['v']
        data = np.ma.masked_values(velocity, -32767.0).filled(0)

    browse_file = product_file.with_suffix('.png')
    image.make_browse(browse_file, data)

    thumbnail_file = create_thumbnail(browse_file)

    return product_file, browse_file, thumbnail_file


def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--bucket', help='AWS bucket to upload product files to')
    parser.add_argument('--bucket-prefix', default='', help='AWS prefix (location in bucket) to add to product files')
    parser.add_argument(
        '--publish-bucket',
        type=utils.nullable_string,
        default=None,
        help='Additionally, publish products to this bucket. Necessary credentials must be provided '
        'via the `PUBLISH_ACCESS_KEY_ID` and `PUBLISH_SECRET_ACCESS_KEY` environment variables.',
    )
    parser.add_argument(
        '--parameter-file',
        default=DEFAULT_PARAMETER_FILE,
        help='Shapefile for determining the correct search parameters by geographic location. '
        'Path to shapefile must be understood by GDAL',
    )

    parser.add_argument(
        '--chip-size',
        type=utils.nullable_int,
        default=None,
        help='(Optional) Specify a single chip size (e.g., 64). Overrides parameter-file approach.',
    )

    parser.add_argument(
        '--search-range',
        type=utils.nullable_int,
        default=None,
        help='(Optional) Specify a search range in pixels (e.g., 32 or 64). Overrides parameter-file defaults.',
    )

    parser.add_argument(
        '--naming-scheme',
        default='ITS_LIVE_OD',
        choices=['ITS_LIVE_OD', 'ITS_LIVE_PROD'],
        help='Naming scheme to use for product files',
    )
    parser.add_argument(
        'granules',
        type=utils.nullable_granule_list,
        nargs='*',
        help='Pair of Sentinel-1, Sentinel-1 Burst, Sentinel-2, or Landsat-8 Collection 2 granules (scenes) to '
        'process. Cannot be used with the `--reference` or `--secondary` arguments.',
    )
    parser.add_argument(
        '--reference',
        type=utils.nullable_granule_list,
        default=[],
        nargs='+',
        help='List of reference Sentinel-1, Sentinel-1 Burst, Sentinel-2, or Landsat-8 Collection 2 granules (scenes) '
        'to process. Cannot be used with the `granules` arguments.',
    )
    parser.add_argument(
        '--secondary',
        type=utils.nullable_granule_list,
        default=[],
        nargs='+',
        help='List of secondary Sentinel-1, Sentinel-1 Burst, Sentinel-2, or Landsat-8 Collection 2 granules (scenes) '
        'to process. Cannot be used with the `granules` arguments.',
    )
    parser.add_argument(
        '--use-static-files',
        type=string_is_true,
        default=True,
        help='Use static topographic correction files for ISCE3 processing if available (Sentinel-1 only).',
    )
    parser.add_argument(
        '--frame-id',
        type=utils.nullable_string,
        default=None,
        help='Optional OPERA frame ID to include in metadata for Sentinel-1 multi-burst processing, '
        'and will be ignored otherwise.',
    )
    args = parser.parse_args()

    logging.basicConfig(
        format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.INFO
    )

    granules = [item for sublist in args.granules for item in sublist]
    reference = [item for sublist in args.reference for item in sublist]
    secondary = [item for sublist in args.secondary for item in sublist]

    has_granules = len(granules) > 0
    has_ref_sec = len(reference) > 0 and len(secondary) > 0

    if not (has_granules or has_ref_sec):
        parser.error('Must provide either `granules` or `--reference` and `--secondary`.')
    if has_granules and has_ref_sec:
        parser.error('Must provide granules OR --reference and --secondary, not both.')
    if has_granules and len(granules) != 2:
        parser.error('Must provide exactly two granules.')

    if has_granules:
        # FIXME: won't actually warn because of: https://github.com/ASFHyP3/burst2safe/issues/160
        warnings.warn(
            'The positional argument for granules is deprecated and will be removed in a future release. '
            'Please use --reference and --secondary.',
            DeprecationWarning,
        )

        granules_sorted = utils.sort_ref_sec([granules[0]], [granules[1]])
        reference = granules_sorted[0]
        secondary = granules_sorted[1]
    else:
        reference, secondary = utils.sort_ref_sec(reference, secondary)
    
    try:
        ref_platforms = {get_platform(scene) for scene in reference}
        sec_platforms = {get_platform(scene) for scene in secondary}
    except NotImplementedError as e:
        parser.error(str(e))

    allowed_multi_platforms = {'S1-BURST', 'S2', 'L4', 'L5', 'L7', 'L8', 'L9'}
    if len(reference) > 1 and not ref_platforms.issubset(allowed_multi_platforms):
        parser.error('Only Sentinel-1 bursts, Sentinel-2, and Landsat support multiple reference scenes.')

    landsat_missions = {'L4', 'L5', 'L7', 'L8', 'L9'}
    if ref_platforms != sec_platforms and not (ref_platforms | sec_platforms).issubset(landsat_missions):
        parser.error('all scenes must be of the same type.')

    is_optical = ref_platforms.issubset({'S2'} | landsat_missions)
    if not is_optical and len(reference) != len(secondary):
        parser.error('Must provide the same number of reference and secondary scenes.')

    product_file, browse_file, thumbnail_file = process(
        reference,
        secondary,
        parameter_file=args.parameter_file,
        chip_size=args.chip_size,
        search_range=args.search_range,
        naming_scheme=args.naming_scheme,
        publish_bucket=args.publish_bucket,
        use_static_files=args.use_static_files,
        frame_id=args.frame_id,
    )

    if args.bucket:
        upload_file_to_s3(product_file, args.bucket, args.bucket_prefix)
        upload_file_to_s3(browse_file, args.bucket, args.bucket_prefix)
        upload_file_to_s3(thumbnail_file, args.bucket, args.bucket_prefix)

    if args.publish_bucket:
        prefix = get_opendata_prefix(product_file)
        utils.upload_file_to_s3_with_publish_access_keys(product_file, args.publish_bucket, prefix)
        utils.upload_file_to_s3_with_publish_access_keys(browse_file, args.publish_bucket, prefix)
        utils.upload_file_to_s3_with_publish_access_keys(thumbnail_file, args.publish_bucket, prefix)

        publish_info_file = save_publication_info(args.publish_bucket, prefix, product_file.name)
        if args.bucket:
            upload_file_to_s3(publish_info_file, args.bucket, args.bucket_prefix)
