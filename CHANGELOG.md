# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [PEP 440](https://www.python.org/dev/peps/pep-0440/)
and uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.1](https://github.com/ASFHyP3/hyp3-autorift/compare/v0.3.0...v0.3.1)

### Changed
* Browse images and thumbnails will be generated using the [ITS_LIVE](https://its-live.jpl.nasa.gov/) colormap

### Fixed
* Failures due to stable surface miss-classification

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
