import argparse
import logging
from pathlib import Path

from hyp3lib.aws import upload_file_to_s3
from hyp3lib.fetch import download_file
from hyp3lib.get_orb import downloadSentinelOrbitFile
from hyp3lib.scene import get_download_url

from hyp3_autorift import geometry, io
from hyp3_autorift.process import DEFAULT_PARAMETER_FILE, get_datetime, get_s1_primary_polarization
from hyp3_autorift.vend.testGeogrid_ISCE import loadParsedata, runGeogrid
log = logging.getLogger(__name__)


def generate_correction_data(reference: str, secondary: str, buffer: int = 0,
                             parameter_file: str = DEFAULT_PARAMETER_FILE):
    reference_path = Path(f'{reference}.zip')
    secondary_path = Path(f'{secondary}.zip')
    orbits = Path('Orbits').resolve()
    orbits.mkdir(parents=True, exist_ok=True)

    for scene_path in [reference_path, secondary_path]:
        if not scene_path.exists():
            scene_url = get_download_url(scene_path.stem)
            _ = download_file(scene_url, chunk_size=5242880)

        state_vec, oribit_provider = downloadSentinelOrbitFile(scene_path.stem, directory=str(orbits))
        log.info(f'Downloaded orbit file {state_vec} from {oribit_provider}')

    polarization = get_s1_primary_polarization(reference)
    lat_limits, lon_limits = geometry.bounding_box(f'{reference}.zip', polarization=polarization, orbits=orbits)

    scene_poly = geometry.polygon_from_bbox(x_limits=lat_limits, y_limits=lon_limits)
    parameter_info = io.find_jpl_parameter_info(scene_poly, parameter_file)

    isce_dem = geometry.prep_isce_dem(parameter_info['geogrid']['dem'], lat_limits, lon_limits)
    io.format_tops_xml(reference, secondary, polarization, isce_dem, orbits)

    reference_meta = loadParsedata(str(reference_path), orbit_dir=orbits, aux_dir=orbits, buffer=buffer)
    secondary_meta = loadParsedata(str(secondary_path), orbit_dir=orbits, aux_dir=orbits, buffer=buffer)
    geogrid_info = runGeogrid(reference_meta, secondary_meta, epsg=parameter_info['epsg'], **parameter_info['geogrid'])

    return geogrid_info


def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument('--bucket', help='AWS bucket to upload product files to')
    parser.add_argument('--bucket-prefix', default='', help='AWS prefix (location in bucket) to add to product files')
    parser.add_argument('--buffer', type=int, default=0, help='Number of pixels to buffer each edge of the input scene')
    parser.add_argument('--parameter-file', default=DEFAULT_PARAMETER_FILE,
                        help='Shapefile for determining the correct search parameters by geographic location. '
                             'Path to shapefile must be understood by GDAL')
    parser.add_argument('granules', type=str.split, nargs='+', help='Granules to process')
    args = parser.parse_args()

    args.granules = [item for sublist in args.granules for item in sublist]
    if len(args.granules) != 2:
        parser.error('Must provide exactly two granules')

    reference, secondary = sorted(args.granules, key=get_datetime)

    _ = generate_correction_data(reference=reference, secondary=secondary, buffer=args.buffer)

    if args.bucket:
        for geotiff in Path.cwd().glob('*.tif'):
            upload_file_to_s3(geotiff, args.bucket, args.bucket_prefix)
