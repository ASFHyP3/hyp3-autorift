"""
AutoRIFT processing for HyP3
"""
import os
import shutil
import sys
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from datetime import datetime

from hyp3lib.aws import upload_file_to_s3
from hyp3lib.fetch import write_credentials_to_netrc_file
from hyp3lib.image import create_thumbnail
from hyp3proclib import (
    earlier_granule_first,
    extra_arg_is,
    failure,
    success,
    upload_product,
    zip_dir,
)
from hyp3proclib.db import get_db_connection
from hyp3proclib.file_system import cleanup_workdir
from hyp3proclib.logger import log
from hyp3proclib.proc_base import Processor
from pkg_resources import load_entry_point

import hyp3_autorift


def entry():
    parser = ArgumentParser(prefix_chars='+', formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '++entrypoint', choices=['hyp3_autorift', 'hyp3_autorift_v2'], default='hyp3_autorift',
        help='Select the HyP3 entrypoint version to use'
    )
    args, unknowns = parser.parse_known_args()

    sys.argv = [args.entrypoint, *unknowns]
    sys.exit(
        load_entry_point('hyp3_autorift', 'console_scripts', args.entrypoint)()
    )


def earlier_granule_first(g1, g2):
    if g1.startswith('S1'):
        date_slice = slice(17,32)
    elif g1.startswith('S2'):
        date_slice = slice(11, 26)
    elif g1.startswith('L'):
        date_slice = slice(17, 25)
    else:
        raise ValueError(f'Unsupported scene format: {g1}')

    if g1[date_slice] <= g2[date_slice]:
        return g1, g2
    return g2, g1


def main_v2():
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

    g1, g2 = earlier_granule_first(args.granules[0], args.granules[1])

    product_file = hyp3_autorift.process(g1, g2)

    browse_file = product_file.with_suffix('.png')

    if args.bucket:
        upload_file_to_s3(product_file, args.bucket, args.bucket_prefix)
        upload_file_to_s3(browse_file, args.bucket, args.bucket_prefix)
        thumbnail_file = create_thumbnail(browse_file)
        upload_file_to_s3(thumbnail_file, args.bucket, args.bucket_prefix)


def hyp3_process(cfg, n):
    try:
        log.info(f'Processing autoRIFT-ISCE pair "{cfg["sub_name"]}" for "{cfg["username"]}"')

        g1, g2 = earlier_granule_first(cfg['granule'], cfg['other_granules'][0])

        d1 = datetime.strptime(g1[17:25], '%Y%m%d')
        d2 = datetime.strptime(g2[17:25], '%Y%m%d')

        cfg['email_text'] = f'This is a {(d2-d1).days}-day feature tracking pair ' \
                            f'from {d1.strftime("%Y-%m-%d")} to {d2.strftime("%Y-%m-%d")}.'

        cfg['ftd'] = '_'.join([g1[17:17+15], g2[17:17+15]])
        log.debug(f'FTD dir is: {cfg["ftd"]}')

        autorift_args = [f'{g1}.zip', f'{g2}.zip', '--process-dir', f'{cfg["ftd"]}', '--download']
        if not extra_arg_is(cfg, 'intermediate_files', 'no'):  # handle processes b4 option added
            autorift_args.append('--product')

        product_file = hyp3_autorift.process(
            reference=f'{g1}.zip',
            secondary=f'{g2}.zip',
            download=True,
            process_dir=cfg["ftd"],
            product=extra_arg_is(cfg, 'intermediate_files', 'yes')
        )
        cfg['attachment'] = str(product_file.with_suffix('.png'))
        cfg['email_text'] = ' '  # fix line break in email

        if extra_arg_is(cfg, 'intermediate_files', 'yes'):
            tmp_product_dir = os.path.join(cfg['workdir'], 'PRODUCT')
            if not os.path.isdir(tmp_product_dir):
                log.info(f'PRODUCT directory not found: {tmp_product_dir}')
                log.error('Processing failed')
                raise Exception('Processing failed: PRODUCT directory not found')

            product_dir = os.path.join(cfg['workdir'], product_file.stem)
            product_file = f'{product_dir}.zip'
            if os.path.isdir(product_dir):
                shutil.rmtree(product_dir)
            if os.path.isfile(product_file):
                os.unlink(product_file)

            log.debug('Renaming ' + tmp_product_dir + ' to ' + product_dir)
            os.rename(tmp_product_dir, product_dir)

            zip_dir(product_dir, product_file)

        cfg['final_product_size'] = [os.stat(product_file).st_size, ]

        with get_db_connection('hyp3-db') as conn:
            upload_product(str(product_file), cfg, conn)
            success(conn, cfg)

    except Exception as e:
        log.exception('autoRIFT processing failed!')
        log.exception('Notifying user')
        failure(cfg, str(e))

    cleanup_workdir(cfg)

    log.info('autoRIFT done')


def main():
    """
    Main entrypoint for hyp3_autorift
    """
    processor = Processor(
        'autorift_isce', hyp3_process, sci_version=hyp3_autorift.__version__
    )
    processor.run()


if __name__ == '__main__':
    main()
