"""
Offline preprocessing. Run this ONCE on your machine, commit the outputs,
and never touch the .gpkg on Heroku.

    python prepare_data.py

Inputs (local only, do NOT deploy these):
    Migros_and_competitors_stores_CH.csv
    population_500by500_grid.gpkg

Outputs (small, committed, deployed):
    data/stores.parquet          store table
    data/pop_points.parquet      one row per inhabited cell: x, y (EPSG:2056), population
    data/pop_overlay.png         pre-rendered population raster, EPSG:3857 aligned
    data/pop_overlay.json        lat/lon bounds + colour scale for the PNG
"""

from __future__ import annotations

import json
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
from PIL import Image

matplotlib.use("Agg")
from matplotlib import cm, colors  # noqa: E402

SRC_CSV = "Migros_and_competitors_stores_CH.csv"
SRC_GPKG = "population_500by500_grid.gpkg"
OUT = Path("data")

# Raster resolution in Web Mercator metres. 500 m at CH latitude is ~750 m in
# EPSG:3857, so this keeps roughly native detail without going silly.
RASTER_RES_M = 750
POP_COLUMN = "population"

OUT.mkdir(exist_ok=True)


def prepare_stores() -> None:
    df = pd.read_csv(SRC_CSV)
    if "radius_km" not in df.columns:
        df["radius_km"] = 5.0

    df["radius_km"] = df["radius_km"].astype("float32")
    df["latitude"] = df["latitude"].astype("float64")
    df["longitude"] = df["longitude"].astype("float64")

    # Project once here so the app never has to.
    pts = gpd.GeoSeries(
        gpd.points_from_xy(df["longitude"], df["latitude"]), crs="EPSG:4326"
    ).to_crs("EPSG:2056")
    df["x_lv95"] = pts.x.astype("float32")
    df["y_lv95"] = pts.y.astype("float32")

    if "chain" not in df.columns:
        # Best-effort chain label so the UI can group stores.
        df["chain"] = (
            df["display_name"].astype(str).str.split(r"[\s\-,]", n=1, regex=True).str[0]
        )

    df.to_parquet(OUT / "stores.parquet", index=False)
    print(f"stores.parquet: {len(df):,} rows")


def prepare_population() -> None:
    grid = gpd.read_file(SRC_GPKG, engine="pyogrio")
    if POP_COLUMN not in grid.columns:
        raise SystemExit(f"columns available: {list(grid.columns)}")

    grid = grid[grid[POP_COLUMN] > 0].copy()

    # --- point table, used for the "population reached" statistics -----------
    lv95 = grid.to_crs("EPSG:2056")
    cent = lv95.geometry.centroid
    pts = pd.DataFrame(
        {
            "x": cent.x.to_numpy("float32"),
            "y": cent.y.to_numpy("float32"),
            "population": grid[POP_COLUMN].to_numpy("float32"),
        }
    )
    pts.to_parquet(OUT / "pop_points.parquet", index=False)
    print(f"pop_points.parquet: {len(pts):,} rows")

    # --- raster overlay, used for display ------------------------------------
    merc = grid.to_crs("EPSG:3857")
    mc = merc.geometry.centroid
    x = mc.x.to_numpy()
    y = mc.y.to_numpy()
    pop = grid[POP_COLUMN].to_numpy("float64")

    x0, x1 = x.min() - RASTER_RES_M, x.max() + RASTER_RES_M
    y0, y1 = y.min() - RASTER_RES_M, y.max() + RASTER_RES_M
    nx = int(np.ceil((x1 - x0) / RASTER_RES_M))
    ny = int(np.ceil((y1 - y0) / RASTER_RES_M))

    ix = np.clip(((x - x0) / RASTER_RES_M).astype(int), 0, nx - 1)
    iy = np.clip(((y1 - y) / RASTER_RES_M).astype(int), 0, ny - 1)  # PNG is top-down

    acc = np.zeros((ny, nx), dtype="float64")
    np.add.at(acc, (iy, ix), pop)

    vmax = float(np.percentile(acc[acc > 0], 99))  # clip outliers so cities don't eat the scale
    norm = colors.Normalize(vmin=0.0, vmax=max(vmax, 1.0), clip=True)
    rgba = (cm.get_cmap("YlOrRd")(norm(acc)) * 255).astype("uint8")
    rgba[..., 3] = np.where(acc > 0, 190, 0)  # transparent where nobody lives

    Image.fromarray(rgba, mode="RGBA").save(
        OUT / "pop_overlay.png", optimize=True
    )

    bounds = (
        gpd.GeoSeries(
            gpd.points_from_xy([x0, x1], [y0, y1]), crs="EPSG:3857"
        )
        .to_crs("EPSG:4326")
    )
    meta = {
        "bounds": [
            [float(bounds.y.min()), float(bounds.x.min())],
            [float(bounds.y.max()), float(bounds.x.max())],
        ],
        "vmax": vmax,
        "res_m": RASTER_RES_M,
        "shape": [ny, nx],
    }
    (OUT / "pop_overlay.json").write_text(json.dumps(meta, indent=2))
    print(f"pop_overlay.png: {nx}x{ny}px, vmax={vmax:.0f}")


if __name__ == "__main__":
    prepare_stores()
    prepare_population()
