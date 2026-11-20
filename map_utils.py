"""
The map on the Overview page: the NVE areas as GeoJSON polygons, coloured with Plotly.

The polygons come from NVE's map services (part 3) and are kept in data/regions/. The map has no background
map (no roads or place names): only the areas are drawn, straight on the page background.
"""
import json
from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from data_utils import VASS_REGIONS, area_label
from ui_utils import FJORD

REGIONS_DIR = Path(__file__).parent / "data" / "regions"

# The NVE map layers have the price areas, but not the water areas (VASS) used by Magasinstatistikk.
# NVE describes VASS1 as south-east Norway (Østlandet, Agder and parts of Rogaland) = regions Øst + Sør,
# VASS2 as west Norway = region Vest, and VASS3 as Mid-Norway. VASS4 (North Norway) has no data in
# Magasinstatistikk, and the capacity of VASS3 matches NO3 + NO4, so the north is part of VASS3.
# The mapping is VASS_REGIONS in data_utils.py, since the weather locations use it too.


def _polygons(geometry):
    """The polygons of a GeoJSON geometry as a list (a Polygon gives one, a MultiPolygon several)."""
    return [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]


def _clockwise(polygon):
    """Plotly's geo maps (d3) want the outer ring clockwise and holes counter-clockwise. The NVE files use the
    opposite order, which makes d3 fill the whole globe except the area, so the rings are turned if needed."""
    rings = []
    for i, ring in enumerate(polygon):
        area = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:]))  # < 0 means clockwise
        rings.append(ring if (area < 0) == (i == 0) else ring[::-1])
    return rings


def _feature(number, polygons):
    """One map feature: an area number and its polygons."""
    return {"type": "Feature", "properties": {"number": number},
            "geometry": {"type": "MultiPolygon", "coordinates": [_clockwise(p) for p in polygons]}}


@st.cache_data
def load_area_geojson(area_type):
    """GeoJSON with one feature per area of the type (EL, VASS or NO), with the area number as property."""
    with open(REGIONS_DIR / "nve_electricity_areas.geojson", encoding="utf-8") as f:
        price_areas = json.load(f)["features"]
    if area_type == "EL":  # "NO 3" -> 3
        features = [_feature(int(f["properties"]["budomr"].split()[-1]), _polygons(f["geometry"])) for f in price_areas]
    elif area_type == "NO":  # the whole country = all price areas together
        features = [_feature(0, [p for f in price_areas for p in _polygons(f["geometry"])])]
    else:
        with open(REGIONS_DIR / "nve_precipitation_areas.geojson", encoding="utf-8") as f:
            regions = json.load(f)["features"]
        features = [
            _feature(number, [p for f in regions if f["properties"]["REGION"] in codes for p in _polygons(f["geometry"])])
            for number, codes in VASS_REGIONS.items()
        ]
    return {"type": "FeatureCollection", "features": features}


def area_map(area_type, values, selected_number, title):
    """
    Map of the areas of one type, coloured by values ({area number: value in %}). The selected area gets a
    thick outline in the main colour. Clicking an area selects it (handled on the Overview page).
    """
    geojson = load_area_geojson(area_type)
    numbers = [f["properties"]["number"] for f in geojson["features"]]
    names = [area_label(area_type, n) for n in numbers]
    fig = go.Figure()
    fig.add_trace(go.Choropleth(
        geojson=geojson, featureidkey="properties.number", locations=numbers,
        z=[values.get(n) for n in numbers], text=names,
        hovertemplate="<b>%{text}</b><br>" + title + ": %{z:.1f}<extra></extra>",
        colorscale=[[0, "#DCE6EB"], [1, FJORD]], marker_opacity=0.85,
        marker_line_color="#FFFFFF", marker_line_width=1,
        colorbar=dict(title=dict(text=title, side="right"), thickness=10, len=0.45, x=0.92, outlinewidth=0),
    ))
    # The outline of the selected area is drawn as a second, transparent layer on top,
    # so the thin white borders of the neighbours do not cover it
    fig.add_trace(go.Choropleth(
        geojson=geojson, featureidkey="properties.number", locations=[selected_number], z=[0],
        colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]], showscale=False,
        marker_line_color=FJORD, marker_line_width=3.5, hoverinfo="skip",
    ))
    fig.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)", projection_type="mercator")
    fig.update_layout(height=640, margin=dict(l=0, r=0, t=0, b=0), dragmode=False)
    return fig
