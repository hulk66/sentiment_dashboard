FROM continuumio/miniconda3

WORKDIR /app

# Create the environment:
COPY environment.yml .
RUN conda env create -f environment.yml
COPY sentiment sentiment
COPY finbert finbert
COPY run.py .
COPY docker-entrypoint.sh .
COPY alembic alembic
COPY alembic.ini .

# COPY run.py .
RUN chmod u+x docker-entrypoint.sh
ADD https://github.com/ufoscout/docker-compose-wait/releases/download/2.7.3/wait /app/wait
RUN chmod +x /app/wait
# Make RUN commands use the new environment:
# SHELL ["conda", "run", "-n", "sentiment_dashboard", "/bin/bash", "-c"]

RUN echo "source activate sentiment_dashboard" > ~/.bashrc
ENV PATH /opt/conda/envs/sentiment_dashboard/bin:$PATH
# RUN echo "conda activate sentiment_dashboard" >> ~/.bashrc
# RUN conda activate sentiment_dashboard
# SHELL ["/bin/bash", "--login", "-c"]
# The code to run when container is started:
# ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "sentiment_dashboard", "python", "sentiment/scrape.py"]

#CMD ls -l sentiment
ENTRYPOINT ["./docker-entrypoint.sh"]

#ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "sentiment_dashboard", "celery", \
#    "-A", "sentiment.celery_app", "worker", \
#    "-Q", "scrape_finviz,scrape_yahoo,scrape_investors,scrape_fool,scrape_ft,scrape_fool,scrape_wsj,scrape_bizjournals,scrape_barrons", \
#    "--autoscale=8,0",  "--loglevel=INFO"]