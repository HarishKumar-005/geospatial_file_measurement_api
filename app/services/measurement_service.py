from typing import Literal
import math
from app.schemas.measurement import MeasurementResult
from pyproj import CRS
from pyproj.exceptions import CRSError
from shapely.geometry.base import BaseGeometry
from app.schemas.measurement import MeasurementResult


MeasurementKind = Literal[
    "area",
    "length",
    "none",
    "unsupported",
]


def classify_geometry_type(
    geometry_type: str | None,
) -> MeasurementKind:
    """Determine the measurement operation for a geometry."""

    if geometry_type in {"Polygon", "MultiPolygon"}:
        return "area"

    if geometry_type in {"LineString", "MultiLineString"}:
        return "length"

    if geometry_type in {"Point", "MultiPoint"}:
        return "none"

    return "unsupported"



class MeasurementError(ValueError):
    """Raised when a geometry measurement cannot be calculated."""


class UnsupportedGeometryMeasurementError(MeasurementError):
    """Raised when the geometry type does not support area measurement."""


def calculate_polygon_area(
    geometry: BaseGeometry,
    measurement_crs: str | CRS,
) -> float:
    """
    Calculate polygon area in square metres.

    Important:
    The geometry must already be transformed into measurement_crs.
    Shapely geometries do not store their CRS themselves.
    """

    try:
        crs = CRS.from_user_input(measurement_crs)
    except (CRSError, TypeError, ValueError) as exc:
        raise MeasurementError(
            "The measurement CRS is invalid."
        ) from exc

    if not crs.is_projected:
        raise MeasurementError(
            "Area calculation requires a projected CRS."
        )

    axes = crs.axis_info

    if len(axes) < 2 or any(
        axis.unit_name.casefold() not in {"metre", "meter"}
        for axis in axes[:2]
    ):
        raise MeasurementError(
            "Area calculation requires a CRS with metre units."
        )

    if not isinstance(geometry, BaseGeometry):
        raise MeasurementError(
            "A valid Shapely geometry is required."
        )

    if geometry.geom_type not in {"Polygon", "MultiPolygon"}:
        raise UnsupportedGeometryMeasurementError(
            f"Area is not supported for {geometry.geom_type}."
        )

    if geometry.is_empty:
        raise MeasurementError(
            "Cannot calculate the area of an empty geometry."
        )

    if not geometry.is_valid:
        raise MeasurementError(
            "Cannot calculate the area of an invalid geometry."
        )

    area = float(geometry.area)

    if not math.isfinite(area) or area < 0:
        raise MeasurementError(
            "The calculated area is not a valid finite value."
        )

    return area



def calculate_line_length(
    geometry: BaseGeometry,
    measurement_crs: str | CRS,
) -> float:
    """
    Calculate LineString or MultiLineString length in metres.

    The geometry must already be transformed into measurement_crs.
    Shapely geometries do not store their CRS themselves.
    """

    try:
        crs = CRS.from_user_input(measurement_crs)
    except (CRSError, TypeError, ValueError) as exc:
        raise MeasurementError(
            "The measurement CRS is invalid."
        ) from exc

    if not crs.is_projected:
        raise MeasurementError(
            "Length calculation requires a projected CRS."
        )

    axes = crs.axis_info

    if len(axes) < 2 or any(
        axis.unit_name.casefold() not in {"metre", "meter"}
        for axis in axes[:2]
    ):
        raise MeasurementError(
            "Length calculation requires a CRS with metre units."
        )

    if not isinstance(geometry, BaseGeometry):
        raise MeasurementError(
            "A valid Shapely geometry is required."
        )

    if geometry.geom_type not in {
        "LineString",
        "MultiLineString",
    }:
        raise UnsupportedGeometryMeasurementError(
            f"Length is not supported for {geometry.geom_type}."
        )

    if geometry.is_empty:
        raise MeasurementError(
            "Cannot calculate the length of an empty geometry."
        )

    if not geometry.is_valid:
        raise MeasurementError(
            "Cannot calculate the length of an invalid geometry."
        )

    length = float(geometry.length)

    if not math.isfinite(length) or length < 0:
        raise MeasurementError(
            "The calculated length is not a valid finite value."
        )

    return length


