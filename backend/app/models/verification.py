import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    JSON,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class VerificationSessionStatus(str, enum.Enum):
    CREATED = "CREATED"
    CAPTURING = "CAPTURING"
    CAPTURE_COMPLETED = "CAPTURE_COMPLETED"
    UPLOADING = "UPLOADING"
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    ABORTED = "ABORTED"
    EXPIRED = "EXPIRED"
    UPLOAD_FAILED = "UPLOAD_FAILED"


class EvidenceFileType(str, enum.Enum):
    VIDEO = "VIDEO"
    SENSOR_DATA = "SENSOR_DATA"
    LOCATION_DATA = "LOCATION_DATA"
    SESSION_METADATA = "SESSION_METADATA"
    MANIFEST = "MANIFEST"
    THUMBNAIL = "THUMBNAIL"


class EvidenceUploadStatus(str, enum.Enum):
    PENDING = "PENDING"
    UPLOADING = "UPLOADING"
    UPLOADED = "UPLOADED"
    FAILED = "FAILED"


ACTIVE_SESSION_SQL = (
    "status IN ('CREATED','CAPTURING','CAPTURE_COMPLETED','UPLOADING','UPLOAD_FAILED')"
)


class VerificationSession(Base):
    __tablename__ = "verification_sessions"
    __table_args__ = (
        Index(
            "uq_active_verification_session_per_inspection",
            "inspection_id",
            unique=True,
            postgresql_where=text(ACTIVE_SESSION_SQL),
            sqlite_where=text(ACTIVE_SESSION_SQL),
        ),
        UniqueConstraint(
            "organization_id",
            "device_session_id",
            name="uq_verification_session_device_session",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    inspection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("inspections.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    inspector_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("inspectors.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    status: Mapped[VerificationSessionStatus] = mapped_column(
        Enum(VerificationSessionStatus, native_enum=False, length=32),
        default=VerificationSessionStatus.CREATED,
        index=True,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    capture_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    capture_ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)

    device_session_id: Mapped[str] = mapped_column(String(80), nullable=False)
    client_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    android_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    device_model: Mapped[str | None] = mapped_column(String(160), nullable=True)

    client_wall_clock: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    client_monotonic_ns: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    clock_offset_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    capture_anchor_wall_clock: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    capture_anchor_monotonic_ns: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    capture_duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    manifest_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    upload_idempotency_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    abort_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)

    site_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    pre_capture_location: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    device_capabilities: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    sensor_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    location_summary: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class EvidenceFile(Base):
    __tablename__ = "evidence_files"
    __table_args__ = (
        UniqueConstraint("session_id", "file_type", name="uq_evidence_session_file_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    inspection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("inspections.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("verification_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    file_type: Mapped[EvidenceFileType] = mapped_column(
        Enum(EvidenceFileType, native_enum=False, length=32), index=True, nullable=False
    )
    storage_key: Mapped[str] = mapped_column(String(700), unique=True, nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    upload_status: Mapped[EvidenceUploadStatus] = mapped_column(
        Enum(EvidenceUploadStatus, native_enum=False, length=20),
        default=EvidenceUploadStatus.PENDING,
        index=True,
        nullable=False,
    )
    hash_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
