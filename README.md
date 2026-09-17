# Multi-Radius Location Viewer

## One-time local step

```bash
pip install -r requirements-dev.txt
python prepare_data.py          # reads the CSV + .gpkg, writes data/
git add data/ && git commit -m "add prepared data"
```

`data/` should end up as a few MB. If `pop_overlay.png` is large, raise
`RASTER_RES_M` in `prepare_data.py`.

## Local run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Heroku

```bash
heroku create your-app-name
heroku stack:set heroku-24
git push heroku main
heroku ps:scale web=1
```

Notes:

- `Procfile` binds to `$PORT`; Heroku kills anything that doesn't within 60 s.
- `.slugignore` keeps the `.gpkg` and CSV out of the slug (500 MB limit).
- Runtime `requirements.txt` has no geopandas/GDAL, so no apt buildpack and a
  much faster, smaller build.
- Streamlit uses WebSockets; Heroku routers support them, nothing extra needed.
- Eco/Basic dynos have 512 MB RAM. The KD-tree over the population points is
  built once per dyno via `@st.cache_resource`; if you hit R14, drop
  `pop_points.parquet` to `float32` only or pre-aggregate to 1 km cells.
- Dynos sleep on Eco. First request after sleep pays the cold start plus the
  cache build — budget ~10 s.
