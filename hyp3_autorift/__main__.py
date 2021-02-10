"""
AutoRIFT processing for HyP3
"""
from argparse import ArgumentParser

from hyp3lib.aws import upload_file_to_s3
from hyp3lib.fetch import write_credentials_to_netrc_file
from hyp3lib.image import create_thumbnail

from hyp3_autorift.process import DEFAULT_PARAMETER_FILE, get_datetime, process


def main():
    parser = ArgumentParser()
    parser.add_argument('--username', help='NASA Earthdata Login username for fetching Sentinel-1 scenes')
    parser.add_argument('--password', help='NASA Earthdata Login password for fetching Sentinel-1 scenes')
    parser.add_argument('--bucket', help='AWS bucket to upload product files to')
    parser.add_argument('--bucket-prefix', default='', help='AWS prefix (location in bucket) to add to product files')
    parser.add_argument('--parameter-file', default=DEFAULT_PARAMETER_FILE,
                        help='Shapefile for determining the correct search parameters by geographic location.'
                             'Path to shapefile must be understood by GDAL')
    parser.add_argument('--naming-scheme', default='ITS_LIVE_OD', choices=['ITS_LIVE_OD', 'ITS_LIVE_PROD', 'ASF'],
                        help='Naming scheme to use for product files')
    parser.add_argument('granules', type=str.split, nargs='+',
                        help='Granule pair to process')
    args = parser.parse_args()

    args.granules = [item for sublist in args.granules for item in sublist]
    if len(args.granules) != 2:
        parser.error('Must provide exactly two granules')

    if args.username and args.password:
        write_credentials_to_netrc_file(args.username, args.password)

    g1, g2 = sorted(args.granules, key=get_datetime)

    product_file = process(g1, g2, parameter_file=args.parameter_file, naming_scheme=args.naming_scheme)

    browse_file = product_file.with_suffix('.png')

    if args.bucket:
        upload_file_to_s3(product_file, args.bucket, args.bucket_prefix)
        upload_file_to_s3(browse_file, args.bucket, args.bucket_prefix)
        thumbnail_file = create_thumbnail(browse_file)
        upload_file_to_s3(thumbnail_file, args.bucket, args.bucket_prefix)


if __name__ == '__main__':
    main()
