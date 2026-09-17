from pathlib import Path
import math

import pandas as pd
import pydeck as pdk
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent

STORE_FILE = BASE_DIR / "Migros_and_competitors_stores_CH.csv"
POPULATION_FILE = BASE_DIR / "population_cells.parquet"

st.set_page_config(
    page_title="Multi-Radius Location Viewer",
    layout="wide",
)

st.title("📍 Multi-Radius Location Viewer")


CIRCLE_COLORS = [
    [220, 20, 60, 45],
    [30, 90, 200, 45],
    [40, 160, 80, 45],
    [130, 60, 180, 45],
    [240, 140, 20, 45],
    [170, 30, 30, 45],
    [40, 150, 170, 45],
]

POPULATION_COLORS = [
    [255, 255, 204],
    [255, 237, 160],
    [254, 217, 118],
    [254, 178, 76],
    [253, 141, 60],
    [240, 59, 32],
    [189, 0, 38],
]


@st.cache_data(show_spinner=False)
def load_stores() -> pd.DataFrame:
    df = pd.read_csv(STORE_FILE)

    required = {
        "display_name",
        "latitude",
        "longitude",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"Missing columns: {', '.join(sorted(missing))}"
        )

    if "radius_km" not in df.columns:
        df["radius_km"] = 5.0

    for column in [
        "latitude",
        "longitude",
        "radius_km",
    ]:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df = df.dropna(
        subset=[
            "display_name",
            "latitude",
            "longitude",
        ]
    ).copy()

    df["radius_km"] = (
        df["radius_km"]
        .fillna(5.0)
        .clip(0.5, 20.0)
    )

    return df.reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_population() -> pd.DataFrame:

    if not POPULATION_FILE.exists():
        raise FileNotFoundError(
            "population_cells.parquet is missing. "
            "Run prepare_population.py first."
        )

    df = pd.read_parquet(POPULATION_FILE)

    required = {
        "latitude",
        "longitude",
        "population",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            "Missing population columns: "
            + ", ".join(sorted(missing))
        )

    df = df[
        [
            "latitude",
            "longitude",
            "population",
        ]
    ].copy()

    df["population"] = pd.to_numeric(
        df["population"],
        errors="coerce",
    ).fillna(0)

    df = df[df["population"] > 0]

    return df.reset_index(drop=True)


def build_view_state(df: pd.DataFrame) -> pdk.ViewState:

    latitude = float(df["latitude"].mean())
    longitude = float(df["longitude"].mean())

    lat_span = (
        df["latitude"].max()
        - df["latitude"].min()
    )

    lon_span = (
        df["longitude"].max()
        - df["longitude"].min()
    )

    span = max(
        float(lat_span),
        float(lon_span),
        0.05,
    )

    zoom = max(
        5.0,
        min(
            13.0,
            math.log2(360.0 / span) - 1.5,
        ),
    )

    return pdk.ViewState(
        latitude=latitude,
        longitude=longitude,
        zoom=zoom,
        pitch=0,
        bearing=0,
    )


try:
    stores = load_stores()
    population = load_population()

except (FileNotFoundError, ValueError, OSError) as exc:
    st.error(str(exc))
    st.stop()


# -----------------------------
# Sidebar
# -----------------------------

st.sidebar.header("⚙️ Radius Settings")

use_custom = st.sidebar.checkbox(
    "Customize individual radii",
    value=False,
)


if "radii" not in st.session_state:
    st.session_state.radii = (
        stores["radius_km"]
        .astype(float)
        .to_dict()
    )


if use_custom:

    with st.sidebar.form(
        "radius_form",
        border=False,
    ):

        proposed_radii = {}

        for idx, row in stores.iterrows():

            proposed_radii[idx] = st.slider(
                f"{row['display_name']} (km)",
                min_value=0.5,
                max_value=20.0,
                value=float(
                    st.session_state.radii.get(
                        idx,
                        row["radius_km"],
                    )
                ),
                step=0.5,
                key=f"radius_slider_{idx}",
            )

        apply_radii = st.form_submit_button(
            "Apply radii",
            use_container_width=True,
        )

        if apply_radii:
            st.session_state.radii = proposed_radii

else:

    st.session_state.radii = (
        stores["radius_km"]
        .astype(float)
        .to_dict()
    )


# -----------------------------
# Store data
# -----------------------------

store_map = stores.copy()

store_map["radius_km"] = [
    st.session_state.radii.get(
        idx,
        float(row.radius_km),
    )
    for idx, row in store_map.iterrows()
]

store_map["radius_m"] = (
    store_map["radius_km"] * 1000
)

store_map["color"] = [
    CIRCLE_COLORS[
        i % len(CIRCLE_COLORS)
    ]
    for i in range(len(store_map))
]

store_map["tooltip"] = store_map.apply(
    lambda r:
        f"{r['display_name']} — "
        f"Radius: {r['radius_km']:.1f} km",
    axis=1,
)


# -----------------------------
# Population layer
# -----------------------------

population_layer = pdk.Layer(
    "HeatmapLayer",
    data=population,
    id="population-heatmap",
    get_position=[
        "longitude",
        "latitude",
    ],
    get_weight="population",
    radius_pixels=20,
    intensity=1.2,
    threshold=0.03,
    opacity=0.65,
    color_range=POPULATION_COLORS,
)


# -----------------------------
# Radius circles
# -----------------------------

radius_layer = pdk.Layer(
    "ScatterplotLayer",
    data=store_map,
    id="store-radii",
    get_position=[
        "longitude",
        "latitude",
    ],
    get_radius="radius_m",
    get_fill_color="color",
    get_line_color="color",
    stroked=True,
    filled=True,
    line_width_min_pixels=2,
    radius_min_pixels=2,
    radius_max_pixels=1000,
    pickable=True,
)


# -----------------------------
# Store markers
# -----------------------------

marker_map = store_map.copy()

marker_map["marker_color"] = [
    [210, 25, 25, 240]
] * len(marker_map)


marker_layer = pdk.Layer(
    "ScatterplotLayer",
    data=marker_map,
    id="store-markers",
    get_position=[
        "longitude",
        "latitude",
    ],
    get_radius=80,
    get_fill_color="marker_color",
    get_line_color=[
        255,
        255,
        255,
        255,
    ],
    radius_min_pixels=5,
    radius_max_pixels=14,
    line_width_min_pixels=2,
    stroked=True,
    filled=True,
    pickable=True,
    auto_highlight=True,
)


# -----------------------------
# Build map
# -----------------------------

deck = pdk.Deck(
    layers=[
        population_layer,
        radius_layer,
        marker_layer,
    ],
    initial_view_state=build_view_state(
        store_map
    ),
    map_style=None,
    tooltip={
        "text": "{tooltip}"
    },
)


# -----------------------------
# Layout
# -----------------------------

col1, col2 = st.columns(
    [3, 2]
)

with col1:

    st.pydeck_chart(
        deck,
        width="stretch",
        height=600,
    )


with col2:

    st.subheader(
        "📋 Locations & Radii"
    )

    st.dataframe(
        store_map[
            [
                "display_name",
                "radius_km",
                "latitude",
                "longitude",
            ]
        ].rename(
            columns={
                "display_name": "Location",
                "radius_km": "Radius (km)",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        f"{len(store_map):,} locations · "
        f"{len(population):,} population cells"
    )