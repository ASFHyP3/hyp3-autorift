"""A HyP3 plugin for feature tracking processing with AutoRIFT-ISCE"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version(__name__)
except PackageNotFoundError:
    print(
        f'{__name__} package is not installed!\n'
        f'Install in editable/develop mode via (from the top of this repo):\n'
        f'   python -m pip install -e .[develop]\n'
        f'Or, to just get the version number use:\n'
        f'   python setup.py --version'
    )

__all__ = [
    '__version__',
]
