import ntpath
import stat
import zlib
from app.repositories.file_repository import get_uploaded_file
from app.schemas.file import FileMetadataResponse
from fastapi import Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from fastapi import Query
from app.db.session import get_db

from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile
from typing import Annotated

from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.schemas.file import FileUploadResponse, APIErrorResponse

import tempfile
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from app.repositories.file_repository import (
    create_uploaded_file,
    save_processed_file,
    mark_uploaded_file_failed,
)
from app.services.file_processing_service import (
    FileProcessingError,
    process_geospatial_file,
)

from app.repositories.file_repository import get_feature_results
from app.schemas.measurement import (
    MeasurementResult,
    FeatureMeasurementResponse,
    FileMeasurementsResponse,
)
from app.services.measurement_service import (
    MeasurementError,
    format_measurement_result,
)

router = APIRouter(prefix="/api/files", tags=["Files"])

ALLOWED_EXTENSIONS = {".kml", ".zip"}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MiB compressed upload

MAX_ZIP_ENTRIES = 1000
MAX_ZIP_TOTAL_SIZE = 100 * 1024 * 1024  # 100 MiB expanded
MAX_ZIP_MEMBER_SIZE = 50 * 1024 * 1024  # 50 MiB per file
MAX_ZIP_COMPRESSION_RATIO = 100


def get_safe_filename(filename: str) -> str:
    # Treat both types of slash as path separators.
    return filename.replace("\\", "/").rsplit("/", 1)[-1]

def get_file_size(file: UploadFile) -> int:
    try:
        file.file.seek(0, 2)
        return file.file.tell()
    finally:
        file.file.seek(0)


def has_kml_root(file: UploadFile) -> bool:
    try:
        file.file.seek(0)

        # Read only until the XML root element is found.
        iterator = ET.iterparse(file.file, events=("start",))
        _, root = next(iterator)

        # Handles namespaced roots such as {namespace}kml.
        root_name = root.tag.rsplit("}", 1)[-1]

        return root_name.lower() == "kml"

    except (
        ET.ParseError,
        DefusedXmlException,
        StopIteration,
        OSError,
        ValueError,
    ):
        return False

    finally:
        file.file.seek(0)



