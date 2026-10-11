import math
from datetime import date, datetime
from typing import Any

import geopandas as gpd
import pandas as pd
from shapely.geometry import mapping
from shapely.geometry.base import BaseGeometry
from app.services.crs_service import inspect_source_crs

from app.schemas.feature import ParsedFeature, ParsedFile


def to_json_safe(value: Any) -> Any:
    """Convert attribute values into JSON-compatible values."""

    if value is None:
        return None

    if isinstance(value, dict):
        return {
            str(key): to_json_safe(item)
            for key, item in value.items()
        }

    if isinstance(value, (list, tuple)):
        return [to_json_safe(item) for item in value]

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()

    if hasattr(value, "item"):
        try:
            value = value.item()
        except (AttributeError, ValueError):
            pass

    if isinstance(value, float) and not math.isfinite(value):
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    return str(value)


def get_source_fid(row) -> str | None:
    """Return an available source ID without inventing one."""

    column_lookup = {
        str(column).casefold(): column
        for column in row.index
    }

    candidates = ("fid", "ogc_fid", "objectid", "id")

    for candidate in candidates:
        actual_column = column_lookup.get(candidate)

        if actual_column is None:
            continue

        value = to_json_safe(row[actual_column])

        if value is not None and str(value).strip():
            return str(value)

    return None


def normalize_geodataframe(
    gdf: gpd.GeoDataFrame,
    filename: str,
    measurement_crs: str | None = None,
) -> ParsedFile:
    """Convert parsed geographic data to a consistent structure."""

    features = []
    geometry_column = gdf.geometry.name

    for index, (_, row) in enumerate(gdf.iterrows()):
        geometry = row[geometry_column]

        if isinstance(geometry, BaseGeometry):
            geometry_type = geometry.geom_type

            geometry_data = (
                mapping(geometry)
                if not geometry.is_empty
                else None
            )
        else:
            geometry_type = None
            geometry_data = None

        properties = {
            str(column): to_json_safe(row[column])
            for column in gdf.columns
            if column != geometry_column
        }

        features.append(
            ParsedFeature(
                feature_index=index,
                source_fid=get_source_fid(row),
                geometry_type=geometry_type,
                geometry=geometry_data,
                properties=properties,
            )
        )

    crs_info = inspect_source_crs(gdf.crs)

    return ParsedFile(
        filename=filename,
        feature_count=len(features),
        source_crs=crs_info.source_crs,
        source_crs_status=crs_info.status,
        features=features,
        measurement_crs=measurement_crs
    )
