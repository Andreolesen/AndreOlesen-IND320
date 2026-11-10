import time
from datetime import date
from pathlib import Path

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


@st.cache_data(ttl="1d")
def load_month_labels():
    """All months in the NVE data as "YYYY-MM" labels, used as options for the interval slider."""
    df = load_all_reservoir_data()
    return sorted(df["date"].dt.strftime("%Y-%m").unique())


@st.cache_data(ttl="1d")
def load_reservoir_interval(area_type, start_month, end_month):
    """
    The data for one area type (NO, EL or VASS) in the chosen interval of months.
    The NVE API has no date parameters, so the full response is downloaded once (cached for a day)
    and only the chosen interval and area type are kept. The result is cached per interval.
    """
    df = load_all_reservoir_data()
    month = df["date"].dt.strftime("%Y-%m")
    selected = df[(df["area_type"] == area_type) & (month >= start_month) & (month <= end_month)]
    return selected.reset_index(drop=True)


@st.cache_data(ttl="1d")
def load_national_key_figures():
    """
    Key figures for the home page: the latest week for the whole country (NO), compared with the
    previous week, the same week last year and the median for the same week in earlier years.
    """
    df = load_all_reservoir_data()
    national = df[(df["area_type"] == "NO") & (df["area_number"] == 0)].set_index("date").sort_index()
    latest_date = national.index[-1]
    latest = national.iloc[-1]

    # Same week last year: 52 weeks (364 days) earlier, or the closest week if that date is missing
    last_year = national.iloc[national.index.get_indexer([latest_date - pd.Timedelta(days=364)], method="nearest")[0]]

    # "Normal" for this time of year: median of the same ISO week in all earlier years
    weeks = national.index.isocalendar().week
    week = latest_date.isocalendar().week
    earlier = national[(weeks == week).to_numpy() & (national.index.year < latest_date.year)]

    return {
        "date": latest_date,
        "week": int(week),
        "fill_ratio": float(latest["fill_ratio"]),
        "change_previous_week": float(latest["fill_ratio_change"]),
        "fill_ratio_last_year": float(last_year["fill_ratio"]),
        "median_same_week": float(earlier["fill_ratio"].median()),
        "first_year": int(earlier.index.year.min()),
        "fill_TWh": float(latest["fill_TWh"]),
        "capacity_TWh": float(latest["capacity_TWh"]),
    }


# Readable names for the area types and area numbers
AREA_TYPE_LABELS = {
    "NO": "Norway (whole country)",
    "EL": "Price areas (EL, NO1-NO5)",
    "VASS": "Watercourse areas (VASS)",
}


def area_label(area_type, area_number):
    """Readable name for one area, e.g. "NO2" for price area 2."""
    if area_type == "NO":
        return "Norway"
    if area_type == "EL":
        return f"NO{area_number}"
    return f"VASS {area_number}"


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


# ---------------------------------------------------------------------------
# Area chosen on the page "Reservoir data". It is saved in st.session_state, so the
# analysis pages use the same area. Default is NO3, the same area as in the notebook.
DEFAULT_AREA = ("EL", 3)


def get_selected_area():
    """The (area_type, area_number) chosen on the reservoir page, or NO3 if nothing is chosen yet."""
    return st.session_state.get("selected_area", DEFAULT_AREA)


@st.cache_data(ttl="1d")
def load_area_numbers(area_type):
    """The area numbers that have data for one area type (e.g. 1-5 for EL)."""
    df = load_all_reservoir_data()
    return sorted(df.loc[df["area_type"] == area_type, "area_number"].unique().tolist())


@st.cache_data(ttl="1d")
def load_fill_series(area_type, area_number):
    """Weekly fill ratio for one area as a Series with the date as index (used by STL and the spectrogram)."""
    df = load_all_reservoir_data()
    area = df[(df["area_type"] == area_type) & (df["area_number"] == area_number)]
    return area.set_index("date")["fill_ratio"].sort_index()


# ---------------------------------------------------------------------------
# Weather data from open-meteo (ERA5). The 1000 random locations per region are made in the
# part 3 notebook (regions from NVE Atlas, sampled with geopandas) and saved in data/region_locations.csv.
LOCATIONS_PATH = Path(__file__).parent / "data" / "region_locations.csv"
WEATHER_URL = "https://archive-api.open-meteo.com/v1/archive"
WEATHER_VARIABLES = [
    "temperature_2m",
    "precipitation",
    "rain",
    "snowfall",
    "relative_humidity_2m",
    "wind_speed_10m",
    "cloud_cover",
]
# Only a few of the 1000 locations are used in the app. One location for a whole year counts as about
# 26 API calls, so 5 locations (about 130 calls) stays far below the limits of open-meteo
# (600 per minute, 5000 per hour, 10 000 per day). The notebook uses 50.
N_APP_LOCATIONS = 5
SEED = 42
FIRST_WEATHER_YEAR = 2000
LAST_WEATHER_YEAR = date.today().year - 1  # last complete year


@st.cache_data
def load_locations():
    """The random locations (region, longitude, latitude) from the notebook."""
    return pd.read_csv(LOCATIONS_PATH)


def get_weather_batch(locations, start, end, max_retries=3):
    """One API request for a few locations. Waits and tries again if the API says the limit is reached."""
    params = {
        "latitude": ",".join(f"{lat:.4f}" for lat in locations["latitude"]),
        "longitude": ",".join(f"{lon:.4f}" for lon in locations["longitude"]),
        "start_date": start,
        "end_date": end,
        "hourly": ",".join(WEATHER_VARIABLES),
        "models": "era5",
        "timezone": "UTC",
    }
    for attempt in range(max_retries):
        response = requests.get(WEATHER_URL, params=params, timeout=300)
        if response.status_code == 429:  # too many requests: wait a minute and try again
            time.sleep(65)
            continue
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else [data]  # one location gives a dict, several give a list
    raise RuntimeError("open-meteo refused the request (API limit reached). Try again later.")


# Cached per region and year (for a week): the archive data for a finished year does not change,
# and the same choice should not use the API again.
@st.cache_data(ttl="7d", show_spinner="Downloading weather data from open-meteo ...")
def load_weather(region, year, n_locations=N_APP_LOCATIONS):
    """
    Hourly ERA5 weather for one region (e.g. "NO3") and year, averaged over n random locations.
    Returns a DataFrame with the time as index and one column per weather variable.
    """
    locations = load_locations()
    region_locations = locations[locations["region"] == region]
    region_locations = region_locations.sample(n_locations, random_state=SEED)

    results = get_weather_batch(region_locations, f"{year}-01-01", f"{year}-12-31")
    frames = []
    for result in results:
        frame = pd.DataFrame(result["hourly"])
        frame["time"] = pd.to_datetime(frame["time"])
        frames.append(frame)
    weather = pd.concat(frames, ignore_index=True)

    # Average over the locations, hour by hour (same as in the notebook)
    return weather.groupby("time")[WEATHER_VARIABLES].mean()
