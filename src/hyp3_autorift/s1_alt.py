import argparse
import logging
import shutil
from pathlib import Path

import numpy as np
from hyp3lib.aws import upload_file_to_s3
from hyp3lib.fetch import download_file
from hyp3lib.image import create_thumbnail
from hyp3lib.scene import get_download_url
from netCDF4 import Dataset
from osgeo import gdal
from s1_orbits import fetch_for_scene


from hyp3_autorift import geometry, image, utils
from hyp3_autorift.crop import crop_netcdf_product
from hyp3_autorift.process import DEFAULT_PARAMETER_FILE, get_datetime, get_opendata_prefix
from hyp3_autorift.s1 import get_s1_primary_polarization
from hyp3_autorift.s1_isce2 import bounding_box, format_tops_xml, prep_isce_dem

log = logging.getLogger(__name__)


def process_sentinel1_without_isce2(reference: str, secondary: str, parameter_file: str, buffer: int) -> Path:
    from hyp3_autorift.vend.testGeogrid_ISCE import loadParsedata, runGeogrid
    from hyp3_autorift.vend.testautoRIFT_ISCE import generateAutoriftProduct

    reference_path = f'{reference}.zip'
    secondary_path = f'{secondary}.zip'

    for scene, scene_path in zip([reference, secondary], [reference_path, secondary_path]):
        if not Path(scene_path).exists():
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
    format_tops_xml(scene, scene, polarization, isce_dem, orbits)

    reference_meta = loadParsedata(reference_path, orbit_dir=orbits, aux_dir=orbits, buffer=buffer)
    secondary_meta = loadParsedata(secondary_path, orbit_dir=orbits, aux_dir=orbits, buffer=buffer)

    geogrid_info = runGeogrid(reference_meta, secondary_meta, epsg=parameter_info['epsg'], **parameter_info['geogrid'])

    # NOTE: After Geogrid is run, all drivers are no longer registered.
    #       I've got no idea why, or if there are other effects...
    gdal.AllRegister()

    netcdf_file = generateAutoriftProduct(
        reference_path, secondary_path, nc_sensor='S1', optical_flag=False, ncname=None,
        geogrid_run_info=geogrid_info, **parameter_info['autorift'],
        parameter_file=parameter_file.replace('/vsicurl/', ''),
    )

    if netcdf_file is None:
        raise Exception('Processing failed! Output netCDF file not found')

    return netcdf_file

def finalize_product_package(netcdf_file: Path, naming_scheme: str) -> tuple[Path, Path, Path]:
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
        data = np.ma.masked_values(velocity, -32767.).filled(0)

    browse_file = product_file.with_suffix('.png')
    image.make_browse(browse_file, data)

    thumbnail_file = create_thumbnail(browse_file)

    return product_file, browse_file, thumbnail_file


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--bucket', help='AWS bucket to upload product files to')
    parser.add_argument('--bucket-prefix', default='', help='AWS prefix (location in bucket) to add to product files')
    parser.add_argument('--publish-bucket', default='',
                        help='Additionally, publish products to this bucket. Necessary credentials must be provided '
                             'via the `PUBLISH_ACCESS_KEY_ID` and `PUBLISH_SECRET_ACCESS_KEY` environment variables.')
    parser.add_argument('--parameter-file', default=DEFAULT_PARAMETER_FILE,
                        help='Shapefile for determining the correct search parameters by geographic location. '
                             'Path to shapefile must be understood by GDAL')
    parser.add_argument('--naming-scheme', default='ITS_LIVE_OD', choices=['ITS_LIVE_OD', 'ITS_LIVE_PROD'],
                        help='Naming scheme to use for product files')
    parser.add_argument('--buffer', type=int, default=0, help='Number of pixels to buffer each edge of the input scene')

    parser.add_argument('reference', help='Reference granule to process')
    parser.add_argument('secondary', help='Secondary granule to process')

    args = parser.parse_args()

    logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s',
                        datefmt='%m/%d/%Y %I:%M:%S %p', level=logging.INFO)


    reference, secondary = sorted((args.reference, args.secondary), key=get_datetime)

    product_file = process_sentinel1_without_isce2(reference=reference, secondary=secondary, parameter_file=args.parameter_file, buffer=args.buffer)

    product_file, browse_file, thumbnail_file = finalize_product_package(product_file, naming_scheme=args.naming_scheme)

    if args.bucket:
        upload_file_to_s3(product_file, args.bucket, args.bucket_prefix)
        upload_file_to_s3(browse_file, args.bucket, args.bucket_prefix)
        upload_file_to_s3(thumbnail_file, args.bucket, args.bucket_prefix)

    # FIXME: HyP3 is passing the default value for this argument as '""' not "", so we're not getting an empty string
    if args.publish_bucket == '""':
        args.publish_bucket = ''

    if args.publish_bucket:
        prefix = get_opendata_prefix(product_file)
        utils.upload_file_to_s3_with_publish_access_keys(product_file, args.publish_bucket, prefix)
        utils.upload_file_to_s3_with_publish_access_keys(browse_file, args.publish_bucket, prefix)
        utils.upload_file_to_s3_with_publish_access_keys(thumbnail_file, args.publish_bucket, prefix)
