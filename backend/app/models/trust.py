import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class VerificationSignalType(str, enum.Enum):
    LOCATION = "LOCATION"
    SESSION_TIME = "SESSION_TIME"
    CHALLENGE_COMPLETION = "CHALLENGE_COMPLETION"
    SENSOR_EVIDENCE = "SENSOR_EVIDENCE"
    VISUAL_EVIDENCE = "VISUAL_EVIDENCE"
    SCENE_CONTINUITY = "SCENE_CONTINUITY"
    VISUAL_INERTIAL_CONSISTENCY = "VISUAL_INERTIAL_CONSISTENCY"


class VerificationSignalStatus(str, enum.Enum):
    PASS = "PASS"
    PARTIAL = "PARTIAL"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    UNAVAILABLE = "UNAVAILABLE"


class VerificationProcessingStatus(str, enum.Enum):
    PENDING = "PENDING"
    WAITING_FOR_SIGNALS = "WAITING_FOR_SIGNALS"
    CALCULATING = "CALCULATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class VerificationVerdict(str, enum.Enum):
    VERIFIED = "VERIFIED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    FLAGGED = "FLAGGED"
    INCONCLUSIVE = "INCONCLUSIVE"


class ReviewDecisionType(str, enum.Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RECAPTURE_REQUIRED = "RECAPTURE_REQUIRED"


class VerificationPolicy(Base):
    __tablename__ = "verification_policies"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "name",
            "version",
            name="uq_verification_policy_org_name_version",
        ),
        Index(
            "ix_verification_policy_org_active",
            "organization_id",
            "active",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    verified_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    review_threshold: Mapped[float] = mapped_column(Float, nullable=False)
    minimum_required_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    weights_json: Mapped[dict[str, float]] = mapped_column(JSON, nullable=False)
    required_signals_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    hard_rules_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class VerificationResult(Base):
    __tablename__ = "verification_results"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "policy_id",
            "engine_version",
            "calculation_revision",
            name="uq_verification_result_session_policy_engine_revision",
        ),
        Index("ix_verification_result_session_current", "session_id", "calculated_at"),
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
    policy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("verification_policies.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    policy_version: Mapped[str] = mapped_column(String(40), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(48), nullable=False)
    calculation_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    processing_status: Mapped[VerificationProcessingStatus] = mapped_column(
        Enum(VerificationProcessingStatus, native_enum=False, length=32),
        default=VerificationProcessingStatus.PENDING,
        index=True,
        nullable=False,
    )
    raw_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    verdict: Mapped[VerificationVerdict | None] = mapped_column(
        Enum(VerificationVerdict, native_enum=False, length=32),
        index=True,
        nullable=True,
    )
    overall_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    hard_rule_triggered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hard_rule_codes_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_reasons_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    warnings_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class VerificationSignalResult(Base):
    __tablename__ = "verification_signal_results"
    __table_args__ = (
        UniqueConstraint(
            "verification_result_id",
            "signal_type",
            name="uq_verification_signal_result_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    verification_result_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("verification_results.id", ondelete="CASCADE"), index=True, nullable=False
    )
    signal_type: Mapped[VerificationSignalType] = mapped_column(
        Enum(VerificationSignalType, native_enum=False, length=40),
        index=True,
        nullable=False,
    )
    status: Mapped[VerificationSignalStatus] = mapped_column(
        Enum(VerificationSignalStatus, native_enum=False, length=20),
        nullable=False,
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    configured_weight: Mapped[float] = mapped_column(Float, nullable=False)
    effective_weight: Mapped[float] = mapped_column(Float, nullable=False)
    weighted_contribution: Mapped[float] = mapped_column(Float, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason_summary: Mapped[str] = mapped_column(String(500), nullable=False)
    reasons_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    source_algorithm_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ReviewDecision(Base):
    __tablename__ = "review_decisions"
    __table_args__ = (
        Index("ix_review_decision_inspection_created", "inspection_id", "created_at"),
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
    verification_result_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("verification_results.id", ondelete="CASCADE"), index=True, nullable=False
    )
    reviewer_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    decision: Mapped[ReviewDecisionType] = mapped_column(
        Enum(ReviewDecisionType, native_enum=False, length=32),
        index=True,
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
