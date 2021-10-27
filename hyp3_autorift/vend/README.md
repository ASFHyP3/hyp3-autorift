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
Landsat-8/Sentintel-2 acquisition times and their respective center date.

**Note:** The `topsinsar_filename.py` included here is not used, but retained for reference.
We've replaced it  with `hyp3_autorift.io.get_topsinsar_config`. 

## Additional Patches

1. The changes listed in `DATE_DT.diff` were applied to report the
   `img_pair_info.date_dt` attribute in the netCDF product as fractional days, instead
   of rounding down to the nearest whole day. These changes should be included in the
   next autoRIFT release.
2. The changes listed in `REF_VEL.diff` were applied to update the reference velocity
   fields for projected velocity. These changes are expected to be a temporary measure
   until better estimates of the velocity fields are generated. 
3. The changes listed in `S2_FILENAMES.diff` were applied to use the full Sentinel-2 COG
   id in the output netCDF product filename to ensure unique names.  
