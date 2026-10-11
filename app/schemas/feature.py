from typing import Any, Literal
from pydantic import BaseModel, Field


class ParsedFeature(BaseModel):
    feature_index: int = Field(ge=0)
    source_fid: str | None = None
    geometry_type: str | None = None
    geometry: dict[str, Any] | None = None
    properties: dict[str, Any] = Field(default_factory=dict)



class ParsedFile(BaseModel):
    filename: str
    feature_count: int = Field(ge=0)

    source_crs: str | None = None
    source_crs_status: Literal["known", "missing"]

    measurement_crs: str | None = None

    features: list[ParsedFeature]

