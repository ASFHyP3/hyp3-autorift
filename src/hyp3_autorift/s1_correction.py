import argparse
import copy
import logging
from datetime import timedelta
from pathlib import Path
from typing import Optional

from hyp3lib.aws import upload_file_to_s3
from hyp3lib.fetch import download_file
from hyp3lib.get_orb import downloadSentinelOrbitFile
from hyp3lib.scene import get_download_url

from hyp3_autorift import geometry, utils
from hyp3_autorift.process import DEFAULT_PARAMETER_FILE, get_s1_primary_polarization
from hyp3_autorift.utils import get_esa_credentials
from hyp3_autorift.vend.testGeogrid_ISCE import loadParsedata, runGeogrid
log = logging.getLogger(__name__)


def generate_correction_data(
    scene: str,
    buffer: int = 0,
    parameter_file: str = DEFAULT_PARAMETER_FILE,
    esa_username: Optional[str] = None,
    esa_password: Optional[str] = None,
):
    scene_path = Path(f'{scene}.zip')
    if not scene_path.exists():
        scene_url = get_download_url(scene)
        scene_path = download_file(scene_url, chunk_size=5242880)

    orbits = Path('Orbits').resolve()
    orbits.mkdir(parents=True, exist_ok=True)

    if (esa_username is None) or (esa_password is None):
        esa_username, esa_password = get_esa_credentials()

    state_vec, oribit_provider = downloadSentinelOrbitFile(
        scene, directory=str(orbits), esa_credentials=(esa_username, esa_password)
    )
    log.info(f'Downloaded orbit file {state_vec} from {oribit_provider}')

    polarization = get_s1_primary_polarization(scene)
    lat_limits, lon_limits = geometry.bounding_box(f'{scene}.zip', polarization=polarization, orbits=orbits)

    scene_poly = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = utils.find_jpl_parameter_info(scene_poly, parameter_file)

    isce_dem = geometry.prep_isce_dem(parameter_info['geogrid']['dem'], lat_limits, lon_limits)
    utils.format_tops_xml(scene, scene, polarization, isce_dem, orbits)

    reference_meta = loadParsedata(str(scene_path), orbit_dir=orbits, aux_dir=orbits, buffer=buffer)

    secondary_meta = copy.deepcopy(reference_meta)
    spoof_dt = timedelta(days=1)
    secondary_meta.sensingStart += spoof_dt
    secondary_meta.sensingStop += spoof_dt

    geogrid_info = runGeogrid(reference_meta, secondary_meta, epsg=parameter_info['epsg'], **parameter_info['geogrid'])

    return geogrid_info


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--bucket', help='AWS bucket to upload product files to')
    parser.add_argument('--bucket-prefix', default='', help='AWS prefix (location in bucket) to add to product files')
    parser.add_argument('--esa-username', default=None, help="Username for ESA's Copernicus Data Space Ecosystem")
    parser.add_argument('--esa-password', default=None, help="Password for ESA's Copernicus Data Space Ecosystem")
    parser.add_argument('--buffer', type=int, default=0, help='Number of pixels to buffer each edge of the input scene')
    parser.add_argument('--parameter-file', default=DEFAULT_PARAMETER_FILE,
                        help='Shapefile for determining the correct search parameters by geographic location. '
                             'Path to shapefile must be understood by GDAL')
    parser.add_argument('granule', help='Reference granule to process')
    args = parser.parse_args()

    _ = generate_correction_data(args.granule, buffer=args.buffer)

    if args.bucket:
        for geotiff in Path.cwd().glob('*.tif'):
            upload_file_to_s3(geotiff, args.bucket, args.bucket_prefix)
