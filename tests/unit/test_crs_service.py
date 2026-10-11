import geopandas as gpd
import pytest
from pyproj import CRS
from shapely.geometry import GeometryCollection, MultiPoint, Point, Polygon

from app.services.crs_service import (
    CRSValidationError,
    MeasurementCRSSelectionError,
    MissingSourceCRSError,
    inspect_source_crs,
    require_source_crs,
    select_measurement_crs,
    transform_to_measurement_crs,
)


def make_local_dataset(crs="EPSG:4326"):
    polygon = Polygon([
        (-122.420, 37.770),
        (-122.419, 37.770),
        (-122.419, 37.771),
        (-122.420, 37.771),
        (-122.420, 37.770),
    ])
    return gpd.GeoDataFrame({"name": ["Test parcel"]}, geometry=[polygon], crs=crs)


def test_inspect_known_geographic_crs():
    info = inspect_source_crs("EPSG:4326")
    assert info.status == "known"
    assert info.source_crs == "EPSG:4326"
    assert info.is_geographic is True
    assert info.axis_units == ("degree", "degree")


def test_missing_crs_is_not_guessed():
    assert inspect_source_crs(None).status == "missing"
    with pytest.raises(MissingSourceCRSError):
        require_source_crs(None)


def test_invalid_crs_is_rejected():
    with pytest.raises(CRSValidationError):
        require_source_crs("NOT_A_VALID_CRS")


def test_selects_local_utm_crs_in_metres():
    measurement_crs = select_measurement_crs(make_local_dataset())
    assert measurement_crs.is_projected
    assert measurement_crs.to_string() == "EPSG:32610"
    assert all(
        axis.unit_name.casefold() in {"metre", "meter"}
        for axis in measurement_crs.axis_info[:2]
    )


def test_transform_does_not_modify_original():
    original = make_local_dataset()
    original_bounds = tuple(original.total_bounds)
    transformed, target = transform_to_measurement_crs(original)
    assert original.crs.to_string() == "EPSG:4326"
    assert tuple(original.total_bounds) == original_bounds
    assert CRS.from_user_input(transformed.crs).equals(target)
    assert tuple(transformed.total_bounds) != original_bounds


def test_empty_dataset_is_rejected():
    empty = gpd.GeoDataFrame(geometry=[], crs="EPSG:4326")
    with pytest.raises(MeasurementCRSSelectionError):
        select_measurement_crs(empty)


def test_only_empty_geometries_are_rejected():
    empty = gpd.GeoDataFrame(
        {"name": ["empty"]}, geometry=[GeometryCollection()], crs="EPSG:4326"
    )
    with pytest.raises(MeasurementCRSSelectionError):
        select_measurement_crs(empty)


def test_polar_latitude_is_rejected_by_v1_policy():
    polar = gpd.GeoDataFrame(
        {"name": ["polar"]}, geometry=[Point(10, 85)], crs="EPSG:4326"
    )
    with pytest.raises(MeasurementCRSSelectionError):
        select_measurement_crs(polar)


def test_wide_longitude_extent_is_rejected():
    wide = gpd.GeoDataFrame(
        {"name": ["wide"]},
        geometry=[MultiPoint([(-10, 20), (0, 20)])],
        crs="EPSG:4326",
    )
    with pytest.raises(MeasurementCRSSelectionError):
        select_measurement_crs(wide)


def test_wide_latitude_extent_is_rejected():
    wide = gpd.GeoDataFrame(
        {"name": ["wide"]},
        geometry=[MultiPoint([(-120, 25), (-120, 35)])],
        crs="EPSG:4326",
    )
    with pytest.raises(MeasurementCRSSelectionError):
        select_measurement_crs(wide)
