from celery import Celery
from celery.schedules import crontab
from sentiment import config
from sentiment.util.celery_util import throttle_task, clear_queue

app = Celery('sentiment', broker=config.CELERY_BROKER_URL, backend=config.CELERY_RESULT_BACKEND)
app.autodiscover_tasks(["sentiment.tasks.scrape_tasks",])
# app.send_task("sentiment.tasks.scrape_tasks.scrape_stocks", queue="scrape")
# app.send_task("sentiment.tasks.scrape_tasks.test", queue="scrape")

clear_queue("sentiment")
clear_queue("scrape")
app.conf.timezone = 'Europe/Berlin'
app.conf.accept_content = ['application/json', 'application/x-python-serialize', 'pickle']
app.conf.beat_schedule = {
    'scrape': {
        'task': 'sentiment.tasks.scrape_tasks.scrape_stocks',
        'options': {'queue': 'scrape'},
        'schedule': crontab(minute=0, hour=config.CRON_HOUR)
    },

}

