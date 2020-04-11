#!/usr/bin/env bash
# NOTE: This is based on autoRIFT v1.0.4 and ISCE v2.3.3 as released on GitHub
#       as that's what conda-forge is building from
# NOTE: ISCE runtime and build dependencies are taken from its conda-forge
#       build recipe, here: https://github.com/conda-forge/isce2-feedstock/blob/master/recipe/meta.yaml
# NOTE: autoRIFT runtime and build dependencies are taken from its conda-forge
#       build recipe, here: https://github.com/conda-forge/autorift-feedstock/blob/master/recipe/meta.yaml

# Fail script if any step fails
set -e

# Create a base `hyp3-autorift` conda environment
# NOTE: we're going to install autoRIFT and ISCE manually, but we want the runtime dependancies
conda create -y -c conda-forge -n hyp3-autorift --only-deps python=3 isce2 autoRIFT
# Activate the environment
conda activate hyp3-autorift

# ISCE has additional build (only) dependancies
# NOTE: this assumes a linux install! If you're not on linux, you'll need to adjust the compilernames
#       as described here: https://docs.conda.io/projects/conda-build/en/latest/resources/compiler-tools.html
conda install -c conda-forge -y gcc_linux-64 gxx_linux-64 gfortran_linux-64 cython scons openmotif-dev


# Do required environment manipulation for building ISCE
ln -s $CONDA_PREFIX/bin/cython $CONDA_PREFIX/bin/cython3

# Get ISCE and autoRIFT
wget https://github.com/isce-framework/isce2/archive/v2.3.3.tar.gz -O isce2-2.3.3.tar.gz
tar -zxvf isce2-2.3.3.tar.gz
wget https://github.com/leiyangleon/autoRIFT/archive/v1.0.4.tar.gz -O autoRIFT-1.0.4.tar.gz
tar -zxvf autoRIFT-1.0.4.tar.gz

# Place geo_autoRIFT into ISCE as a contributed module and add it to the SCons build script
cp -r autoRIFT-1.0.4/geo_autoRIFT isce2-2.3.3/contrib/

# Setup the ISCE build
pushd isce2-2.3.3
export ISCE_SRC_ROOT=${PWD}
mkdir -p ${ISCE_SRC_ROOT}/_scons ${ISCE_SRC_ROOT}/_build
export SCONS_CONFIG_DIR=${ISCE_SRC_ROOT}/_scons

# Get needed info from the conda environment
export CONDA_HOST_NAME=$($CC -dumpmachine)
# NOTE: Careful we don't conflict with any of python expected env. variables: 
#       https://docs.python.org/3/using/cmdline.html#environment-variables
export PYTHON_SITE_PACKAGES=$(python -c "from sysconfig import get_paths; print(get_paths()['purelib'])")
export PYTHON_INCLUDE_DIR=$(python -c "from sysconfig import get_paths; print(get_paths()['include'])")
export NUMPY_INCLUDE_DIR=$(python -c "import numpy; print(numpy.get_include())")

echo ' 
# The directory in which ISCE will be built
PRJ_SCONS_BUILD = $ISCE_SRC_ROOT/_build/isce

# The directory into which ISCE will be installed
PRJ_SCONS_INSTALL = $PYTHON_SITE_PACKAGES/isce

# The location of libraries, such as libstdc++, libfftw3
LIBPATH = $CONDA_PREFIX/$CONDA_HOST_NAME/sysroot/lib $CONDA_PREFIX/lib

# The location of Python.h. If you have multiple installations of python
# make sure that it points to the right one
CPPPATH = $PYTHON_INCLUDE_DIR $NUMPY_INCLUDE_DIR $CONDA_PREFIX/include

# The location of the fftw3.h
FORTRANPATH =  $CONDA_PREFIX/include

# The location of your Fortran compiler. If not specified it will use the system one
FORTRAN = $FC
# The location of your C compiler. If not specified it will use the system one
CC = $CC
# The location of your C++ compiler. If not specified it will use the system one
CXX = $CXX

# Libraries needed for mdx display utility
MOTIFLIBPATH = $CONDA_PREFIX/lib       # path to libXm.dylib
X11LIBPATH = $CONDA_PREFIX/lib         # path to libXt.dylib
MOTIFINCPATH = $CONDA_PREFIX/include   # path to location of the Xm
                                         # directory with various include files (.h)
X11INCPATH = $CONDA_PREFIX/include     # path to location of the X11 directory
                                         # with various include files

# Explicitly enable cuda if needed
ENABLE_CUDA = False
' > _scons/SConfigISCE

scons install > >(tee -a _scons/scons.out) 2> >(tee -a _scons/scons.err >&2)

# Restore environment, mark completion, and ensure directory is not empty
mkdir -p ${PYTHON_SITE_PACKAGES}/isce/helper
touch ${PYTHON_SITE_PACKAGES}/isce/helper/completed

# Move stack processors to share
mkdir -p ${CONDA_PREFIX}/share/isce2
cp -r contrib/stack/* ${CONDA_PREFIX}/share/isce2
cp -r contrib/timeseries/* ${CONDA_PREFIX}/share/isce2

# Set required environment variables
conda env config vars set ISCE_HOME=${PYTHON_SITE_PACKAGES}/isce
conda env config vars set ISCE_STACK=${PYTHON_SITE_PACKAGES}/share/isce2
conda env config vars set PATH=${PATH}:${PYTHON_SITE_PACKAGES}/isce/bin:${PYTHON_SITE_PACKAGES}/isce/applications

# Finalize our conda env. by removing the ISCE build (only) dependencies
conda remove -y gcc_linux-64 gxx_linux-64 gfortran_linux-64 cython scons openmotif-dev

# And reset, since we've messed with the environment a bit
conda deactivate && conda activate hyp3-autorift

# Install finished, so back to where we started for testing and cleanup
popd

# Test the ISCE install!
topsApp.py --help --steps
stripmapApp.py --help --steps
dem.py --help
isce2gis.py -h
imageMath.py -h
mdx
# Test the autoRIFT and Geogrid ISCE packages
python -c "from isce.components.contrib.geo_autoRIFT.autoRIFT import autoRIFT_ISCE; print(autoRIFT_ISCE.__doc__)"
python -c "from isce.components.contrib.geo_autoRIFT.geogrid import Geogrid; print(Geogrid.__doc__)"


## OPTIONAL ##
# ------------
# At this point, our install is all happy, so we can do some cleanup.

# Remove the source directories 
rm -rf isce2-2.3.3.tar.gz isce2-2.3.3/
rm -rf autoRIFT-1.0.4.tar.gz  autoRIFT-1.0.4/

# Unset the variables we defined
unset ISCE_SRC_ROOT
unset SCONS_CONFIG_DIR
unset PYTHON_SITE_PACKAGES
unset PYTHON_INCLUDE_DIR
unset NUMPY_INCLUDE_DIR
