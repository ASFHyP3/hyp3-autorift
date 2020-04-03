FROM ubuntu:18.04

# For opencontainers label definitions, see:
#    https://github.com/opencontainers/image-spec/blob/master/annotations.md
LABEL org.opencontainers.image.title="HyP3 autoRIFT ISCE"
LABEL org.opencontainers.image.description="A HyP3 plugin for feature tracking processing with AutoRIFT-ISCE"
LABEL org.opencontainers.image.vendor="Alaska Satellite Facility"
LABEL org.opencontainers.image.authors="ASF APD/Tools Team <uaf-asf-apd@alaska.edu>"
LABEL org.opencontainers.image.licenses="BSD-3-Clause"
LABEL org.opencontainers.image.url="https://github.com/asfadmin/hyp3-autorift"
LABEL org.opencontainers.image.source="https://github.com/asfadmin/hyp3-autorift"
# LABEL org.opencontainers.image.documentation=""

# Dynamic lables to define at build time via `docker build --label`
# LABEL org.opencontainers.image.created=""
# LABEL org.opencontainers.image.version=""
# LABEL org.opencontainers.image.revision=""

ARG DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=true

RUN apt-get update && apt-get upgrade -y && apt-get install -y software-properties-common && \
    add-apt-repository -y ppa:ubuntugis/ubuntugis-unstable && apt-get update && \
    apt-get install -y unzip vim wget curl build-essential cmake \
    gfortran imagemagick libatlas-base-dev gdal-bin libgdal-dev \
    libavcodec-dev libavformat-dev libfftw3-dev libgl1-mesa-dev libgtk-3-dev \
    libhdf5-dev libjpeg-dev libmotif-dev libpng-dev libswscale-dev libtiff-dev \
    libv4l-dev libx264-dev libxvidcore-dev pkg-config python3-dev python3-h5py \
    python3-matplotlib python3-pip python3-scipy scons cython3 && \
    apt-get clean

RUN cd /opt && wget https://github.com/opencv/opencv/archive/3.4.7.zip -O opencv-3.4.7.zip && \
    wget https://github.com/opencv/opencv_contrib/archive/3.4.7.zip -O opencv_contrib-3.4.7.zip && \
    unzip opencv-3.4.7.zip && unzip opencv_contrib-3.4.7.zip && \
    export OPENCV_CONTRIB_MODULES=/opt/opencv_contrib-3.4.7/modules && \
    mkdir opencv-3.4.7/_build opencv-3.4.7/_release && cd opencv-3.4.7/_build && \
    cmake -D CMAKE_BUILD_TYPE=RELEASE \
      -D CMAKE_INSTALL_PREFIX=/usr/local \
      -D INSTALL_PYTHON_EXAMPLES=ON \
      -D OPENCV_EXTRA_MODULES_PATH=${OPENCV_CONTRIB_MODULES} \
      -D PYTHON_EXECUTABLE=$(which python3) \
      -D BUILD_EXAMPLES=ON \
      .. && \
      make -j4 install && cd /opt && ldconfig

RUN pip3 install --upgrade pip && \
    python3 -m pip install --upgrade numpy scipy statsmodels scikit-image

ARG CONDA_UID=1000
ARG CONDA_GID=1000

RUN cd /opt && \
    wget https://github.com/isce-framework/isce2/archive/f43daae0150cd93abd961eb2e57e6d45045bceb6.zip \
    -O isce2-f43daae0150cd93abd961eb2e57e6d45045bceb6.zip && \
    unzip isce2-f43daae0150cd93abd961eb2e57e6d45045bceb6.zip && \
    mv isce2-f43daae0150cd93abd961eb2e57e6d45045bceb6 isce2-2.3.2 && \
    wget https://github.com/leiyangleon/autoRIFT/archive/v1.0.4.tar.gz -O autoRIFT-1.0.4.tar.gz && \
    tar -zxvf autoRIFT-1.0.4.tar.gz && \
    cp -r autoRIFT-1.0.4/geo_autoRIFT isce2-2.3.2/contrib/ && \
    mkdir /opt/isce2-2.3.2/_scons /opt/isce2-2.3.2/_build

COPY hyp3_autorift/etc/SConfigISCE /opt/isce2-2.3.2/_scons/

RUN export ISCE_SRC_ROOT=/opt/isce2-2.3.2 && cd ${ISCE_SRC_ROOT} && \
    export SCONS_CONFIG_DIR=${ISCE_SRC_ROOT}/_scons && \
    export PYTHON_SITE_PACKAGES=$(python3 -c "from sysconfig import get_paths; print(get_paths()['purelib'])") && \
    export PYTHON_INCLUDE_DIR=$(python3 -c "from sysconfig import get_paths; print(get_paths()['include'])") && \
    export NUMPY_INCLUDE_DIR=$(python3 -c "import numpy; print(numpy.get_include())") && \
    scons install && \
    mkdir -p ${PYTHON_SITE_PACKAGES}/isce/helper && \
    touch ${PYTHON_SITE_PACKAGES}/isce/helper/completed && \
    mkdir -p /usr/local/share/isce2 && \
    cp -r contrib/stack/* /usr/local/share/isce2 && \
    cp -r contrib/timeseries/* /usr/local/share/isce2 && \
    cd /opt && rm -rf opencv-3.4.7.zip opencv-3.4.7/ opencv_contrib-3.4.7.zip opencv_contrib-3.4.7/ && \
    rm -rf isce2-f43daae0150cd93abd961eb2e57e6d45045bceb6.zip isce2-2.3.2/ autoRIFT-1.0.4.tar.gz  autoRIFT-1.0.4/

ARG S3_PYPI_HOST

RUN python3 -m pip install --no-cache-dir hyp3_autorift \
    --trusted-host "${S3_PYPI_HOST}" \
    --extra-index-url "http://${S3_PYPI_HOST}"

RUN groupadd -g "${CONDA_GID}" --system conda && \
    useradd -l -u "${CONDA_UID}" -g "${CONDA_GID}" --system -d /home/conda -m  -s /bin/bash conda && \
    chown -R conda:conda /opt && \
    export PYTHON_SITE_PACKAGES=$(python3 -c "from sysconfig import get_paths; print(get_paths()['purelib'])") && \
    echo "export ISCE_HOME=${PYTHON_SITE_PACKAGES}/isce" >> /home/conda/.bashrc && \
    echo "export ISCE_STACK=${PYTHON_SITE_PACKAGES}/share/isce2" >> /home/conda/.bashrc && \
    echo "export PATH=${PATH}:${PYTHON_SITE_PACKAGES}/isce/bin:${PYTHON_SITE_PACKAGES}/isce/applications" >> /home/conda/.bashrc

USER ${CONDA_UID}
SHELL ["/bin/bash", "-l", "-c"]
WORKDIR /home/conda/

ENTRYPOINT ["/usr/local/bin/hyp3_autorift"]
CMD ["-v"]