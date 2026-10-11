import math

import pytest

from app.services.file_processing_service import (
    FileProcessingError,
    process_geospatial_file,
)
from app.services.geospatial_service import (
    GeospatialParseError,
    read_kml,
    read_shapefile_zip,
)


def test_kml_parser_extracts_feature(tmp_path, kml_bytes):
    path = tmp_path / "demo.kml"
    path.write_bytes(kml_bytes)
    gdf = read_kml(path)
    assert len(gdf) == 1
    assert gdf.geometry.iloc[0].geom_type == "Polygon"
    assert gdf.crs.to_string() == "EPSG:4326"
    assert gdf.iloc[0]["Name"] == "Demo Parcel"


def test_shapefile_zip_parser_extracts_feature(tmp_path, shapefile_zip_bytes):
    path = tmp_path / "demo.zip"
    path.write_bytes(shapefile_zip_bytes)
    gdf = read_shapefile_zip(path)
    assert len(gdf) == 1
    assert gdf.geometry.iloc[0].geom_type == "Polygon"
    assert gdf.crs.to_string() == "EPSG:4326"
    assert gdf.iloc[0]["Name"] == "Demo Parcel"


def test_end_to_end_kml_processing(tmp_path, kml_bytes):
    path = tmp_path / "demo.kml"
    path.write_bytes(kml_bytes)
    parsed, measurements, measurement_crs = process_geospatial_file(path, path.name)
    assert parsed.feature_count == 1
    assert parsed.source_crs == "EPSG:4326"
    assert parsed.source_crs_status == "known"
    assert measurement_crs == "EPSG:32610"
    assert len(measurements) == 1
    assert measurements[0].geometry_type == "Polygon"
    assert measurements[0].measurement_status == "measured"
    assert measurements[0].area_m2 is not None
    assert math.isfinite(measurements[0].area_m2)
    assert measurements[0].area_m2 > 0


def test_end_to_end_shapefile_processing(tmp_path, shapefile_zip_bytes):
    path = tmp_path / "demo.zip"
    path.write_bytes(shapefile_zip_bytes)
    parsed, measurements, measurement_crs = process_geospatial_file(path, path.name)
    assert parsed.feature_count == 1
    assert parsed.source_crs == "EPSG:4326"
    assert measurement_crs == "EPSG:32610"
    assert measurements[0].area_m2 > 0
    assert measurements[0].length_m is None


def test_equivalent_kml_and_shapefile_measurements_match(
    tmp_path, kml_bytes, shapefile_zip_bytes
):
    kml_path = tmp_path / "demo.kml"
    zip_path = tmp_path / "demo.zip"
    kml_path.write_bytes(kml_bytes)
    zip_path.write_bytes(shapefile_zip_bytes)

    _, kml_measurements, _ = process_geospatial_file(kml_path, kml_path.name)
    _, shp_measurements, _ = process_geospatial_file(zip_path, zip_path.name)

    assert math.isclose(
        kml_measurements[0].area_m2,
        shp_measurements[0].area_m2,
        rel_tol=1e-8,
    )


def test_missing_prj_does_not_guess_crs(tmp_path, shapefile_zip_without_prj_bytes):
    path = tmp_path / "no_prj.zip"
    path.write_bytes(shapefile_zip_without_prj_bytes)
    gdf = read_shapefile_zip(path)
    assert gdf.crs is None
    with pytest.raises(FileProcessingError):
        process_geospatial_file(path, path.name)


def test_malformed_kml_is_rejected(tmp_path):
    path = tmp_path / "malformed.kml"
    path.write_text("<kml><Document>", encoding="utf-8")
    with pytest.raises(GeospatialParseError):
        read_kml(path)


def test_wrong_file_suffix_is_rejected(tmp_path):
    path = tmp_path / "data.txt"
    path.write_text("not a geographic file", encoding="utf-8")
    with pytest.raises(GeospatialParseError):
        read_kml(path)
