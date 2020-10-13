# Vendored modules for the HyP3 autoRIFT plugin

This directory contains modules needed for the HyP3 autoRIFT plugin that couldn't
be easily incorporated from a package manager or installed appropriately.

## `testautoRIFT_ISCE.py`

This module was provided in the autoRIFT 
[v1.0.7 release](https://github.com/leiyangleon/autoRIFT/releases/tag/v1.0.7),
and is required for the  expected workflow provided to ASF. However, in its 
original form, required too many unpackaged or distributed modules to be found
in the global namespace and therefore cannot be easily incorporated into this
plugin. It also still contains oppressive references to master/slave which is no longer
supported by ISCE 2.4+. Changes, as listed in `CHANGES.diff`, were done to
facilitate better packaging and distribution of the plugin, and remove oppressive
language.

## `testGeogrid_ISCE.py`

This module/script is required for the expected workflow provided to ASF, but is
not provided in the autoRIFT v1.0.7 release and instead resides in the "sister"
Geogrid package (https://github.com/leiyangleon/Geogrid). Geogrid and autoRIFT
are exact duplicate packages and only differ in the README and test scripts, so
simply installing Geogrid was not an option, and furthermore, the Geogrid
repository (no longer) has any tagged or released versions. Finally, Geogrid still
contains oppressive references to master/slave which is no longer supported by
ISCE 2.4+. This script corresponds to the phantom Geogrid v1.0.7 release, which
is commit `09fa392`. Changes, as listed in `CHANGES.diff`, were done to
facilitate better packaging and distribution of the plugin, and remove oppressive
language.
