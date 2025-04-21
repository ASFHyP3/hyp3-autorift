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

The version located in this directory corresponds to release [`v1.5.0`](https://github.com/nasa-jpl/autoRIFT/releases/tag/v1.5.0).
Changes, as listed in `CHANGES.diff`, were done to: 
* facilitate better packaging and distribution of these modules
* correctly handle Sentinel-2 Level 1C products, including:
  * process Sentinel-2 scenes in the `s3://s2-l1c-us-west-2` mirror bucket preferentially (cost savings)
  * use the full Sentinel-2 COG id in the output netCDF product filename to ensure unique names

## Additional Patches

1. The changes listed in `CHANGES-173.diff` were applied in [ASFHyP3/hyp3-autorift#173](https://github.com/ASFHyP3/hyp3-autorift/pull/173)
   to handle Landsat scene pairs in differing projections. These changes are *not* expected to be applied upstream to
   `nasa-jpl/autoRIFT` because they are a significant departure of the "expected" upstream workflow and there's no easy
   way to communicated or document those changes upstream.
2. The changes listed in `CHANGES-183.diff` were applied in [ASFHyP3/hyp3-autorift#183](https://github.com/ASFHyP3/hyp3-autorift/pull/183)
   to correctly set the netcdf `img_pair_info:correction_level_img` attribute values for Sentinel-2 scenes after the transition from
   Earth Search COG IDs to ESA IDs.
3. The changes listed in `CHANGES-211.diff` were applied in [ASFHyP3/hyp3-autorift#211](https://github.com/ASFHyP3/hyp3-autorift/pull/211)
   to fix bug in the zero mask used for Landsat 7 scenes. Like (4), these changes are *not* expected to be applied
   upstream to `nasa-jpl/autoRIFT`.
4. The changes listed in `CHANGES-213.diff` were applied in [ASFHyP3/hyp3-autorift#213](https://github.com/ASFHyP3/hyp3-autorift/pull/213)
   to fix bug where early (SLC-On) Landsat 7 scenes would be filtered twice. Like (4), these changes are *not* expected to be applied
   upstream to `nasa-jpl/autoRIFT`.
5. The changes listed in `CHANGES-214.diff` were applied in [ASFHyP3/hyp3-autorift#214](https://github.com/ASFHyP3/hyp3-autorift/pull/214)
   to fix the `noDataMask` used for the search range and %-valid pixel calculations. Unfortunately, this bug exists
   upstream but this fix is dependent on changes in (4) which are not easily applied upstream. Therefore, these changes
   are *not* expected to be applied upstream to `nasa-jpl/autoRIFT` without a significant refactor upstream.
