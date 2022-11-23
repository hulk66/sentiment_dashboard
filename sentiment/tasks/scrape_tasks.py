from logging.handlers import RotatingFileHandler

from pymysql import IntegrityError
from sentiment.celery_app import app
import logging
from urllib.request import urlopen, Request
from urllib.error import HTTPError
import requests

from sentiment.domain import Base, Stock, FinancialData, Log, Ticker
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import date, datetime
from transformers import pipeline, BertForSequenceClassification, BertTokenizer
import yfinance as yf
from  sentiment import config
import logging
import hashlib
from bs4 import BeautifulSoup
from celery.signals import after_setup_logger, worker_process_init, worker_process_shutdown
from sentiment.util.celery_util import throttle_task
import random


logger = logging.getLogger(__name__)
sentiment_pipeline = None 
session = None
# make sure the DB structure is created first
Base.metadata.create_all(create_engine(config.DB_URL), checkfirst=True)


@worker_process_init.connect
def init_worker(**kwargs):
    global session, sentiment_pipeline
    logger.info("Connecting to Database %s", config.DB_URL)
    engine = create_engine(config.DB_URL)
    Base.metadata.create_all(engine, checkfirst=True)
    session = Session(engine)
    logger.info("Loading sentiment pipeline ...")
    tokenizer = BertTokenizer.from_pretrained("./finbert")
    finbert = BertForSequenceClassification.from_pretrained("./finbert")
    sentiment_pipeline = pipeline("sentiment-analysis", model=finbert, tokenizer=tokenizer)
    logger.info("... done")
    # sentiment_pipeline = pipeline("sentiment-analysis", model="ProsusAI/finbert")

@worker_process_shutdown.connect
def stop_worker(**kwargs):
    global session
    logger.info("Disconnecting Database %s", config.DB_URL)
    session.close()

@after_setup_logger.connect
def setup_loggers(*args, **kwargs):
    logger = logging.getLogger()
    logging.getLogger("celery").setLevel(logging.WARN)
    logger.handlers.clear()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # StreamHandler
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    logger.addHandler(sh)

    fh = RotatingFileHandler(config.LOG_PATH + "/scrape.log", maxBytes=10**7, backupCount=5)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

def rand_user_agent():
    return random.choice(config.USER_AGENT_LIST)

def scrape_finwiz_news(ticker):
    url = config.FINVIZ_URL + '/quote.ashx?t=' + ticker
    req = Request(url=url,headers={'User-Agent': config.DEFAULT_USER_AGENT}) 
    response = urlopen(req)    
    # Read the contents of the file into 'html'
    html = BeautifulSoup(response, features="lxml")
    # Find 'news-table' in the Soup and load it into 'news_table'
    news_table = html.find(id='news-table')
    return news_table

dummy_res = [
    "Bad news negativ trend",
    "positive trend going up good",
    "neutral no new news same as before"
]
def scrape_by_class_test(link, element, clazz):
    return random.choice(dummy_res)

def scrape_by_class(link, element, clazz):
    logger.debug("Scraping %s", link)
    req = Request(url=link, headers={'User-Agent': rand_user_agent()}) 
    response = urlopen(req)      
    html = BeautifulSoup(response, features="lxml")
    news_detail = html.findAll(element, {"class" : clazz})
    result = ""
    for e in news_detail:
        result += e.text
    return " ".join(result.split())

@app.task
def set_sentiment(ticker_id):
    logger.debug("Set Sentiment for %i", ticker_id)
    ticker = session.query(Ticker).get(ticker_id)
    if ticker is not None:
        if ticker.text is not None:
            sentiment = sentiment_pipeline(ticker.text[:512])
        else:
            sentiment = sentiment_pipeline(ticker.headline)
        ticker.sentiment = sentiment[0]['label']
        ticker.score = sentiment[0]['score']
        logger.info("Ticker score for %i is %s with %f", ticker.id, ticker.sentiment, ticker.score)
        session.commit()
    else:
        logger.warning("Sentiment Analysis failed, Ticker %i not found", ticker_id)


def scrape_div_class(ticker_id, link, clazz):
    logger.info("Scraping Ticker %i, Div %s in %s ...", ticker_id, clazz, link)
    ticker = session.query(Ticker).filter(Ticker.id == ticker_id, Ticker.scrape_result == None).one_or_none()
    if ticker is not None:
        try:
            ticker.text = scrape_by_class(link, "div", clazz)
            if not ticker.text:
                ticker.scrape_result = "CAPTCHA_PAYWALL"
                ticker.text = None
            else: 
                ticker.scrape_result = "OK"
            logger.debug("... done")
        except HTTPError as exc:
            logger.warning("Scraping Error for %s", link)
            logger.warning(exc)
            ticker.scrape_result = "HTTP_" + str(exc.code)
        session.commit()
        set_sentiment.apply_async(queue="sentiment", args=[ticker_id,])
    else:
        logger.error("Either Ticker with id %i was not found or has been scrapes already", ticker_id)

