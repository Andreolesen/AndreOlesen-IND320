import io
import json
import time
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
def load_key_figures(area_type, area_number, end_month):
    """
    Key figures for the Overview page: the last week of one area up to the end of the chosen period,
    with the change from the previous week and the "normal" for that week (median of the same ISO week
    in all earlier years).
    """
    df = load_all_reservoir_data()
    area = df[(df["area_type"] == area_type) & (df["area_number"] == area_number)].set_index("date").sort_index()
    area = area[area.index.strftime("%Y-%m") <= end_month]
    latest_date = area.index[-1]
    latest = area.iloc[-1]

    weeks = area.index.isocalendar().week
    week = latest_date.isocalendar().week
    earlier = area[(weeks == week).to_numpy() & (area.index.year < latest_date.year)]

    return {
        "date": latest_date,
        "week": int(week),
        "fill_ratio": float(latest["fill_ratio"]),
        "change_previous_week": float(latest["fill_ratio_change"]),
        "median_same_week": float(earlier["fill_ratio"].median()),
        "first_year": int(earlier.index.year.min()),
        "fill_TWh": float(latest["fill_TWh"]),
        "capacity_TWh": float(latest["capacity_TWh"]),
    }


@st.cache_data(ttl="1d")
def load_map_values(area_type, start_month, end_month):
    """
    Values for the map on the Overview page, one per area of the type (in %): the fill ratio in the last
    week of the period, and the change in fill ratio from the first to the last week of the period.
    """
    df = load_all_reservoir_data()
    month = df["date"].dt.strftime("%Y-%m")
    period = df[(df["area_type"] == area_type) & (month >= start_month) & (month <= end_month)].sort_values("date")
    first = period.groupby("area_number")["fill_ratio"].first()
    last = period.groupby("area_number")["fill_ratio"].last()
    return {"fill": (last * 100).to_dict(), "change": ((last - first) * 100).to_dict()}


