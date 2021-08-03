# Vendored modules for the HyP3 autoRIFT plugin

This directory contains modules needed for the HyP3 autoRIFT plugin that couldn't
be easily incorporated from a package manager or installed appropriately.

## `testautoRIFT_ISCE.py`, `testautoRIFT.py`, `testGeogrid_ISCE.py`, and `testGeogridOptical.py`

These modules are required for the expected workflow provided to ASF, and are
provided in autoRIFT, but not distributed as part of the package. These modules
correspond to release [`v1.3.1`](https://github.com/leiyangleon/autoRIFT/releases/tag/v1.3.1)
with the unreleased [minor error estimate edits](https://github.com/leiyangleon/autoRIFT/commit/f11d5eee9b12fb7acb4aa5ce96fe6d69e1548195)
included. Changes, as listed in `CHANGES.diff`, were done to facilitate better packaging 
and distribution of these modules, to correctly handle Sentinel-2 Level 1C
products, to prevent truncating Landsat scene names in the netCDF file names, 
and to provide better netCDF metadata. Furthermore, a patch, as listed in `L8-PATCH.diff`, was applied to
`testautoRIFT_ISCE.py` and `testautoRIFT.py` to provide more detailed acquisition times
for Landsat-8 pairs.
