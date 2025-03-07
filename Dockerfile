FROM condaforge/mambaforge:latest

# For opencontainers label definitions, see:
#    https://github.com/opencontainers/image-spec/blob/master/annotations.md
LABEL org.opencontainers.image.title="HyP3 autoRIFT ISCE"
LABEL org.opencontainers.image.description="A HyP3 plugin for feature tracking processing with AutoRIFT-ISCE"
LABEL org.opencontainers.image.vendor="Alaska Satellite Facility"
LABEL org.opencontainers.image.authors="ASF APD/Tools Team <uaf-asf-apd@alaska.edu>"
LABEL org.opencontainers.image.licenses="BSD-3-Clause"
LABEL org.opencontainers.image.url="https://github.com/ASFHyP3/hyp3-autorift"
LABEL org.opencontainers.image.source="https://github.com/ASFHyP3/hyp3-autorift"
LABEL org.opencontainers.image.documentation="https://hyp3-docs.asf.alaska.edu"

# Dynamic lables to define at build time via `docker build --label`
# LABEL org.opencontainers.image.created=""
# LABEL org.opencontainers.image.version=""
# LABEL org.opencontainers.image.revision=""

ARG DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=true

RUN apt-get update && apt-get install -y --no-install-recommends libgl1-mesa-glx unzip vim patch wget && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

ARG CONDA_UID=1000
ARG CONDA_GID=1000

RUN groupadd -g "${CONDA_GID}" --system conda && \
    useradd -l -u "${CONDA_UID}" -g "${CONDA_GID}" --system -d /home/conda -m  -s /bin/bash conda && \
    chown -R conda:conda /opt && \
    echo ". /opt/conda/etc/profile.d/conda.sh" >> /home/conda/.profile && \
    echo "conda activate base" >> /home/conda/.profile

USER ${CONDA_UID}
SHELL ["/bin/bash", "-l", "-c"]
WORKDIR /home/conda/

COPY --chown=${CONDA_UID}:${CONDA_GID} . /hyp3-autorift/

RUN mamba env create -f /hyp3-autorift/environment.yml && \
    conda clean -afy && \
    conda activate hyp3-autorift && \
    sed -i 's/conda activate base/conda activate hyp3-autorift/g' /home/conda/.profile && \
    python -m pip install --no-cache-dir /hyp3-autorift

RUN export PYTHON_SITE_PACKAGES=$(python -c "from sysconfig import get_paths; print(get_paths()['purelib'])") && \
    patch -d ${PYTHON_SITE_PACKAGES}/autoRIFT < /hyp3-autorift/src/hyp3_autorift/vend/CHANGES-UPSTREAM-79.diff && \
    patch -d ${PYTHON_SITE_PACKAGES}/isce/components/contrib/geo_autoRIFT/autoRIFT < /hyp3-autorift/src/hyp3_autorift/vend/CHANGES-UPSTREAM-79.diff && \
    patch -d ${PYTHON_SITE_PACKAGES}/autoRIFT < /hyp3-autorift/src/hyp3_autorift/vend/CHANGES-UPSTREAM-107.diff && \
    patch -d ${PYTHON_SITE_PACKAGES}/isce/components/contrib/geo_autoRIFT/autoRIFT < /hyp3-autorift/src/hyp3_autorift/vend/CHANGES-UPSTREAM-107.diff

ENTRYPOINT ["/hyp3-autorift/src/hyp3_autorift/etc/entrypoint.sh"]
CMD ["-h"]
