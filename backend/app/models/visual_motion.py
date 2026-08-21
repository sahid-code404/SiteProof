import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class VisualAnalysisStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    INCONCLUSIVE = "INCONCLUSIVE"
    FAILED = "FAILED"


class VisualDirection(str, enum.Enum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    UP = "UP"
    DOWN = "DOWN"
    MIXED = "MIXED"
    NONE = "NONE"


class VisualQuality(str, enum.Enum):
    GOOD = "GOOD"
    FAIR = "FAIR"
    POOR = "POOR"


class VisualMotionResult(Base):
    __tablename__ = "visual_motion_results"
    __table_args__ = (
        UniqueConstraint(
            "challenge_id",
            "analysis_version",
            name="uq_visual_motion_challenge_version",
        ),
        Index("ix_visual_motion_session_status", "session_id", "analysis_status"),
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

    analysis_version: Mapped[str] = mapped_column(String(40), nullable=False)
    analysis_status: Mapped[VisualAnalysisStatus] = mapped_column(
        Enum(VisualAnalysisStatus, native_enum=False, length=20), index=True, nullable=False
    )
    visual_direction: Mapped[VisualDirection] = mapped_column(
        Enum(VisualDirection, native_enum=False, length=16), nullable=False, default=VisualDirection.NONE
    )
    visual_quality: Mapped[VisualQuality] = mapped_column(
        Enum(VisualQuality, native_enum=False, length=12), nullable=False, default=VisualQuality.POOR
    )

    estimated_rotation_degrees: Mapped[float | None] = mapped_column(Float, nullable=True)
    translation_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    translation_y: Mapped[float | None] = mapped_column(Float, nullable=True)
    scale_change: Mapped[float | None] = mapped_column(Float, nullable=True)
    motion_start_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    motion_end_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    feature_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tracked_feature_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    inlier_ratio: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    visual_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    scene_continuity_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    duplicate_frame_ratio: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    freeze_duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invalid_frame_ratio: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    diagnostics_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
