"""
AutoRIFT processing for HyP3
"""
import sys
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser

from hyp3lib.aws import upload_file_to_s3
from hyp3lib.fetch import write_credentials_to_netrc_file
from hyp3lib.image import create_thumbnail
from pkg_resources import load_entry_point

from hyp3_autorift.process import get_datetime, process


def entry():
    parser = ArgumentParser(prefix_chars='+', formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '++entrypoint', choices=['hyp3_autorift'], default='hyp3_autorift',
        help='Select the HyP3 entrypoint version to use'
    )
    args, unknowns = parser.parse_known_args()

    sys.argv = [args.entrypoint, *unknowns]
    sys.exit(
        load_entry_point('hyp3_autorift', 'console_scripts', args.entrypoint)()
    )


def main():
    parser = ArgumentParser()
    parser.add_argument('--username')
    parser.add_argument('--password')
    parser.add_argument('--bucket')
    parser.add_argument('--bucket-prefix', default='')
    parser.add_argument('granules', type=str.split, nargs='+')
    args = parser.parse_args()

    args.granules = [item for sublist in args.granules for item in sublist]
    if len(args.granules) != 2:
        parser.error('Must provide exactly two granules')

    if args.username and args.password:
        write_credentials_to_netrc_file(args.username, args.password)

    g1, g2 = sorted(args.granules, key=get_datetime)

    product_file = process(g1, g2)

    browse_file = product_file.with_suffix('.png')

    if args.bucket:
        upload_file_to_s3(product_file, args.bucket, args.bucket_prefix)
        upload_file_to_s3(browse_file, args.bucket, args.bucket_prefix)
        thumbnail_file = create_thumbnail(browse_file)
        upload_file_to_s3(thumbnail_file, args.bucket, args.bucket_prefix)


if __name__ == '__main__':
    main()
