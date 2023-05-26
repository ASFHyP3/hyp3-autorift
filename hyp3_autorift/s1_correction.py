import argparse
import logging
from pathlib import Path

from hyp3lib.aws import upload_file_to_s3
from hyp3lib.fetch import download_file, write_credentials_to_netrc_file
from hyp3lib.get_orb import downloadSentinelOrbitFile
from hyp3lib.scene import get_download_url

from hyp3_autorift import geometry, io
from hyp3_autorift.process import DEFAULT_PARAMETER_FILE, check_earthdata_credentials, get_s1_primary_polarization
from hyp3_autorift.vend.testGeogrid_ISCE import loadParsedata, runGeogrid
log = logging.getLogger(__name__)


def generate_correction_data(scene: str, buffer: int = 0, parameter_file: str = DEFAULT_PARAMETER_FILE):
    scene_path = Path(f'{scene}.zip')
    if not scene_path.exists():
        scene_url = get_download_url(scene)
        scene_path = download_file(scene_url, chunk_size=5242880)

    orbits = Path('Orbits').resolve()
    orbits.mkdir(parents=True, exist_ok=True)
    state_vec, oribit_provider = downloadSentinelOrbitFile(scene, directory=str(orbits))
    log.info(f'Downloaded orbit file {state_vec} from {oribit_provider}')

    polarization = get_s1_primary_polarization(scene)
    lat_limits, lon_limits = geometry.bounding_box(f'{scene}.zip', polarization=polarization, orbits=orbits)

    scene_poly = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = io.find_jpl_parameter_info(scene_poly, parameter_file)

    isce_dem = geometry.prep_isce_dem(parameter_info['geogrid']['dem'], lat_limits, lon_limits)
    io.format_tops_xml(scene, scene, polarization, isce_dem, orbits)

    scene_meta = loadParsedata(str(scene_path), orbit_dir=orbits, aux_dir=orbits, buffer=buffer)
    geogrid_info = runGeogrid(scene_meta, scene_meta, epsg=parameter_info['epsg'], **parameter_info['geogrid'])

    return geogrid_info


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--username', help='NASA Earthdata Login username for fetching Sentinel-1 scenes')
    parser.add_argument('--password', help='NASA Earthdata Login password for fetching Sentinel-1 scenes')
    parser.add_argument('--bucket', help='AWS bucket to upload product files to')
    parser.add_argument('--bucket-prefix', default='', help='AWS prefix (location in bucket) to add to product files')
    parser.add_argument('--buffer', type=int, default=0, help='Number of pixels to buffer each edge of the input scene')
    parser.add_argument('--parameter-file', default=DEFAULT_PARAMETER_FILE,
                        help='Shapefile for determining the correct search parameters by geographic location. '
                             'Path to shapefile must be understood by GDAL')
    parser.add_argument('granule', help='Reference granule to process')
    args = parser.parse_args()

    username, password = check_earthdata_credentials(args.username, args.password)
    if username and password:
        write_credentials_to_netrc_file(username, password)

    _ = generate_correction_data(args.granule, buffer=args.buffer)

    if args.bucket:
        for geotiff in Path.cwd().glob('*.tif'):
            upload_file_to_s3(geotiff, args.bucket, args.bucket_prefix)
