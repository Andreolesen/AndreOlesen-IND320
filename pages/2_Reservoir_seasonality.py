import streamlit as st
from analysis_utils import filling_spectrogram, stl_decomposition
from data_utils import area_label, get_selected_area, load_fill_series

st.title("Seasonality in reservoir filling")
st.write("STL decomposition and spectrogram of the weekly fill ratio from NVE (all weeks since 1995).")

# The area is a global setting: this page uses the area chosen on the page "Reservoir data"
# (saved in st.session_state) instead of a local selector, since it is the same NVE data.
# The parameters for STL and the spectrogram are local, since they only matter on this page. STL and the spectrogram need the whole series, so the interval slider there is not used.
area_type, area_number = get_selected_area()
series = load_fill_series(area_type, area_number)

info, link = st.columns([3, 1])
info.info(
    f"Area: **{area_label(area_type, area_number)}**, {len(series)} weeks from "
    f"{series.index.min().date()} to {series.index.max().date()}."
)
link.page_link("pages/1_Reservoir_data.py", label="Change area", icon=":material/tune:")

stl_tab, spectrogram_tab = st.tabs(["STL decomposition", "Spectrogram"])

# ---------------------------------------------------------------- STL
with stl_tab:
    c1, c2, c3, c4 = st.columns(4)
    period = c1.slider("Period (weeks)", min_value=26, max_value=104, value=52,
                       help="Length of one season. 52 weeks = one year.")
    seasonal = c2.slider("Seasonal smoother", min_value=7, max_value=51, value=13, step=2,
                         help="Odd number. Lower values let the yearly pattern change faster from year to year.")
    # The trend smoother must be an odd number larger than the period
    trend_min = period + 1 if period % 2 == 0 else period + 2
    trend = c3.slider("Trend smoother (weeks)", min_value=trend_min, max_value=trend_min + 260,
                      value=max(105, trend_min), step=2, help="Odd number. Higher values give a smoother trend.")
    robust = c4.checkbox("Robust fitting", value=True,
                         help="Gives less weight to extreme weeks, so they end up in the remainder.")

    st.pyplot(stl_decomposition(series, period=period, seasonal=seasonal, trend=trend, robust=robust))

    with st.expander("How to read the plot"):
        st.markdown(
            """
            STL (Seasonal-Trend decomposition using LOESS) splits the fill ratio into
            **trend + seasonal + remainder**.
            - **Trend:** the slow change over several years.
            - **Seasonal:** the normal yearly pattern (low in spring before the snow melts, high in autumn).
            - **Remainder:** what is left, i.e. weeks that are unusual compared to a normal year.

            The trend at the very start and end of the series is less certain (edge effect).
            """
        )

# ---------------------------------------------------------------- spectrogram
with spectrogram_tab:
    c1, c2, c3 = st.columns(3)
    window_length = c1.slider("Window length (weeks)", min_value=26, max_value=260, value=104,
                              help="Must be longer than a year to see the yearly rhythm.")
    overlap = c2.slider("Overlap (weeks)", min_value=0, max_value=window_length - 1,
                        value=min(78, window_length - 1), help="Weeks shared by two neighbouring windows.")
    max_frequency = c3.slider("Highest frequency shown (cycles per year)", min_value=2, max_value=26, value=6)

    st.pyplot(filling_spectrogram(series, window_length=window_length, overlap=overlap,
                                  max_frequency=max_frequency))

    with st.expander("How to read the plot"):
        st.markdown(
            """
            The series is cut into overlapping windows, and the frequency content of each window is calculated.
            The x-axis is time, the y-axis is frequency in cycles per year, and the colour is the power.
            The yearly rhythm is at **1 cycle per year**. A longer window gives finer steps in frequency
            (1 / window length in years), but less detail in time.
            """
        )