# Readable names for the area types and area numbers
AREA_TYPE_LABELS = {
    "EL": "Price areas",
    "VASS": "Water areas",
    "NO": "Norway",
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
# Area chosen on the Overview page (map click). It is saved in st.session_state under "area_type" and
# "area_number", so all pages use the same area. Default is NO3, the same area as in the notebooks.
DEFAULT_AREA = ("EL", 3)


def get_selected_area():
    """The (area_type, area_number) chosen on the Overview page, or NO3 if nothing is chosen yet."""
    return (st.session_state.get("area_type", DEFAULT_AREA[0]),
            st.session_state.get("area_number", DEFAULT_AREA[1]))


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
# part 3 notebook (regions from NVE Atlas, sampled with geopandas) and saved as GeoJSON points in
# data/regions/region_locations.geojson (one feature per location, with the region as property).
LOCATIONS_PATH = Path(__file__).parent / "data" / "regions" / "region_locations.geojson"
WEATHER_URL = "https://archive-api.open-meteo.com/v1/archive"

# Hourly variables: (label, unit, how the hours are combined to a week or period)
WEATHER_VARIABLES = {
    "temperature_2m": ("Temperature", "°C", "mean"),
    "precipitation": ("Precipitation", "mm", "sum"),
    "rain": ("Rain", "mm", "sum"),
    "snowfall": ("Snowfall", "cm", "sum"),
    "relative_humidity_2m": ("Relative humidity", "%", "mean"),
    "wind_speed_10m": ("Wind speed", "km/h", "mean"),
    "cloud_cover": ("Cloud cover", "%", "mean"),
}

# How many of the 1000 locations are used. The feedback on part 3 was to use a larger sample, so the
# pages that look at the weather itself use 20 locations. One location for a year counts as about 26 API
# calls (limits: 600 per minute, 5000 per hour, 10 000 per day), so the forecast (10+ years) and the map
# (all areas at once) use 5: the part 4 notebook showed that 5 or 20 locations give almost the same
# forecast error (6.1 against 6.0 pp).
N_APP_LOCATIONS = 20
N_LIGHT_LOCATIONS = 5
SEED = 42
ERA5_GRID = 0.25  # degrees; two locations in the same ERA5 grid cell get identical values
FIRST_WEATHER_YEAR = 2000

# The weather locations are drawn per NVE region. A price area has its own points; a water area (VASS) uses the
# NVE regions it consists of (see map_utils.py), and Norway uses all price areas.
VASS_REGIONS = {1: ["RØ", "RS"], 2: ["RV"], 3: ["RM", "RN"]}


def weather_regions(area_type, area_number):
    """The location regions (as in region_locations.geojson) that make up one area."""
    if area_type == "EL":
        return [f"NO{area_number}"]
    if area_type == "VASS":
        return VASS_REGIONS[area_number]
    return [f"NO{n}" for n in range(1, 6)]


@st.cache_data
def load_locations():
    """The random locations (region, longitude, latitude) from the notebook, read from the GeoJSON file."""
    with open(LOCATIONS_PATH, encoding="utf-8") as f:
        features = json.load(f)["features"]
    return pd.DataFrame([
        {"region": feature["properties"]["region"],
         "longitude": feature["geometry"]["coordinates"][0],   # GeoJSON order is (longitude, latitude)
         "latitude": feature["geometry"]["coordinates"][1]}
        for feature in features
    ])


def area_locations(area_type, area_number, n_locations):
    """n random locations in the area, at most one per ERA5 grid cell (same idea as the part 4 notebook)."""
    locations = load_locations()
    points = locations[locations["region"].isin(weather_regions(area_type, area_number))]
    cells = points.assign(cell_lat=(points["latitude"] / ERA5_GRID).round(),
                          cell_lon=(points["longitude"] / ERA5_GRID).round())
    cells = cells.drop_duplicates(["cell_lat", "cell_lon"])
    return cells.sample(min(n_locations, len(cells)), random_state=SEED)


def get_weather_batch(locations, start, end, max_retries=3):
    """
    One API request for all locations. If open-meteo answers 429 (too many requests), its own reason says which
    limit is reached: only the per-minute limit is worth waiting for, so the request is tried again after a minute.
    For the hourly or daily limit an error with open-meteo's reason is raised at once, so the user does not wait.
    """
    params = {
        "latitude": ",".join(f"{lat:.4f}" for lat in locations["latitude"]),
        "longitude": ",".join(f"{lon:.4f}" for lon in locations["longitude"]),
        "start_date": start,
        "end_date": end,
        "hourly": ",".join(WEATHER_VARIABLES),
        "models": "era5",
        "timezone": "UTC",  # always UTC: open-meteo's own time zone conversion ignores summer time (notebook)
    }
    for attempt in range(max_retries):
        response = requests.get(WEATHER_URL, params=params, timeout=300)
        if response.status_code == 429:
            try:
                reason = response.json().get("reason", "API limit reached")
            except ValueError:
                reason = "API limit reached"
            if "minutely" in reason.lower() and attempt < max_retries - 1:
                time.sleep(65)  # the per-minute limit: wait a minute and try again
                continue
            raise WeatherLimitError(reason)  # e.g. "Daily API request limit exceeded. Please try again tomorrow."
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, list) else [data]  # one location gives a dict, several give a list
    raise WeatherLimitError("open-meteo's API limit is reached. Try again later.")


class WeatherLimitError(RuntimeError):
    """open-meteo refused the request because an API limit is reached (the message is open-meteo's reason)."""


# Cached for a week per area and date range. The ranges are cut at the turn of the year, so a full year in the
# middle of a period is cached as the same range whatever the period is, and can be reused for other periods.
@st.cache_data(ttl="7d", show_spinner=False)
def load_weather(area_type, area_number, start, end, n_locations=N_APP_LOCATIONS):
    """
    Hourly ERA5 weather for one area from start to end ("YYYY-MM-DD", UTC), averaged over n random locations
    in the area. Returns a DataFrame with the time as index and one column per weather variable.
    """
    results = get_weather_batch(area_locations(area_type, area_number, n_locations), start, end)
    frames = []
    for result in results:
        frame = pd.DataFrame(result["hourly"])
        frame["time"] = pd.to_datetime(frame["time"])
        frames.append(frame)
    weather = pd.concat(frames, ignore_index=True)

    # Average over the locations, hour by hour (same as in the notebook)
    return weather.groupby("time")[list(WEATHER_VARIABLES)].mean()


