"""
AutoRIFT processing for HyP3
"""
import os
import shutil
from datetime import datetime

import hyp3proclib
from hyp3proclib.db import get_db_connection
from hyp3proclib.logger import log
from hyp3proclib.proc_base import Processor

import hyp3_autorift
from hyp3_autorift.process import process as autorift_process


def hyp3_process(cfg, n):
    try:
        g1, g2 = hyp3proclib.earlier_granule_first(cfg['granule'], cfg['other_granules'][0])

        d1 = datetime.strptime(g1[17:25], '%Y%m%d')
        d2 = datetime.strptime(g2[17:25], '%Y%m%d')

        cfg['email_text'] = f'This is a {(d2-d1).days}-day feature tracking pair ' \
                            f'from {d1.strftime("%Y-%m-%d")} to {d2.strftime("%Y-%m-%d")}.'

        cfg['ftd'] = '_'.join([g1[17:17+15], g2[17:17+15]])

        if not cfg['skip_processing']:
            log.info(f'Process starting at {datetime.now()}')
            launch_dir = os.getcwd()
            os.chdir(cfg['workdir'])

            autorift_process(g1, g2, download=True, process_dir=cfg['ftd'], product=True)

            os.chdir(launch_dir)
        else:
            log.info('Processing skipped!')
            log.info(f'Command would be: autorift_proc_pair {g1} {g2} --process-dir {cfg["ftd"]} --download '
                     f'--product-dir')
            cfg['log'] += "(debug mode)"

        cfg['success'] = True
        hyp3proclib.update_completed_time(cfg)

        # FIXME: But, why?
        cfg["granule_name"] = cfg["granule"]
        cfg["processes"] = [cfg["proc_id"], ]
        cfg["subscriptions"] = [cfg["sub_id"], ]

        tmp_product_dir = os.path.join(cfg['workdir'], 'PRODUCT')
        if not os.path.isdir(tmp_product_dir):
            log.info(f'PRODUCT directory not found: {tmp_product_dir}')
            log.error('Processing failed')
            raise Exception('Processing failed: PRODUCT directory not found')
        else:
            out_name = hyp3proclib.build_output_name_pair(g1, g2, cfg['workdir'], cfg['suffix'])
            log.info(f'Output name: {out_name}')

            product_dir = os.path.join(cfg['workdir'], out_name)
            zip_file = f'{product_dir}.zip'
            if os.path.isdir(product_dir):
                shutil.rmtree(product_dir)
            if os.path.isfile(zip_file):
                os.unlink(zip_file)
            cfg['out_path'] = product_dir

            log.debug('Renaming ' + tmp_product_dir + ' to ' + product_dir)
            os.rename(tmp_product_dir, product_dir)

            # TODO:
            #  * browse images
            #  * citation
            #  * phase_png (?)

            hyp3proclib.zip_dir(product_dir, zip_file)

            cfg['final_product_size'] = [os.stat(zip_file).st_size, ]
            cfg['original_product_size'] = 0

            with get_db_connection('hyp3-db') as conn:
                hyp3proclib.record_metrics(cfg, conn)
                hyp3proclib.upload_product(zip_file, cfg, conn)
                hyp3proclib.success(conn, cfg)

    except Exception as e:
        log.exception('autoRIFT processing failed!')
        log.exception('Notifying user')
        hyp3proclib.failure(cfg, str(e))

    hyp3proclib.file_system.cleanup_workdir(cfg)

    log.info('autoRIFT done')


def main():
    """
    Main entrypoint for hyp3_autorift
    """
    processor = Processor(
        'autorift', hyp3_process, sci_version=hyp3_autorift.__version__
    )
    processor.run()


if __name__ == '__main__':
    main()
