
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    __table_args__ = (
        CheckConstraint(
            "feature_count >= 0",
            name="ck_uploaded_files_feature_count",
        ),
        CheckConstraint(
            "file_format IN ('kml', 'zip')",
            name="ck_uploaded_files_format",
        ),
        CheckConstraint(
            "status IN ('received', 'processing', 'completed', 'failed')",
            name="ck_uploaded_files_status",
        ),
        Index("ix_uploaded_files_created_at", "created_at"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    file_format: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
    )

    feature_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    source_crs: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    measurement_crs: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="processing",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    features: Mapped[list["FeatureResult"]] = relationship(
        back_populates="uploaded_file",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class FeatureResult(Base):
    __tablename__ = "feature_results"

    __table_args__ = (
        UniqueConstraint(
            "file_id",
            "feature_index",
            name="uq_feature_file_index",
        ),
        CheckConstraint(
            "feature_index >= 0",
            name="ck_feature_index_nonnegative",
        ),
        CheckConstraint(
            "area_m2 IS NULL OR area_m2 >= 0",
            name="ck_feature_area_nonnegative",
        ),
        CheckConstraint(
            "length_m IS NULL OR length_m >= 0",
            name="ck_feature_length_nonnegative",
        ),
        CheckConstraint(
            "measurement_status IN ("
            "'measured', 'not_applicable', "
            "'unsupported_geometry', 'empty_geometry', "
            "'invalid_geometry')",
            name="ck_feature_measurement_status",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    file_id: Mapped[int] = mapped_column(
        ForeignKey("uploaded_files.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    feature_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    source_fid: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    geometry_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    geometry_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    properties_json: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )

    area_m2: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    length_m: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    measurement_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    measurement_crs: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    uploaded_file: Mapped["UploadedFile"] = relationship(
        back_populates="features",
    )
