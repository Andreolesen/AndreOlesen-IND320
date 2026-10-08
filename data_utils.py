import pandas as pd
import requests
import streamlit as st

# NVE Magasinstatistikk API (replaces data/reservoirs.csv from part 1). No API key needed.
NVE_URL = "https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk/HentOffentligData"

# English column names 
COLUMN_NAMES = {
    "dato_Id": "date",
    "omrType": "area_type",
    "omrnr": "area_number",
    "fyllingsgrad": "fill_ratio",
    "kapasitet_TWh": "capacity_TWh",
    "fylling_TWh": "fill_TWh",
    "fyllingsgrad_forrige_uke": "fill_ratio_previous_week",
    "endring_fyllingsgrad": "fill_ratio_change",
}

DATA_COLUMNS = [
    "fill_ratio",
    "capacity_TWh",
    "fill_TWh",
    "fill_ratio_previous_week",
    "fill_ratio_change",
]


# Cached for one day: NVE publishes new data once a week (Wednesdays), so there is
# no need to call the API on every page load or widget change.
@st.cache_data(ttl="1d")
def load_all_reservoir_data():
    """
    Download all reservoir data (all areas: NO, EL, VASS) from the NVE API and clean it:
    - English column names, dropping ISO year/week (same info as the date) and
      neste_Publiseringsdato (contains the unparsable placeholder 0001-01-01).
    - Convert the date to datetime and sort chronologically within each area.
    """
    response = requests.get(NVE_URL, timeout=30)
    response.raise_for_status()  # Show an error in the app if the API call fails

    df = pd.DataFrame(response.json())
    df = df.rename(columns=COLUMN_NAMES)[list(COLUMN_NAMES.values())]
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["area_type", "area_number", "date"]).reset_index(drop=True)


@st.cache_data(ttl="1d")
def load_reservoir_data():
    """
    National total only (NO, area 0): one clean weekly time series, used by the
    data table and plot pages from part 1. Returns the data and the data columns.
    """
    df = load_all_reservoir_data()
    df_national = df[(df["area_type"] == "NO") & (df["area_number"] == 0)]
    return df_national[["date"] + DATA_COLUMNS].reset_index(drop=True), DATA_COLUMNS


# Readable labels for the data columns, shared by all pages so the names are
# the same everywhere. The internal column names stay unchanged.
column_display_names = {
    "fill_ratio": "Fill ratio",
    "capacity_TWh": "Capacity (TWh)",
    "fill_TWh": "Fill (TWh)",
    "fill_ratio_previous_week": "Fill ratio, previous week",
    "fill_ratio_change": "Fill ratio, week-over-week change",
}