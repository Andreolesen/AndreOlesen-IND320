import calendar

import streamlit as st
from analysis_utils import lof_anomalies, spc_outliers
from data_utils import N_APP_LOCATIONS, WEATHER_VARIABLES, WeatherLimitError, area_label, load_weather_period
from ui_utils import page_header, selected_area, selected_period, selection_line

page_header("Weather outliers", "patterns",
            "Outliers and anomalies in hourly ERA5 weather from open-meteo, averaged over random locations in the area.")

# Area and period are global choices from the Overview page. The weather property and the method settings are
# local, since they only matter on this page.
area_type, area_number = selected_area()
start_month, end_month = selected_period()
selection_line()

# The download is an integrated, hidden part of the page: it starts by itself when the area or period changes,
# shows a progress bar (one step per year) and is cached, so the settings below do not download again.
try:
    weather = load_weather_period(area_type, area_number, start_month, end_month)
except WeatherLimitError as error:  # an API limit is reached: show open-meteo's own reason
    st.error(f"open-meteo refused the download: {error}")
    st.stop()
except Exception as error:  # e.g. no internet
    st.error(f"Could not download weather data from open-meteo ({type(error).__name__}). Try again later.")
    st.stop()
st.caption(f"{len(weather):,} hours of ERA5 data, mean of {N_APP_LOCATIONS} random locations in "
           f"{area_label(area_type, area_number)}. Cached, so changing the settings below does not download again.")


def choose_property(key, default):
    """Select box with the weather properties; returns the column name."""
    options = list(WEATHER_VARIABLES)
    return st.selectbox("Weather property", options=options, index=options.index(default), key=key,
                        format_func=lambda v: WEATHER_VARIABLES[v][0])


spc_tab, lof_tab = st.tabs(["Outliers (SATV and SPC)", "Anomalies (LOF)"])

# ---------------------------------------------------------------- DCT + SPC
with spc_tab:
    c1, c2, c3 = st.columns(3)
    with c1:
        variable = choose_property("spc_property", "temperature_2m")
    cutoff = c2.slider("DCT cut-off (cycles per year)", min_value=1, max_value=100, value=25,
                       help="Variations slower than this are removed before the limits are found. "
                            "25 cycles per year ≈ two weeks.")
    n_std = c3.slider("Number of robust standard deviations", min_value=1.0, max_value=6.0, value=3.0, step=0.5)
    label, unit, _ = WEATHER_VARIABLES[variable]

    fig, outliers, summary = spc_outliers(weather[variable], cutoff_per_year=cutoff, n_std=n_std, label=label, unit=unit)
    st.plotly_chart(fig, theme=None)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Outliers", f"{summary['n_outliers']:,}", border=True)
    m2.metric("Share of hours", f"{summary['share_outliers']:.1%}", border=True)
    m3.metric("Above / below the limits", f"{summary['n_above']} / {summary['n_below']}", border=True)
    m4.metric(f"Robust σ ({unit})", f"{summary['robust_sigma']:.3g}", border=True,
              help="1.4826 · MAD of the seasonally adjusted variations, a standard deviation that is not pulled by "
                   "the outliers themselves.")
    with st.expander("Table of outliers"):
        st.dataframe(outliers.round(3), width="stretch")
    st.caption("The slow variation is removed with a DCT high-pass filter; what is left is the seasonally adjusted "
               "variation (SATV). Hours where the SATV is more than the chosen number of robust standard deviations "
               "from the median are outliers. The limits are drawn around the slow variation.")

# ---------------------------------------------------------------- LOF
with lof_tab:
    c1, c2, c3 = st.columns(3)
    with c1:
        variable = choose_property("lof_property", "precipitation")
    contamination = c2.slider("Proportion of anomalies", min_value=0.001, max_value=0.05, value=0.01,
                              step=0.001, format="%.3f")
    n_neighbors = c3.slider("Number of neighbours", min_value=5, max_value=100, value=20)
    label, unit, _ = WEATHER_VARIABLES[variable]

    with st.spinner("Finding anomalies with Local Outlier Factor ..."):
        fig, anomalies, summary = lof_anomalies(weather[variable], contamination=contamination,
                                                n_neighbors=n_neighbors, label=label, unit=unit)
    st.plotly_chart(fig, theme=None)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Anomalies", f"{summary['n_anomalies']:,}", border=True)
    m2.metric("Share of hours", f"{summary['share_anomalies']:.1%}", border=True)
    m3.metric(f"Lowest anomaly ({unit})", f"{summary['lowest']:.1f}", border=True)
    m4.metric(f"Highest anomaly ({unit})", f"{summary['highest']:.1f}", border=True)
    months = ", ".join(f"{calendar.month_name[m]} ({n})" for m, n in summary["months_with_most_anomalies"].items())
    st.write(f"Months with most anomalies: {months}")
    with st.expander("Table of anomalies (most unusual first)"):
        st.dataframe(anomalies.round(2), width="stretch")
    st.caption("Local Outlier Factor compares the density around each hour (time and value) with the density around "
               "its neighbours. Hours in sparse areas, for example sudden changes, become anomalies.")
