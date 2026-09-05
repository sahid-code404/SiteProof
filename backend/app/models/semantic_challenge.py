import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
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


class SemanticChallengeType(str, enum.Enum):
    SHOW_OVERVIEW = "SHOW_OVERVIEW"
    SHOW_TASK_DETAIL = "SHOW_TASK_DETAIL"
    SHOW_SITE_CONTEXT = "SHOW_SITE_CONTEXT"
    SHOW_ASSET_IDENTITY = "SHOW_ASSET_IDENTITY"


class SemanticChallengeStatus(str, enum.Enum):
    ISSUED = "ISSUED"
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class SemanticCaptureChallenge(Base):
    """Server-issued visual proof action performed inside the continuous capture.

    These challenges are intentionally separate from inertial movement challenges. They bind an
    unpredictable, assignment-specific visual instruction to a nonce and monotonic capture window;
    later semantic analysis can evaluate only the evidence that falls inside that window.
    """

    __tablename__ = "semantic_capture_challenges"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "sequence_number",
            name="uq_semantic_challenge_session_sequence",
        ),
        UniqueConstraint("nonce", name="uq_semantic_challenge_nonce"),
        Index("ix_semantic_challenge_session_status", "session_id", "status"),
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
    challenge_type: Mapped[SemanticChallengeType] = mapped_column(
        Enum(SemanticChallengeType, native_enum=False, length=32), index=True, nullable=False
    )
    instruction: Mapped[str] = mapped_column(String(1200), nullable=False)
    target_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    nonce: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[SemanticChallengeStatus] = mapped_column(
        Enum(SemanticChallengeStatus, native_enum=False, length=20),
        default=SemanticChallengeStatus.ISSUED,
        index=True,
        nullable=False,
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    client_start_monotonic_ns: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    client_complete_monotonic_ns: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    window_start_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    window_end_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
