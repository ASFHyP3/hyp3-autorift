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

The version located in this directory corresponds to release [`v1.5.0`](https://github.com/nasa-jpl/autoRIFT/releases/tag/v1.5.0).
Changes, as listed in `CHANGES.diff`, were done to: 
* facilitate better packaging and distribution of these modules
* correctly handle Sentinel-2 Level 1C products, including:
  * process Sentinel-2 scenes in the `s3://s2-l1c-us-west-2` mirror bucket preferentially (cost savings)
  * use the full Sentinel-2 COG id in the output netCDF product filename to ensure unique names

**Note:** The `topsinsar_filename.py` included here is not used, but retained for reference.
We've replaced it  with `hyp3_autorift.io.get_topsinsar_config`. 
