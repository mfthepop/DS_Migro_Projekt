# Deploying

Repo layout:

    app.py
    Migros_and_competitors_stores_CH.csv
    requirements.txt
    Procfile        # Heroku only
    runtime.txt     # Heroku only
    .streamlit/config.toml

## .streamlit/config.toml

    [server]
    headless = true
    fileWatcherType = "none"     # saves RAM/CPU on a dyno
    enableCORS = false
    enableXsrfProtection = false
    maxUploadSize = 5

    [browser]
    gatherUsageStats = false

    [theme]
    base = "light"

## Heroku

    heroku create my-radius-viewer
    heroku stack:set heroku-24
    git push heroku main

Notes:
* Heroku injects `$PORT`; Streamlit defaults to 8501, so the Procfile flags are
  mandatory or the dyno will be killed with R10 (boot timeout).
* Streamlit uses websockets. They work on Heroku, but the router closes idle
  connections after 55s, so the app will reconnect — harmless here because all
  state is either cached or in `st.session_state`.
* Basic dynos have 512 MB RAM. Keep `geopandas`/`GDAL` out of
  `requirements.txt` unless you truly need them (see below); the wheel stack is
  ~250 MB and pushes the 500 MB slug limit.
* Free/eco dynos sleep. First request after sleep re-reads the CSV and rebuilds
  the map; that is the cold-start cost.

## Streamlit Community Cloud

Push the same repo, point the app at `app.py`. `Procfile`/`runtime.txt` are
ignored; set the Python version in the app's Advanced settings instead.

## The commented-out population grid

`gpd.read_file("population_500by500_grid.gpkg")` was the most expensive line in
the original file. Do not put it back as-is. Pre-process it offline once:

    import geopandas as gpd
    g = gpd.read_file("population_500by500_grid.gpkg")
    g = g.to_crs(4326)
    g["geometry"] = g.geometry.simplify(0.0005)
    g[["population", "geometry"]].to_parquet("population.parquet")

Then, at runtime, either read the parquet with `pandas` + `shapely` only, or
better: rasterise the grid to a PNG/`folium.raster_layers.ImageOverlay`, or
serve it as vector tiles. A 500x500 m grid over Switzerland is >150k polygons —
`folium.Choropleth` will try to embed all of them as GeoJSON in the page and the
browser tab will die long before the server does.
