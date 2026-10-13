import pandas as pd
import requests
import streamlit as st
from pymongo import MongoClient

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




# st.cache_resource (not cache_data): the client is a connection object that should be
# created once and shared across reruns, not copied like data.
@st.cache_resource
def get_mongo_client():
    """Connect to MongoDB Atlas. The URI is read from st.secrets
    locally from .streamlit/secrets.toml"""
    return MongoClient(st.secrets["mongo"]["uri"])



# ---------------------------------------------------------------------------
# Cross-border flows (ENTSO-E). The data is prepared in the notebook (Cassandra + Spark)
# and stored in MongoDB, collection ind320.cross_border_flows: one document per hour,
# connection and direction, with the fields connection, direction, time, year, month, mwh.

# Readable names for the connections, shown in the app instead of the codes
CONNECTION_NAMES = {
    "NO1-SE3": "NO1 - Sweden SE3",
    "NO2-DK1": "NO2 - Denmark DK1 (Skagerrak)",
    "NO2-NL": "NO2 - Netherlands (NorNed)",
    "NO2-DE-LU": "NO2 - Germany (NordLink)",
    "NO2-GB": "NO2 - Great Britain (North Sea Link)",
    "NO3-SE2": "NO3 - Sweden SE2",
    "NO4-SE1": "NO4 - Sweden SE1",
    "NO4-SE2": "NO4 - Sweden SE2",
    "NO4-FI": "NO4 - Finland",
}


def get_flows_collection():
    """The MongoDB collection with the hourly cross-border flows."""
    return get_mongo_client()["ind320"]["cross_border_flows"]


# The data in MongoDB only changes when I run the notebook again, so caching for a day is fine
@st.cache_data(ttl="1d")
def load_flow_options():
    """Connections and years that exist in MongoDB, used to fill the widgets."""
    collection = get_flows_collection()
    return sorted(collection.distinct("connection")), sorted(collection.distinct("year"))


@st.cache_data(ttl="1d")
def load_yearly_totals(connection, year):
    """Total energy (TWh) per direction for one connection and year.
    The sum is done in MongoDB (aggregation pipeline), so only two numbers are sent to the app."""
    pipeline = [
        {"$match": {"connection": connection, "year": year}},
        {"$group": {"_id": "$direction", "mwh": {"$sum": "$mwh"}}},
    ]
    result = list(get_flows_collection().aggregate(pipeline))
    return {row["_id"]: row["mwh"] / 1e6 for row in result}


@st.cache_data(ttl="1d")
def load_month_flows(connection, year, month):
    """Hourly flows for one connection and month, as a DataFrame (time, direction, mwh)."""
    cursor = get_flows_collection().find(
        {"connection": connection, "year": year, "month": month},
        {"_id": 0, "time": 1, "direction": 1, "mwh": 1},
    )
    return pd.DataFrame(list(cursor))