@app.task(bind=True)
@throttle_task("6/m")
def test_rate6m(self, i):
    logger.info("Test 6m Rate %i", i)


@app.task(bind=True)
@throttle_task("3/m")
def test_rate1m(self, i):
    logger.info("Test 1m Rate %i", i)

@app.task()
def test():
    logger.info("Start test")
    for i in range(20):
        app.send_task("sentiment.tasks.scrape_tasks.test_rate6m", args=(i,))
        app.send_task("sentiment.tasks.scrape_tasks.test_rate1m", args=(i,))


@app.task(bind=True)
@throttle_task(config.THROTTLE_WEAK)
def scrape_yahoo(self, ticker_id, link):
    scrape_div_class(ticker_id, link, "caas-body")

@app.task(bind=True)
@throttle_task(config.THROTTLE_STRONG)
def scrape_wsj_livecoverage(self, ticker_id, link):
    scrape_div_class(ticker_id, link, "WSJTheme-module--text--37ld_QSx")

@app.task(bind=True)
@throttle_task(config.THROTTLE_STRONG)
def scrape_wsj_article(self, ticker_id, link):
    scrape_div_class(ticker_id, link, "article-content")

@app.task(bind=True)
@throttle_task(config.THROTTLE_STRONG)
def scrape_investors(self, ticker_id, link):
    scrape_div_class(ticker_id, link, "single-post-content")

@app.task(bind=True)
@throttle_task(config.THROTTLE_STRONG)
def scrape_bizjournals(self, ticker_id, link):
    scrape_div_class(ticker_id, link, "content")

@app.task(bind=True)
@throttle_task(config.THROTTLE_STRONG)
def scrape_barrons(self, ticker_id, link):
    scrape_div_class(ticker_id, link, "article__body")

@app.task(bind=True)
@throttle_task(config.THROTTLE_STRONG)
def scrape_fool(self, ticker_id, link):
    scrape_div_class(ticker_id, link, "shadow-card")

@app.task(bind=True)
@throttle_task(config.THROTTLE_STRONG)
def scrape_ft(self, ticker_id, link):
    scrape_div_class(ticker_id, link, "n-content-body")


@app.task(bind=True)
@throttle_task(config.THROTTLE_STRONG)
def scrape_the_street(self, ticker_id, link):
    scrape_div_class(ticker_id, link, "l-grid--content-body")


@app.task(bind=True)
@throttle_task(config.THROTTLE_STRONG)
def scrape_investopedia(self, ticker_id, link):
    scrape_div_class(ticker_id, link, "article-body")


@app.task(bind=True)
@throttle_task(config.THROTTLE_STRONG)
def scrape_marketwatch_picks(self, ticker_id, link):
    scrape_div_class(ticker_id, link, "paywall")


def scrape_detail(ticker_id, link):
    if link.startswith("https://finance.yahoo.com/news") or link.startswith("https://finance.yahoo.com/video"):
        scrape_yahoo.apply_async(queue="scrape", args=[ticker_id, link])
    elif link.startswith("https://www.wsj.com/articles"):
        scrape_wsj_article.apply_async(queue="scrape", args=[ticker_id, link])
    elif link.startswith("https://www.wsj.com/livecoverage"):
        scrape_wsj_livecoverage.apply_async(queue="scrape", args=[ticker_id, link])
    elif link.startswith("https://www.investors.com"):
        scrape_investors.apply_async(queue="scrape", args=[ticker_id, link])
    elif link.startswith("https://www.bizjournals.com"):
        scrape_bizjournals.apply_async(queue="scrape", args=[ticker_id, link])
    elif link.startswith("https://www.barrons.com/articles") or link.startswith("https://www.marketwatch.com/story") or link.startswith("https://aap.thestreet.com/story"): 
        scrape_barrons.apply_async(queue="scrape", args=[ticker_id, link])
    elif link.startswith("https://www.fool.com/"):
        scrape_fool.apply_async(queue="scrape", args=[ticker_id, link])
    elif link.startswith("https://www.ft.com/"):
        scrape_ft.apply_async(queue="scrape", args=[ticker_id, link])
    elif link.startswith("https://www.thestreet.com/markets"):
        scrape_the_street.apply_async(queue="scrape", args=[ticker_id, link])
    elif link.startswith("https://www.investopedia.com/articles"):
        scrape_investopedia.apply_async(queue="scrape", args=[ticker_id, link])
    elif link.startswith("https://www.marketwatch.com/picks"):
        scrape_marketwatch_picks.apply_async(queue="scrape", args=[ticker_id, link])


