FROM continuumio/miniconda3:4.7.12-alpine

ENV PATH=/opt/conda/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

USER 0
RUN apk add --no-cache bash && \
    rm /home/anaconda/.profile && \
    echo ". /opt/conda/etc/profile.d/conda.sh" >> /home/anaconda/.profile && \
    chown anaconda:anaconda /home/anaconda/.profile

USER 10151
SHELL ["bash", "-l", "-c"]
ENV PYTHONDONTWRITEBYTECODE=true
WORKDIR /home/anaconda/autoRIFT

RUN conda create -y -n autoRIFT python=3 && \
    conda clean -afy && \
    echo "conda activate autoRIFT" >> /home/anaconda/.profile

# Won't need this bit once this is actually a package...
COPY --chown=anaconda:anaconda setup.py MANIFEST.in LICENSE README.md ./
COPY --chown=anaconda:anaconda hyp3_autorift/ hyp3_autorift/
RUN pip install .
RUN ls -la

ENTRYPOINT ["conda", "run", "-n", "autoRIFT", "hyp3_autorift"]
CMD ["-v"]