def load_weather_period(area_type, area_number, start_month, end_month, n_locations=N_APP_LOCATIONS):
    """
    Hourly weather for one area from the start of start_month to the end of end_month ("YYYY-MM").
    Only the months in the period are downloaded (not whole calendar years), one year at a time with a progress
    bar, since the first download of several years can take a minute.
    """
    start = max(pd.Timestamp(start_month), pd.Timestamp(f"{FIRST_WEATHER_YEAR}-01-01"))
    last_day = pd.Timestamp.today().normalize() - pd.Timedelta(days=7)  # ERA5 is a few days behind
    end = min(pd.Period(end_month).end_time.normalize(), last_day)
    years = range(start.year, end.year + 1)
    progress = st.progress(0.0, text="Downloading weather from open-meteo ...")
    frames = []
    try:
        for i, year in enumerate(years):
            progress.progress(i / len(years),
                              text=f"Downloading weather from open-meteo: {year} ({i + 1} of {len(years)})")
            part_start = max(start, pd.Timestamp(f"{year}-01-01"))
            part_end = min(end, pd.Timestamp(f"{year}-12-31"))
            frames.append(load_weather(area_type, area_number, part_start.strftime("%Y-%m-%d"),
                                       part_end.strftime("%Y-%m-%d"), n_locations))
    finally:
        progress.empty()
    return pd.concat(frames)


def to_weeks(hourly):
    """
    Hourly weather (UTC) to the same weeks as Magasinstatistikk: converted to Norwegian time first (pandas knows
    the summer-time rules), then weeks ending on Sunday. Means or sums per variable, as in WEATHER_VARIABLES.
    Weeks with less than 90 % of the hours (the ends of the period) are dropped.
    """
    local = hourly.copy()
    local.index = local.index.tz_localize("UTC").tz_convert("Europe/Oslo").tz_localize(None)
    weekly = local.resample("W-SUN").agg({column: how for column, (_, _, how) in WEATHER_VARIABLES.items()})
    hours = local.resample("W-SUN").size()
    return weekly[hours >= 0.9 * 168]


# ---------------------------------------------------------------------------
# Weekly weather for all areas, prepared in the part 4 notebook and stored in MongoDB (collection weather_weekly),
# so the pages never wait for open-meteo or run into its API limits. The data go up to the day the notebook was
# last run (in a real app a scheduled job would add the new weeks). 5 locations per area (N_LIGHT_LOCATIONS),
# chosen exactly like area_locations() above.
@st.cache_data(ttl="1d", show_spinner=False)
def load_stored_weekly_weather(area_type, area_number):
    """The weekly weather for one area from MongoDB (empty DataFrame if nothing is stored)."""
    cursor = get_mongo_client()["ind320"]["weather_weekly"].find(
        {"area_type": area_type, "area_number": int(area_number)}, {"_id": 0, "area_type": 0, "area_number": 0})
    weekly = pd.DataFrame(list(cursor))
    return weekly.set_index("date").sort_index() if not weekly.empty else weekly


def load_weekly_weather(area_type, area_number, start_month, end_month):
    """
    Weekly weather (NVE weeks) for one area and period from MongoDB. Only if nothing is stored for the area, or
    MongoDB cannot be reached, the weather is downloaded directly from open-meteo instead (slower).
    """
    try:
        weekly = load_stored_weekly_weather(area_type, area_number)
    except Exception:  # no connection to MongoDB (e.g. no secrets)
        weekly = pd.DataFrame()
    if weekly.empty:
        weekly = to_weeks(load_weather_period(area_type, area_number, start_month, end_month, N_LIGHT_LOCATIONS))
    return weekly.loc[pd.Timestamp(start_month):pd.Period(end_month).end_time]


# ---------------------------------------------------------------------------
# Exchange rates from Norges Bank (same function as in the part 4 notebook). No API key needed.
NB_URL = "https://data.norges-bank.no/api/data/EXR"


@st.cache_data(ttl="1d", show_spinner="Downloading exchange rates from Norges Bank ...")
def load_exchange_rates(start, end, currencies=("EUR", "USD")):
    """Daily exchange rates (NOK per 1 unit of currency) from Norges Bank, one column per currency."""
    key = f"B.{'+'.join(currencies)}.NOK.SP"
    params = {"format": "csv", "startPeriod": start, "endPeriod": end, "locale": "en"}
    response = requests.get(f"{NB_URL}/{key}", params=params, timeout=60)
    response.raise_for_status()
    raw = pd.read_csv(io.StringIO(response.text), sep=None, engine="python")
    rates = raw.pivot(index="TIME_PERIOD", columns="BASE_CUR", values="OBS_VALUE")
    rates.index = pd.to_datetime(rates.index)
    rates.index.name = "date"
    rates.columns.name = None
    return rates.astype(float)
