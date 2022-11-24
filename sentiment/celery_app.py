from celery import Celery
from celery.schedules import crontab
from sentiment import config

app = Celery('sentiment', broker=config.CELERY_BROKER_URL, backend=config.CELERY_RESULT_BACKEND)
app.autodiscover_tasks(["sentiment.tasks.scrape_tasks",])
# app.send_task("sentiment.tasks.scrape_tasks.scrape_stocks", queue="scrape")
# app.send_task("sentiment.tasks.scrape_tasks.test", queue="scrape")

app.conf.beat_schedule = {
    'scrape': {
        'task': 'sentiment.tasks.scrape_tasks.scrape_stocks',
        'options': {'queue': 'scrape'},
        'schedule': crontab(hour=config.CRON_HOUR)
    },
    'test': {
        'task': 'sentiment.tasks.scrape_tasks.test',
        'options': {'queue': 'scrape'},
        'schedule': crontab(minute=2)
    },

}

