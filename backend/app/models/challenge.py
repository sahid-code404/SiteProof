import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
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


class ChallengeType(str, enum.Enum):
    ROTATE_LEFT = "ROTATE_LEFT"
    ROTATE_RIGHT = "ROTATE_RIGHT"
    TILT_UP = "TILT_UP"
    TILT_DOWN = "TILT_DOWN"


class ChallengeStatus(str, enum.Enum):
    ISSUED = "ISSUED"
    STARTED = "STARTED"
    PASSED = "PASSED"
    FAILED = "FAILED"
    INCONCLUSIVE = "INCONCLUSIVE"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class ChallengeResult(str, enum.Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"


class VerificationChallenge(Base):
    __tablename__ = "verification_challenges"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "sequence_number",
            "attempt_number",
            name="uq_challenge_session_sequence_attempt",
        ),
        UniqueConstraint("nonce", name="uq_verification_challenge_nonce"),
        UniqueConstraint(
            "session_id",
            "submission_idempotency_key",
            name="uq_challenge_submission_idempotency",
        ),
        Index("ix_challenge_session_status", "session_id", "status"),
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
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    challenge_type: Mapped[ChallengeType] = mapped_column(
        Enum(ChallengeType, native_enum=False, length=32), index=True, nullable=False
    )
    parameters_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    nonce: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[ChallengeStatus] = mapped_column(
        Enum(ChallengeStatus, native_enum=False, length=24),
        default=ChallengeStatus.ISSUED,
        index=True,
        nullable=False,
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    client_start_monotonic_ns: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    sensor_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    validation_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    result: Mapped[ChallengeResult | None] = mapped_column(
        Enum(ChallengeResult, native_enum=False, length=20), nullable=True
    )
    failure_reason: Mapped[str | None] = mapped_column(String(160), nullable=True)
    reasons_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    metrics_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    sensor_quality_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    evidence_sha256: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    submission_idempotency_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    nonce_consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
