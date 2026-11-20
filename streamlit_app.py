"""
Entry point of the app. It only sets up the page and the navigation; the content is in app_pages/.

Streamlit runs this file on every rerun, so the shared parts (theme in .streamlit/config.toml and the global
choices in st.session_state) are set up here for every page. The menu is a bar at the top
with one dropdown per group of pages, grouped by type of task.
"""
import streamlit as st

st.set_page_config(page_title="IND320 · Norwegian reservoirs", page_icon=":material/water_drop:", layout="wide")

from ui_utils import init_state, menu_style  # noqa: E402 (after set_page_config)

pages = {
    # An empty section name puts the page first in the menu bar, outside the dropdowns
    "": [st.Page("app_pages/overview.py", title="Overview", icon=":material/home:", default=True)],
    ":material/table_chart: Explore the data": [
        st.Page("app_pages/reservoir_data.py", title="Reservoir data"),
        st.Page("app_pages/cross_border_flows.py", title="Cross-border flows"),
        st.Page("app_pages/exchange_rates.py", title="Exchange rates"),
    ],
    ":material/insights: Patterns and anomalies": [
        st.Page("app_pages/seasonality.py", title="Seasonality"),
        st.Page("app_pages/weather_outliers.py", title="Weather outliers"),
        st.Page("app_pages/weather_vs_reservoir.py", title="Weather vs reservoir"),
    ],
    ":material/trending_up: Forecast": [
        st.Page("app_pages/reservoir_forecast.py", title="Reservoir forecast"),
    ],
}
page = st.navigation(pages, position="top")
menu_style()

# Global choices (area and period), set the first time the app is opened
try:
    init_state()
except Exception as error:  # the default period needs the NVE data
    st.error(f"Could not load the reservoir data from NVE: {error}")
    st.stop()
page.run()
