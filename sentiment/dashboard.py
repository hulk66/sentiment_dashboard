from dash import Dash, html, dcc
import plotly.express as px
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy import select
from domain import Base, FinancialData, Ticker, Stock

app = Dash(__name__)
# engine = engine = create_engine("mysql+pymysql://root:yosemite66@qn/sentiment")
engine = create_engine("sqlite:///ticker.db", echo=False, future=True)
Base.metadata.create_all(engine, checkfirst=True)
session = Session(engine)

recommendations = session.query(FinancialData)
rdf = pd.DataFrame.from_records([r.to_dict() for r in recommendations])
best_recommendations = rdf.loc[(rdf['recommendationMean'] < 2) & (rdf['numberOfAnalystOpinions'] > 5)]
best_recommendations["Diff"] = best_recommendations.apply(lambda row: (row.targetMeanPrice - row.currentPrice)/100*row.currentPrice, axis=1)



fig = px.bar(df, x="Fruit", y="Amount", color="City", barmode="group")

app.layout = html.Div(children=[
    html.H1(children='Hello Dash'),

    html.Div(children='''
        Dash: A web application framework for your data.
    '''),

    dcc.Graph(
        id='example-graph',
        figure=fig
    )
])

if __name__ == '__main__':
    app.run_server(debug=True)