def measure_geometry(
    geometry: BaseGeometry,
    measurement_crs: str | CRS,
) -> MeasurementResult:
    """
    Measure a supported geometry or return an explicit status
    when a measurement cannot be produced.
    """

    if not isinstance(geometry, BaseGeometry):
        raise MeasurementError(
            "A valid Shapely geometry is required."
        )

    geometry_type = geometry.geom_type

    # Check empty geometries before their geometry type.
    if geometry.is_empty:
        return MeasurementResult(
            geometry_type=geometry_type,
            area_m2=None,
            length_m=None,
            measurement_status="empty_geometry",
            measurement_crs=None,
            message="The geometry is empty.",
        )

    # Invalid geometry should not produce a measurement.
    if not geometry.is_valid:
        return MeasurementResult(
            geometry_type=geometry_type,
            area_m2=None,
            length_m=None,
            measurement_status="invalid_geometry",
            measurement_crs=None,
            message="The geometry is invalid.",
        )

    measurement_kind = classify_geometry_type(geometry_type)

    # Points do not have area or line length in this API.
    if measurement_kind == "none":
        return MeasurementResult(
            geometry_type=geometry_type,
            area_m2=None,
            length_m=None,
            measurement_status="not_applicable",
            measurement_crs=None,
            message="Area and line length are not applicable.",
        )

    # Preserve unsupported types without attempting a calculation.
    if measurement_kind == "unsupported":
        return MeasurementResult(
            geometry_type=geometry_type,
            area_m2=None,
            length_m=None,
            measurement_status="unsupported_geometry",
            measurement_crs=None,
            message="This geometry type is not supported in version 1.",
        )

    # Calculate only after geometry checks have passed.
    crs = CRS.from_user_input(measurement_crs)

    if measurement_kind == "area":
        area = calculate_polygon_area(geometry, crs)

        return MeasurementResult(
            geometry_type=geometry_type,
            area_m2=area,
            length_m=None,
            measurement_status="measured",
            measurement_crs=crs.to_string(),
            message=None,
        )

    length = calculate_line_length(geometry, crs)

    return MeasurementResult(
        geometry_type=geometry_type,
        area_m2=None,
        length_m=length,
        measurement_status="measured",
        measurement_crs=crs.to_string(),
        message=None,
    )



MEASUREMENT_DECIMAL_PLACES = 2


def format_measurement_result(
    result: MeasurementResult,
) -> dict:
    """
    Format a measurement result for an API response.

    Calculations retain their original precision.
    Only this output representation is rounded.
    """

    data = result.model_dump()

    area = result.area_m2
    length = result.length_m

    if result.measurement_status == "measured":
        # Exactly one measurement must be present.
        if (area is None) == (length is None):
            raise MeasurementError(
                "A measured result must contain exactly one "
                "of area_m2 or length_m."
            )

        if result.measurement_crs is None:
            raise MeasurementError(
                "A measured result must identify its measurement CRS."
            )

    else:
        # Non-measured results must not contain numeric measurements.
        if area is not None or length is not None:
            raise MeasurementError(
                "A non-measured result must have null area and length."
            )

    for field in ("area_m2", "length_m"):
        value = data[field]

        if value is None:
            continue

        if not math.isfinite(value) or value < 0:
            raise MeasurementError(
                f"{field} must be a finite, non-negative number."
            )

        rounded_value = round(value, MEASUREMENT_DECIMAL_PLACES)

        # Avoid displaying negative zero.
        data[field] = (
            0.0 if rounded_value == 0 else rounded_value
        )

    return data


