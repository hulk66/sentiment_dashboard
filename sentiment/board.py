from calendar import month
from datetime import datetime, date, timedelta
import streamlit as st
import pandas as pd

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy import select
from domain import Base, FinancialData, Ticker, Stock

engine = create_engine("mysql+pymysql://sentiment:sentiment@qn/sentiment")
# engine = create_engine("sqlite:///ticker.db", echo=False, future=True)
Base.metadata.create_all(engine, checkfirst=True)
session = Session(engine)

st.title = "Tobias' Dashboard"
st.write("""
# Tobias' first fine Dashboard
""")
st.write("""
## Best Recommendations
""")

today = date.today()
dt = datetime(today.year, today.month, today.day)
min_date  = today - timedelta(weeks=6)

max_score = st.slider("Max Recommendation Mean", min_value=1.0, max_value=5.0, value=2.0, step=0.1)
min_analysts = st.slider("Min Number of Analysts", 0, 20, 5)
good_recommendations_today = session.query(FinancialData) \
    .filter(FinancialData.datetime == dt, \
            FinancialData.recommendationMean < max_score, \
            FinancialData.numberOfAnalystOpinions >= min_analysts, \
            FinancialData.targetMeanPrice > FinancialData.currentPrice) \
    .order_by(FinancialData.recommendationMean.asc()) \
    .limit(25)

#    .join(Ticker, Recommendation.stock_id == Ticker.stock_id) \
# Ticker.datetime >= min_date, \
#recommendations = session.query(Recommendation) \
#    .filter(Recommendation.datetime > min_date, Recommendation.recommendationMean < 2)

df_rt = pd.DataFrame.from_records([r.to_dict() for r in good_recommendations_today])
df_rt = df_rt[["symbol", "shortName", "industry", "recommendationMean", "currentPrice", "targetMeanPrice", "targetMedianPrice"]]
df_rt["Possible Gain in %"] = (df_rt.targetMeanPrice - df_rt.currentPrice)/df_rt.currentPrice*100

select_items = df_rt[["symbol", "shortName"]]

st.dataframe(df_rt)
selected_option = st.selectbox("Select Stock for more Detail", select_items, format_func=lambda s:session.query(Stock).get(s).shortName)
st.write("Option = " + selected_option)
history = session.query(FinancialData) \
    .filter(FinancialData.stock_id == selected_option) \
        .order_by(FinancialData.datetime.asc())
df_history = pd.DataFrame.from_records([r.to_dict() for r in history])
df_history = df_history[["datetime", "currentPrice", "targetMeanPrice", "targetMedianPrice"]]
st.line_chart(df_history, x="datetime")


weeks_to_look_back  = st.slider("Ticker Entries: How many weeks in the Past", min_value=1, max_value=52, value=10)
min_date  = today - timedelta(weeks=weeks_to_look_back)

tickers = session.query(Ticker).filter(Ticker.stock_id == selected_option, Ticker.datetime >= min_date)

def uni_value(ticker):
    if ticker.sentiment == "positive":
        return ticker.score
    elif ticker.sentiment == "negative":
        return ticker.score * -1
    return 0

if tickers.count() > 0:
    tickers_df = pd.DataFrame.from_records([t.to_dict() for t in tickers])

    tickers_df["score"] = tickers_df.apply(lambda t: uni_value(t), axis=1)
    tickers_df["date"] = tickers_df.datetime.dt.date
    tickers_df = tickers_df.groupby(tickers_df["date"])["score"].mean()

    # tickers_df = tickers_df[["date", "score"]]
    st.bar_chart(tickers_df)
else:
    st.write("""
    ## No Recent Tickers
    """)
