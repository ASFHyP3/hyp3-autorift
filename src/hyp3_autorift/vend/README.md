# Vendored modules for the HyP3 autoRIFT plugin

This directory contains modules needed for the HyP3 autoRIFT plugin that couldn't
be easily incorporated from a package manager or installed appropriately.

## autoRIFT workflow scripts

These modules are required for the expected autoRIFT workflow:
* `testautoRIFT.py`
* `testGeogridOptical.py`
* `netcdf_output.py`

and are included in the [autoRIFT source code](https://github.com/nasa-jpl/autoRIFT),
but not distributed as part of the package. 

The version located in this directory corresponds to release [`v2.0.0`](https://github.com/nasa-jpl/autoRIFT/releases/tag/v2.0.0).
Changes, as listed in `CHANGES.diff`, were done to: 
1. facilitate better packaging and distribution of these modules
2. correctly handle Sentinel-2 Level 1C products, including:
   * process Sentinel-2 scenes in the `s3://s2-l1c-us-west-2` mirror bucket preferentially (cost savings)
   * use the full Sentinel-2 COG id in the output netCDF product filename to ensure unique names
3. handle Landsat scene pairs in differing projections.
4. correctly set the netcdf `img_pair_info:correction_level_img` attribute values for Sentinel-2 scenes after the 
   transition from Earth Search COG IDs to ESA IDs.
5. fix a bug in the zero mask used for Landsat 7 scenes.
6. fix a bug where early (SLC-On) Landsat 7 scenes would be filtered twice.
7. fix the `noDataMask` used for the search range and %-valid pixel calculations. Unfortunately, this bug exists
   upstream but this fix is dependent on changes in (4) which are not easily applied upstream.

> [!IMPORTANT]
> These above changes are *not* expected to be applied upstream to `nasa-jpl/autoRIFT` at this time because they are a
> significant departure of the "expected" upstream workflow and there's no easy way to communicate or document those
> changes upstream.
