from pathlib import Path

import geopandas as gpd
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent

INPUT_FILE = (
    BASE_DIR /
    "population_500by500_grid.gpkg"
)

OUTPUT_FILE = (
    BASE_DIR /
    "population_cells.parquet"
)


grid = gpd.read_file(
    INPUT_FILE,
    columns=["population"],
)

if grid.crs is None:
    raise ValueError(
        "GeoPackage has no CRS."
    )

grid = grid.to_crs(4326)

centers = grid.geometry.representative_point()

population = pd.DataFrame(
    {
        "longitude": centers.x,
        "latitude": centers.y,
        "population": pd.to_numeric(
            grid["population"],
            errors="coerce",
        ).fillna(0),
    }
)

population = population[
    population["population"] > 0
].reset_index(drop=True)

population.to_parquet(
    OUTPUT_FILE,
    index=False,
    compression="zstd",
)

print(
    f"Created {OUTPUT_FILE} "
    f"with {len(population):,} cells."
)