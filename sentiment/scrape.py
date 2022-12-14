from urllib.request import urlopen, Request
from urllib.error import HTTPError
from bs4 import BeautifulSoup
from datetime import datetime, date
 
import requests
# from sqlalchemy.orm import declarative_base, joinedload, subqueryload
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy import select

from transformers import pipeline
import yfinance as yf
from domain import Base, FinancialData, Ticker, Stock, Log

import logging
import hashlib

def scrape_finwiz_news(ticker):
    finwiz_url = 'https://finviz.com/quote.ashx?t='
    url = finwiz_url + ticker
    req = Request(url=url,headers={'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0'}) 
    response = urlopen(req)    
    # Read the contents of the file into 'html'
    html = BeautifulSoup(response, features="lxml")
    # Find 'news-table' in the Soup and load it into 'news_table'
    news_table = html.find(id='news-table')
    return news_table

def scrape_by_class(link, element, clazz):
    logging.debug("Scraping %s", link)
    req = Request(url=link, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:20.0) Gecko/20100101 Firefox/20.0'}) 
    response = urlopen(req)      
    html = BeautifulSoup(response, features="lxml")
    news_detail = html.findAll(element, {"class" : clazz})
    result = ""
    for e in news_detail:
        result += e.text
    return " ".join(result.split())

def scrape_detail(link):
    try:
        if link.startswith("https://finance.yahoo.com/news"):
            return scrape_by_class(link, "div", "caas-body")
        elif link.startswith("https://www.wsj.com/articles"):
            return scrape_by_class(link, "div", "article-content")
        elif link.startswith("https://www.wsj.com/livecoverage"):
            return scrape_by_class(link, "div", "WSJTheme-module--text--37ld_QSx")
        elif link.startswith("https://www.investors.com"):
            return scrape_by_class(link, "div", "single-post-content")
        elif link.startswith("https://www.bizjournals.com"):
            return scrape_by_class(link, "div", "content")
        elif link.startswith("https://www.barrons.com/articles") or link.startswith("https://www.marketwatch.com/story") or link.startswith("https://aap.thestreet.com/story"): 
            return scrape_by_class(link, "div", "article__body")   
        elif link.startswith("https://www.fool.com/"):
            return scrape_by_class(link, "div", "shadow-card")  
        elif link.startswith("https://www.ft.com/"):
            return scrape_by_class(link, "div", "n-content-body")  

    except HTTPError:
        logging.warning("Scraping Error for %s", link)
    return None

def set_sentiment(ticker):
    if ticker.text is not None:
        sentiment = sentiment_pipeline(ticker.text[:512])
    else:
        sentiment = sentiment_pipeline(ticker.headline)
    ticker.sentiment = sentiment[0]['label']
    ticker.score = sentiment[0]['score']
    
def create_ticker_entry(row, last_date = None):
    link = row.a['href'].strip()
    hash = hashlib.md5(link.encode()).hexdigest()
    ticker = session.query(Ticker).filter(Ticker.link_hash == hash).one_or_none()
    if ticker is None:
        ticker = Ticker()
        ticker.link = link
        ticker.link_hash = hash
        date_scrape = row.td.text.strip().split()
        ticker.date = last_date
        if len(date_scrape) == 1:
            ticker.time = date_scrape[0]
        else:
            ticker.date = date_scrape[0]
            ticker.time = date_scrape[1]
        ticker.datetime = datetime.strptime(ticker.date + ' ' + ticker.time, "%b-%d-%y %I:%M%p")
        ticker.headline = row.a.text
        ticker.source = row.span.text.strip()
        ticker.text = scrape_detail(link)
        set_sentiment(ticker)
    return ticker


def get_raw_value(fin_data, key):
    return fin_data[key]['raw'] if 'raw' in fin_data[key] else None

def date_as_datetime(d: date) -> datetime:
    return datetime(d.year, d.month, d.day)

def create_recommendation(stock):
    
    # do this only if we don't already have the recommmendations for this today
    today = date.today()
    dt = datetime(today.year, today.month, today.day)
    fdata = session.query(FinancialData).filter(FinancialData.datetime == dt, FinancialData.stock == stock).one_or_none()
    if not fdata:
        logging.info("Get Recommendation for %s", stock.shortName)
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

def parse_finwiz_news(symbol):
    try:
        news = scrape_finwiz_news(symbol)
        if news:
            stmt = select(Stock).where(Stock.symbol == symbol)
            stock = session.scalars(stmt).one_or_none()        
            if stock is None:
                stock = Stock()
                stock.symbol = symbol
                stock_data = yf.Ticker(symbol)
                stock.longName = stock_data.info['longName'][:512] if 'longName' in stock_data.info else None
                stock.shortName = stock_data.info['shortName'][:255] if 'shortName' in stock_data.info else None
                stock.industry = stock_data.info['industry'][:255] if 'industry' in stock_data.info else None

                session.add(stock)

            rows = news.findAll('tr')
            result = []
            last_date = None
            for row in rows:
                ticker = create_ticker_entry(row, last_date)
                last_date = ticker.date
                ticker.stock = stock

            create_recommendation(stock)
            session.commit()
    except HTTPError:
        logging.warning("Scraping Error")

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
    logging.info("Rescraping empty tickers", )
    empty_ticker_text = session.query(Ticker).filter(Ticker.text == None)
    for ticker in empty_ticker_text:
        ticker.text = scrape_detail(ticker.link)
        set_sentiment(ticker)
    session.commit()

    
def main():
    global session, sentiment_pipeline

    logging.basicConfig(format='%(asctime)s - %(message)s', level=logging.INFO)
    logging.info("Connecting to Database")
    engine = create_engine("mysql+pymysql://sentiment:sentiment@qn/sentiment")
    Base.metadata.create_all(engine, checkfirst=True)
    session = Session(engine)
    log = Log()
    log.start = datetime.now()
    log.status = "running"
    session.add(log)
    session.commit()

    logging.info("Setting up Sentiment Pipeline")

    sentiment_pipeline = pipeline("sentiment-analysis", model="ProsusAI/finbert")

    logging.info("Getting News from Finviz")
    finviz_html = get_finviz_html()
    top_gainers = get_top_gainers(finviz_html)
    top_loosers = get_top_loosers(finviz_html)
    major_news = get_major_news(finviz_html)
    known_stocks = session.scalars(select(Stock))
    known_symbols = [stock.symbol for stock in known_stocks]
    tickers = list(set(known_symbols + top_gainers + top_loosers + major_news))
    count = 0
    total = len(tickers)
    for ticker in tickers[:2]:
        logging.info("%i/%i - Getting News for %s", count, total, ticker)
        parse_finwiz_news(ticker)
        count += 1

    # re_scrape()
    log.end = datetime.now()
    log.status = "done"
    session.commit()
    session.close()
    logging.info("----- done ------")


if __name__ == "__main__":
    main()