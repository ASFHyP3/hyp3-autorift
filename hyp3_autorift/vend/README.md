# Vendored modules for the HyP3 autoRIFT plugin

This directory contains modules needed for the HyP3 autoRIFT plugin that couldn't
be easily incorporated from a package manager or installed appropriately.

## `testautoRIFT_ISCE.py` and `testautoRIFT.py`

These modules are required for the expected workflow provided to ASF, and are
provided in autoRIFT, but not distributed as part of the package. These modules
correspond to commit 
[`b973c1b`](https://github.com/leiyangleon/autoRIFT/commit/b973c1b48b82f3398ece3c34a7cbfca71c4e07cb), 
which is a [minor patch](https://github.com/leiyangleon/autoRIFT/pull/28)
to [`v1.2.0`](https://github.com/leiyangleon/autoRIFT/releases/tag/v1.2.0).
Changes, as listed in `CHANGES.diff`, were done to facilitate better packaging 
and distribution of these modules, to correctly handle Sentinel-2 Level 1C
products, and to provide better netCDF metadata. Additionally, `NC-PATCH.diff`
was applied to fix the grid resolution specifier in the netCDF file names and to
not truncate Landsat scene names in the netCDF file names.

## `testGeogrid_ISCE.py` and `testGeogridOptical.py`

These modules are required for the expected workflow provided to ASF, and are
provided in autoRIFT, but not distributed as part of the package. These modules
correspond to release [`v1.2.0`](https://github.com/leiyangleon/autoRIFT/releases/tag/v1.2.0).
Changes, as listed in `CHANGES.diff`, were done to facilitate better packaging 
and distribution of these modules, to correctly handle Sentinel-2 Level 1C
products, and to provide better netCDF metadata. 