DOMAINS = [
    "https://finance.yahoo.com/news",
    "https://finance.yahoo.com/video",
    "https://www.wsj.com/articles",
    "https://www.wsj.com/livecoverage",
    "https://www.investors.com",
    "https://www.bizjournals.com",
    "https://www.barrons.com/articles",
    "https://www.marketwatch.com/story",
    "https://aap.thestreet.com/story",
    "https://www.fool.com/",
    "https://www.ft.com/",
    "https://www.investopedia.com/articles",
    "https://www.marketwatch.com/picks"
]

def create_ticker_entry(stock, row, last_date = None):
    link = row.a['href'].strip()
    date_scrape = row.td.text.strip().split()
    date = None
    if len(date_scrape) == 1:
        date = last_date
        time = date_scrape[0]
    else:
        date = date_scrape[0]
        time = date_scrape[1]

    # check if we can scrape this
    go_on = False
    for l in DOMAINS:
        if link.startswith(l):
            go_on = True
            break

    if not go_on:
        logger.debug("Unknown Ticker link or Paywall")
        return date

    logger.debug("Create Ticker Entry for %s", link)
    hash = hashlib.md5(link.encode()).hexdigest()
    ticker = session.query(Ticker).filter(Ticker.link_hash == hash).one_or_none()
    if ticker is None:
        ticker = Ticker()
        ticker.stock = stock
        ticker.link = link
        ticker.link_hash = hash
        ticker.headline = row.a.text
        ticker.date = date
        ticker.time = time
        ticker.datetime = datetime.strptime(ticker.date + ' ' + ticker.time, "%b-%d-%y %I:%M%p")
        ticker.source = row.span.text.strip()
        session.commit()
        scrape_detail(ticker.id, link)
        return ticker.date
    else:
        logger.info("Ticker already exists %i", ticker.id)
        return last_date


def get_raw_value(fin_data, key):
    return fin_data[key]['raw'] if 'raw' in fin_data[key] else None

def date_as_datetime(d: date) -> datetime:
    return datetime(d.year, d.month, d.day)


def get_financial_data_test(stock):
    pass

def get_financial_data(stock):
    
    # do this only if we don't already have the recommmendations for this today
    today = date.today()
    dt = datetime(today.year, today.month, today.day)
    fdata = session.query(FinancialData).filter(FinancialData.datetime == dt, FinancialData.stock == stock).one_or_none()
    if not fdata:
        logger.info("Get Financial Data for %s", stock.shortName)
        module = "financialData"
        # recommendationTrend also possible
        url = f'https://query1.finance.yahoo.com/v10/finance/quoteSummary/{stock.symbol}?modules={module}'
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0'}) 
        if r.json()['quoteSummary']['result']:
            result = r.json()['quoteSummary']['result'][0]
            fin_data = result['financialData']
            fdata = FinancialData()
            fdata.stock = stock
            fdata.datetime = date.today()
            fdata.recommendationMean = get_raw_value(fin_data, 'recommendationMean')
            fdata.targetMeanPrice = get_raw_value(fin_data, 'targetMeanPrice')
            fdata.currentPrice = get_raw_value(fin_data, 'currentPrice')
            fdata.targetHighPrice = get_raw_value(fin_data, 'targetHighPrice')
            fdata.targetLowPrice = get_raw_value(fin_data, 'targetLowPrice')
            fdata.targetMedianPrice = get_raw_value(fin_data, 'targetMedianPrice')
            fdata.recommendationKey = fin_data['recommendationKey'] if 'recommendationKey' in fin_data else None
            fdata.revenuePerShare = get_raw_value(fin_data, 'revenuePerShare')
            fdata.returnOnAssets = get_raw_value(fin_data, 'returnOnAssets')
            fdata.returnOnEquity = get_raw_value(fin_data, 'returnOnEquity')
            fdata.grossProfits = get_raw_value(fin_data, 'grossProfits')
            fdata.freeCashflow = get_raw_value(fin_data, 'freeCashflow')
            fdata.operatingCashflow = get_raw_value(fin_data, 'operatingCashflow')
            fdata.earningsGrowth = get_raw_value(fin_data, 'earningsGrowth')
            fdata.revenueGrowth = get_raw_value(fin_data, 'revenueGrowth')
            fdata.grossMargins = get_raw_value(fin_data, 'grossMargins')
            fdata.ebitdaMargins = get_raw_value(fin_data, 'ebitdaMargins')
            fdata.operatingMargins = get_raw_value(fin_data, 'operatingMargins')
            fdata.profitMargins = get_raw_value(fin_data, 'profitMargins')
            fdata.numberOfAnalystOpinions = get_raw_value(fin_data, 'numberOfAnalystOpinions')
            fdata.totalCash = get_raw_value(fin_data, 'totalCash')
            fdata.totalCashPerShare = get_raw_value(fin_data, 'totalCashPerShare')
            fdata.ebitda = get_raw_value(fin_data, 'ebitda')
            fdata.totalDebt = get_raw_value(fin_data, 'totalDebt')
            fdata.quickRatio = get_raw_value(fin_data, 'quickRatio')
            fdata.currentRatio = get_raw_value(fin_data, 'currentRatio')
            fdata.totalRevenue = get_raw_value(fin_data, 'totalRevenue')
            fdata.quickRatio = get_raw_value(fin_data, 'quickRatio')
            fdata.debtToEquity = get_raw_value(fin_data, 'debtToEquity')

    return fdata

