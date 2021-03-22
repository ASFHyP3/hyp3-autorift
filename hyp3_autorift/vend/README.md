# Vendored modules for the HyP3 autoRIFT plugin

This directory contains modules needed for the HyP3 autoRIFT plugin that couldn't
be easily incorporated from a package manager or installed appropriately.

## `testautoRIFT_ISCE.py` and `testautoRIFT.py`

These modules are required for the expected workflow provided to ASF, and are
provided in autoRIFT, but not distributed as part of the package. These modules
correspnd to commit [`b944d97`](https://github.com/leiyangleon/autoRIFT/commit/b944d97611389a4e5d0b8c89aca1d244689fa34d).
Changes, as listed in `CHANGES.diff`, were done to facilitate better packaging 
and distribution of these modules and to correctly handle Sentinel-2 Level 1C
products. 

## `testGeogrid_ISCE.py` and `testGeogridOptical.py`

These modules are required for the expected workflow provided to ASF, but are
not provided in the autoRIFT as described above.
Instead, they reside in the "sister" 
[Geogrid package](https://github.com/leiyangleon/Geogrid), 
which has no tagged or released versions. These modules correspond to
commit [`eb05203`](https://github.com/leiyangleon/Geogrid/commit/eb0520336aa48e27ec1be5731953c8f390bdd993).
Changes, as listed in `CHANGES.diff`, were done to correctly handle Sentinel-2
Level 1C products. 
