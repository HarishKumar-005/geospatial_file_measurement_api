
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.db.models import FeatureResult, UploadedFile
from app.schemas.feature import ParsedFile
from app.schemas.measurement import MeasurementResult

def create_uploaded_file(
    db: Session,
    filename: str,
    file_format: str,
) -> UploadedFile:
    """Save a new uploaded-file metadata record."""

    record = UploadedFile(
        filename=filename,
        file_format=file_format,
        feature_count=0,
        source_crs=None,
        measurement_crs=None,
        status="processing",
    )

    try:
        db.add(record)
        db.commit()
        db.refresh(record)

    except SQLAlchemyError:
        db.rollback()
        raise

    return record



def save_processed_file(
    db: Session,
    record: UploadedFile,
    parsed_file: ParsedFile,
    measurements: list[MeasurementResult],
    measurement_crs: str,
) -> UploadedFile:
    """Save file metadata and all feature results in one transaction."""

    if len(parsed_file.features) != len(measurements):
        raise ValueError(
            "The number of measurements must match the feature count."
        )

    feature_records = []

    for feature, result in zip(
        parsed_file.features,
        measurements,
        strict=True,
    ):
        feature_records.append(
            FeatureResult(
                file_id=record.id,
                feature_index=feature.feature_index,
                source_fid=feature.source_fid,
                geometry_type=feature.geometry_type,
                geometry_json=feature.geometry,
                properties_json=feature.properties,
                area_m2=result.area_m2,
                length_m=result.length_m,
                measurement_status=result.measurement_status,
                measurement_crs=result.measurement_crs,
                message=result.message,
            )
        )

    try:
        record.feature_count = parsed_file.feature_count
        record.source_crs = parsed_file.source_crs
        record.measurement_crs = measurement_crs
        record.status = "completed"
        record.error_message = None

        db.add_all(feature_records)
        db.commit()
        db.refresh(record)

    except Exception:
        db.rollback()
        raise

    return record


def mark_uploaded_file_failed(
    db: Session,
    record: UploadedFile,
    error_message: str,
) -> None:
    """Record a controlled processing failure."""

    try:
        db.rollback()

        failed_record = db.get(UploadedFile, record.id)

        if failed_record is None:
            return

        failed_record.status = "failed"
        failed_record.error_message = error_message

        db.commit()

    except Exception:
        db.rollback()
        raise



def get_uploaded_file(
    db: Session,
    file_id: int,
) -> UploadedFile | None:
    """Retrieve one uploaded-file record by its ID."""

    return db.get(UploadedFile, file_id)



def get_feature_results(
    db: Session,
    file_id: int,
    limit: int = 100,
    offset: int = 0,
) -> list[FeatureResult]:
    """Retrieve one page of feature results in feature order."""

    statement = (
        select(FeatureResult)
        .where(FeatureResult.file_id == file_id)
        .order_by(FeatureResult.feature_index)
        .offset(offset)
        .limit(limit)
    )

    return list(db.scalars(statement).all())


