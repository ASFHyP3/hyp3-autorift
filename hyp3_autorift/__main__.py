"""
AutoRIFT processing for HyP3
"""


import sys
import argparse

from hyp3_autorift import process


def parse_args(args=None):
    """
    Parse the CLI arguments with argparse
    """
    parser = argparse.ArgumentParser(
        prog='hyp3_autorift', description=__doc__,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        '-v',  '--verbose', action='store_true',
        help='Print detailed information to stdout'
    )

    return parser.parse_args(args)


def main():
    """
    Main entrypoint for hyp3_autorift
    """
    cli_args = sys.argv[1:] if len(sys.argv) > 1 else None
    args = parse_args(cli_args)
    process(**vars(args))


if __name__ == '__main__':
    main()
