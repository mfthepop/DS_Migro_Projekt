import json
import folium
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

# Define a grouping function to clean up the temporary duplications from the left join
def aggregate_competitor_metrics(group):
    if group["company"].isna().all():
        return pd.Series({"nearest_shops": 0, "shop_names": "None"})

    unique_brands = ", ".join(group["company"].dropna().unique())
    total_stores = group["company"].dropna().count()
    return pd.Series({"nearest_shops": total_stores, "shop_names": unique_brands})

def get_places_for_small_stores(agg_plot_reset, df_migros_and_competitors, allowed_competitors, r_distance_km):

    # ==============================================================================
    # 1. GEOSPATIAL DATA PREPARATION
    # ==============================================================================

    # Convert the population DataFrame to a GeoDataFrame using the standard WGS84 coordinate system
    gdf_pop = gpd.GeoDataFrame(agg_plot_reset, geometry="geometry", crs="EPSG:4326")

    # Build Point geometries for the stores using their Longitude and Latitude columns
    geometry_stores = [
        Point(xy)
        for xy in zip(
            df_migros_and_competitors["longitude"],
            df_migros_and_competitors["latitude"],
        )
    ]

    # Convert the competitors DataFrame into a GeoDataFrame mapped to WGS84
    gdf_stores = gpd.GeoDataFrame(
        df_migros_and_competitors, geometry=geometry_stores, crs="EPSG:4326"
    )

    # Filter the store dataset to isolate only targeted competitor brands
    gdf_competitors = gdf_stores[gdf_stores["company"].isin(allowed_competitors)]

    # ==============================================================================
    # 2. METRIC TRANSFORMATIONS & BUFFERING (SWISS METRIC SYSTEM)
    # ==============================================================================

    # Project both datasets to EPSG:2056 (Swiss National Grid) to compute real-world distances in meters
    gdf_pop_m = gdf_pop.to_crs("EPSG:2056")
    gdf_competitors_m = gdf_competitors.to_crs("EPSG:2056")

    # Define the minimum clearance distance R allowed between your top selected stores (in Kilometers)
    r_distance_meters = r_distance_km * 1000

    # Generate circular trade areas around competitors using radius R (in km)
    gdf_competitors_m["geometry_buffer"] = gdf_competitors_m.apply(
        lambda row: row["geometry"].buffer(r_distance_meters), axis=1
    )

    # Swap the active geometry column from single points to the generated trade area circles
    gdf_competitors_buffer = gdf_competitors_m.set_geometry("geometry_buffer")

    # ==============================================================================
    # 3. SPATIAL INTERSECTIONS & AGGREGATION
    # ==============================================================================

    # Map which 500x500m population polygons intersect with the competitors' business radius
    zones_intersected = gpd.sjoin(
        gdf_pop_m, gdf_competitors_buffer, how="left", predicate="intersects"
    )

    # Apply the aggregation using the index of the original population grids
    competition_summary = zones_intersected.groupby(zones_intersected.index).apply(
        aggregate_competitor_metrics
    )

    # Merge metrics back onto our metric population GeoDataFrame
    gdf_pop_m = gdf_pop_m.join(competition_summary)

    # ==============================================================================
    # 4. FILTERING & INITIAL SCORING
    # ==============================================================================

    # CRITICAL FILTER: Keep only locations that have at least 1 competitor
    #gdf_valid_zones = gdf_pop_m[gdf_pop_m["nearest_shops"] >= 1].copy()
    gdf_valid_zones = gdf_pop_m[(gdf_pop_m['nearest_shops'] >= 1) & (~gdf_pop_m['shop_names'].str.contains('Migros', na=False))].copy()

    # Compute initial opportunity score before the distance exclusion loop
    gdf_valid_zones["norm_pop"] = (
        gdf_valid_zones["population"] / gdf_valid_zones["population"].max()
    )
    gdf_valid_zones["norm_comp"] = 1 / gdf_valid_zones["nearest_shops"]
    gdf_valid_zones["opportunity_score"] = (gdf_valid_zones["norm_pop"] * 0.5) + (
        gdf_valid_zones["norm_comp"] * 0.5
    )

    # Sort candidates by score descending
    candidates = gdf_valid_zones.sort_values(
        by="opportunity_score", ascending=False
    ).copy()

    # ==============================================================================
    # 5. DISTANCE CONSTRAINT R FILTERING (NON-MAXIMUM SUPPRESSION)
    # ==============================================================================

    selected_rows = []

    # Iteratively select the best option and drop neighbors closer than R
    while len(selected_rows) < 10 and not candidates.empty:
        # Pick the absolute best remaining candidate
        best_candidate = candidates.iloc[0]
        selected_rows.append(best_candidate)

        # Get the geometry of the selected point to compute proximity
        best_geom = best_candidate["geometry"]

        # Measure distance from all remaining candidates to this chosen location
        distances = candidates.distance(best_geom)

        # Keep only candidates that are further away than R meters from our selected site
        candidates = candidates[distances > r_distance_meters]

    # Convert the selected list back into a structured GeoDataFrame
    top_10_places_m = gpd.GeoDataFrame(selected_rows, crs="EPSG:2056")

    # Convert back to WGS84 for mapping output and coordinates extraction
    top_10_places = top_10_places_m.to_crs("EPSG:4326")
    top_10_places["centroid"] = top_10_places["geometry"].centroid
    top_10_places["latitude"] = top_10_places["centroid"].y
    top_10_places["longitude"] = top_10_places["centroid"].x

    return top_10_places

