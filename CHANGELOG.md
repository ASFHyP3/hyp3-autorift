# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [PEP 440](https://www.python.org/dev/peps/pep-0440/)
and uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.19.0]
### Changed
* Orbits are now downloaded using `s1_orbits` rather than `hyp3lib`.

### Removed
* Removed support for the `--esa-username` and `--esa-password` command-line options and the `ESA_USERNAME` and `ESA_PASSWORD` environment variables.

## [0.18.1]
### Changed
* The conversion matrices netCDF file created bt the S1 correction workflow is now called `conversion_matricies.nc` and no longer includes the scene name per feedback from JPL. 

### Fixed
* `s2_isce2.generate_correction_data` now returns a Path instead of a str as expected by `hyp3lib.aws.upload_file_to_s3`.
* `s2_isce2.create_conversion_matricies` now uses the pixel-center instead of the upper-left corner for the x,y dimensions.
* `s2_isce2.create_conversion_matricies` now explicitly syncs data to and closes the netCDF file to prevent corrupt files from being uploaded.

## [0.18.0]
### Added
* The Sentinel-1 correction workflow will now calculate and write the M11/M12 conversion matrices to a netCDF file.

### Fixed
* `hyp3_autorift.crop` will now preserve the `add_offset` and `scale_factor` encoding attributes for all variables, and in particular, for the M11/M12 conversion matrices. 

### Removed
* Support for Python 3.8 has been dropped.

## [0.17.0]
## Changed
* In preparation for a major update, the Sentinel-1 processing workflow has been isolated to a new `hyp3_autorift.s1_isce2` module. 

## [0.16.0]
### Fixed
* `hyp3_autorift` will no longer attempt to crop files with no valid data

### Removed
* The unused `ASF` naming scheme has been removed from the `hyp3_autorift` CLI and the `hyp3_autorift.process` function

## Changed
* Everything in `hyp3_autorift.io` has been moved into `hyp3_autorift.utils` to prevent shadowing the builtin `io` module
* `hyp3_autorift.process.process` now returns the product file, browse image, and (new) thumbnail image

## [0.15.0]
### Added
* `--publish-bucket` option has been added to the HyP3 entry point to additionally publish products an AWS bucket, such as the ITS_LIVE AWS Open Data bucket, `s3://its-live-data`.
* `upload_file_to_s3_with_publish_access_keys` to perform S3 uploads using credentials from the `PUBLISH_ACCESS_KEY_ID` and `PUBLISH_SECRET_ACCESS_KEY` environment vairables.

## [0.14.1]
### Changed
* Upgraded to `hyp3lib=>3,<4` from `>=2,<3`

## [0.14.0]
### Added
* `utils.get_esa_credentials` to check for the existence of CDSE credentials before processing begins.

### Changed
* Updated `hyp3lib` to  v2.0.2+, which uses the new Copernicus Data Space Ecosystem (CDSE) API to download orbit files.
* Calls to `downloadSentinelOrbitFile` now specify the `esa_credentials` argument.

## [0.13.0]

