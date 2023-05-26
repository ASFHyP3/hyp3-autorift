"""
AutoRIFT processing for HyP3
"""


import argparse
import os
import sys
from importlib.metadata import entry_points


def main():
    parser = argparse.ArgumentParser(prefix_chars='+', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '++process', choices=['hyp3_autorift', 's1_correction'], default='hyp3_autorift',
        help='Select the console_script entrypoint to use'  # console_script entrypoints are specified in `setup.py`
    )
    parser.add_argument('++omp-num-threads', type=int, help='The number of OpenMP threads to use for parallel regions')

    args, unknowns = parser.parse_known_args()

    if args.omp_num_threads:
        os.environ['OMP_NUM_THREADS'] = str(args.omp_num_threads)

    eps = entry_points()['console_scripts']
    (process_entry_point,) = {process for process in eps if process.name == args.process}

    sys.argv = [args.process, *unknowns]
    sys.exit(
        process_entry_point.load()()
    )


if __name__ == '__main__':
    main()
