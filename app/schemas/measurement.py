from typing import Any, Literal

from pydantic import BaseModel

class MeasurementResult(BaseModel):
    geometry_type: str

    area_m2: float | None = None
    length_m: float | None = None

    measurement_status: Literal[
        "measured",
        "not_applicable",
        "unsupported_geometry",
        "empty_geometry",
        "invalid_geometry",
    ]

    measurement_crs: str | None = None
    message: str | None = None


class FeatureMeasurementResponse(BaseModel):
    feature_index: int
    source_fid: str | None = None
    geometry_type: str | None = None
    properties: dict[str, Any]

    area_m2: float | None = None
    length_m: float | None = None

    measurement_status: Literal[
        "measured",
        "not_applicable",
        "unsupported_geometry",
        "empty_geometry",
        "invalid_geometry",
    ]

    measurement_crs: str | None = None
    message: str | None = None


class FileMeasurementsResponse(BaseModel):
    id: int
    filename: str
    feature_count: int
    returned_count: int
    limit: int
    offset: int
    source_crs: str | None = None
    measurement_crs: str | None = None
    status: Literal[
        "received",
        "processing",
        "completed",
        "failed",
    ]
    features: list[FeatureMeasurementResponse]
