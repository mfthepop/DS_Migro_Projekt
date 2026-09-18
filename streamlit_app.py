from pathlib import Path

import numpy as np
import pandas as pd
import pydeck as pdk
import streamlit as st
from geopy.geocoders import Nominatim

from ten_small_competitors_adapted import get_places_for_small_stores
# =========================================================
# CONFIGURATION
# =========================================================
top_10_places_ready=pd.DataFrame() 

BASE_DIR = Path(__file__).resolve().parent

STORE_FILE = (
    BASE_DIR /
    "Migros_and_competitors_stores_CH.csv"
)

POPULATION_FILE = (
    BASE_DIR /
    "population_cells.parquet"
)


st.set_page_config(
    page_title="Migros Location Opportunity",
    layout="wide",
)

st.title(" Migros Location Opportunity Analysis")


@st.cache_data
def get_town_cached(topten):
    return get_town(topten)

@st.cache_data
def reverse_geocode_town(lat, lon):
    geolocator = Nominatim(user_agent="migros_opportunity_app")

    try:
        location = geolocator.reverse(
            (lat, lon),
            exactly_one=True
        )

        if location:
            address = location.raw.get("address", {})
            return (
                address.get("town")
                or address.get("municipality")
                or address.get("village")
                or address.get("city")
                or address.get("suburb")
                or "Unknown"
            )

    except Exception:
        pass

    return "Unknown"




# =========================================================
# LOAD STORES
# =========================================================

@st.cache_data(show_spinner=False)
def load_stores():

    df = pd.read_csv(STORE_FILE)

    required = {
        "display_name",
        "latitude",
        "longitude",
        "company",
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            "Missing store columns: "
            + ", ".join(sorted(missing))
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
            "display_name",
            "latitude",
            "longitude",
            "company",
        ]
    )

    return df.reset_index(drop=True)


# =========================================================
# LOAD POPULATION
# =========================================================

@st.cache_data(show_spinner=False)
def load_population():

    if not POPULATION_FILE.exists():

        raise FileNotFoundError(
            "population_cells.parquet is missing."
        )

    df = pd.read_parquet(
        POPULATION_FILE
    )

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

    for column in [
        "latitude",
        "longitude",
        "population",
    ]:

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df = df.dropna(
        subset=[
            "latitude",
            "longitude",
        ]
    )

    df = df[
        df["population"] > 0
    ]

    return df.reset_index(drop=True)


# =========================================================
# LOAD DATA
# =========================================================

try:

    stores = load_stores()
    population = load_population()

    #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<SECOND MODEL<<<<<<<<<<<<<<<<<<<<<<<<<<<
    #allowed_competitors = ["Migros", "Denner", "Lidl", "ALDI", "Vogl", "Spar"]#, "Aligro"]
    #r_distance_km=3 # Define the minimum clearance distance R allowed between the top selected stores (in Kilometers)
    #top_10_places=get_places_for_small_stores(population,stores,allowed_competitors,r_distance_km)
    #top_10_places_ready = top_10_places.reset_index()
    #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<SECOND MODEL<<<<<<<<<<<<<<<<<<<<<<<<<<<

    # CRITICAL FIX: Drop the secondary 'centroid' geometry column to avoid serialization errors
    #if 'centroid' in top_10_places_ready.columns:
    #    top_10_places_ready = top_10_places_ready.drop(columns=['centroid'])

except Exception as exc:

    st.error(str(exc))
    st.stop()


# =========================================================
# SIDEBAR SETTINGS
# =========================================================

st.sidebar.header(
    "Analysis Settings"
)


# ---------------------------------------------------------
# Radius
# ---------------------------------------------------------

radius_km = st.sidebar.slider(
    "Competitor radius",
    min_value=0.5,
    max_value=20.0,
    value=3.0,
    step=0.5,
)

radius_m = radius_km * 1000

def deactivate_with_existing_competitors():
    st.session_state.checkbox_with_existing_competitors=False

# ---------------------------------------------------------
# Migros / Denner setting
# ---------------------------------------------------------

setting_migros_only = st.sidebar.checkbox(
    "Migros only",
    value=True,
    key="checkbox_migros_only",
    on_change=deactivate_with_existing_competitors
)


# ---------------------------------------------------------
# Competitor setting
# ---------------------------------------------------------

setting_all_competitors = st.sidebar.checkbox(
    "All competitors",
    value=True,
    key="checkbox_all_competitors",
    on_change=deactivate_with_existing_competitors
)

# ---------------------------------------------------------
# Second model based on existent competitors stores <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<SECOND MODEL<<<<<<<<<<<<<<<<<<<<<<<<<<<
# ---------------------------------------------------------

