import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AutonomousAnalysisStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETE = "COMPLETE"
    UNAVAILABLE = "UNAVAILABLE"
    FAILED = "FAILED"


class AutonomousVerificationResult(Base):
    """Immutable-at-version semantic analysis for one verification session.

    The model/VLM never owns the final SiteProof verdict. It records structured observations
    that can only constrain an otherwise deterministic verification result.
    """

    __tablename__ = "autonomous_verification_results"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "analysis_version",
            name="uq_autonomous_verification_session_version",
        ),
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
    status: Mapped[AutonomousAnalysisStatus] = mapped_column(
        Enum(AutonomousAnalysisStatus, native_enum=False, length=20),
        default=AutonomousAnalysisStatus.PENDING,
        index=True,
        nullable=False,
    )

    analysis_version: Mapped[str] = mapped_column(String(48), nullable=False)
    contract_version: Mapped[str] = mapped_column(String(48), nullable=False)
    contract_prompt_version: Mapped[str] = mapped_column(String(48), nullable=False)
    vision_prompt_version: Mapped[str] = mapped_column(String(48), nullable=False)
    compiler_model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    primary_vlm_model: Mapped[str | None] = mapped_column(String(160), nullable=True)
    secondary_vlm_model: Mapped[str | None] = mapped_column(String(160), nullable=True)

    contract_source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    contract_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    contract_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    sampled_frame_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    frame_hashes_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    task_match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    task_match_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    asset_identity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    asset_identity_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_coverage_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_coverage_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    live_scene_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    live_scene_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    presentation_attack_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    presentation_attack_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    mandatory_failures_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    model_disagreement: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    observations_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    raw_response_hashes_json: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