### Changed
* Upgraded to ASFHyP3/actions v0.8.3
* `hyp3-autorift` now uses a `src` layout per this [recommendation](https://packaging.python.org/en/latest/discussions/src-layout-vs-flat-layout/).
* `hyp3-autorift` now only uses `pyproject.toml` for package creation now that `setuptools` recommends [not using setup.py](https://setuptools.pypa.io/en/latest/userguide/quickstart.html#setuppy-discouraged).

### Fixed
* Patch [235](src/hyp3_autorift/vend/CHANGES-227.diff) was applied  to make it easier for users to correct for ionosphere
  streaks without needing to know the scale factor.

## [0.12.0]

### Added
* [`hyp3_autorift.crop`](src/hyp3_autorift/crop.py) provides a `crop_netcdf_product` function to crop HyP3 AutoRIFT products
  to the extent of valid `v` data

### Changed
* HyP3 AutoRIFT products generated with the main workflow will be cropped to the extent of the valid `v` data

### Fixed
* Patch [227](src/hyp3_autorift/vend/CHANGES-227.diff) was applied to align the S1 granules velocity description with the
  optical products

## [0.11.1]

### Fixed
* Patch [223](src/hyp3_autorift/vend/CHANGES-223.diff) was applied so that the polarization is correctly selected in the
  sentinel-1 workflow

## [0.11.0]

### Added
* `hyp3_autorift`'s main entrypoint now accepts `++process` arguments to support multiple workflows
  * `++process hyp3_autorift` (default) will run the same autoRIFT pair processing workflow
  * `++process s1_correction` will run a Geogrid-only workflow to create the GeoTIFFs necessary for correcting the
    scale-projection issue in polar-sterographic products generated from Sentinel-1 pairs that were created using HyP3
    autoRIFT versions < 0.9.0, which was released November 2, 2022
  
### Changed
* Patch [nasa-jpl/autorift#78](src/hyp3_autorift/vend/CHANGES-UPSTREAM-78.diff) was applied from upstream to support the
  Sentinel-1 correction workflow

### Removed
* The unused `autorift_proc_pair` console script entrypoint was removed

## [0.10.5]

### Fixed
* The zero mask and nodata value for wallis-filtered Landsat-7 images are now set appropriately
* Early (SLC-On) Landsat-7 images are no longer incorrectly filtered a second time with the high-pass filter
* The search range and %-valid pixels are now correctly calculated for Landsat-7 images

## [0.10.4]

### Fixed
* Landsat 7+8 pairs will be filtered appropriately; see [#201](https://github.com/ASFHyP3/hyp3-autorift/issues/201)

## [0.10.3]

### Added
* `--omp-num-threads` parameter to the `main()` entrypoint to limit the number of threads used by ISCE during multiprocessing.

### Changed
* `hyp3_autorift` will now ensure both scenes are in the same projection for Landsat missions

## [0.10.2]

### Changed

* Patch [196](src/hyp3_autorift/vend/CHANGES-189.diff) was applied to update the `flag_meanings` netCDF attribute to be
  inline with CF-Convention 1.8, as described in the [vendored software README.md](src/hyp3_autorift/vend/README.md)

## [0.10.1]

### Changed
* Patches [189](src/hyp3_autorift/vend/CHANGES-189.diff),  [191](src/hyp3_autorift/vend/CHANGES-191.diff), and [194](src/hyp3_autorift/vend/CHANGES-194.diff) 
  were applied to update some netCDF variable attributes, as described in the [vendored software README.md](src/hyp3_autorift/vend/README.md)

## [0.10.0]

### Changed
* Sentinel-2 scenes are now retrieved from [Google Cloud](https://cloud.google.com/storage/docs/public-datasets/sentinel-2),
  rather than [AWS](https://registry.opendata.aws/sentinel-2/).

### Removed
* Sentinel-2 granules may no longer be specified using Element84 COG names, only
  [ESA names](https://sentinels.copernicus.eu/web/sentinel/user-guides/sentinel-2-msi/naming-convention).

## [0.9.1]

### Changed
* [A patch](src/hyp3_autorift/vend/CHANGES-176.diff) was applied to update some netCDF variable attributes, as described
  in the [vendored software README.md](src/hyp3_autorift/vend/README.md)

## [0.9.0]

### Added
* Added support for processing Landsat-4, -5, and -7 Collection 2 scenes
* `hyp3_autorift.process.get_lc2_stac_json_key` will now work for landsat missions 4-9 and for all sensors

### Changed
* Upgraded autoRIFT to [v1.5.0](https://github.com/nasa-jpl/autoRIFT/releases/tag/v1.5.0) 
  and [ISCE2 v2.6.1 built with autoRIFT v1.5.0](https://anaconda.org/hyp3/isce2)

### Fixed 
* Pinned Python to `<3.10` as ISCE2 is currently [incompatible with Python 3.10](https://github.com/isce-framework/isce2/issues/458).
  This restriction will be lifted once the conda-forge distribution of ISCE2 is compatible with Python 3.10

## [0.8.7]

### Fixed
* Updated the USGS STAC catalog API endpoint

## [0.8.6]

### Fixed
* Datetime information can now be correctly extracted from 25-character S2 Earth Search names. Fixes #152

## [0.8.5]

### Added
* The Earth Search STAC catalog is incomplete for Sentinel-2 L1C, with many more scenes in the AWS bucket than the 
  catalog. When a S2 scene cannot be found in the STAC catalog, `hyp3-autorift` will fall back to a bundled S2 metadata
  catalog derived from an inventory of scenes in the AWS bucket and the Google Earth catalog

## [0.8.4]

### Fixed
* A GDAL issue preventing Sentinel-1 processing introduced in v0.8.1

## [0.8.3]

### Fixed
* Vendored `testGeogrid_ISCE.py` and `testGeogridOptical.py` scripts no longer raise an
  `Exception('Optical data NOT supported yet!')` when processing scenes in the `s3://s2-l1c-us-west-2` bucket

## [0.8.2]

### Changed
* When processing Sentinel-2 scenes, `hyp3_autorift` will now prefer scenes available in `s3://s2-l1c-us-west-2`
  over the canonical `s3://sentinel-s2-l1c` bucket in the `eu-central-1` region

## [0.8.1]

### Changed
* Upgraded to hyp3lib [v1.7.0](https://github.com/ASFHyP3/hyp3-lib/blob/develop/CHANGELOG.md#170) from v1.6.8

## [0.8.0]

### Added
* `hyp3_autorift` can now process Landsat 9 Collection 2 scenes

## [0.7.5](https://github.com/ASFHyP3/hyp3-autorift/compare/v0.7.4...v0.7.5)

### Added
* It is now possible to inject Earthdata username and password using environment variables: `EARTHDATA_USERNAME`
  and `EARTHDATA_PASSWORD`.

### Fixed
* The `opencv` conda package has been pinned to `4.5.3` due to a breaking change to its `libopencv_core.so.*`
  naming scheme in `4.5.5`.

## [0.7.4](https://github.com/ASFHyP3/hyp3-autorift/compare/v0.7.3...v0.7.4)

### Changed
* Patches were applied to clean up some netCDF variable attributes, as described
  in the [vendored software README.md](src/hyp3_autorift/vend/README.md)

## [0.7.3](https://github.com/ASFHyP3/hyp3-autorift/compare/v0.7.2...v0.7.3)

### Changed
* Default autoRIFT parameter file was updated to point at the new `its-live-data` AWS S3 bucket
  instead of `its-live-data.jpl.nasa.gov`
* In the netCDF product, the default autoRIFT parameter file URL will always be reported
  instead of reporting copies used to support custom HyP3 deployments
* A patch was applied to fix some Sentinel-1 and Sentinel-2 product metadata, as described
  in the [vendored software README.md](src/hyp3_autorift/vend/README.md)

### Fixed
* Updated the upgrade to autoRIFT `v1.4.0` to account for the autoRIFT source repo
  having moved the `v1.4.0` tag  (between commits [`67e4996..b6700f9`](https://github.com/nasa-jpl/autoRIFT/compare/67e4996..b6700f9))
  and changed the conda-forge package accordingly (new sha256 and bumped the build number).
  * The autoRIFT workflow scripts are now based on the moved tag and any still
    necessary fixes were applied as described in the [vendored software README.md](src/hyp3_autorift/vend/README.md)
* For Sentinel-2 products, file names now include the full COG Id to ensure unique
  file names are produced and to be consistent with other products.

## [0.7.2](https://github.com/ASFHyP3/hyp3-autorift/compare/v0.7.1...v0.7.2)

### Fixed
* Geogrid now points to `fine_coreg` for Sentinel-1 workflows, fixing common `IndexError` failures

## [0.7.1](https://github.com/ASFHyP3/hyp3-autorift/compare/v0.7.0...v0.7.1)

### Changed
* Applied a fix to the autoRIFT packaging script that updates the reference velocity
  fields for projected velocity, as described in the [vendored software README.md](src/hyp3_autorift/vend/README.md)

## [0.7.0](https://github.com/ASFHyP3/hyp3-autorift/compare/v0.6.3...v0.7.0)

### Changed
* Upgraded autoRIFT to [v1.4.0](https://github.com/leiyangleon/autoRIFT/releases/tag/v1.4.0)
  and [ISCE2 v2.5.3 built with autoRIFT v1.4.0](https://anaconda.org/hyp3/isce2)
* Applied some fixes to the autoRIFT workflow scripts as described in the
  [vendored software README.md](src/hyp3_autorift/vend/README.md)
* `hyp3_autorift.io.save_topsinsar_mat` has been renamed to `hyp3_autorift.io.get_topsinsar_config`
  * It no longer writes a config `.mat` file and instead returns the config dictionary

### Removed
* `topsinsar_filename.py` console script entrypoint has been removed 
  (use `hyp3_autorift.io.get_topsinsar_config` instead)
* The `hyp3_autorift/netcdf_output.py` module has been removed in favor of the (new)
  vendored `hyp3_autorift/vend/netcdf_output.py`

## [0.6.3](https://github.com/ASFHyP3/hyp3-autorift/compare/v0.6.2...v0.6.3)

### Changed
* Applied some minor error estimate fixes and netCDF metadata attribute updates as
  described in the [vendored software README.md](src/hyp3_autorift/vend/README.md)
* `process.get_lc2_metadata()` now attempts to fetch STAC metadata from the
  https://landsatlook.usgs.gov/ API and falls back the STAC json in the S3 bucket

### Removed
* `hyp3_autorift.process` and the associated `autorift_proc_pair` entrypoint no longer
  accept the `band` argument, which wasn't being used.

## [0.6.2](https://github.com/ASFHyP3/hyp3-autorift/compare/v0.6.1...v0.6.2)

### Changed
* `conda-env.yml` has been renamed to `environment.yml` in-line with community practice
* Upgraded to hyp3lib [v1.6.8](https://github.com/ASFHyP3/hyp3-lib/blob/develop/CHANGELOG.md#168) from v1.6.7
* Upgrade to [ISCE2 v2.5.2 built with autoRIFT v1.3.1](https://anaconda.org/hyp3/isce2)

## [0.6.1](https://github.com/ASFHyP3/hyp3-autorift/compare/v0.6.0...v0.6.1)

### Changed
* Upgraded autoRIFT to [v1.3.1](https://github.com/leiyangleon/autoRIFT/releases/tag/v1.3.1)
  and [ISCE2 v2.5.1 built with autoRIFT v1.3.1](https://anaconda.org/hyp3/isce2)
  
## [0.6.0](https://github.com/ASFHyP3/hyp3-autorift/compare/v0.5.2...v0.6.0)

### Changed
* Upgraded autoRIFT to [v1.3.0](https://github.com/leiyangleon/autoRIFT/releases/tag/v1.3.0)
  and [ISCE2 v2.5.1 built with autoRIFT v1.3.0](https://anaconda.org/hyp3/isce2)

## [0.5.2](https://github.com/ASFHyP3/hyp3-autorift/compare/v0.5.1...v0.5.2)

### Changed
* `process.get_lc2_metadata()` now fetches STAC metadata from the `usgs-landsat` S3 bucket instead of the
  https://landsatlook.usgs.gov/ API.

## [0.5.1](https://github.com/ASFHyP3/hyp3-autorift/compare/v0.5.0...v0.5.1)

### Changed
* Minor updates to the netCDF product metadata
* Pairs that end up having a 0 ROI (no valid data) will not fail at the end of processing,
  but instead will upload a netCDF product that reports 0 ROI

## [0.5.0](https://github.com/ASFHyP3/hyp3-autorift/compare/v0.4.5...v0.5.0)

### Changed
* autoRIFT products will now be generated with a 120 m pixel spacing instead of 240 m
* `hyp3_autorift` will directly access Landsat-8 and Sentinel-2 data in the cloud
  instead of downloading the scenes locally
* Upgraded autoRIFT to [v1.2.0](https://github.com/leiyangleon/autoRIFT/releases/tag/v1.2.0)
  and [ISCE2 v2.5.1 built with autoRIFT v1.2.0](https://anaconda.org/hyp3/isce2)

### Fixed
* Sentinel-2 L1C metadata is generated correctly
* Sentinel-2 search by ESA granule id
* Landsat-8 scene names are no longer truncated in the `ITS_LIVE` naming schemes

## [0.4.5](https://github.com/ASFHyP3/hyp3-autorift/compare/v0.4.4...v0.4.5)

### Changed
* Upgraded to hyp3lib [v1.6.7](https://github.com/ASFHyP3/hyp3-lib/blob/develop/CHANGELOG.md#167) from v1.6.2

## [0.4.4](https://github.com/ASFHyP3/hyp3-autorift/compare/v0.4.3...v0.4.4)

### Added
* Log message prior to downloading Sentinel-2 and Landsat 8 products

## [0.4.3](https://github.com/ASFHyP3/hyp3-autorift/compare/v0.4.2...v0.4.3)

### Added
* Ability to specify shapefile used to determine the correct search parameters by geographic location
  * a `--parameter-file` option has been added to `hyp3_autorift`
  * a `parameter_file` keyword argument has been added to `hyp3_autorift.process.process`
* Ability to specify a preferred product naming scheme
  * a `--naming-scheme` option has been added to `hyp3_autorift`
  * a `naming_scheme` keyword argument has been added to `hyp3_autorift.process.process`

## [0.4.2](https://github.com/ASFHyP3/hyp3-autorift/compare/v0.4.1...v0.4.2)

### Fixed
* A *partial* fix was implemented to correct out of index errors when processing
  optical scenes (typically seen with Landsat-8 pairs) due to calculating different
  overlapping subset sizes when co-registering the images. Currently, only the
  smallest subset size is used, so the bounding box may be 1px too small in x
  and/or y, but there shouldn't be any pixel offsets. Full fix will need to be
  implemented upstream in [autoRIFT](https://github.com/leiyangleon/autoRIFT).

## [0.4.1](https://github.com/ASFHyP3/hyp3-autorift/compare/v0.4.0...v0.4.1)

### Changed
* `hyp3_autorift` will determine the polarization of Sentinel-1 scenes based on
  reference scene to allow for VV in addition to HH processing.

### Removed
* `autorift_proc_pair` entrypoint no longer accepts a `-p`/`--polarization` option
* `hyp3_autorift.process.process` no longer accepts a `polarization=` keyword argument

### Fixed
* ValueError exception when processing scenes with short (23 char) Element 84 Sentinel-2 IDs

## [0.4.0](https://github.com/ASFHyP3/hyp3-autorift/compare/v0.3.3...v0.4.0)

**HyP3 v1 is no longer supported as of this release.**

### Added
* Added support for global processing (previously only Greenland and Antarctica) 
  by pointing at the new autoRIFT parameter files provided by JPL
* Added support for processing Landsat-8 Collection 2 scene pairs
* Example documentation for submitting autoRIFT jobs via the [HyP3 SDK](docs/sdk_example.ipynb)
  or [HyP3 API](docs/api_example.md)

### Changed
* Sentinel-2 support now targets level-1c products instead of level-2a products to
  remove baked in slope correction
* `hyp3_autorift` entrypoint point now kicks off HyP3 v2 processing (options have changed! see `--help`)

### Fixed
* 1/2 pixel offset in netCDF file due to gdal and netCDF using different pixel reference points

### Removed
* The `autorift` entrypoint and HyP3 v1 support has been removed
* The `hyp3_autorift_v2` entrypoint has been removed (now just `hyp3_autorift`)

## [0.3.1](https://github.com/ASFHyP3/hyp3-autorift/compare/v0.3.0...v0.3.1)

### Changed
* Browse images and thumbnails will be generated using the [ITS_LIVE](https://its-live.jpl.nasa.gov/) colormap

### Fixed
* Failures due to stable surface misclassification

## [0.3.0](https://github.com/ASFHyP3/hyp3-autorift/compare/v0.2.0...v0.3.0)

### Added
* Installed autoRIFT v1.0.8 for processing optical scenes (in addition to v1.0.7 already installed as part of ISCE)
* Added support for processing Sentinel-2 scene pairs

### Changed
* Upgraded to isce2 [v2.4.2](https://github.com/isce-framework/isce2/releases/tag/v2.4.2) from v2.4.1
* Upgraded to hyp3lib [v1.6.2](https://github.com/ASFHyP3/hyp3-lib/blob/develop/CHANGELOG.md#162) from v1.6.1

### Removed
* Removed the "include intermediate files" option when running jobs via HyP3 v1

## [0.2.0](https://github.com/ASFHyP3/hyp3-autorift/compare/v0.1.0...v0.2.0)

### Changed
* `hyp3_autorift` now requires python >=3.8, and depends on ISCE >=2.4.1 which 
  includes [autoRIFT 1.0.7](https://github.com/leiyangleon/autoRIFT/releases/tag/v1.0.7)
* Upgraded to hyp3lib [v1.6.1](https://github.com/ASFHyP3/hyp3-lib/blob/develop/CHANGELOG.md#161) from v1.5.0
* Output product names have change to follow HyP3's standard pair-processing naming scheme
* Browse images are now uploaded for hyp3v1 and will appear in email notifications
* NetCDF product files include a `source` and `reference` global attribute in line with
  [CF-Conventions](https://cfconventions.org/Data/cf-conventions/cf-conventions-1.8/cf-conventions.html#description-of-file-contents)
  ([see PR #20](https://github.com/ASFHyP3/hyp3-autorift/pull/20)) 

## [0.1.1](https://github.com/ASFHyP3/hyp3-autorift/compare/v0.1.0...v0.1.1)

### Added
* A browse image of the ice velocity is produced for HyP3v1 and v2, and a thumbnail 
  of the browse image will be produced for HyP3v2

### Fixes
* Restrict ISCE version to 2.4.0 which includes autoRIFT 1.0.6

## [0.1.0](https://github.com/ASFHyP3/hyp3-autorift/compare/v0.0.0...v0.1.0)

Initial release of hyp3-autorift, a HyP3 plugin for feature tracking processing
with AutoRIFT-ISCE. This plugin consists of:
 * `hyp3_autorift`, a `pip` installable python package that runs the autoRIFT
   inside the HyP3 plugin. This package provides:
   * `autorift` entrypoint used as they HyP3 plugin (container) entrypoint, which
     passes arguments down to the selected HyP3 version entrypoints:
     * `hyp3_autorift`
     * `hyp3_autorift_2`
   * `autorift_proc_pair` for running the autoRIFT process for Sentinel-1 image
     pairs (independent of HyP3)
 * a `Dockerfile` to build the HyP3 plugin
 * GitHub Actions workflows that will build and distribute hyp3-autorift's
   python package and HyP3 plugin