def deactivate_other_checkboxes():
    st.session_state.checkbox_all_competitors = False
    st.session_state.checkbox_migros_only = False

setting_with_existing_competitors = st.sidebar.checkbox(
    "With existing small competitors",
    value=False,
    key="checkbox_with_existing_competitors",
    on_change=deactivate_other_checkboxes
)

# ---------------------------------------------------------
# Minimum distance between Top 10
# ---------------------------------------------------------

min_distance_km = st.sidebar.slider(
    "Minimum distance between Top 10 points",
    min_value=0.5,
    max_value=10.0,
    value=2.0,
    step=0.5,
)


# =========================================================
# MAIN COMPANY
# =========================================================

if setting_migros_only:

    main_company = [
        "Migros"
    ]

else:

    main_company = [
        "Migros",
        "Denner",
    ]


# =========================================================
# COMPETITORS
# =========================================================

if setting_all_competitors:

    competition_companies = [
        "Coop",
        "ALDI",
        "Lidl",
        "SPAR",
        "Volg",
    ]

    if setting_migros_only:

        competition_companies.append(
            "Denner"
        )

elif setting_with_existing_competitors: #<<<<<<<<<<<<<<<<<SECOND MODEL<<<<<<<<<<<<<<<
    competition_companies = [
        "Migros", 
        "Denner", 
        "Lidl", 
        "ALDI", 
        "Vogl", 
        "Spar"
    ]
    top_10_places=get_places_for_small_stores(population,stores,competition_companies,min_distance_km)
    top_10_places_ready = top_10_places.reset_index()
else:

    competition_companies = [
        "Coop"
    ]


# =========================================================
# OPPORTUNITY CALCULATION
# =========================================================

def calculate_opportunity(
    population,
    stores,
    main_company,
    competition_companies,
    radius_m,
):
    """
    Calculate:

        opportunity =
            population
            * nearest_migros_distance_km
            / (1 + competitor_count)

    All spatial calculations are performed
    using latitude/longitude with a vectorized
    haversine calculation.
    """

    pop_lat = np.radians(
        population["latitude"].to_numpy()
    )

    pop_lon = np.radians(
        population["longitude"].to_numpy()
    )

    # -----------------------------------------------------
    # MAIN STORES
    # -----------------------------------------------------

    main_stores = stores[
        stores["company"].isin(
            main_company
        )
    ]

    if main_stores.empty:

        raise ValueError(
            "No main-company stores found."
        )

    main_lat = np.radians(
        main_stores["latitude"].to_numpy()
    )

    main_lon = np.radians(
        main_stores["longitude"].to_numpy()
    )


    # -----------------------------------------------------
    # DISTANCE TO NEAREST MIGROS
    # -----------------------------------------------------

    nearest_distance = np.full(
        len(population),
        np.inf,
    )

    earth_radius_m = 6_371_000.0

    # Calculate nearest store distance
    # without a Python loop over population cells.
    for lat, lon in zip(
        main_lat,
        main_lon,
    ):

        dlat = pop_lat - lat
        dlon = pop_lon - lon

        a = (
            np.sin(dlat / 2) ** 2
            +
            np.cos(lat)
            * np.cos(pop_lat)
            * np.sin(dlon / 2) ** 2
        )

        a = np.clip(
            a,
            0,
            1,
        )

        distance = (
            2
            * earth_radius_m
            * np.arcsin(
                np.sqrt(a)
            )
        )

        nearest_distance = np.minimum(
            nearest_distance,
            distance,
        )


    # -----------------------------------------------------
    # COMPETITORS
    # -----------------------------------------------------

    competitors = stores[
        stores["company"].isin(
            competition_companies
        )
    ]

    competitor_lat = np.radians(
        competitors["latitude"].to_numpy()
    )

    competitor_lon = np.radians(
        competitors["longitude"].to_numpy()
    )


    # -----------------------------------------------------
    # COUNT COMPETITORS WITHIN RADIUS
    # -----------------------------------------------------

    competitor_count = np.zeros(
        len(population),
        dtype=np.int32,
    )


    for lat, lon in zip(
        competitor_lat,
        competitor_lon,
    ):

        dlat = pop_lat - lat
        dlon = pop_lon - lon

        a = (
            np.sin(dlat / 2) ** 2
            +
            np.cos(lat)
            * np.cos(pop_lat)
            * np.sin(dlon / 2) ** 2
        )

        a = np.clip(
            a,
            0,
            1,
        )

        distance = (
            2
            * earth_radius_m
            * np.arcsin(
                np.sqrt(a)
            )
        )

        competitor_count += (
            distance <= radius_m
        )


    # -----------------------------------------------------
    # RESULT
    # -----------------------------------------------------

    result = population.copy()

    result["migros_distance_m"] = (
        nearest_distance
    )

    result["migros_distance_km"] = (
        nearest_distance / 1000
    )

    result["competitor_count"] = (
        competitor_count
    )


    # -----------------------------------------------------
    # YOUR EXACT SCORE
    # -----------------------------------------------------

    result["opportunity"] = (
        result["population"]
        * result["migros_distance_km"]
        / (
            1
            + result["competitor_count"]
        )
    )


    return result


