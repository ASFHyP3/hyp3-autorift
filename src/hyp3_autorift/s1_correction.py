import argparse
import logging
from pathlib import Path

from hyp3lib.aws import upload_file_to_s3

from hyp3_autorift.process import DEFAULT_PARAMETER_FILE
from hyp3_autorift.s1_isce2 import generate_correction_data

log = logging.getLogger(__name__)


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
    parser.add_argument('granule', help='Reference granule to process')
    args = parser.parse_args()

    _, conversion_nc = generate_correction_data(args.granule, buffer=args.buffer)

    if args.bucket:
        upload_file_to_s3(conversion_nc, args.bucket, args.bucket_prefix)
        for geotiff in Path.cwd().glob('*.tif'):
            upload_file_to_s3(geotiff, args.bucket, args.bucket_prefix)
