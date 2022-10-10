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

class Stock(Base):
    __tablename__ = "stock"
    symbol = Column(String(50), primary_key=True)
    ticker = relationship("Ticker", back_populates="stock", cascade="all, delete-orphan")    
    recommendations = relationship("Recommendation", back_populates="stock", cascade="all, delete-orphan")    

    industry = Column(String(50))
    shortName = Column(String(50))
    longName = Column(String(100))
    
class Recommendation(Base):
    __tablename__ = "recommendation"

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

    
    date = Column(String(20))
    time = Column(String(20))
    datetime = Column(DateTime)
    headline = Column(String(512))
    link = Column(String(512), primary_key=True)
    source = Column(String(100))
    text = Column(Text)
    stock_id = Column(String(50), ForeignKey("stock.symbol"), nullable=False)
    stock = relationship("Stock", back_populates="ticker")
    sentiment = Column(String(20))
    score = Column(Float)

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