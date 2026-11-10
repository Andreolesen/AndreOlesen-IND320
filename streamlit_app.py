import streamlit as st
# Page settings for the home page: browser tab title, icon and wide layout.
st.set_page_config(page_title="IND320 - Data to Decision", page_icon=":bar_chart:", layout="wide")
# Home page of the app. Streamlit automatically adds every .py file in the
# pages/ folder to the sidebar menu (ordered by the number prefix), so the
# navigation to the other pages comes from the folder structure.

from data_utils import load_national_key_figures

st.title("IND320 - Data to Decision")


# ---------------------------------------------------------------- key figures
# A quick overview of the reservoirs in Norway right now, from the same NVE data as the reservoir page
# (cached for a day). The deltas are in percentage points (pp), since the fill ratio is already a share.
st.subheader("Norway's reservoirs right now")
try:
    key = load_national_key_figures()
except Exception as error:  # the home page should still work if the NVE API is down
    st.warning(f"Could not load the key figures from NVE: {error}")
else:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        "Fill ratio",
        f"{key['fill_ratio']:.1%}",
        delta=f"{key['change_previous_week'] * 100:+.1f} pp vs previous week",
    )
    c2.metric(
        "Same week last year",
        f"{key['fill_ratio_last_year']:.1%}",
        delta=f"{(key['fill_ratio'] - key['fill_ratio_last_year']) * 100:+.1f} pp this year",
    )
    c3.metric(
        f"Normal for week {key['week']}",
        f"{key['median_same_week']:.1%}",
        delta=f"{(key['fill_ratio'] - key['median_same_week']) * 100:+.1f} pp this year",
        help=f"Median of week {key['week']} in {key['first_year']}-{key['date'].year - 1}.",
    )
    c4.metric(
        "Stored energy",
        f"{key['fill_TWh']:.1f} TWh",
        delta=f"of {key['capacity_TWh']:.1f} TWh capacity",
        delta_color="off",  # grey and no arrow, since this is not a change
        delta_arrow="off",
    )
    st.caption(f"Source: NVE Magasinstatistikk, week {key['week']} ({key['date'].date()}). NVE publishes new numbers every week.")

st.divider()
st.write("Use the menu in the sidebar to open the pages:")
st.markdown(
    """
    1. **Reservoir data** - weekly reservoir statistics from NVE (table and plot). The area chosen here is
       also used by the two analysis pages.
    2. **Reservoir seasonality** - STL decomposition and spectrogram of the fill ratio.
    3. **Weather outliers** - outliers in precipitation (DCT + SPC) and anomalies in temperature (LOF)
       for weather data from open-meteo (ERA5).
    4. **Cross border flows** - electricity flows between Norway and neighbouring countries (ENTSO-E).
    """
)

