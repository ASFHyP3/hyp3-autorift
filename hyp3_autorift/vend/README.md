# Vendored modules for the HyP3 autoRIFT plugin

This directory contains modules needed for the HyP3 autoRIFT plugin that couldn't
be easily incorporated from a package manager or installed appropriately.

## autoRIFT workflow scripts

These modules are required for the expected autoRIFT workflow:
* `testautoRIFT_ISCE.py`
* `testautoRIFT.py`
* `testGeogrid_ISCE.py` 
* `testGeogridOptical.py`
* `netcdf_output.py`
* `topsinsar_filename.py`

and are included in the [autoRIFT source code](https://github.com/nasa-jpl/autoRIFT),
but not distributed as part of the package. 

The version located in this directory correspond to release [`v1.4.0`](https://github.com/nasa-jpl/autoRIFT/releases/tag/v1.4.0),
with the unreleased [packaging updates](https://github.com/leiyangleon/autoRIFT/commit/8e84619962cc0d5b9876240deb6696de71dee357)
included. Changes, as listed in `CHANGES.diff`, were done to facilitate better packaging
and distribution of these modules, to correctly handle Sentinel-2 Level 1C
products, to prevent truncating Landsat scene names in the netCDF file names, 
and to provide better netCDF metadata including more detailed reporting of
Landsat-8 acquisition times and their respective center date.

**Note:** The `topsinsar_filename.py` included here is not used, but retained for reference.
We've replaced it  with `hyp3_autorift.io.get_topsinsar_config`. 
