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

1. The changes listed in `CHANGES-METADATA.diff` were applied to
   * correct `aquisition_img*` to `acquisition_date_img*` in the NETCDF metadata
     for Sentinel-1 products
   * provide `sensor_img*=MSI` in the NETCDF metadata for Sentinel-2 products
   These changes should be included in the next autoRIFT release.
2. The changes listed in `CHANGES-METADATA-2.diff` were applied to
   * alphabetize the sensor attributes for the `img_pair_info` variable 
   * change the `flag_stable_shift*` netCDF attributes to `stable_shift_flag*` so
     that they group with the other stable shift attributes
   * change `*_error*` netCDF attributes to `error*` as the prefix is redundant
     because these attributes are attached to the variable (e.g., `vx_error` is
     an attribute of the `vx` variable).
   These changes should be included in the next autoRIFT release.
3. The changes listed in `CHANGES-METADATA-3.diff` were applied to
   * uniformly order all data variable attributes, loosely in alphabetical order
   * significantly improve the codestyle (e.g., PEP8) of `netcdf_output.py`
   These changes should be included in the next autoRIFT release.
4. The changes listed in `CHANGES-L9.diff` were applied to allow Landsat-9
   Collection 2 scenes to be processed by autoRIFT. These changes should be
   included in the next autoRIFT release.
5. The changes listed in `CHANGES-S2-WEST.diff` were applied to allow `testGeogrid_ISCE.py`
   and `testGeogridOptical.py` to process scenes in the `s3://s2-l1c-us-west-2` bucket
6. The changes listed in `CHANGES-WALLLIS-WIDTH.diff` were applied to select the correct
   Wallis filter width for Sentinel-1 scenes. These changes should be included in the next
   autoRIFT release.
