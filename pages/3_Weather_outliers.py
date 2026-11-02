import calendar

import streamlit as st
from analysis_utils import precipitation_outliers, temperature_anomalies
from data_utils import (
    FIRST_WEATHER_YEAR,
    LAST_WEATHER_YEAR,
    N_APP_LOCATIONS,
    area_label,
    get_selected_area,
    load_weather,
)

st.title("Weather: outliers and anomalies")
st.write("Hourly ERA5 weather from open-meteo, averaged over random locations in the chosen price area.")

# The area is a global setting: it comes from the page "Reservoir data" (saved in st.session_state), so all
# pages use the same area. The random locations only exist for the price areas NO1-NO5 (from NVE Atlas),
# so the page stops if another area type is chosen there.
area_type, area_number = get_selected_area()
if area_type != "EL":
    st.warning(
        f"The chosen area is **{area_label(area_type, area_number)}**. Weather data are only available for the "
        "price areas NO1-NO5. Choose a price area on the page Reservoir data."
    )
    st.page_link("pages/1_Reservoir_data.py", label="Go to Reservoir data", icon=":material/tune:")
    st.stop()

region = area_label(area_type, area_number)  # e.g. "NO3"

# The year is a local setting, since only this page uses weather data
# (the reservoir page uses months, which fit the weekly NVE data)
info, choice = st.columns([3, 1])
years = list(range(LAST_WEATHER_YEAR, FIRST_WEATHER_YEAR - 1, -1))
year = choice.selectbox("Year", options=years, index=years.index(2024) if 2024 in years else 0)
info.info(f"Area: **{region}** (change on the page Reservoir data), average of {N_APP_LOCATIONS} random locations.")

# The download is an integrated, hidden part of the page (no separate download page): it starts by itself
# when the area or year changes, shows a spinner while it runs, and is cached, so the sliders below
# do not download again. A short confirmation shows what was downloaded.
try:
    weather = load_weather(region, year)
except Exception as error:  # e.g. no internet or the API limit is reached
    st.error(f"Could not download weather data from open-meteo: {error}")
    st.stop()
st.caption(
    f"Downloaded {len(weather)} hours of ERA5 data for {N_APP_LOCATIONS} locations in {region} ({year}) "
    f"from open-meteo. The data are cached, so changing the settings below does not download again."
)

spc_tab, lof_tab = st.tabs(["Outliers in precipitation (SPC)", "Anomalies in temperature (LOF)"])

# ---------------------------------------------------------------- precipitation: DCT + SPC
with spc_tab:
    c1, c2 = st.columns(2)
    freq_cutoff = c1.slider("DCT cut-off (lowest frequencies removed)", min_value=1, max_value=500, value=50,
                            help="Higher values remove more of the slow variation before the limits are found.")
    n_std = c2.slider("Number of robust standard deviations", min_value=1.0, max_value=6.0, value=3.0, step=0.5)

    fig, outliers, summary = precipitation_outliers(weather["precipitation"], freq_cutoff=freq_cutoff, n_std=n_std)
    st.pyplot(fig)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Outliers", summary["n_outliers"])
    m2.metric("Share of hours", f"{summary['share_outliers']:.1%}")
    m3.metric("Above / below the limits", f"{summary['n_above']} / {summary['n_below']}")
    m4.metric("Robust σ (mm/h)", summary["robust_sigma"])

    with st.expander("Table of outliers"):
        st.dataframe(outliers.round(3), width="stretch")
    st.caption(
        "The slow variation (season and weather systems) is removed with a DCT high-pass filter. Hours where the "
        "remaining variation is more than the chosen number of robust standard deviations (1.4826 · MAD) from "
        "the median are outliers. Precipitation is skewed, so most outliers are hours with heavy precipitation."
    )

# ---------------------------------------------------------------- temperature: LOF
with lof_tab:
    c1, c2 = st.columns(2)
    contamination = c1.slider("Proportion of anomalies", min_value=0.001, max_value=0.05, value=0.01,
                              step=0.001, format="%.3f")
    n_neighbors = c2.slider("Number of neighbours", min_value=5, max_value=100, value=20)

    fig, anomalies, summary = temperature_anomalies(weather["temperature_2m"], contamination=contamination,
                                                    n_neighbors=n_neighbors)
    st.pyplot(fig)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Anomalies", summary["n_anomalies"])
    m2.metric("Share of hours", f"{summary['share_anomalies']:.1%}")
    m3.metric("Coldest anomaly", f"{summary['coldest_anomaly']} °C")
    m4.metric("Warmest anomaly", f"{summary['warmest_anomaly']} °C")
    months = ", ".join(f"{calendar.month_name[m]} ({n})" for m, n in summary["months_with_most_anomalies"].items())
    st.write(f"Months with most anomalies: {months}")

    with st.expander("Table of anomalies (most unusual first)"):
        st.dataframe(anomalies.round(2), width="stretch")
    st.caption(
        "Local Outlier Factor compares the density around each hour (time and temperature) with the density "
        "around its neighbours. Hours in sparse areas, for example quick temperature shifts, become anomalies."
    )