def validate_shapefile_zip(file: UploadFile) -> tuple[int, str] | None:
    try:
        file.file.seek(0)

        with ZipFile(file.file, "r") as archive:
            members = archive.infolist()

            if not members:
                return 422, "The ZIP archive is empty."

            if len(members) > MAX_ZIP_ENTRIES:
                return 413, "The ZIP archive contains too many entries."

            total_size = 0
            seen_paths = set()
            shapefile_groups = {}

            for member in members:
                original_name = member.filename

                # Normalize Windows separators for path inspection.
                normalized_name = original_name.replace("\\", "/")

                # Reject absolute paths and Windows drive paths.
                drive, _ = ntpath.splitdrive(original_name)

                if drive or normalized_name.startswith("/"):
                    return 422, "The ZIP contains an unsafe absolute path."

                if "\x00" in original_name:
                    return 422, "The ZIP contains an invalid filename."

                path_name = normalized_name.rstrip("/")

                if not path_name:
                    return 422, "The ZIP contains an invalid path."

                parts = path_name.split("/")

                # Reject traversal and ambiguous path components.
                if any(part in {"", ".", ".."} for part in parts):
                    return 422, "The ZIP contains an unsafe path."

                archive_path = PurePosixPath(path_name)
                canonical_path = archive_path.as_posix().casefold()

                # Avoid collisions on case-insensitive filesystems.
                if canonical_path in seen_paths:
                    return 422, "The ZIP contains duplicate paths."

                seen_paths.add(canonical_path)

                # Symbolic links are not needed for our GIS uploads.
                mode = (member.external_attr >> 16) & 0xFFFF

                if stat.S_ISLNK(mode):
                    return 422, "The ZIP contains a symbolic link."

                # Password-protected entries are not supported.
                if member.flag_bits & 0x1:
                    return 422, "Encrypted ZIP entries are not supported."

                if member.is_dir() or normalized_name.endswith("/"):
                    continue

                if member.file_size > MAX_ZIP_MEMBER_SIZE:
                    return 413, "A ZIP entry exceeds the 50 MiB limit."

                total_size += member.file_size

                if total_size > MAX_ZIP_TOTAL_SIZE:
                    return 413, "The ZIP expands beyond the 100 MiB limit."

                # Detect unusually high expansion ratios.
                if member.file_size > 0:
                    if member.compress_size == 0:
                        return 422, "The ZIP contains a suspicious entry."

                    ratio = member.file_size / member.compress_size

                    if ratio > MAX_ZIP_COMPRESSION_RATIO:
                        return 422, (
                            "The ZIP contains an entry with an "
                            "excessive compression ratio."
                        )

                # Group Shapefile components by directory and basename.
                extension = archive_path.suffix.casefold()

                if extension in {".shp", ".shx", ".dbf"}:
                    group_key = (
                        str(archive_path.parent).casefold(),
                        archive_path.stem.casefold(),
                    )

                    shapefile_groups.setdefault(group_key, set()).add(
                        extension
                    )

            required_components = {".shp", ".shx", ".dbf"}

            has_shapefile = any(
                required_components.issubset(components)
                for components in shapefile_groups.values()
            )

            if not has_shapefile:
                return 422, (
                    "The ZIP must contain matching .shp, .shx, "
                    "and .dbf files."
                )

            # Read entries to detect corrupt data and CRC errors.
            try:
                corrupt_member = archive.testzip()
            except (BadZipFile, OSError, RuntimeError, NotImplementedError,
                    EOFError, zlib.error):
                return 422, "The ZIP archive contains corrupt or unreadable data."

            if corrupt_member is not None:
                return 422, "The ZIP archive failed its integrity check."

            return None

    except (BadZipFile, OSError, RuntimeError, ValueError, EOFError):
        return 422, "The uploaded file is not a valid readable ZIP archive."

    finally:
        file.file.seek(0)




@router.post(
    "/",
    status_code=201,
    response_model=FileUploadResponse,
    responses={
        413: {
            "model": APIErrorResponse,
            "description": "Upload or archive exceeds configured size limits.",
        },
        415: {
            "model": APIErrorResponse,
            "description": "Unsupported file extension.",
        },
        422: {
            "model": APIErrorResponse,
            "description": "Invalid file, archive, or request data.",
        },
    },
)
async def upload_file(
    file: Annotated[
        UploadFile,
        File(
            description=(
                "Upload a KML file or a ZIP archive containing "
                "Shapefile data."
            )
        ),
    ],
    db: Annotated[Session, Depends(get_db)],
):
    if not file.filename:
        raise HTTPException(
            status_code=422,
            detail="A filename is required.",
        )

    filename = get_safe_filename(file.filename)

    if not filename or filename in {".", ".."}:
        raise HTTPException(
            status_code=422,
            detail="The supplied filename is invalid.",
        )

    extension = Path(filename).suffix.lower()

    # Check the extension against our allowlist.
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Upload a .kml or .zip file.",
        )

    file_size = get_file_size(file)

    if file_size == 0:
        raise HTTPException(
            status_code=422,
            detail="The uploaded file is empty.",
        )

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail="File exceeds the maximum allowed size of 10 MiB.",
        )

    # Check that ZIP uploads are actually ZIP archives.
    if extension == ".zip":
        zip_error = validate_shapefile_zip(file)

        if zip_error is not None:
            status_code, detail = zip_error

            raise HTTPException(
                status_code=status_code,
                detail=detail,
            )

    # Check that KML uploads have a KML XML root element.
    if extension == ".kml" and not has_kml_root(file):
        raise HTTPException(
            status_code=422,
            detail="The uploaded file does not have a valid KML root element.",
        )


    try:
        record = create_uploaded_file(
            db=db,
            filename=filename,
            file_format=extension[1:],
        )
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not save upload metadata.",
        ) from exc

    try:
        # Stage the validated upload in a temporary directory.
        # The client-supplied filename is not used as a filesystem path.
        with tempfile.TemporaryDirectory(
            prefix="geospatial-upload-"
        ) as temporary_directory:
            staged_path = (
                Path(temporary_directory) / f"upload{extension}"
            )

            await file.seek(0)

            with staged_path.open("wb") as destination:
                while chunk := await file.read(1024 * 1024):
                    destination.write(chunk)

            await file.seek(0)

            parsed_file, measurements, measurement_crs = (
                process_geospatial_file(
                    staged_path,
                    filename,
                )
            )

        record = save_processed_file(
            db=db,
            record=record,
            parsed_file=parsed_file,
            measurements=measurements,
            measurement_crs=measurement_crs,
        )

    except FileProcessingError as exc:
        try:
            mark_uploaded_file_failed(
                db,
                record,
                str(exc),
            )
        except SQLAlchemyError as db_exc:
            raise HTTPException(
                status_code=500,
                detail="Could not save the processing status.",
            ) from db_exc

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not save the processed feature results.",
        ) from exc

    return FileUploadResponse(
        id=record.id,
        filename=record.filename,
        file_format=record.file_format,
        content_type=file.content_type,
        feature_count=record.feature_count,
        source_crs=record.source_crs,
        measurement_crs=record.measurement_crs,
        status="completed",
        message="File processed and feature results saved successfully.",
    )



