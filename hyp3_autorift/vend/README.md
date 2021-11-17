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

The version located in this directory corresponds to release [`v1.4.0`](https://github.com/nasa-jpl/autoRIFT/releases/tag/v1.4.0).
Changes, as listed in `CHANGES.diff`, were done to: 
* facilitate better packaging and distribution of these modules
* correctly handle Sentinel-2 Level 1C products
* use the full Sentinel-2 COG id in the output netCDF product filename to ensure unique names
* prevent truncating Landsat scene names in the netCDF file names
* provide better netCDF metadata including
  * more detailed reporting of Landsat-8/Sentintel-2 acquisition times and their respective center date

**Note:** The `topsinsar_filename.py` included here is not used, but retained for reference.
We've replaced it  with `hyp3_autorift.io.get_topsinsar_config`. 

## Additional Patches

1. The changes listed in `CHANGES-PARAMETER-FILE.diff` were applied to always report
   the canonical URL for the parameter file instead of existing copies to support custom HyP3 deployments.
2. The changes listed in `CHANGES-METADATA.diff` were applied to
   * correct `aquisition_img*` to `acquisition_date_img*` in the NETCDF metadata
     for Sentinel-1 products
   * provide `sensor_img*=MSI`  in the NETCDF metadata for Sentinel-2 products;
     these changes should be included in the next autoRIFT release.
