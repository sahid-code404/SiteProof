import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class FusionAnalysisStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class ConsistencyStatus(str, enum.Enum):
    CONSISTENT = "CONSISTENT"
    PARTIALLY_CONSISTENT = "PARTIALLY_CONSISTENT"
    MISMATCH = "MISMATCH"
    INCONCLUSIVE = "INCONCLUSIVE"


class MotionDirection(str, enum.Enum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    UP = "UP"
    DOWN = "DOWN"
    MIXED = "MIXED"
    NONE = "NONE"


class MismatchReason(str, enum.Enum):
    OPPOSITE_DIRECTION = "OPPOSITE_DIRECTION"
    VISUAL_WITHOUT_SENSOR_MOTION = "VISUAL_WITHOUT_SENSOR_MOTION"
    SENSOR_WITHOUT_VISUAL_MOTION = "SENSOR_WITHOUT_VISUAL_MOTION"
    MAGNITUDE_MISMATCH = "MAGNITUDE_MISMATCH"
    TEMPORAL_MISMATCH = "TEMPORAL_MISMATCH"
    DURATION_MISMATCH = "DURATION_MISMATCH"
    LOW_SENSOR_QUALITY = "LOW_SENSOR_QUALITY"
    LOW_VISUAL_QUALITY = "LOW_VISUAL_QUALITY"
    SCENE_CONTINUITY_ANOMALY = "SCENE_CONTINUITY_ANOMALY"
    CURVE_UNAVAILABLE = "CURVE_UNAVAILABLE"


class VisualInertialResult(Base):
    __tablename__ = "visual_inertial_results"
    __table_args__ = (
        UniqueConstraint(
            "challenge_id",
            "fusion_version",
            name="uq_visual_inertial_challenge_version",
        ),
        Index(
            "ix_visual_inertial_session_status",
            "session_id",
            "consistency_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("verification_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    challenge_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("verification_challenges.id", ondelete="CASCADE"), index=True, nullable=False
    )

    fusion_version: Mapped[str] = mapped_column(String(40), nullable=False)
    analysis_status: Mapped[FusionAnalysisStatus] = mapped_column(
        Enum(FusionAnalysisStatus, native_enum=False, length=20),
        index=True,
        nullable=False,
    )
    consistency_status: Mapped[ConsistencyStatus] = mapped_column(
        Enum(ConsistencyStatus, native_enum=False, length=32),
        index=True,
        nullable=False,
        default=ConsistencyStatus.INCONCLUSIVE,
    )

    sensor_direction: Mapped[MotionDirection] = mapped_column(
        Enum(MotionDirection, native_enum=False, length=16),
        nullable=False,
        default=MotionDirection.NONE,
    )
    visual_direction: Mapped[MotionDirection] = mapped_column(
        Enum(MotionDirection, native_enum=False, length=16),
        nullable=False,
        default=MotionDirection.NONE,
    )

    sensor_angle_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    visual_angle_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    angle_difference_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    relative_angle_error: Mapped[float | None] = mapped_column(Float, nullable=True)

    sensor_start_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visual_start_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_offset_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sensor_peak_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visual_peak_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sensor_end_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visual_end_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_offset_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sensor_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    visual_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    motion_curve_correlation: Mapped[float | None] = mapped_column(Float, nullable=True)
    best_lag_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    direction_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    magnitude_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    timing_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    duration_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    correlation_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    raw_consistency_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    effective_consistency_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    fusion_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    sensor_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    visual_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    mismatch_reasons_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    diagnostics_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
