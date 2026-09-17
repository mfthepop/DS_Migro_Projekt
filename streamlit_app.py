import streamlit as st
import pandas as pd
import folium
import geopandas as gpd 
import plotly.express as px
from streamlit_folium import st_folium
from branca.element import IFrame

st.set_page_config(page_title="Multi-Radius Location Viewer", layout="wide")
st.title("📍 Multi-Radius Location Viewer")

# Colors to differentiate overlapping location circles
CIRCLE_COLORS = ["crimson", "blue", "green", "purple", "orange", "darkred", "cadetblue"]

@st.cache_data
def load_data():
    df = pd.read_csv("Migros_and_competitors_stores_CH.csv")
    # Set default radius if the column is missing in CSV
    if "radius_km" not in df.columns:
        df["radius_km"] = 5.0
    return df

try:
    df = load_data()
    #agg_plot = gpd.read_file("population_500by500_grid.gpkg")

    # 1. Sidebar Controls
    st.sidebar.header("⚙️ Radius Settings")

    use_custom_sidebar = st.sidebar.checkbox("Customize Individual Radiuses", value=False)
    
    updated_radiuses = []
    
    for idx, row in df.iterrows():
        if use_custom_sidebar:
            r = st.sidebar.slider(
                f"Radius for {row['display_name']} (km)",
                min_value=0.5,
                max_value=20.0,
                value=float(row["radius_km"]),
                step=0.5,
                key=f"slider_{idx}"
            )
        else:
            r = row["radius_km"]
        updated_radiuses.append(r)

    df["radius_km"] = updated_radiuses

    # 2. Map Initialization (centered at the average lat/lon)
    center_lat = df["latitude"].mean()
    center_lon = df["longitude"].mean()
    m = folium.Map(location=[center_lat, center_lon], zoom_start=12)

    # 3. Add Marker + Radius Circle for EACH Location
    for idx, row in df.iterrows():
        color = CIRCLE_COLORS[idx % len(CIRCLE_COLORS)]
        
        # Add the Radius Circle (meters = km * 1000)
        # folium.Circle(
        #     location=[row["latitude"], row["longitude"]],
        #     radius=row["radius_km"] * 1000,
        #     color=color,
        #     fill=True,
        #     fill_color=color,
        #     fill_opacity=0.15,
        #     popup=f"<b>{row['display_name']}</b><br>Radius: {row['radius_km']} km"
        # ).add_to(m)

        #Add Marker Pin at Center
        folium.Marker(
            location=[row["latitude"], row["longitude"]],
            popup=f"<b>{row['display_name']}</b><br>Radius: {row['radius_km']} km",
            tooltip=f"{row['display_name']} ({row['radius_km']} km radius)",
            icon=folium.Icon(color="red", icon="info-sign")
        ).add_to(m)

    #agg_plot_reset = agg_plot.reset_index()
    # folium.Choropleth(
    #     geo_data=agg_plot.geometry.__geo_interface__,
    #     data=agg_plot_reset,
    #     columns=[agg_plot_reset.columns[0], "population"],  # [index/ID column, value column]
    #     key_on="feature.id",  # Matches the feature ID in geojson
    #     fill_color="YlOrRd",  # Choose a color palette (e.g., 'Viridis', 'YlGnBu', 'YlOrRd')
    #     fill_opacity=0.6,     # Equivalent to opacity=0.6
    #     line_opacity=0.2,
    #     legend_name="Population"
    #     ).add_to(m)

    # 4. Render Layout
    col1, col2 = st.columns([3, 2])

    with col1:
        st_folium(m, width=800, height=550)

    with col2:
        st.subheader("📋 Locations & Radiuses")
        st.dataframe(
            df[["display_name", "radius_km", "latitude", "longitude"]].reset_index(drop=True),
            use_container_width=True
        )
        
  

except FileNotFoundError:
    st.error("Please ensure 'Migros_and_competitors_stores_CH.csv' is present in your app directory.")