# Vendored modules for the HyP3 autoRIFT plugin

This directory contains modules needed for the HyP3 autoRIFT plugin that couldn't
be easily incorporated from a package manager or installed appropriately.

## `testautoRIFT_ISCE.py` and `testautoRIFT.py`

---
*Note: A patch from autoRIFT was applied to these files to prevent failures due
 to stable surface miss-classification, which will be included in the next release:*
```diff
-                stable_count = np.sum(SSM & np.logical_not(np.isnan(DX)))
+                stable_count = np.sum(SSM & np.logical_not(np.isnan(DX)) & (DX-DXref > -5) & (DX-DXref < 5) & (DY-DYref > -5) & (DY-DYref < 5))
```
---

These modules were provided in the autoRIFT 
[v1.0.8 release](https://github.com/leiyangleon/autoRIFT/releases/tag/v1.0.8),
and are required for the expected workflow provided to ASF. However, in their 
original form, they required too many unpackaged or distributed modules to be found
in the global namespace and therefore could not be easily incorporated into this
plugin. They also still contained oppressive references to master/slave which is no longer
supported by ISCE 2.4+. Changes, as listed in `CHANGES.diff`, were done to
facilitate better packaging and distribution of the plugin, and remove oppressive
language.

## `testGeogrid_ISCE.py` and `testGeogridOptical.py`

These modules are required for the expected workflow provided to ASF, but are
not provided in the autoRIFT v1.0.8 release and instead resides in the "sister"
Geogrid package (https://github.com/leiyangleon/Geogrid). Geogrid and autoRIFT
are exact duplicate packages and only differ in the README and test modules, so
simply installing Geogrid was not an option, and furthermore, the Geogrid
repository (no longer) has any tagged or released versions. Finally, Geogrid still
contains oppressive references to master/slave which is no longer supported by
ISCE 2.4+. These modules corresponds to the phantom Geogrid v1.0.8 release, which
is commit `4c9cc59`. Changes, as listed in `CHANGES.diff`, were done to
facilitate better packaging and distribution of the plugin, and remove oppressive
language.
