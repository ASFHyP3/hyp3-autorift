FROM continuumio/miniconda3:4.7.12-alpine

ENV PYTHONDONTWRITEBYTECODE=true
ENV PATH=/opt/conda/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

WORKDIR /home/anaconda/autoRIFT

COPY setup.py MANIFEST.in LICENSE README.md ./
COPY hyp3_autorift/ hyp3_autorift/

RUN pip install .

ENTRYPOINT ["conda", "run", "hyp3_autorift"]