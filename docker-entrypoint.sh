#!/bin/bash
set -e
# conda activate sentiment_dashboard
if [ $APP = 'board' ]
  then
      streamlit run run.py
elif [ $APP = 'scrape' ]
  then 
      # alembic upgrade head
      celery -A sentiment.celery_app purge -f -Q scrape,sentiment
      celery -A sentiment.celery_app worker -B -Q scrape,sentiment --$WORKER_CONCURRENCY --loglevel INFO -s /tmp/celery-beat
elif [ $APP = 'beat' ]
  then 
      celery -A sentiment.celery_app beat --loglevel DEBUG -s /tmp/celery-beat
fi
