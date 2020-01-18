"""
AutoRIFT processing for HyP3
"""

# FIXME: Python 3.8+ this should be `from importlib.metadata...`
from importlib_metadata import version, PackageNotFoundError
from .process import process


try:
    __version__ = version(__name__)
except PackageNotFoundError:
    # package is not installed!
    # Install in editable/develop mode via (from the top of this repo):
    #    pip install --user .
    # Or, to just get the version number use:
    #    python setup.py --version
    pass

