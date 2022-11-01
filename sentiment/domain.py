from sqlalchemy.orm import declarative_base, joinedload, subqueryload
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Text 
from sqlalchemy import DateTime, Date
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship

Base = declarative_base()
LEN_STR_SHORT = 255
LEN_STR_LONG = 512


class Log(Base):
    __tablename__ = "log"
    id = Column(Integer, primary_key = True, autoincrement = True)
    start = Column(DateTime)
    end = Column(DateTime)
    status = Column(String(10))

class Stock(Base):
    __tablename__ = "stock"
    symbol = Column(String(50), primary_key=True)
    ticker = relationship("Ticker", back_populates="stock", cascade="all, delete-orphan")    
    recommendations = relationship("FinancialData", back_populates="stock", cascade="all, delete-orphan")    

    industry = Column(String(LEN_STR_SHORT))
    shortName = Column(String(LEN_STR_SHORT))
    longName = Column(String(LEN_STR_LONG))
    
class FinancialData(Base):
    __tablename__ = "fin_data"

    id = Column(Integer, primary_key = True, autoincrement = True)
    stock_id = Column(String(50), ForeignKey("stock.symbol"), nullable=False)
    stock = relationship("Stock", back_populates="recommendations")
    datetime = Column(DateTime)
    recommendationMean = Column(Float)
    targetMeanPrice = Column(Float)
    currentPrice = Column(Float)
    
    targetHighPrice = Column(Float)
    targetLowPrice = Column(Float)
    targetMedianPrice = Column(Float)
    recommendationKey = Column(String(50))
    revenuePerShare = Column(Float)
    returnOnAssets = Column(Float)
    returnOnEquity = Column(Float)
    grossProfits = Column(Float)
    freeCashflow = Column(Float)
    operatingCashflow = Column(Float)
    earningsGrowth = Column(Float)
    revenueGrowth = Column(Float)
    grossMargins = Column(Float)
    ebitdaMargins = Column(Float)
    operatingMargins = Column(Float)
    profitMargins = Column(Float)    
    numberOfAnalystOpinions = Column(Integer)
    totalCash = Column(Float)    
    totalCashPerShare = Column(Float)    
    ebitda = Column(Float)
    totalDebt = Column(Float)
    quickRatio = Column(Float)
    currentRatio = Column(Float)
    totalRevenue = Column(Float)
    debtToEquity = Column(Float)    
    
    def to_dict(self):
        return {
            'symbol': self.stock.symbol,
            'shortName': self.stock.shortName,
            'industry': self.stock.industry,
            'datetime': self.datetime,
            'recommendationMean': self.recommendationMean,
            'targetMeanPrice': self.targetMeanPrice,
            'currentPrice': self.currentPrice,
            'targetHighPrice': self.targetHighPrice,
            'targetLowPrice': self.targetLowPrice,
            'targetMedianPrice': self.targetMedianPrice,
            'recommendationKey': self.recommendationKey,
            'revenuePerShare': self.revenuePerShare,
            'returnOnAssets': self.returnOnAssets,
            'returnOnEquity': self.returnOnEquity,
            'grossProfits': self.grossProfits,
            'freeCashflow': self.freeCashflow,
            'operatingCashflow': self.operatingCashflow,
            'earningsGrowth': self.earningsGrowth,
            'revenueGrowth': self.revenueGrowth,
            'grossMargins': self.grossMargins,
            'ebitdaMargins': self.ebitdaMargins,
            'operatingMargins': self.operatingMargins,
            'profitMargins': self.profitMargins,
            'numberOfAnalystOpinions': self.numberOfAnalystOpinions,
            'totalCash': self.totalCash,
            'totalCashPerShare': self.totalCashPerShare,
            'ebitda': self.ebitda,
            'totalDebt': self.totalDebt,
            'quickRatio': self.quickRatio,
            'currentRatio': self.currentRatio,
            'totalRevenue': self.totalRevenue,
            'quickRatio': self.quickRatio,
            'debtToEquity': self.debtToEquity
            
        }

class Ticker(Base):
    __tablename__ = "ticker"
    id = Column(Integer, primary_key = True, autoincrement = True)

    
    date = Column(String(20))
    time = Column(String(20))
    datetime = Column(DateTime)
    headline = Column(String(LEN_STR_LONG), nullable=False)
    link = Column(String(LEN_STR_LONG), nullable=False)
    source = Column(String(LEN_STR_SHORT), nullable=False)
    text = Column(Text)
    stock_id = Column(String(50), ForeignKey("stock.symbol"), nullable=False)
    stock = relationship("Stock", back_populates="ticker")
    sentiment = Column(String(20), nullable=False)
    score = Column(Float, nullable=False)
    link_hash = Column(String(128), unique=True, nullable=False)

    def to_dict(self):
        return {
            'symbol': self.stock.symbol,
            'headline': self.headline,
            'source': self.source,
            'link': self.link,
            'datetime': self.datetime,
            'sentiment': self.sentiment,
            'score': self.score,
            'date': self.date,
            'time': self.time,
            'industry': self.stock.industry,
            'shortName': self.stock.shortName
        }
    def __repr__(self):
        return f"Ticker({self.date}, {self.headline})"