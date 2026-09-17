from pathlib import Path

import numpy as np
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

st.title("📍 Population Coverage Viewer")


# ---------------------------------------------------------
# Load data
# ---------------------------------------------------------

@st.cache_data(show_spinner=False)
def load_stores():

    df = pd.read_csv(STORE_FILE)

    if "radius_km" not in df.columns:
        df["radius_km"] = 5.0

    required = [
        "display_name",
        "latitude",
        "longitude",
    ]

    missing = [
        col for col in required
        if col not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing columns: {missing}"
        )

    df["latitude"] = pd.to_numeric(
        df["latitude"],
        errors="coerce",
    )

    df["longitude"] = pd.to_numeric(
        df["longitude"],
        errors="coerce",
    )

    df = df.dropna(
        subset=[
            "latitude",
            "longitude",
        ]
    )

    return df.reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_population():

    df = pd.read_parquet(POPULATION_FILE)

    required = [
        "latitude",
        "longitude",
        "population",
    ]

    missing = [
        col for col in required
        if col not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing population columns: {missing}"
        )

    df["latitude"] = pd.to_numeric(
        df["latitude"],
        errors="coerce",
    )

    df["longitude"] = pd.to_numeric(
        df["longitude"],
        errors="coerce",
    )

    df["population"] = pd.to_numeric(
        df["population"],
        errors="coerce",
    ).fillna(0)

    df = df.dropna(
        subset=[
            "latitude",
            "longitude",
        ]
    )

    df = df[df["population"] > 0]

    return df.reset_index(drop=True)


stores = load_stores()
population = load_population()


# ---------------------------------------------------------
# Radius
# ---------------------------------------------------------

st.sidebar.header("⚙️ Coverage Settings")

radius_km = st.sidebar.slider(
    "Radius for all locations",
    min_value=0.5,
    max_value=20.0,
    value=5.0,
    step=0.5,
)


# ---------------------------------------------------------
# Calculate population coverage
# ---------------------------------------------------------

def find_uncovered_population(
    population,
    stores,
    radius_km,
):
    """
    Return only population cells that are outside
    the radius of EVERY store.
    """

    pop_lat = np.radians(
        population["latitude"].to_numpy()
    )

    pop_lon = np.radians(
        population["longitude"].to_numpy()
    )

    store_lat = np.radians(
        stores["latitude"].to_numpy()
    )

    store_lon = np.radians(
        stores["longitude"].to_numpy()
    )

    radius = radius_km * 1000

    earth_radius = 6_371_000

    # Start by assuming every population point
    # is uncovered.
    covered = np.zeros(
        len(population),
        dtype=bool,
    )

    # Process stores one by one.
    #
    # This avoids creating one enormous
    # population × store matrix.
    for lat, lon in zip(
        store_lat,
        store_lon,
    ):

        dlat = pop_lat - lat
        dlon = pop_lon - lon

        a = (
            np.sin(dlat / 2) ** 2
            + np.cos(lat)
            * np.cos(pop_lat)
            * np.sin(dlon / 2) ** 2
        )

        distance = (
            2
            * earth_radius
            * np.arcsin(
                np.sqrt(a)
            )
        )

        covered |= distance <= radius

        # Once everything is covered,
        # no need to process remaining stores.
        if covered.all():
            break

    return population.loc[
        ~covered
    ].copy()


uncovered_population = find_uncovered_population(
    population,
    stores,
    radius_km,
)

# ---------------------------------------------------------
# Top 10 most populated uncovered areas
# ---------------------------------------------------------

top_10_uncovered = (
    uncovered_population
    .nlargest(10, "population")
    .copy()
)

top_10_uncovered["rank"] = range(
    1,
    len(top_10_uncovered) + 1
)

top_10_uncovered["label"] = (
    "Top "
    + top_10_uncovered["rank"].astype(str)
    + " — "
    + top_10_uncovered["population"]
        .map(lambda x: f"{x:,.0f}")
    + " people"
)

# ---------------------------------------------------------
# Store circles
# ---------------------------------------------------------

store_map = stores.copy()

store_map["radius_m"] = radius_km * 1000

store_map["tooltip"] = store_map[
    "display_name"
].astype(str) + (
    f" — Radius: {radius_km:.1f} km"
)


# ---------------------------------------------------------
# Population heatmap
# ---------------------------------------------------------

