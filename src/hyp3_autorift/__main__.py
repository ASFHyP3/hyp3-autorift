"""
AutoRIFT processing for HyP3
"""

import argparse
import os
import sys
import warnings
from importlib.metadata import entry_points
from pathlib import Path

from hyp3lib.fetch import write_credentials_to_netrc_file


def main():
    parser = argparse.ArgumentParser(prefix_chars='+', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '++process',
        choices=['hyp3_autorift'],
        default='hyp3_autorift',
        help='Select the console_script entrypoint to use',  # console_script entrypoints are specified in `setup.py`
    )
    parser.add_argument('++omp-num-threads', type=int, help='The number of OpenMP threads to use for parallel regions')

    args, unknowns = parser.parse_known_args()

    if args.omp_num_threads:
        os.environ['OMP_NUM_THREADS'] = str(args.omp_num_threads)

    username = os.getenv('EARTHDATA_USERNAME')
    password = os.getenv('EARTHDATA_PASSWORD')
    if username and password:
        write_credentials_to_netrc_file(username, password, append=False)

    if not (Path.home() / '.netrc').exists():
        warnings.warn('Earthdata credentials must be present as environment variables, or in your netrc.', UserWarning)

    eps = entry_points(group='console_scripts')
    (process_entry_point,) = {process for process in eps if process.name == args.process}

    sys.argv = [args.process, *unknowns]
    sys.exit(process_entry_point.load()())


if __name__ == '__main__':
    main()
