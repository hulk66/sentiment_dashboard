from calendar import month
from datetime import datetime, date, timedelta
import streamlit as st
import pandas as pd

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy import select
from sentiment.domain import Base, FinancialData, Ticker, Stock

from sentiment import config
from sentiment.celery_app import app


engine = create_engine(config.DB_URL)
Base.metadata.create_all(engine, checkfirst=True)
session = Session(engine)

st.title = "Tobias' Dashboard"
st.write("""
# Tobias' first fine Dashboard
""")


def get_task_info():
    inspect = app.control.inspect()
    # st.write("Registered" + str(inspect.registered()))
    active = list(inspect.active().keys())[0]
    a_dict = inspect.active()
    if len(a_dict) > 0:
        a_key = list(inspect.active().keys())[0]
        for s in a_dict[a_key]:
            r = s["request"]
            st.write(r["name"], r["args"][0] )


    s_dict = inspect.scheduled()
    if len(s_dict) > 0:
        s_key = list(inspect.scheduled().keys())[0]

        for s in s_dict[s_key]:
            r = s["request"]
            #st.write(s)
            #st.write(s["name"])
            st.write(r["name"], r["args"][0] )

    #st.write("Active " + str(inspect.active()))
    #st.write("Scheduled " + str(inspect.scheduled()))
    #st.write("Scheduled " + scheduled)
    #st.write("Reserved " + str(inspect.reserved()))


def start_scrape():
    # scrape_stocks.apply_async(queue="scrape_finviz")
    app.send_task("sentiment.tasks.scrape_tasks.scrape_stocks", queue="scrape")

st.button("Start Scraping", on_click=start_scrape)

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
def uni_value(ticker):
    if ticker.sentiment == "positive":
        return ticker.score
    elif ticker.sentiment == "negative":
        return ticker.score * -1
    return 0


if good_recommendations_today.count() > 0:
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
