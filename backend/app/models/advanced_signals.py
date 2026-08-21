import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Index, JSON, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AdvancedSignalResult(Base):
    __tablename__ = "advanced_signal_results"
    __table_args__ = (
        UniqueConstraint("session_id", "algorithm_version", name="uq_advanced_signal_session_version"),
        Index("ix_advanced_signal_inspection_created", "inspection_id", "created_at"),
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
    process_status: Mapped[str] = mapped_column(String(20), nullable=False)
    environment_status: Mapped[str] = mapped_column(String(24), nullable=False)
    environment_consistency_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    environment_risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    environment_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    statistical_anomaly_status: Mapped[str] = mapped_column(String(24), nullable=False)
    statistical_anomaly_score: Mapped[float] = mapped_column(Float, nullable=False)
    statistical_anomaly_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reason_codes_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    reasons_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(48), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
