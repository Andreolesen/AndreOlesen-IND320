# AndreOlesen-IND320

Project work in IND320 Data to Decision (NMBU), autumn 2026: Norwegian hydropower reservoirs, cross-border
electricity flows, weather and exchange rates, analysed in Jupyter notebooks and presented in a Streamlit app.

- Streamlit app: https://andreolesen-ind320.streamlit.app/
- Screencasts for each part: `screencast/`

## Notebooks (`Notebooks/`)

| Notebook | Content |
|---|---|
| `IND320_part1.ipynb` | Dashboard basics: exploring the reservoir data (reservoirs.csv) and the first Streamlit app |
| `ind320_part2.ipynb` | The NVE Magasinstatistikk API instead of the CSV file, and cross-border flows from ENTSO-E through Cassandra/Spark into MongoDB Atlas |
| `IND320_part3.ipynb` | Regions from NVE Atlas, random locations, weather from open-meteo (ERA5), outliers (DCT + SPC) and anomalies (LOF), STL and spectrogram |
| `IND320_part4.ipynb` | Exchange rates from Norges Bank, time zones in the four sources, reservoir forecast with River (SNARIMAX and a lag model), weekly weather for all areas stored in MongoDB, sketch of the app and sliding window correlation |

## Data sources

| Source | Used for | How the app gets it |
|---|---|---|
| NVE Magasinstatistikk API | Weekly reservoir filling per price area, water area and Norway | Directly, cached for a day |
| ENTSO-E Transparency Platform | Hourly cross-border flows | MongoDB (prepared in part 2) |
| open-meteo, ERA5 | Hourly weather for random locations in each area | Weekly values from MongoDB (prepared in the part 4 notebook); the Weather outliers page downloads hourly data directly, cached for a week |
| Norges Bank API | Daily EUR and USD exchange rates | Directly, cached for a day |
| NVE Atlas | Polygons of the price areas and precipitation regions, random locations | `data/regions/` (GeoJSON) |

The weather is prepared in the notebook because open-meteo has hourly and daily limits, and downloading years of
weather while the user waits would make the app slow. In a real app, that notebook cell would be a scheduled job.

## Repository structure

```
streamlit_app.py        menu (st.navigation) and global choices
app_pages/              one file per page: overview, reservoir data, cross-border flows, exchange rates,
                        seasonality, weather outliers, weather vs reservoir, reservoir forecast
data_utils.py           loading and caching of all data (NVE, MongoDB, open-meteo, Norges Bank)
analysis_utils.py       outliers, anomalies, STL and spectrogram
forecast_utils.py       reservoir forecast with River
map_utils.py            map of the areas from the GeoJSON files
ui_utils.py             theme colours, Plotly template, page header and the area/period popover
.streamlit/config.toml  the "Fjord" theme
data/regions/           GeoJSON files used by the app (in git)
data/cache/             downloads from the notebooks (not in git)
Notebooks/              the four notebooks and images/ with the app sketch
```

## Run locally

```
pip install -r requirements.txt
streamlit run streamlit_app.py
```

The app needs `.streamlit/secrets.toml` with the MongoDB URI (not included in the repository).
