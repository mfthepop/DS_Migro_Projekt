"""Multi-Radius Location Viewer.

Optimised for Streamlit Community Cloud and Heroku:
  * the CSV is parsed once and cached
  * the Folium map is built once per (data, radius, view) combination and cached
    as a plain HTML string
  * the HTML is injected with components.html, so panning/zooming the map never
    triggers a Streamlit rerun
  * all points are rendered as two GeoJSON layers instead of 2*N Python objects
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Multi-Radius Location Viewer", layout="wide")

DATA_FILE = Path(__file__).with_name("Migros_and_competitors_stores_CH.csv")
DEFAULT_RADIUS_KM = 5.0
MAP_HEIGHT = 560
CIRCLE_COLORS = [
    "crimson", "blue", "green", "purple", "orange", "darkred", "cadetblue",
]

# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #


@st.cache_data(show_spinner="Loading stores…")
def load_data(path: str, mtime: float) -> pd.DataFrame:
    """Read the store CSV. `mtime` is only part of the cache key."""
    df = pd.read_csv(
        path,
        dtype={"display_name": "string"},
        engine="pyarrow" if _has_pyarrow() else "c",
    )

    missing = {"display_name", "latitude", "longitude"} - set(df.columns)
    if missing:
        raise ValueError(f"CSV is missing required column(s): {sorted(missing)}")

    if "radius_km" not in df.columns:
        df["radius_km"] = DEFAULT_RADIUS_KM

    # Vectorised cleanup — no iterrows anywhere in this file.
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["radius_km"] = pd.to_numeric(df["radius_km"], errors="coerce").fillna(
        DEFAULT_RADIUS_KM
    )
    df = df.dropna(subset=["latitude", "longitude"]).reset_index(drop=True)

    df["color"] = [CIRCLE_COLORS[i % len(CIRCLE_COLORS)] for i in range(len(df))]
    return df


def _has_pyarrow() -> bool:
    try:
        import pyarrow  # noqa: F401
    except ImportError:
        return False
    return True


# --------------------------------------------------------------------------- #
# Map
# --------------------------------------------------------------------------- #


def to_geojson(df: pd.DataFrame) -> str:
    """Build a FeatureCollection as a JSON string (a stable cache key)."""
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "display_name": name,
                "radius_km": round(float(km), 2),
                "radius_m": float(km) * 1000.0,
                "color": color,
            },
        }
        for name, lat, lon, km, color in zip(
            df["display_name"].astype(str),
            df["latitude"],
            df["longitude"],
            df["radius_km"],
            df["color"],
        )
    ]
    return json.dumps({"type": "FeatureCollection", "features": features})


@st.cache_data(show_spinner="Rendering map…", max_entries=8)
def build_map_html(geojson_str: str, height: int) -> str:
    """Return fully rendered Leaflet HTML. Cached on the GeoJSON payload."""
    import folium  # imported lazily so a cache hit costs nothing

    data = json.loads(geojson_str)
    coords = [f["geometry"]["coordinates"] for f in data["features"]]
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]

    m = folium.Map(
        tiles="OpenStreetMap",  # CartoDB basemaps now need an API key
        prefer_canvas=True,  # canvas renderer: much faster above ~500 shapes
        control_scale=True,
    )
    if coords:
        m.fit_bounds([[min(lats), min(lons)], [max(lats), max(lons)]])
    else:
        m.location = [46.8, 8.23]  # Switzerland
        m.zoom_start = 8

    tooltip_fields = ["display_name", "radius_km"]

    # Layer 1: catchment circles (metres, so they scale with zoom).
    folium.GeoJson(
        data,
        name="Radius",
        marker=folium.Circle(fill=True, fill_opacity=0.15, weight=1),
        style_function=lambda feat: {
            "radius": feat["properties"]["radius_m"],
            "color": feat["properties"]["color"],
            "fillColor": feat["properties"]["color"],
        },
        tooltip=folium.GeoJsonTooltip(
            fields=tooltip_fields, aliases=["Store", "Radius (km)"]
        ),
    ).add_to(m)

    # Layer 2: centre dots. CircleMarker instead of folium.Icon — an Icon is a
    # DOM element per store, a CircleMarker is a canvas draw call.
    folium.GeoJson(
        data,
        name="Stores",
        marker=folium.CircleMarker(
            radius=4, color="#111", weight=1, fill=True, fill_color="#fff",
            fill_opacity=1,
        ),
        tooltip=folium.GeoJsonTooltip(
            fields=tooltip_fields, aliases=["Store", "Radius (km)"]
        ),
        popup=folium.GeoJsonPopup(
            fields=tooltip_fields, aliases=["Store", "Radius (km)"]
        ),
    ).add_to(m)

    folium.LayerControl(collapsed=True).add_to(m)

    m.get_root().height = f"{height}px"
    return m.get_root().render()


# --------------------------------------------------------------------------- #
# App
# --------------------------------------------------------------------------- #

st.title("📍 Multi-Radius Location Viewer")

if not DATA_FILE.exists():
    st.error(f"'{DATA_FILE.name}' is missing from the app directory.")
    st.stop()

base = load_data(str(DATA_FILE), DATA_FILE.stat().st_mtime)

with st.sidebar:
    st.header("⚙️ Radius settings")
    global_radius = st.slider(
        "Radius for all stores (km)", 0.5, 20.0, DEFAULT_RADIUS_KM, 0.5
    )
    customise = st.checkbox("Customise individual radiuses", value=False)
    st.caption(f"{len(base):,} stores loaded")

df = base.copy()
df["radius_km"] = global_radius

if customise:
    # ONE widget for N rows instead of N sliders. Edits are kept in session
    # state so they survive reruns.
    st.subheader("✏️ Per-store radius")
    edited = st.data_editor(
        df[["display_name", "radius_km", "latitude", "longitude"]],
        column_config={
            "radius_km": st.column_config.NumberColumn(
                "Radius (km)", min_value=0.5, max_value=20.0, step=0.5
            ),
            "display_name": st.column_config.TextColumn("Store", disabled=True),
            "latitude": st.column_config.NumberColumn(disabled=True, format="%.5f"),
            "longitude": st.column_config.NumberColumn(disabled=True, format="%.5f"),
        },
        hide_index=True,
        use_container_width=True,
        height=320,
        key="radius_editor",
    )
    df["radius_km"] = edited["radius_km"].to_numpy()

col1, col2 = st.columns([3, 2], gap="medium")

with col1:
    html = build_map_html(to_geojson(df), MAP_HEIGHT)
    components.html(html, height=MAP_HEIGHT, scrolling=False)

with col2:
    st.subheader("📋 Locations & radiuses")
    st.dataframe(
        df[["display_name", "radius_km", "latitude", "longitude"]],
        hide_index=True,
        use_container_width=True,
        height=MAP_HEIGHT - 60,
    )
    st.download_button(
        "⬇️ Download current radiuses (CSV)",
        df[["display_name", "radius_km", "latitude", "longitude"]].to_csv(index=False),
        file_name="store_radiuses.csv",
        mime="text/csv",
    )