def load_data():
    df = pd.read_csv("Migros_and_competitors_stores_CH.csv")
    # Set default radius if the column is missing in CSV
    if "radius_km" not in df.columns:
        df["radius_km"] = 5.0
    return df

# ==============================================================================
# HOW TO USE THE functions above
# ==============================================================================

#Prepare data and parameters to call 'get_places_for_small_stores' to get the dataframe with the positions
df_migros_and_competitors = load_data()
agg_plot = gpd.read_file("population_500by500_grid.gpkg")
agg_plot_reset = agg_plot.reset_index()
#It is necessary to include Migros as allowed competitors
allowed_competitors = ["Migros", "Denner", "Lidl", "ALDI", "Vogl", "Spar"]#, "Aligro"]
r_distance_km=3 # Define the minimum clearance distance R allowed between the top selected stores (in Kilometers)

#Get the dataframe 
top_10_places = get_places_for_small_stores(agg_plot_reset, df_migros_and_competitors, allowed_competitors,r_distance_km)
top_10_places_ready = top_10_places.reset_index()

# CRITICAL FIX: Drop the secondary 'centroid' geometry column to avoid serialization errors
if 'centroid' in top_10_places_ready.columns:
    top_10_places_ready = top_10_places_ready.drop(columns=['centroid'])

# ==============================================================================
# FOLIUM INTERACTIVE CHOROPLETH GENERATION
# ==============================================================================

#Drawing data. In this case, just as example, the graphs is saved in a .html file

map_center_lat = top_10_places_ready.loc[0, 'latitude']
map_center_lon = top_10_places_ready.loc[0, 'longitude']

m = folium.Map(
    location=[map_center_lat, map_center_lon],
    zoom_start=11,
    tiles="cartodbpositron",
)

# This will now execute perfectly without any TypeError
geojson_features = json.loads(top_10_places_ready.to_json())

folium.Choropleth(
    geo_data=geojson_features,
    name="Top 10 Spaced Expansion Sites",
    data=top_10_places_ready,
    columns=["index", "population"],
    key_on="feature.properties.index",
    fill_color="YlOrRd",
    fill_alpha=0.6,
    line_alpha=0.8,
    legend_name="Total Population within 500x500m Grid",
    highlight=True,
).add_to(m)

# Drop marker points onto the map
for rank_idx, row in top_10_places_ready.iterrows():
    tooltip_html = f"""
    <strong>Rank Position:</strong> #{rank_idx + 1}<br>
    <strong>Population Density:</strong> {row['population']} residents<br>
    <strong>Competitors in Radius:</strong> {row['nearest_shops']}<br>
    <strong>Active Brands:</strong> {row['shop_names']}
    """
    folium.Marker(
        location=[row["latitude"], row["longitude"]],
        popup=folium.Popup(tooltip_html, max_width=300),
        icon=folium.Icon(color="purple", icon="store", prefix="fa"),
    ).add_to(m)

m.save("top_10_spaced_expansion_map.html")
