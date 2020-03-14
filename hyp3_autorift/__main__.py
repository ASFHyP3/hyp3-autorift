"""
AutoRIFT processing for HyP3
"""
import os
from datetime import datetime

import hyp3proclib
from hyp3proclib.logger import log
from hyp3proclib.proc_base import Processor

import hyp3_autorift


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

            # TODO: Process

            os.chdir(launch_dir)
        else:
            log.info('Processing skipped!')
            # TODO: Log call 'command was'
            cfg['log'] += "(debug mode)"

        cfg['success'] = True
        hyp3proclib.update_completed_time(cfg)

        cfg["granule_name"] = cfg["granule"]
        cfg["processes"] = [cfg["proc_id"], ]
        cfg["subscriptions"] = [cfg["sub_id"], ]

        product_dir = os.path.join(cfg['workdir'], 'PRODUCT')
        if not os.path.isdir(product_dir):
            log.info(f'PRODUCT directory not found: {product_dir}')
            log.error('Processing failed')
            raise Exception('Processing failed: PRODUCT directory not found')
        else:
            # TODO: This.
            pass

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
