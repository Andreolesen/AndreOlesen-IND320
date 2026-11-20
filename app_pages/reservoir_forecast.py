import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from data_utils import (
    N_LIGHT_LOCATIONS,
    WEATHER_VARIABLES,
    area_label,
    load_all_reservoir_data,
    load_exchange_rates,
    load_weekly_weather,
)
from forecast_utils import WEEKS_PER_YEAR, forecast_filling
from ui_utils import FJORD, GREY, GROUPS, page_header, selected_area, selected_period, selection_line

FORECAST_COLOUR = GROUPS["forecast"][1]

page_header(
    "Reservoir forecast", "forecast",
    "Forecast of the weekly fill ratio with River, using the models tested in the part 4 notebook. "
    "The default settings are the best ones from the notebook.",
)

# The area and the end of the training data come from the Overview page (the end of the chosen period),
# so the forecast starts where the map and the other pages end. Everything else is chosen here.
area_type, area_number = selected_area()
_, end_month = selected_period()
selection_line()

nve = load_all_reservoir_data()
fill = (nve[(nve["area_type"] == area_type) & (nve["area_number"] == area_number)]
        .set_index("date")["fill_ratio"].sort_index().asfreq("W-SUN").interpolate())
weeks_in_period = fill.loc[:pd.Period(end_month).end_time]
cutoff = weeks_in_period.index[-1]
st.caption(f"The training data end in week {cutoff.isocalendar().week} {cutoff.year} ({cutoff:%d %b %Y}), the last "
           "week of the period chosen on the Overview page. Move the period there to forecast from an earlier "
           "date and compare with what really happened.")

MODELS = {"snarimax": "SNARIMAX (recommended)", "lags": "Lag model", "naive": "Naive (last year's development)"}
EXOGENOUS = {"temperature_2m": "Temperature", "precipitation": "Precipitation", "EUR": "EUR rate", "USD": "USD rate"}

# ---------------------------------------------------------------- settings (a form: nothing runs until the button)
# The forecast only runs when the button is pressed, so changing several settings does not train the model
# again and again. The weather comes from MongoDB (prepared in the part 4 notebook), so it is ready at once.
with st.form("forecast_settings"):
    c1, c2, c3 = st.columns([2, 1, 1])
    model = c1.radio("Model", options=list(MODELS), format_func=MODELS.get, horizontal=True)
    history_years = c2.slider("Training data (years)", min_value=3, max_value=15, value=10)
    horizon = c3.slider("Horizon (weeks)", min_value=4, max_value=52, value=26)
    exogenous = st.multiselect("Exogenous variables", options=list(EXOGENOUS), default=[],
                               format_func=EXOGENOUS.get,
                               help="Weekly mean temperature and weekly precipitation for the area, and weekly mean "
                                    "exchange rates. For future weeks a normal year (mean of the same week) is used.")
    with st.expander("Model parameters"):
        lag_column, arima_column = st.columns(2)
        with lag_column:
            st.markdown("**Lag model**")
            n_lags = st.number_input("Number of lags (weeks)", min_value=1, max_value=13, value=2)
        with arima_column:
            st.markdown("**SNARIMAX** (seasonal period 52 weeks)")
            a1, a2, a3 = st.columns(3)
            p = a1.number_input("p", 0, 6, 2)
            d = a2.number_input("d", 0, 2, 0)
            q = a3.number_input("q", 0, 6, 1)
            sp = a1.number_input("sp", 0, 3, 1)
            sd = a2.number_input("sd", 0, 1, 1)
            sq = a3.number_input("sq", 0, 3, 0)
    run = st.form_submit_button("Run forecast", type="primary", icon=":material/play_arrow:")


def build_dataset(first_month, last_month):
    """Weekly table with the fill ratio and the chosen exogenous variables, from first_month to last_month."""
    data = fill.loc[pd.Timestamp(first_month):pd.Period(last_month).end_time].to_frame("fill")
    weather_columns = [c for c in exogenous if c in WEATHER_VARIABLES]
    if weather_columns:
        weekly = load_weekly_weather(area_type, area_number, first_month, last_month)
        data = data.join(weekly[weather_columns])
    rate_columns = [c for c in exogenous if c in ("EUR", "USD")]
    if rate_columns:
        rates = load_exchange_rates(pd.Timestamp(first_month).strftime("%Y-%m-%d"),
                                    pd.Period(last_month).end_time.strftime("%Y-%m-%d"))
        data = data.join(rates.resample("W-SUN").mean()[rate_columns])
    return data


if run:
    # Same as in the notebook: "10 years" = 520 weeks, of which the first year only gives the lag model last
    # year's change. Data from one extra year back (a margin for missing weeks) to the end of the horizon,
    # or to today if the horizon goes into the future
    first = (cutoff - pd.DateOffset(years=history_years + 1)).strftime("%Y-%m")
    last = min(cutoff + pd.Timedelta(weeks=horizon), pd.Timestamp.today()).strftime("%Y-%m")
    try:
        data = build_dataset(first, last)
    except Exception as error:
        st.error(f"Could not download the exogenous variables ({type(error).__name__}). Try again later, or run "
                 "the forecast without them.")
        st.stop()
    with st.spinner("Training the model and forecasting ..."):
        forecast, used_cutoff, seconds = forecast_filling(
            data, model=model, history_weeks=history_years * WEEKS_PER_YEAR, horizon_weeks=horizon,
            cutoff=cutoff, p=p, d=d, q=q, sp=sp, sd=sd, sq=sq, n_lags=n_lags,
        )
    # Kept in st.session_state, so the result stays on the page when other widgets are used
    st.session_state["forecast_result"] = {
        "forecast": forecast, "cutoff": used_cutoff, "seconds": seconds, "model": model, "area": (area_type, area_number),
        "exogenous": exogenous, "history_years": history_years,
    }

