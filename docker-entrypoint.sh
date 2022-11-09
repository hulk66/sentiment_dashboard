#!/bin/bash
set -e
# conda activate sentiment_dashboard
if [ $APP = 'board' ]
  then
      ./wait
      streamlit run run.py
elif [ $APP = 'scrape' ]
  then 
      ./wait
      # alembic upgrade head
      celery -A sentiment.celery_app worker -Q scrape,sentiment --$WORKER_CONCURRENCY --loglevel=INFO
elif [ $APP = 'beat' ]
  then 
      ./wait
      celery -A sentiment.celery_app beat 
fi
