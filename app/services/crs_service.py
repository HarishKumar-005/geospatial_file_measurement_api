from dataclasses import dataclass
from typing import Literal

from pyproj import CRS
from pyproj.exceptions import CRSError
import math
import shapely
import geopandas as gpd

class CRSValidationError(ValueError):
    """Raised when CRS metadata is present but invalid."""


@dataclass(frozen=True)
class CRSInfo:
    source_crs: str | None
    status: Literal["known", "missing"]
    is_geographic: bool | None
    axis_units: tuple[str, ...]


def inspect_source_crs(source_crs: object) -> CRSInfo:
    """
    Inspect source CRS metadata without guessing missing information.
    """

    if source_crs is None:
        return CRSInfo(
            source_crs=None,
            status="missing",
            is_geographic=None,
            axis_units=(),
        )

    if isinstance(source_crs, str) and not source_crs.strip():
        return CRSInfo(
            source_crs=None,
            status="missing",
            is_geographic=None,
            axis_units=(),
        )

    try:
        crs = CRS.from_user_input(source_crs)
    except (CRSError, TypeError, ValueError) as exc:
        raise CRSValidationError(
            "The source CRS metadata is invalid."
        ) from exc

    return CRSInfo(
        source_crs=crs.to_string(),
        status="known",
        is_geographic=crs.is_geographic,
        axis_units=tuple(
            axis.unit_name for axis in crs.axis_info
        ),
    )



class MissingSourceCRSError(ValueError):
    """Raised when a dataset has no source CRS."""


def require_source_crs(source_crs: object) -> CRSInfo:
    """
    Require valid CRS metadata before coordinate transformation
    or measurement.
    """

    crs_info = inspect_source_crs(source_crs)

    if crs_info.status == "missing":
        raise MissingSourceCRSError(
            "The source CRS is missing. Measurements cannot proceed "
            "until the coordinate reference system is established."
        )

    return crs_info



class MeasurementCRSSelectionError(ValueError):
    """Raised when a suitable measurement CRS cannot be selected."""


def select_measurement_crs(gdf: gpd.GeoDataFrame) -> CRS:
    """
    Estimate a projected UTM CRS for a local geographic dataset.

    This version uses conservative extent limits. It does not
    support global datasets or datasets spanning multiple UTM zones.
    """

    if not isinstance(gdf, gpd.GeoDataFrame):
        raise MeasurementCRSSelectionError(
            "Expected a GeoDataFrame."
        )

    require_source_crs(gdf.crs)

    if gdf.empty:
        raise MeasurementCRSSelectionError(
            "Cannot select a CRS for an empty dataset."
        )

    try:
        geometry = gdf.geometry
        usable_mask = ~(shapely.is_missing(geometry.array) | shapely.is_empty(geometry.array))
        usable = gdf.loc[usable_mask]

        if usable.empty:
            raise MeasurementCRSSelectionError(
                "The dataset has no non-empty geometries."
            )

        # Convert a temporary copy to geographic coordinates
        # so we can examine the dataset's longitude/latitude extent.
        geographic = usable.to_crs("EPSG:4326")
        bounds = geographic.total_bounds

    except MeasurementCRSSelectionError:
        raise
    except Exception as exc:
        raise MeasurementCRSSelectionError(
            "Could not determine the dataset's geographic extent."
        ) from exc

    min_lon, min_lat, max_lon, max_lat = map(float, bounds)

    if not all(
        math.isfinite(value)
        for value in (min_lon, min_lat, max_lon, max_lat)
    ):
        raise MeasurementCRSSelectionError(
            "The dataset has non-finite geographic bounds."
        )

    # UTM's conventional latitude coverage is approximately
    # 80 degrees south to 84 degrees north.
    if min_lat < -80 or max_lat > 84:
        raise MeasurementCRSSelectionError(
            "The dataset is outside the supported UTM latitude range."
        )

    longitude_span = max_lon - min_lon
    latitude_span = max_lat - min_lat

    # Conservative version 1 limits for local datasets.
    if longitude_span > 6:
        raise MeasurementCRSSelectionError(
            "The dataset spans more than 6 degrees of longitude. "
            "A single UTM zone may not be suitable."
        )

    if latitude_span > 6:
        raise MeasurementCRSSelectionError(
            "The dataset spans more than 6 degrees of latitude. "
            "A regional CRS strategy is required."
        )

    try:
        estimated = geographic.estimate_utm_crs(
            datum_name="WGS 84"
        )

        if estimated is None:
            raise MeasurementCRSSelectionError(
                "No suitable UTM CRS could be estimated."
            )

        measurement_crs = CRS.from_user_input(estimated)

    except MeasurementCRSSelectionError:
        raise
    except Exception as exc:
        raise MeasurementCRSSelectionError(
            "Could not estimate a measurement CRS."
        ) from exc

    if not measurement_crs.is_projected:
        raise MeasurementCRSSelectionError(
            "The selected measurement CRS is not projected."
        )

    axes = measurement_crs.axis_info

    if len(axes) < 2 or any(
        axis.unit_name.casefold() not in {"metre", "meter"}
        for axis in axes[:2]
    ):
        raise MeasurementCRSSelectionError(
            "The selected CRS does not use metres on its first two axes."
        )

    return measurement_crs



class CRSTransformationError(ValueError):
    """Raised when geometries cannot be transformed."""


def transform_to_measurement_crs(
    gdf: gpd.GeoDataFrame,
) -> tuple[gpd.GeoDataFrame, CRS]:
    """
    Transform geometries to the selected measurement CRS.

    Returns:
        A new GeoDataFrame in the measurement CRS and that CRS.

    The original GeoDataFrame is not modified.
    """

    if not isinstance(gdf, gpd.GeoDataFrame):
        raise CRSTransformationError(
            "Expected a GeoDataFrame."
        )

    require_source_crs(gdf.crs)

    # Select the target CRS using our M4.3 logic.
    measurement_crs = select_measurement_crs(gdf)

    try:
        # to_crs() returns a transformed GeoDataFrame.
        transformed_gdf = gdf.to_crs(measurement_crs)

    except Exception as exc:
        raise CRSTransformationError(
            "Could not transform geometries to the measurement CRS."
        ) from exc

    if transformed_gdf.crs is None:
        raise CRSTransformationError(
            "The transformed dataset has no CRS metadata."
        )

    actual_crs = CRS.from_user_input(transformed_gdf.crs)

    if not actual_crs.equals(measurement_crs):
        raise CRSTransformationError(
            "The transformed dataset CRS does not match the target CRS."
        )

    return transformed_gdf, measurement_crs