# =========================================================
# CALCULATE OPPORTUNITIES
# =========================================================

with st.spinner(
    "Calculating location opportunities..."
):

    opportunities = calculate_opportunity(
        population=population,
        stores=stores,
        main_company=main_company,
        competition_companies=competition_companies,
        radius_m=radius_m,
    )


# =========================================================
# SELECT TOP 10
# =========================================================

def select_top_10(
    opportunities,
    min_distance_km,
    number_of_points=10,
):

    candidates = (
        opportunities
        .sort_values(
            "opportunity",
            ascending=False,
        )
        .copy()
    )

    # Convert coordinates to radians
    lat = np.radians(
        candidates["latitude"].to_numpy()
    )

    lon = np.radians(
        candidates["longitude"].to_numpy()
    )

    earth_radius_km = 6371.0

    selected_indices = []


    # -----------------------------------------------------
    # GREEDY SELECTION
    # -----------------------------------------------------

    for i in range(
        len(candidates)
    ):

        if len(selected_indices) >= (
            number_of_points
        ):
            break


        # First candidate is automatically selected
        if not selected_indices:

            selected_indices.append(i)

            continue


        selected_lat = lat[
            selected_indices
        ]

        selected_lon = lon[
            selected_indices
        ]


        # Distance from current candidate
        # to all already-selected candidates

        dlat = (
            selected_lat
            - lat[i]
        )

        dlon = (
            selected_lon
            - lon[i]
        )


        a = (
            np.sin(dlat / 2) ** 2
            +
            np.cos(lat[i])
            * np.cos(selected_lat)
            * np.sin(dlon / 2) ** 2
        )


        distances = (
            2
            * earth_radius_km
            * np.arcsin(
                np.sqrt(
                    np.clip(
                        a,
                        0,
                        1,
                    )
                )
            )
        )


        # Candidate must be far enough
        # from EVERY selected point

        if np.all(
            distances >= min_distance_km
        ):

            selected_indices.append(i)


    top_10 = (
        candidates
        .iloc[selected_indices]
        .copy()
    )


    top_10 = (
        top_10
        .sort_values(
            "opportunity",
            ascending=False,
        )
        .reset_index(drop=True)
    )


    top_10["rank"] = (
        top_10.index + 1
    )


    return top_10


top_10 = select_top_10(
    opportunities,
    min_distance_km,
)
top_10["town"] = top_10.apply(
    lambda row: reverse_geocode_town(
        row["latitude"],
        row["longitude"]
    ),
    axis=1
)

# =========================================================
# STATISTICS
# =========================================================

total_population = (
    population["population"]
    .sum()
)

uncovered_population = (
    opportunities[
        opportunities["migros_distance_km"]
        > radius_km
    ]
)


uncovered_population_total = (
    uncovered_population["population"]
    .sum()
)


# =========================================================
# TOP 10 MAP DATA
# =========================================================

top_10["display"] = (
    "Rank "
    + top_10["rank"].astype(str)
    + " | "
    + top_10["population"]
        .map(lambda x: f"{x:,.0f}")
    + " people"
)


# =========================================================
# MAP LAYERS
# =========================================================

# Population heatmap
population_layer = pdk.Layer(
    "HeatmapLayer",

    data=opportunities,

    id="population-heatmap",

    get_position=[
        "longitude",
        "latitude",
    ],

    get_weight="population",

    radius_pixels=25,

    intensity=1.2,

    threshold=0.03,

    opacity=0.65,
)


