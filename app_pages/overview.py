import pandas as pd
import streamlit as st
from data_utils import (
    AREA_TYPE_LABELS,
    N_LIGHT_LOCATIONS,
    WEATHER_VARIABLES,
    area_label,
    load_area_numbers,
    load_key_figures,
    load_map_values,
    load_month_labels,
    load_weekly_weather,
)
from map_utils import area_map
from ui_utils import month_name, page_header, selected_area, selected_period

page_header(
    "Norway’s reservoirs",
    "overview",
    "Choose a type of area, click an area on the map and choose a period. The other pages use the same choices.",
)

# What the map can be coloured by: the reservoirs (NVE) or a weather property (open-meteo) over the period
COLOUR_OPTIONS = {
    "fill": "Fill ratio at the end of the period (%)",
    "change": "Change in fill ratio over the period (pp)",
    "temperature_2m": "Weather: mean temperature (°C)",
    "precipitation": "Weather: precipitation (mm per week)",
    "snowfall": "Weather: snowfall (cm per week)",
    "wind_speed_10m": "Weather: mean wind speed (km/h)",
}
WEATHER_MONTHS = 12  # the weather on the map covers at most the last 12 months of the period


def weather_map_values(area_type, variable, start_month, end_month):
    """
    One value per area for a weather property over the last WEATHER_MONTHS months of the period: the mean of the
    weekly values, i.e. the mean temperature or wind, or the mean weekly precipitation or snowfall. The weekly
    weather of all areas is stored in MongoDB (part 4 notebook), so the map does not wait for downloads.
    """
    return {number: load_weekly_weather(area_type, number, start_month, end_month)[variable].mean()
            for number in load_area_numbers(area_type)}


area_type, area_number = selected_area()
start_month, end_month = selected_period()
controls, map_column = st.columns([2, 3], gap="large")

# ---------------------------------------------------------------- global choices
# The widgets get their start value from st.session_state (the global choice), and the new value is written
# back. Streamlit forgets a widget's own state when you go to another page, so the global value is kept
# under its own key ("area_type", "area_number", "period"), not under the widget key.
with controls:
    chosen_type = st.segmented_control(
        "Type of area", options=list(AREA_TYPE_LABELS), format_func=AREA_TYPE_LABELS.get,
        default=area_type, key="overview_area_type",
    )
    if chosen_type and chosen_type != area_type:  # None if the user clicks the chosen option again
        numbers = load_area_numbers(chosen_type)
        st.session_state["area_type"] = chosen_type
        # keep the same area number if it exists for the new type (e.g. 3), otherwise take the first one
        st.session_state["area_number"] = area_number if area_number in numbers else numbers[0]
        st.rerun()

    colour_by = st.selectbox("Colour the map by", options=list(COLOUR_OPTIONS), format_func=COLOUR_OPTIONS.get,
                             key="overview_colour_by")

    months = load_month_labels()
    period = st.select_slider(
        "Period", options=months, value=(start_month, end_month), format_func=month_name, key="overview_period",
    )
    if period != (start_month, end_month):
        st.session_state["period"] = period
        st.rerun()

    # ------------------------------------------------------------ key figures for the selected area
    key = load_key_figures(area_type, area_number, end_month)
    st.subheader(f"{area_label(area_type, area_number)}, week {key['week']} {key['date'].year}", anchor=False)
    c1, c2 = st.columns(2)
    c1.metric("Fill ratio", f"{key['fill_ratio']:.1%}", border=True)
    c2.metric("vs last week", f"{key['change_previous_week'] * 100:+.1f} pp", border=True)
    c1.metric(
        "vs normal", f"{(key['fill_ratio'] - key['median_same_week']) * 100:+.1f} pp", border=True,
        help=f"Normal = median of week {key['week']} in {key['first_year']}–{key['date'].year - 1}.",
    )
    c2.metric("Stored energy", f"{key['fill_TWh']:.1f} TWh", f"of {key['capacity_TWh']:.1f} TWh",
              delta_color="off", delta_arrow="off", border=True)
    st.caption("The last week of the chosen period. Source: NVE Magasinstatistikk.")

# ---------------------------------------------------------------- map
with map_column:
    if colour_by in WEATHER_VARIABLES:
        weather_start = max(start_month, (pd.Period(end_month) - (WEATHER_MONTHS - 1)).strftime("%Y-%m"))
        try:
            values = weather_map_values(area_type, colour_by, weather_start, end_month)
        except Exception as error:
            st.error(f"Could not download weather data from open-meteo ({type(error).__name__}). "
                     "The map is coloured by the fill ratio instead.")
            colour_by, values = "fill", load_map_values(area_type, start_month, end_month)["fill"]
        else:
            st.caption(f"Weather for {month_name(weather_start)} – {month_name(end_month)} (at most the last "
                       f"{WEATHER_MONTHS} months of the period), mean of {N_LIGHT_LOCATIONS} random locations per area.")
    else:
        values = load_map_values(area_type, start_month, end_month)[colour_by]
    title = {"fill": "Fill ratio (%)", "change": "Change (pp)", "temperature_2m": "Temperature (°C)",
             "precipitation": "Precipitation (mm/week)", "snowfall": "Snowfall (cm/week)",
             "wind_speed_10m": "Wind speed (km/h)"}[colour_by]
    fig = area_map(area_type, values, area_number, title)
    # Clicking an area selects it. The key includes the area type, so an old click on one type of area
    # is not read again after the type is changed.
    event = st.plotly_chart(
        fig, key=f"map_{area_type}", on_select="rerun", selection_mode="points", theme=None,
        config={"displayModeBar": False, "scrollZoom": False},
    )
    points = event["selection"]["points"] if event else []
    if points and points[0].get("location") is not None and int(points[0]["location"]) != area_number:
        st.session_state["area_number"] = int(points[0]["location"])
        st.rerun()
    st.caption(f"{AREA_TYPE_LABELS[area_type]}, {month_name(start_month)} – {month_name(end_month)}. "
               "Click an area to select it.")
