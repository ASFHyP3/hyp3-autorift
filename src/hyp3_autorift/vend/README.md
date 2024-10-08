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
We've replaced it  with `hyp3_autorift.s1_isce2.get_topsinsar_config`. 

## Additional Patches

1. The changes listed in `CHANGES-176.diff` were applied in [ASFHyP3/hyp3-autorift#176](https://github.com/ASFHyP3/hyp3-autorift/pull/176)
   and [ASFHyP3/hyp3-autorift#180](https://github.com/ASFHyP3/hyp3-autorift/pull/180) to:
   * Ensure Landsat `satellite_img1` and `satellite_img2` netCDF attributes were string like `'4'` to match the
     convention of other missions
   * Set the fallback value of `stable_shift` netCDF attribute to `0` instead `np.nan`
   These changes have been [proposed upstream](https://github.com/nasa-jpl/autoRIFT/pull/73) and should be applied
   in the next `nasa-jpl/autoRIFT` release.
2. The changes listed in `CHANGES-183.diff` were applied in [ASFHyP3/hyp3-autorift#183](https://github.com/ASFHyP3/hyp3-autorift/pull/183)
   to correctly set the netcdf `img_pair_info:correction_level_img` attribute values for Sentinel-2 scenes after the transition from
   Earth Search COG IDs to ESA IDs.
3. The changes listed in `CHANGES-189.diff`,  `CHANGES-191.diff`, `CHANGES-194.diff`, and  `CHANGES-194.diff` were applied in
   [ASFHyP3/hyp3-autorift#189](https://github.com/ASFHyP3/hyp3-autorift/pull/189),
   [ASFHyP3/hyp3-autorift#191](https://github.com/ASFHyP3/hyp3-autorift/pull/191), 
   [ASFHyP3/hyp3-autorift#194](https://github.com/ASFHyP3/hyp3-autorift/pull/194),
   and [ASFHyP3/hyp3-autorift#196](https://github.com/ASFHyP3/hyp3-autorift/pull/196),
   after an extensive metadata review to prepare netCDF output for ingest to NSIDC DAAC. These changes have been
   [proposed upstream](https://github.com/nasa-jpl/autoRIFT/pull/74) and should be applied in the next
   `nasa-jpl/autoRIFT` release.
4. The changes listed in `CHANGES-173.diff` were applied in [ASFHyP3/hyp3-autorift#173](https://github.com/ASFHyP3/hyp3-autorift/pull/173)
   to handle Landsat scene pairs in differing projections. These changes are *not* expected to be applied upstream to
   `nasa-jpl/autoRIFT` because they are a significant departure of the "expected" upstream workflow and there's no easy
   way to communicated or document those changes upstream.
5. The changes listed in `CHANGES-211.diff` were applied in [ASFHyP3/hyp3-autorift#211](https://github.com/ASFHyP3/hyp3-autorift/pull/211)
   to fix bug in the zero mask used for Landsat 7 scenes. Like (4), these changes are *not* expected to be applied
   upstream to `nasa-jpl/autoRIFT`.
6. The changes listed in `CHANGES-213.diff` were applied in [ASFHyP3/hyp3-autorift#213](https://github.com/ASFHyP3/hyp3-autorift/pull/213)
   to fix bug where early (SLC-On) Landsat 7 scenes would be filtered twice. Like (4), these changes are *not* expected to be applied
   upstream to `nasa-jpl/autoRIFT`.
7. The changes listed in `CHANGES-214.diff` were applied in [ASFHyP3/hyp3-autorift#214](https://github.com/ASFHyP3/hyp3-autorift/pull/214)
   to fix the `noDataMask` used for the search range and %-valid pixel calculations. Unfortunately, this bug exists
   upstream but this fix is dependent on changes in (4) which are not easily applied upstream. Therefore, these changes
   are *not* expected to be applied upstream to `nasa-jpl/autoRIFT` without a significant refactor upstream.
8. The changes listed in `CHANGES-UPSTREAM-78.diff` were applied from upstream ([nasa-jpl/autorift#78](https://github.com/nasa-jpl/autorift/pull/78))
   in [ASFHyP3/hyp3-autorift#218](https://github.com/ASFHyP3/hyp3-autorift/pull/218) to run a Geogrid-only workflow to
   create the GeoTIFFs necessary for correcting the scale-projection issue in polar-sterographic products generated
   from Sentinel-1 pairs that were created using HyP3 autoRIFT versions < 0.9.0, which was released November 2, 2022
9. The changes listed in `CHANGES-223.diff` were applied in [ASFHyP3/hyp3-autorift#223](https://github.com/ASFHyP3/hyp3-autorift/pull/223)
   were applied to the S1 correction workflow so that the scene's polarization was set correctly 
10. The changes listed in `CHANGES-227.diff` were applied in [ASFHyP3/hyp3-autorift#227](https://github.com/ASFHyP3/hyp3-autorift/pull/227)
    were applied to align the S1 granules velocity description with the optical products. These changes have been
    [proposed upstream](https://github.com/nasa-jpl/autoRIFT/pull/87) and should be applied in the next 
    `nasa-jpl/autoRIFT` release.    
11. The changes listed in `CHANGES-235.diff` were applied in [ASFHyP3/hyp3-autorift#235](https://github.com/ASFHyP3/hyp3-autorift/pull/235)
    to make it easier for users to correct for ionosphere streaks without needing to know the scale
    factor. These changes have been [proposed upstream](https://github.com/nasa-jpl/autoRIFT/pull/92) and should be
    applied in the next `nasa-jpl/autoRIFT` release.
12. The changes listed in `CHANGES-UPSTREAM-101.diff` were applied from upstream ([nasa-jpl/autorift#101](https://github.com/nasa-jpl/autorift/pull/101))
    in [ASFHyP3/hyp3-autorift#291](https://github.com/ASFHyP3/hyp3-autorift/pull/291) so that M11/M12 variables are
    output as `float32` instead of compressed `int16` variables which did not even use the full dynamic range.
