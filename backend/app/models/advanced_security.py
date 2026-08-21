import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AdvancedProcessStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETE = "COMPLETE"
    INCONCLUSIVE = "INCONCLUSIVE"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    INCONCLUSIVE = "INCONCLUSIVE"


class AttestationChallenge(Base):
    __tablename__ = "attestation_challenges"
    __table_args__ = (
        Index("ix_attestation_challenge_session_consumed", "session_id", "consumed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("verification_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    nonce_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(96), index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DeviceAttestation(Base):
    __tablename__ = "device_attestations"
    __table_args__ = (
        UniqueConstraint("raw_token_hash", name="uq_device_attestation_token_hash"),
        Index("ix_device_attestation_session_validated", "session_id", "validated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("verification_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    provider: Mapped[str] = mapped_column(String(48), nullable=False)
    provider_version: Mapped[str] = mapped_column(String(48), nullable=False)
    request_nonce_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(96), nullable=False)
    app_integrity_status: Mapped[str] = mapped_column(String(24), nullable=False)
    device_integrity_status: Mapped[str] = mapped_column(String(24), nullable=False)
    licensing_status: Mapped[str] = mapped_column(String(32), nullable=False)
    token_issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    validated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    risk_flags_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    raw_token_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    validation_status: Mapped[AdvancedProcessStatus] = mapped_column(
        Enum(AdvancedProcessStatus, native_enum=False, length=20), index=True, nullable=False
    )
    diagnostics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class LocationRiskResult(Base):
    __tablename__ = "location_risk_results"
    __table_args__ = (
        UniqueConstraint("session_id", "algorithm_version", name="uq_location_risk_session_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("verification_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    process_status: Mapped[AdvancedProcessStatus] = mapped_column(
        Enum(AdvancedProcessStatus, native_enum=False, length=20), nullable=False
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, native_enum=False, length=20), index=True, nullable=False
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    mock_location_detected: Mapped[bool] = mapped_column(default=False, nullable=False)
    max_implied_speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    impossible_jump_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sensor_location_consistency: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason_codes_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    reasons_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(48), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ReplayRiskResult(Base):
    __tablename__ = "replay_risk_results"
    __table_args__ = (
        UniqueConstraint("session_id", "algorithm_version", name="uq_replay_risk_session_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("verification_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    process_status: Mapped[AdvancedProcessStatus] = mapped_column(
        Enum(AdvancedProcessStatus, native_enum=False, length=20), nullable=False
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, native_enum=False, length=20), index=True, nullable=False
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    display_rectangle_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    moire_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    banding_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    evidence_reuse_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    fusion_mismatch_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    reason_codes_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    reasons_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(48), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SensorAnomalyResult(Base):
    __tablename__ = "sensor_anomaly_results"
    __table_args__ = (
        UniqueConstraint("session_id", "algorithm_version", name="uq_sensor_anomaly_session_version"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("verification_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    process_status: Mapped[AdvancedProcessStatus] = mapped_column(
        Enum(AdvancedProcessStatus, native_enum=False, length=20), nullable=False
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, native_enum=False, length=20), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    anomaly_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    duplicate_sequence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    timestamp_anomaly_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    range_anomaly_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cross_sensor_conflict_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    reason_codes_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    reasons_json: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(48), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AdvancedSecurityResult(Base):
    __tablename__ = "advanced_security_results"
    __table_args__ = (
        UniqueConstraint("session_id", "algorithm_version", name="uq_advanced_security_session_version"),
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
    process_status: Mapped[AdvancedProcessStatus] = mapped_column(
        Enum(AdvancedProcessStatus, native_enum=False, length=20), nullable=False
    )
    overall_risk: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, native_enum=False, length=20), index=True, nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    location_risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    sensor_anomaly_score: Mapped[float] = mapped_column(Float, nullable=False)
    replay_risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    evidence_reuse_score: Mapped[float] = mapped_column(Float, nullable=False)
    device_integrity_status: Mapped[str] = mapped_column(String(32), nullable=False)
    device_risk_score: Mapped[float] = mapped_column(Float, nullable=False)
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
