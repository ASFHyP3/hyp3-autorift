# Vendored modules for the HyP3 autoRIFT plugin

This directory contains modules needed for the HyP3 autoRIFT plugin that couldn't
be easily incorporated from a package manager or installed appropriately.

## `testautoRIFT_ISCE.py`, `testautoRIFT.py`, `testGeogrid_ISCE.py`, and `testGeogridOptical.py`

These modules are required for the expected workflow provided to ASF, and are
provided in autoRIFT, but not distributed as part of the package. These modules
correspond to commit [`67570d9`](https://github.com/leiyangleon/autoRIFT/commit/67570d9d69f459afc3407e7cec9fb88edb508359).
Changes, as listed in `CHANGES.diff`, were done to facilitate better packaging 
and distribution of these modules and to correctly handle Sentinel-2 Level 1C
products. 
