
from typing import Literal

from pydantic import BaseModel

from datetime import datetime



class FileUploadResponse(BaseModel):
    id: int
    filename: str
    file_format: Literal["kml", "zip"]
    content_type: str | None
    feature_count: int
    source_crs: str
    measurement_crs: str
    status: Literal["completed"]
    message: str




class APIErrorResponse(BaseModel):
    detail: str



class FileMetadataResponse(BaseModel):
    id: int
    filename: str
    file_format: Literal["kml", "zip"]
    feature_count: int
    source_crs: str | None
    measurement_crs: str | None
    status: Literal[
        "received",
        "processing",
        "completed",
        "failed",
    ]
    created_at: datetime
    error_message: str | None
