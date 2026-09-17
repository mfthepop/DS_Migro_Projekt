import matplotlib.pyplot as plt
import pandas as pd
import geopandas as gpd
import numpy as np
from shapely.geometry import box
import plotly.express as px


###LOAD DATA
stores = pd.read_csv("Migros_and_competitors_stores_CH.csv") #load stores data
grid = gpd.read_file("population_500by500_grid.gpkg") #load population density grid

stores_gdf = gpd.GeoDataFrame(
    stores,
    geometry=gpd.points_from_xy(stores.longitude, stores.latitude),
    crs="EPSG:4326" #gps-like coordinates is what we have in the stores file
)


#put everything in meters
grid = grid.to_crs(2056)
stores_gdf = stores_gdf.to_crs(2056)



###SETTINGS FOR THE SIDEBAR
#settings the user can change in the streamlit UI (the user can choose/adjust)

#Setting 1: radius for the chart and the analysis (used to determine how many competitors are within that distance)
r = 1 #user input: 1 km
radius = r * 1000 #the threshold for the radius used in the score is in meters

#Setting 2: #flag to select Migros only or Migros + Denner as part of our "company"
setting_migros_only = True #True means we only consider Migros. False means Migros + Denner

#Setting 3: #flag to define which competition to choose from: all companies or just Coop (the biggest one)
setting_all_competitors = True #True means all competitors. False is just for Coop

#main company
main_company = ["Migros"] if setting_migros_only else ["Migros", "Denner"]

#competitors
if setting_all_competitors:
    competition_companies = ["Coop", "ALDI", "Lidl", "SPAR", "Volg"]

    # If Denner is not considered part of the main company,
    # include it as a competitor
    if setting_migros_only:
        competition_companies.append("Denner")
else:
    competition_companies = ["Coop"]




###FACTOR1: CALCULATE DISTANCE TO NEAREST MIGROS
main_stores = stores_gdf[stores_gdf["company"].isin(main_company)]

nearest = gpd.sjoin_nearest(
    grid[["geometry"]],
    main_stores[["geometry"]],
    how="left",
    distance_col="migros_distance"
)

#within each grid cell, take the smallest distance.
nearest_distance = (
    nearest
    .groupby(level=0)["migros_distance"]
    .min()
)

#add the nearest distance resutls to the grid
grid["migros_distance"] = nearest_distance




###FACTOR2: CALCULATE THE NUMBER OF COMPETITORS WITHIN "RADIUS" METERS
competitors = stores_gdf[
    stores_gdf.company.isin(competition_companies)  
]

buffers = grid[["geometry"]].copy()
buffers["geometry"] = buffers.geometry.buffer(radius)

competitor_join = gpd.sjoin(
    buffers,
    competitors[["company", "geometry"]],
    predicate="contains"
)

competitor_count = competitor_join.groupby(
    competitor_join.index
).size()

grid["competitor_count"] = competitor_count
grid["competitor_count"] = grid["competitor_count"].fillna(0)



###SCORE: CALCULATE THE OPPORTUNITY SCORE

grid["opportunity"] = (
    grid["population"]
    * (grid["migros_distance"] / 1000)
    / (1 + grid["competitor_count"])
)

#Interpretation:
#- more population → higher opportunity
#- further from existing Migros → higher opportunity
#- more competitors → lower opportunity

#sort entires by opportunity score
opportunities = grid.sort_values(
    "opportunity",
    ascending=False
)


#####AFTER THIS; GET TOP 10, AND DISPLAY IN THE CHART