@app.task
def parse_finwiz_news(symbol):
    try:
        news = scrape_finwiz_news(symbol)
        if news:
            stock = session.query(Stock).get(symbol)
            if stock is None:
                try:
                    stock = Stock()
                    stock.symbol = symbol
                    stock_data = yf.Ticker(symbol)
                    stock.longName = stock_data.info['longName'][:512] if 'longName' in stock_data.info else None
                    stock.shortName = stock_data.info['shortName'][:255] if 'shortName' in stock_data.info else None
                    stock.industry = stock_data.info['industry'][:255] if 'industry' in stock_data.info else None
                    session.add(stock)
                    session.commit()
                except IntegrityError:
                    # due to parallel execution this might happen but is ok
                    logger.warn("Overlap in creation of new Stock")
                    stock = session.query(Stock).get(symbol)
            rows = news.findAll('tr')
            last_date = None
            for row in rows[:config.LIMIT_SCRAPING]:
                last_date = create_ticker_entry(stock, row, last_date)
            get_financial_data(stock)
            session.commit()
    except HTTPError:
        logger.warning("Scraping Error")

def get_gainers_loosers(html, id):
    tickers = html.find(id=id)
    return [ticker.text for ticker in tickers.find_all("a", class_="tab-link")]

def get_top_gainers(html = None):
    return get_gainers_loosers(html, "signals_1")

def get_top_loosers(html = None):
    return get_gainers_loosers(html, "signals_2")

def get_major_news(html = None):
    if not html:
        url = 'https://finviz.com'
        req = Request(url=url,headers={'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0'}) 
        response = urlopen(req)    
        # Read the contents of the file into 'html'
        html = BeautifulSoup(response)
    major_news_table  = html.find(id="major-news").parent
    return [ticker.text for ticker in major_news_table.find_all("a", class_="tab-link-nw")]


def get_finviz_html():
    url = 'https://finviz.com'
    req = Request(url=url,headers={'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0'}) 
    response = urlopen(req)    
    # Read the contents of the file into 'html'
    html = BeautifulSoup(response, features="lxml")
    return html

def amend_stock_data():
    known_stocks = session.scalars(select(Stock))
    for stock in known_stocks:
        stock_data = yf.Ticker(stock.symbol)
        stock.longName = stock_data.info['longName'] if 'longName' in stock_data.info else None
        stock.shortName = stock_data.info['shortName'] if 'shortName' in stock_data.info else None
        stock.industry = stock_data.info['industry'] if 'industry' in stock_data.info else None
    session.commit()    

def re_scrape():
    logger.debug("Rescraping empty tickers", )
    empty_ticker_text = session.query(Ticker).filter(Ticker.text == None)
    for ticker in empty_ticker_text:
        ticker.text = scrape_detail(ticker.link)
        set_sentiment(ticker)
    session.commit()


@app.task
def scrape_stocks():
    logger.info("Start new Run")
    log = Log()
    log.start = datetime.now()
    log.status = "running"
    session.add(log)
    session.commit()

    finviz_html = get_finviz_html()
    top_gainers = get_top_gainers(finviz_html)
    top_loosers = get_top_loosers(finviz_html)
    major_news = get_major_news(finviz_html)
    known_stocks = session.scalars(select(Stock))
    known_symbols = [stock.symbol for stock in known_stocks]
    tickers = list(set(known_symbols + top_gainers + top_loosers + major_news))
    count = 0
    total = len(tickers)
    for ticker in tickers[:config.LIMIT_SCRAPING]:
        logger.info("%i/%i - Getting News for %s", count, total, ticker)
        parse_finwiz_news.apply_async(queue="scrape", args=[ticker,])
        count += 1


