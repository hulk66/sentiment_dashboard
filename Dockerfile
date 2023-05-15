# FROM continuumio/miniconda3
FROM mambaorg/micromamba
WORKDIR /app
USER $MAMBA_USER
#USER $CONDA_USER

# Create the environment:
COPY environment.yml .
# RUN conda env create -f environment.yml
RUN  micromamba create -f environment.yml && micromamba clean --all --yes

COPY finbert finbert
COPY sentiment sentiment
COPY run.py .
COPY docker-entrypoint.sh .
COPY alembic alembic
COPY alembic.ini .

# COPY run.py .
# USER root
# ADD https://github.com/ufoscout/docker-compose-wait/releases/download/2.7.3/wait /app/wait
#RUN groupadd -r swuser -g 433 && \
#    useradd -u 431 -r -g swuser -s /sbin/nologin -c "Docker image user" swuser


# RUN chmod +x /app/wait
# RUN chmod a+x docker-entrypoint.sh
# Make RUN commands use the new environment:
ENV PATH /opt/conda/envs/sentiment_dashboard/bin:$PATH
SHELL ["micromamba", "run", "-n", "sentiment_dashboard", "/bin/bash", "-c"]
# cd ARG MAMBA_DOCKERFILE_ACTIVATE=1 

RUN echo "source activate sentiment_dashboard" > ~/.bashrc
ENTRYPOINT ["./docker-entrypoint.sh"]


#ENTRYPOINT ["/usr/local/bin/_entrypoint.sh"]
#CMD streamlit run run.py

