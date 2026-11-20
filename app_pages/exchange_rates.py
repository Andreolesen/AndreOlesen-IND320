import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from data_utils import load_exchange_rates
from ui_utils import FJORD, month_name, page_header, selected_period, selection_line

page_header("Exchange rates", "explore",
            "Daily exchange rates for EUR and USD from Norges Bank, in NOK per unit of the currency.")

# The period is a global choice from the Overview page; the currencies are a local choice
start_month, end_month = selected_period()
selection_line(area_text="", show_period=True)

CURRENCY_COLOURS = {"EUR": FJORD, "USD": "#C9810A"}
currencies = st.pills("Currencies", options=["EUR", "USD"], selection_mode="multi", default=["EUR", "USD"])
if not currencies:
    st.info("Choose at least one currency.")
    st.stop()

# Norges Bank's API takes dates, so the period is sent as the first and last day of the chosen months
start, end = pd.Timestamp(start_month), pd.Period(end_month).end_time.normalize()
try:
    rates = load_exchange_rates(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
except Exception as error:  # no internet, the API is down or answers with something unexpected
    st.error(f"Could not download exchange rates from Norges Bank ({type(error).__name__}). Try again later.")
    st.stop()
if rates.empty:
    st.warning("Norges Bank has no exchange rates for this period.")
    st.stop()

# ---------------------------------------------------------------- key figures: last rate and change over the period
columns = st.columns(len(currencies) * 2)
for i, currency in enumerate(currencies):
    series = rates[currency].dropna()
    change = series.iloc[-1] / series.iloc[0] - 1
    columns[2 * i].metric(f"{currency}, {series.index[-1]:%d %b %Y}", f"{series.iloc[-1]:.3f} NOK", border=True)
    columns[2 * i + 1].metric(f"{currency}, change over the period", f"{change:+.1%}",
                              f"from {series.iloc[0]:.3f} NOK", delta_color="off", delta_arrow="off", border=True)

# ---------------------------------------------------------------- plot
fig = go.Figure()
for currency in currencies:
    fig.add_trace(go.Scatter(x=rates.index, y=rates[currency], name=currency, mode="lines",
                             line=dict(color=CURRENCY_COLOURS[currency], width=1.8)))
fig.update_layout(
    title=f"NOK per unit of currency, {month_name(start_month)} – {month_name(end_month)}",
    yaxis_title="NOK", hovermode="x unified", height=460,
    legend=dict(orientation="h", y=1.02, x=1, xanchor="right", yanchor="bottom"),
)
st.plotly_chart(fig, theme=None)

with st.expander("About the data"):
    st.markdown(
        """
        - **Source:** Norges Bank's open API (SDMX), dataset `EXR`, daily spot rates (`B.EUR+USD.NOK.SP`).
        - The rates are mid-rates from the interbank market, published at about 16:00 Norwegian time on business
          days. Weekends and Norwegian public holidays have no rate, so the line has small gaps there.
        - Cached for a day, so changing the currencies does not download again.
        """
    )
