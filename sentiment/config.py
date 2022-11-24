from os import environ as env


DB_URL=env.get("DB_URL", "mysql+pymysql://sentiment:sentiment@localhost/sentiment")
REDIS=env.get("REDIS", "redis://localhost:6379")
CELERY_BROKER_URL=env.get("CELERY_BROKER_URL", REDIS + '/0')
CELERY_RESULT_BACKEND="rpc://"
REDIS_CACHE=REDIS + '/1'
FINVIZ_URL='https://finviz.com'
LOG_PATH=env.get("LOG_PATH", "./data/log")
CRON_HOUR=env.get("CRON_HOUR", "*/5")
USER_AGENT_LIST = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36 Edge/16.16299'
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.1.1 Safari/605.1.15',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36'
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:77.0) Gecko/20100101 Firefox/77.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:77.0) Gecko/20100101 Firefox/77.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.97 Safari/537.36',   
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/51.0.2704.79 Safari/537.36 Edge/14.14393'
]
DEFAULT_USER_AGENT=USER_AGENT_LIST[0]

THROTTLE_WEAK=env.get("THROTTLE_WEAK", '1/s')
THROTTLE_STRONG=env.get("THROTTLE_STRONG", '12/h')
# only for testing
LIMIT_SCRAPING=int(env.get("LIMIT_SCRAPING")) if env.get("LIMIT_SCRAPING") else None 