# Store radius
radius_layer = pdk.Layer(
    "ScatterplotLayer",

    data=stores,

    id="store-radii",

    get_position=[
        "longitude",
        "latitude",
    ],

    get_radius=radius_m,

    get_fill_color=[
        220,
        20,
        60,
        30,
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


# Store markers
store_marker_layer = pdk.Layer(
    "ScatterplotLayer",

    data=stores,

    id="store-markers",

    get_position=[
        "longitude",
        "latitude",
    ],

    get_radius=100,

    get_fill_color=[
        200,
        30,
        30,
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


# =========================================================
# TOP 10 HIGHLIGHT LAYER 
# =========================================================

if setting_with_existing_competitors: #<<<<<<<<<<<<<<<<<<<<<<<<<<<<
    top_10=top_10_places_ready

top_10_layer = pdk.Layer(
    "ScatterplotLayer",

    data=top_10,

    id="top-10-opportunities",

    get_position=[
        "longitude",
        "latitude",
    ],

    get_radius=700,

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

    radius_min_pixels=9,

    radius_max_pixels=22,

    line_width_min_pixels=3,

    stroked=True,

    filled=True,

    pickable=True,

    auto_highlight=True,
)


# =========================================================
# MAP
# =========================================================

view_state = pdk.ViewState(
    latitude=float(
        stores["latitude"].mean()
    ),

    longitude=float(
        stores["longitude"].mean()
    ),

    zoom=8,

    pitch=0,

    bearing=0,
)

tooltip={} #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
if not setting_with_existing_competitors:
    tooltip={
        "html":
            "<b>{display}</b><br/>"
            "Population: {population}<br/>"
            "Migros distance: "
            "{migros_distance_km} km<br/>"
            "Competitors: "
            "{competitor_count}<br/>"
            "Opportunity: "
            "{opportunity}"
    }
else:
    tooltip={
            "html":
                "Population: {population}<br/>"
                "Competitor: "
                "{shop_names}<br/>"
                "Opportunity score: "
                "{opportunity_score}<br/>"
        }

deck = pdk.Deck(
    layers=[
        population_layer,
        radius_layer,
        store_marker_layer,
        top_10_layer,
    ],

    initial_view_state=view_state,

    tooltip=tooltip,
)


# =========================================================
# DISPLAY
# =========================================================

col1, col2 = st.columns(
    [3, 1]
)


# ---------------------------------------------------------
# MAP
# ---------------------------------------------------------

with col1:

    st.pydeck_chart(
        deck,
        width="stretch",
        height=650,
    )


# ---------------------------------------------------------
# INFORMATION PANEL
# ---------------------------------------------------------

with col2:

    # st.subheader(
    #     "Analysis"
    # )

    # st.metric(
    #     "Competitor radius",
    #     f"{radius_km:.1f} km",
    # )

    # st.metric(
    #     "Population cells",
    #     f"{len(population):,}",
    # )

    # st.metric(
    #     "Total population",
    #     f"{total_population:,.0f}",
    # )

    # st.metric(
    #     "Top 10 locations",
    #     str(len(top_10)),
    # )


    # st.divider()


    st.subheader(
        " Top 10 Opportunities"
    )

    if top_10.empty:

        st.warning(
            "No suitable locations found."
        )

    else:
        #<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< #Normal cases: Migros only and All competitors
        if not setting_with_existing_competitors:
            display_table = (
                                top_10[
                                    [
                                        "rank",
                                        "town",
                                        "population",
                                        "migros_distance_km",
                                        "competitor_count",
                                        "opportunity",
                                    ]
                                ]
                                .rename(
                                    columns={
                                        "rank": "Rank",
                                        "population": "Population",
                                        "migros_distance_km":
                                            "Migros distance (km)",
                                        "competitor_count":
                                            "Competitors",
                                        "opportunity":
                                            "Opportunity",
                                    }
                                )
                            )
            st.dataframe(
                display_table,
                use_container_width=True,
                hide_index=True,
            )
        else: # With existing competitors <<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<
            #top_10_places=get_places_for_small_stores(population,stores,competition_companies,min_distance_km)
            #top_10_places_ready = top_10_places.reset_index()
            top_10['rank']=1+top_10.index
            display_table = (
                                            top_10[
                                                [
                                                    "rank",
                                                    "population",
                                                    #"migros_distance_km",
                                                    "nearest_shops",
                                                    "opportunity_score",
                                                ]
                                            ]
                                            .rename(
                                                columns={
                                                    "rank": "Rank",
                                                    "population": "Population",
                                                    #"migros_distance_km": "Migros distance (km)",
                                                    "nearest_shops": "Competitors",
                                                    "opportunity_score": "Opportunity",
                                                }
                                            )
                                        )
            st.dataframe(
                            top_10_places_ready.drop(columns=["index","geometry","norm_pop","norm_comp"]),
                            use_container_width=True,
                            hide_index=True,
                        )


    st.caption(
        f"Top locations are at least "
        f"{min_distance_km:.1f} km apart."
    )