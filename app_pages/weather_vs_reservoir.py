import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from data_utils import (
    N_LIGHT_LOCATIONS,
    WEATHER_VARIABLES,
    load_all_reservoir_data,
    load_weekly_weather,
)
from ui_utils import FJORD, GREY, page_header, selected_area, selected_period, selection_line

page_header(
    "Weather vs reservoir", "patterns",
    "Sliding window correlation between a weather property and the reservoirs: how strongly they move together, "
    "and how that changes over time.",
)

# Area and period are global choices from the Overview page; the rest are local choices for this page
area_type, area_number = selected_area()
start_month, end_month = selected_period()
selection_line()

RESERVOIR_VARIABLES = {
    "fill_ratio_change": "Weekly change in fill ratio (pp)",
    "fill_ratio": "Fill ratio (%)",
}
c1, c2, c3, c4 = st.columns(4)
weather_variable = c1.selectbox("Weather property", options=list(WEATHER_VARIABLES), index=1,  # precipitation
                                format_func=lambda v: f"{WEATHER_VARIABLES[v][0]} ({WEATHER_VARIABLES[v][1]} per week)"
                                if WEATHER_VARIABLES[v][2] == "sum" else f"{WEATHER_VARIABLES[v][0]} ({WEATHER_VARIABLES[v][1]})")
reservoir_variable = c2.selectbox("Reservoir variable", options=list(RESERVOIR_VARIABLES),
                                  format_func=RESERVOIR_VARIABLES.get,
                                  help="The weekly change shows when water comes in; the fill ratio itself mostly "
                                       "follows the season.")
lag = c3.slider("Lag (weeks)", min_value=0, max_value=26, value=2,
                help="How many weeks the weather comes before the reservoir. Lag 2 compares the reservoir this week "
                     "with the weather two weeks earlier.")
window = c4.slider("Window length (weeks)", min_value=4, max_value=52, value=13,
                   help="Number of weeks in each correlation. Short windows react fast but are noisy.")

# ---------------------------------------------------------------- data (weekly)
# Weather: weekly values for the area, stored in MongoDB by the part 4 notebook (only the newest weeks are
# downloaded from open-meteo), in the same weeks as NVE (Norwegian time, weeks ending on Sunday)
try:
    weekly_weather = load_weekly_weather(area_type, area_number, start_month, end_month)
except Exception as error:
    st.error(f"Could not download weather data from open-meteo ({type(error).__name__}). Try again later.")
    st.stop()

nve = load_all_reservoir_data()
reservoir = (nve[(nve["area_type"] == area_type) & (nve["area_number"] == area_number)]
             .set_index("date")[reservoir_variable] * 100)  # in % and percentage points

# The weather is shifted forward by the lag, so each reservoir week is compared with the weather lag weeks earlier
data = pd.DataFrame({"reservoir": reservoir, "weather": weekly_weather[weather_variable].shift(lag, freq="W-SUN")})
data = data.loc[pd.Timestamp(start_month):pd.Period(end_month).end_time].dropna()
if len(data) < window + 4:
    st.warning(f"The period gives only {len(data)} weeks with both series. Choose a longer period on the Overview "
               "page or a shorter window.")
    st.stop()

# Sliding window correlation, centred, so each value belongs to the middle week of its window
rolling = data["reservoir"].rolling(window, center=True).corr(data["weather"])

# Correlation over the whole period for every lag, to see which lag fits best
lags = range(0, 27)
by_lag = pd.Series({k: reservoir.corr(weekly_weather[weather_variable].shift(k, freq="W-SUN")
                                      .loc[pd.Timestamp(start_month):pd.Period(end_month).end_time]) for k in lags})

# ---------------------------------------------------------------- key figures
weather_label = WEATHER_VARIABLES[weather_variable][0]
m1, m2, m3 = st.columns(3)
m1.metric(f"Correlation, lag {lag} weeks", f"{data['reservoir'].corr(data['weather']):+.2f}", border=True,
          help="Pearson correlation over the whole period.")
m2.metric("Strongest lag", f"{by_lag.abs().idxmax()} weeks", f"r = {by_lag[by_lag.abs().idxmax()]:+.2f}",
          delta_color="off", delta_arrow="off", border=True)
m3.metric("Windows with |r| > 0.5", f"{(rolling.abs() > 0.5).mean():.0%}", border=True,
          help="Share of the windows where the two series are strongly related.")

# ---------------------------------------------------------------- plots
left, right = st.columns([3, 1])
with left:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08, row_heights=[0.55, 0.45],
                        specs=[[{"secondary_y": True}], [{}]])
    fig.add_trace(go.Scatter(x=data.index, y=data["reservoir"], name=RESERVOIR_VARIABLES[reservoir_variable],
                             line=dict(color=FJORD, width=1.8)), row=1, col=1)
    fig.add_trace(go.Scatter(x=data.index, y=data["weather"], name=f"{weather_label}, {lag} weeks earlier",
                             line=dict(color="#1A7F8E", width=1.2, dash="dot")), row=1, col=1, secondary_y=True)
    fig.add_trace(go.Scatter(x=rolling.index, y=rolling, name=f"Correlation ({window}-week window)",
                             line=dict(color=FJORD, width=2), fill="tozeroy", fillcolor="rgba(31,95,122,0.12)"),
                  row=2, col=1)
    fig.add_hline(y=0, line=dict(color=GREY, width=1), row=2, col=1)
    fig.update_yaxes(title_text=RESERVOIR_VARIABLES[reservoir_variable], row=1, col=1, secondary_y=False)
    unit, how = WEATHER_VARIABLES[weather_variable][1], WEATHER_VARIABLES[weather_variable][2]
    fig.update_yaxes(title_text=f"{weather_label} ({unit}{' per week' if how == 'sum' else ''})", row=1, col=1,
                     secondary_y=True, showgrid=False)
    fig.update_yaxes(title_text="Correlation", range=[-1, 1], row=2, col=1)
    fig.update_layout(height=620, hovermode="x unified", margin=dict(t=60),
                      legend=dict(orientation="h", y=1.04, x=0, yanchor="bottom"))
    st.plotly_chart(fig, theme=None)

with right:
    bar = go.Figure(go.Bar(x=by_lag.index, y=by_lag.values,
                           marker_color=[FJORD if k == lag else "#B5CCD6" for k in by_lag.index],
                           hovertemplate="Lag %{x} weeks: r = %{y:.2f}<extra></extra>"))
    bar.update_layout(title="Correlation by lag", xaxis_title="Lag (weeks)", yaxis_title="r",
                      yaxis_range=[-1, 1], height=620, showlegend=False)
    st.plotly_chart(bar, theme=None)

with st.expander("How to read the plots"):
    st.markdown(
        f"""
        - **Top:** the reservoir variable and the weather property, with the weather moved {lag} weeks forward,
          so the two lines are compared week by week as the correlation sees them.
        - **Bottom:** the Pearson correlation in a window of {window} weeks that slides along the period. Values
          near +1 mean the two move up and down together, near −1 that one goes up when the other goes down, and
          near 0 that there is no linear relation in that window. The window is centred on each week.
        - **Right:** the correlation over the whole period for every lag from 0 to 26 weeks; the chosen lag is dark.
        - Weather: hourly ERA5 from open-meteo, mean of {N_LIGHT_LOCATIONS} random locations in the area, converted
          to Norwegian time and summed or averaged per week (weeks ending on Sunday, like Magasinstatistikk). The
          weeks are prepared in the part 4 notebook and stored in MongoDB, so the page does not wait for downloads.
        """
    )