result = st.session_state.get("forecast_result")
if result is None:
    st.info("Choose the settings and press **Run forecast**.", icon=":material/info:")
    st.stop()
if result["area"] != (area_type, area_number):
    st.warning(f"The forecast below is for {area_label(*result['area'])}. Press Run forecast for "
               f"{area_label(area_type, area_number)}.")

# ---------------------------------------------------------------- results
forecast, used_cutoff = result["forecast"], result["cutoff"]
area_fill = (nve[(nve["area_type"] == result["area"][0]) & (nve["area_number"] == result["area"][1])]
             .set_index("date")["fill_ratio"].sort_index())
observed = area_fill.loc[used_cutoff - pd.Timedelta(weeks=2 * WEEKS_PER_YEAR):used_cutoff]
actual = area_fill.loc[used_cutoff:forecast.index[-1]]  # what really happened, if the forecast is in the past
now = observed.iloc[-1]

m1, m2, m3, m4 = st.columns(4)
m1.metric(f"Fill ratio, {used_cutoff:%d %b %Y}", f"{now:.1%}", border=True)
m2.metric(f"Forecast in {len(forecast)} weeks", f"{forecast.iloc[-1]:.1%}",
          f"{(forecast.iloc[-1] - now) * 100:+.1f} pp", border=True)
errors = (forecast - actual).dropna().abs() * 100
if len(errors) >= 4:  # only meaningful when a good part of the horizon has happened
    m3.metric("Mean error vs what happened", f"{errors.mean():.1f} pp", f"over {len(errors)} weeks",
              delta_color="off", delta_arrow="off", border=True)
else:
    m3.metric("Mean error vs what happened", "–", "the horizon has not happened yet", delta_color="off",
              delta_arrow="off", border=True)
m4.metric("Time used", f"{result['seconds'] * 1000:.0f} ms", MODELS[result["model"]].split(" (")[0],
          delta_color="off", delta_arrow="off", border=True)

# Plot with a Plotly animation: the forecast is drawn week by week when Play is pressed
line = pd.concat([observed.iloc[-1:], forecast]) * 100  # starts at the last observed week, so the lines connect
fig = go.Figure()
fig.add_trace(go.Scatter(x=observed.index, y=observed * 100, name="Observed", line=dict(color=FJORD, width=2)))
if len(actual) > 1:
    fig.add_trace(go.Scatter(x=actual.index, y=actual * 100, name="What happened", line=dict(color=GREY, width=1.5, dash="dot")))
fig.add_trace(go.Scatter(x=line.index, y=line, name="Forecast", mode="lines+markers",
                         line=dict(color=FORECAST_COLOUR, width=3), marker=dict(size=5)))
forecast_trace = len(fig.data) - 1
fig.frames = [go.Frame(data=[go.Scatter(x=line.index[:k + 1], y=line.iloc[:k + 1])], traces=[forecast_trace], name=str(k))
              for k in range(1, len(line))]
fig.add_vline(x=used_cutoff, line=dict(color=GREY, width=1, dash="dash"))
fig.update_layout(
    title=f"Fill ratio, {area_label(*result['area'])}: forecast from {used_cutoff:%d %b %Y}",
    yaxis=dict(title="Fill ratio (%)", range=[0, 100]),
    xaxis=dict(range=[observed.index[0], forecast.index[-1] + pd.Timedelta(weeks=2)]),
    height=520, hovermode="x unified", legend=dict(orientation="h", y=1.02, x=1, xanchor="right", yanchor="bottom"),
    updatemenus=[dict(type="buttons", x=0, y=-0.12, xanchor="left", direction="left", showactive=False, buttons=[
        dict(label="▶ Play", method="animate",
             args=[None, dict(frame=dict(duration=120, redraw=False), transition=dict(duration=0), fromcurrent=False)]),
        dict(label="❚❚ Pause", method="animate",
             args=[[None], dict(frame=dict(duration=0, redraw=False), mode="immediate")]),
    ])],
)
st.plotly_chart(fig, theme=None)

exog_text = ", ".join(EXOGENOUS[c] for c in result["exogenous"]) or "none"
with st.expander("About the forecast"):
    st.markdown(
        f"""
        - **Model:** {MODELS[result['model']]}, trained on {result['history_years']} years of weekly data up to
          {used_cutoff:%d %b %Y}. Exogenous variables: {exog_text}.
        - **Dynamic forecast:** the lag model predicts one week at a time, and each prediction is used as the newest
          lag for the next week. SNARIMAX forecasts the whole horizon from its own model.
        - **Exogenous variables in the future:** a normal year (the mean of the same week in the training data),
          also when the forecast starts in the past, since a real forecast does not know the future weather. The same
          is used for the newest weeks if the stored weather does not reach the end of the training data.
        - **Weather:** weekly values, mean of {N_LIGHT_LOCATIONS} random locations in the area, prepared in the part 4
          notebook and stored in MongoDB. The notebook showed that 5 or 20 locations give almost the same forecast
          error.
        - In the notebook (22 test dates in 2021–2026, price area NO3), SNARIMAX without exogenous variables had a
          mean error of 7.9 pp over 26 weeks, the lag model 8.7 pp and the naive forecast 10.4 pp. With a normal year
          for the future weather, the weather made the forecasts slightly worse, so it is not used by default.
        """
    )
