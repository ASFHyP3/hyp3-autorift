FROM ghcr.io/prefix-dev/pixi:latest

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

RUN apt-get update && apt-get install -y --no-install-recommends git g++ unzip vim patch wget ca-certificates && \
    apt-get clean && rm -rf /var/lib/apt/lists/*


USER 1000
SHELL ["/bin/bash", "-l", "-c"]

COPY --chown=1000:1000 . /hyp3-autorift/

WORKDIR /hyp3-autorift/

RUN pixi install --locked && \
    pixi shell-hook -s bash >> /home/ubuntu/.profile && \
    pixi run install-editable

WORKDIR /home/ubuntu/

ENTRYPOINT ["/hyp3-autorift/src/hyp3_autorift/etc/entrypoint.sh"]
CMD ["-h"]
