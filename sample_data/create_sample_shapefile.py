from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

import geopandas as gpd
from shapely.geometry import Polygon


sample_dir = Path("sample_data")
shapefile_dir = sample_dir / "generated_shapefile"

shapefile_dir.mkdir(parents=True, exist_ok=True)

polygon = Polygon([
    (-122.42, 37.77),
    (-122.41, 37.77),
    (-122.41, 37.78),
    (-122.42, 37.78),
    (-122.42, 37.77),
])

gdf = gpd.GeoDataFrame(
    {"Name": ["Sample Parcel"]},
    geometry=[polygon],
    crs="EPSG:4326",
)

shapefile_path = shapefile_dir / "demo.shp"

gdf.to_file(
    shapefile_path,
    driver="ESRI Shapefile",
    engine="pyogrio",
    index=False,
)

zip_path = sample_dir / "real_shapefile.zip"

components = {
    ".shp", ".shx", ".dbf", ".prj", ".cpg"
}

with ZipFile(zip_path, "w", ZIP_DEFLATED) as archive:
    for component in shapefile_dir.iterdir():
        if component.suffix.lower() in components:
            archive.write(component, arcname=component.name)

print("Created:", zip_path)
print("Shapefile components:")
for component in shapefile_dir.iterdir():
    print("-", component.name)