@router.get(
    "/{file_id}/",
    response_model=FileMetadataResponse,
    responses={
        404: {
            "model": APIErrorResponse,
            "description": "The requested file ID does not exist.",
        },
    },
)
def get_file_metadata(
    file_id: int,
    db: Annotated[Session, Depends(get_db)],
):
    record = get_uploaded_file(db, file_id)

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="File not found.",
        )

    return FileMetadataResponse(
        id=record.id,
        filename=record.filename,
        file_format=record.file_format,
        feature_count=record.feature_count,
        source_crs=record.source_crs,
        measurement_crs=record.measurement_crs,
        status=record.status,
        created_at=record.created_at,
        error_message=record.error_message,
    )



@router.get(
    "/{file_id}/measurements/",
    response_model=FileMeasurementsResponse,
    responses={
        404: {
            "model": APIErrorResponse,
            "description": "The requested file ID does not exist.",
        },
    },
)
def get_file_measurements_endpoint(
    file_id: int,
    db: Annotated[Session, Depends(get_db)],
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    record = get_uploaded_file(db, file_id)

    if record is None:
        raise HTTPException(
            status_code=404,
            detail="File not found.",
        )

    feature_records = get_feature_results(
        db,
        file_id,
        limit=limit,
        offset=offset,
    )

    response_features = []

    for feature in feature_records:
        measurement = MeasurementResult(
            geometry_type=feature.geometry_type or "Unknown",
            area_m2=feature.area_m2,
            length_m=feature.length_m,
            measurement_status=feature.measurement_status,
            measurement_crs=feature.measurement_crs,
            message=feature.message,
        )

        try:
            formatted = format_measurement_result(measurement)
        except (MeasurementError, ValueError) as exc:
            raise HTTPException(
                status_code=500,
                detail="A saved measurement result is invalid.",
            ) from exc

        response_features.append(
            FeatureMeasurementResponse(
                feature_index=feature.feature_index,
                source_fid=feature.source_fid,
                geometry_type=feature.geometry_type,
                properties=feature.properties_json or {},
                area_m2=formatted["area_m2"],
                length_m=formatted["length_m"],
                measurement_status=feature.measurement_status,
                measurement_crs=feature.measurement_crs,
                message=feature.message,
            )
        )

    return FileMeasurementsResponse(
        id=record.id,
        filename=record.filename,
        feature_count=record.feature_count,
        returned_count=len(response_features),
        limit=limit,
        offset=offset,
        source_crs=record.source_crs,
        measurement_crs=record.measurement_crs,
        status=record.status,
        features=response_features,
    )
