# Vendored modules for the HyP3 autoRIFT plugin

This directory contains modules needed for the HyP3 autoRIFT plugin that couldn't
be easily incorporated from a package manager or installed appropriately.

## `testautoRIFT_ISCE.py`, `testautoRIFT.py`, `testGeogrid_ISCE.py`, and `testGeogridOptical.py`

These modules are required for the expected workflow provided to ASF, and are
provided in autoRIFT, but not distributed as part of the package. These modules
correspond to release [`v1.4.0`](https://github.com/nasa-jpl/autoRIFT/releases/tag/v1.4.0).
Changes, as listed in `CHANGES.diff`, were done to facilitate better packaging
and distribution of these modules, to correctly handle Sentinel-2 Level 1C
products, to prevent truncating Landsat scene names in the netCDF file names, 
and to provide better netCDF metadata including more detailed reporting of
Landsat-8 acquisition times and their respective center date.