population_layer = pdk.Layer(
    "HeatmapLayer",

    data=uncovered_population,

    id="uncovered-population",

    get_position=[
        "longitude",
        "latitude",
    ],

    get_weight="population",

    radius_pixels=25,

    intensity=1.2,

    threshold=0.03,

    opacity=0.75,
)


# ---------------------------------------------------------
# Radius circles
# ---------------------------------------------------------

radius_layer = pdk.Layer(
    "ScatterplotLayer",

    data=store_map,

    id="store-radii",

    get_position=[
        "longitude",
        "latitude",
    ],

    get_radius="radius_m",

    get_fill_color=[
        220,
        20,
        60,
        35,
    ],

    get_line_color=[
        220,
        20,
        60,
        180,
    ],

    stroked=True,

    filled=True,

    line_width_min_pixels=2,

    pickable=True,
)


# ---------------------------------------------------------
# Store markers
# ---------------------------------------------------------

marker_layer = pdk.Layer(
    "ScatterplotLayer",

    data=store_map,

    id="store-markers",

    get_position=[
        "longitude",
        "latitude",
    ],

    get_radius=100,

    get_fill_color=[
        220,
        20,
        20,
        255,
    ],

    get_line_color=[
        255,
        255,
        255,
        255,
    ],

    radius_min_pixels=5,

    radius_max_pixels=12,

    stroked=True,

    filled=True,

    pickable=True,

    auto_highlight=True,
)


# ---------------------------------------------------------
# Top 10 uncovered population points
# ---------------------------------------------------------

top_10_layer = pdk.Layer(
    "ScatterplotLayer",

    data=top_10_uncovered,

    id="top-10-uncovered",

    get_position=[
        "longitude",
        "latitude",
    ],

    get_radius=500,

    get_fill_color=[
        255,
        215,
        0,
        255,
    ],

    get_line_color=[
        0,
        0,
        0,
        255,
    ],

    radius_min_pixels=8,

    radius_max_pixels=20,

    line_width_min_pixels=3,

    stroked=True,

    filled=True,

    pickable=True,

    auto_highlight=True,
)

# ---------------------------------------------------------
# Map
# ---------------------------------------------------------

center_lat = stores["latitude"].mean()
center_lon = stores["longitude"].mean()


view_state = pdk.ViewState(
    latitude=float(center_lat),
    longitude=float(center_lon),
    zoom=8,
    pitch=0,
    bearing=0,
)


deck = pdk.Deck(
    layers=[
        population_layer,
        radius_layer,
        marker_layer,
        top_10_layer,
    ],
    initial_view_state=view_state,

    tooltip={
        "text": "{display_name}"
    },
)


# ---------------------------------------------------------
# Display
# ---------------------------------------------------------

col1, col2 = st.columns(
    [3, 1]
)


with col1:

    st.pydeck_chart(
        deck,
        width="stretch",
        height=650,
    )


with col2:

    st.subheader("📊 Coverage")

    total_population = population[
        "population"
    ].sum()

    uncovered = uncovered_population[
        "population"
    ].sum()

    covered = (
        total_population
        - uncovered
    )

    coverage_percent = (
        covered / total_population * 100
        if total_population > 0
        else 0
    )

    uncovered_percent = (
        uncovered / total_population * 100
        if total_population > 0
        else 0
    )

    st.metric(
        "Radius",
        f"{radius_km:.1f} km",
    )

    st.metric(
        "Total population",
        f"{total_population:,.0f}",
    )

    st.metric(
        "Covered population",
        f"{covered:,.0f}",
    )

    st.metric(
        "Uncovered population",
        f"{uncovered:,.0f}",
    )

    st.metric(
        "Coverage",
        f"{coverage_percent:.1f}%",
    )

    st.metric(
        "Uncovered",
        f"{uncovered_percent:.1f}%",
    )

    st.divider()

    st.subheader("Locations")

    st.dataframe(
        store_map[
            [
                "display_name",
                "latitude",
                "longitude",
            ]
        ].rename(
            columns={
                "display_name": "Location",
                "latitude": "Latitude",
                "longitude": "Longitude",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    st.subheader(
        "🎯 Top 10 Uncovered Areas"
    )

    st.dataframe(
        top_10_uncovered[
            [
                "rank",
                "latitude",
                "longitude",
                "population",
            ]
    ].rename(
        columns={
            "rank": "Rank",
            "latitude": "Latitude",
            "longitude": "Longitude",
            "population": "Population",
        }
    ),
    use_container_width=True,
    hide_index=True,
)