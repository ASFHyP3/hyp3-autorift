"""
Process with autoRIFT ICSE
"""

import os


def process(verbose=False):
    """Process the requested granules with autoRIFT + ISCE
    :param verbose:
    :return:
    """
    try:
        conda_env = os.environ['CONDA_PREFIX']
        if verbose:
            print(f'You are running hyp3_autorift in the {conda_env} conda environment.')
    except KeyError:
        if verbose:
            print('FAILURE: You are not running in an active conda environment!')
        raise
