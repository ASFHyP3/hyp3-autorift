# Vendored modules for the HyP3 autoRIFT plugin

This directory contains modules needed for the HyP3 autoRIFT plugin that couldn't
be easily incorporated from a package manager or installed appropriately.

## `testautoRIFT_ISCE.py` and `testautoRIFT.py`

These modules were provided in autoRIFT 
[FIXME](https://github.com/leiyangleon/autoRIFT/releases/tag/FIXME),
and are required for the expected workflow provided to ASF.

## `testGeogrid_ISCE.py` and `testGeogridOptical.py`

These modules are required for the expected workflow provided to ASF, but are
not provided in autoRIFT 
[FIXME](https://github.com/leiyangleon/autoRIFT/releases/tag/FIXME) 
and instead resides in the "sister" 
[Geogrid package](https://github.com/leiyangleon/Geogrid), 
which no longer has any tagged or released versions. These modules correspond to
the phantom Geogrid FIXME release, which is commit [`FIXME`](). 
