import math

import pytest
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)

from app.schemas.measurement import MeasurementResult
from app.services.measurement_service import (
    MeasurementError,
    calculate_line_length,
    calculate_polygon_area,
    classify_geometry_type,
    format_measurement_result,
    measure_geometry,
)


@pytest.mark.parametrize(
    ("geometry_type", "expected"),
    [
        ("Polygon", "area"),
        ("MultiPolygon", "area"),
        ("LineString", "length"),
        ("MultiLineString", "length"),
        ("Point", "none"),
        ("MultiPoint", "none"),
        ("GeometryCollection", "unsupported"),
        (None, "unsupported"),
        ("UnknownGeometry", "unsupported"),
    ],
)
def test_geometry_classification(geometry_type, expected):
    assert classify_geometry_type(geometry_type) == expected


def test_polygon_area_exact_rectangle():
    polygon = Polygon([(0, 0), (10, 0), (10, 20), (0, 20), (0, 0)])
    assert calculate_polygon_area(polygon, "EPSG:32610") == 200.0


def test_multipolygon_area_is_combined():
    first = Polygon([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)])
    second = Polygon([(20, 0), (30, 0), (30, 10), (20, 10), (20, 0)])
    assert calculate_polygon_area(MultiPolygon([first, second]), "EPSG:32610") == 200.0


def test_area_rejects_geographic_crs():
    polygon = Polygon([(0, 0), (10, 0), (10, 20), (0, 20), (0, 0)])
    with pytest.raises(MeasurementError):
        calculate_polygon_area(polygon, "EPSG:4326")


def test_area_rejects_invalid_polygon():
    polygon = Polygon([(0, 0), (10, 10), (0, 10), (10, 0), (0, 0)])
    with pytest.raises(MeasurementError):
        calculate_polygon_area(polygon, "EPSG:32610")


def test_line_length_exact_345_line():
    assert calculate_line_length(LineString([(0, 0), (3, 4)]), "EPSG:32610") == 5.0


def test_multiline_length_is_combined():
    lines = MultiLineString([[(0, 0), (3, 4)], [(10, 10), (10, 16)]])
    assert calculate_line_length(lines, "EPSG:32610") == 11.0


def test_length_rejects_geographic_crs():
    with pytest.raises(MeasurementError):
        calculate_line_length(LineString([(0, 0), (3, 4)]), "EPSG:4326")


@pytest.mark.parametrize("geometry", [Point(5, 5), MultiPoint([(5, 5), (6, 6)])])
def test_points_have_no_measurement(geometry):
    result = measure_geometry(geometry, "EPSG:32610")
    assert result.measurement_status == "not_applicable"
    assert result.area_m2 is None
    assert result.length_m is None


def test_empty_geometry_has_explicit_status():
    result = measure_geometry(Polygon(), "EPSG:32610")
    assert result.measurement_status == "empty_geometry"
    assert result.area_m2 is None
    assert result.length_m is None


def test_invalid_polygon_has_explicit_status():
    polygon = Polygon([(0, 0), (10, 10), (0, 10), (10, 0), (0, 0)])
    result = measure_geometry(polygon, "EPSG:32610")
    assert result.measurement_status == "invalid_geometry"
    assert result.area_m2 is None
    assert result.length_m is None


def test_geometry_collection_is_unsupported():
    result = measure_geometry(GeometryCollection([Point(1, 1)]), "EPSG:32610")
    assert result.measurement_status == "unsupported_geometry"


def test_formatter_rounds_output_but_preserves_raw_value():
    result = MeasurementResult(
        geometry_type="Polygon",
        area_m2=123.456789,
        length_m=None,
        measurement_status="measured",
        measurement_crs="EPSG:32610",
    )
    formatted = format_measurement_result(result)
    assert formatted["area_m2"] == 123.46
    assert result.area_m2 == 123.456789


def test_formatter_rejects_nan():
    result = MeasurementResult(
        geometry_type="Polygon",
        area_m2=float("nan"),
        length_m=None,
        measurement_status="measured",
        measurement_crs="EPSG:32610",
    )
    with pytest.raises(MeasurementError):
        format_measurement_result(result)


def test_measurements_are_finite():
    polygon = Polygon([(0, 0), (10, 0), (10, 20), (0, 20), (0, 0)])
    result = measure_geometry(polygon, "EPSG:32610")
    assert math.isfinite(result.area_m2)
