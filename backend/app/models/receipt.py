from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, Float, ForeignKey, Index, String, Text, UniqueConstraint, Uuid, event, func, inspect
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class SigningKeyStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"
    COMPROMISED = "COMPROMISED"


class ReceiptType(str, enum.Enum):
    AUTOMATED_VERIFICATION = "AUTOMATED_VERIFICATION"


class ReceiptLifecycleStatus(str, enum.Enum):
    ISSUED = "ISSUED"
    REVOKED = "REVOKED"
    SUPERSEDED = "SUPERSEDED"


class ReceiptProcessStatus(str, enum.Enum):
    PENDING = "PENDING"
    GENERATING_MANIFEST = "GENERATING_MANIFEST"
    HASHING_EVIDENCE = "HASHING_EVIDENCE"
    SIGNING = "SIGNING"
    ISSUED = "ISSUED"
    FAILED = "FAILED"


class SigningKey(Base):
    __tablename__ = "signing_keys"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    key_id: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    algorithm: Mapped[str] = mapped_column(String(32), nullable=False)
    public_key_base64: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[SigningKeyStatus] = mapped_column(Enum(SigningKeyStatus, native_enum=False, length=24), default=SigningKeyStatus.ACTIVE, index=True, nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class EvidenceManifest(Base):
    __tablename__ = "evidence_manifests"
    __table_args__ = (UniqueConstraint("session_id", "schema_version", name="uq_evidence_manifest_session_schema"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), index=True, nullable=False)
    inspection_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("inspections.id", ondelete="RESTRICT"), index=True, nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("verification_sessions.id", ondelete="RESTRICT"), index=True, nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False)
    canonical_payload: Mapped[str] = mapped_column(Text, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    evidence_file_count: Mapped[int] = mapped_column(nullable=False)
    total_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sealed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class SignedReceipt(Base):
    __tablename__ = "signed_receipts"
    __table_args__ = (UniqueConstraint("verification_result_id", "receipt_type", name="uq_signed_receipt_verification_type"), Index("ix_signed_receipt_session_status", "session_id", "lifecycle_status"))
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    receipt_number: Mapped[str] = mapped_column(String(80), unique=True, index=True, nullable=False)
    lookup_token: Mapped[str] = mapped_column(String(160), unique=True, index=True, nullable=False)
    organization_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), index=True, nullable=False)
    inspection_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("inspections.id", ondelete="RESTRICT"), index=True, nullable=False)
    session_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("verification_sessions.id", ondelete="RESTRICT"), index=True, nullable=False)
    verification_result_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("verification_results.id", ondelete="RESTRICT"), index=True, nullable=False)
    manifest_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("evidence_manifests.id", ondelete="RESTRICT"), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False)
    receipt_type: Mapped[ReceiptType] = mapped_column(Enum(ReceiptType, native_enum=False, length=40), nullable=False)
    canonical_payload: Mapped[str] = mapped_column(Text, nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    verdict: Mapped[str] = mapped_column(String(24), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(48), nullable=False)
    signature_algorithm: Mapped[str] = mapped_column(String(32), nullable=False)
    signature_base64: Mapped[str] = mapped_column(Text, nullable=False)
    signing_key_id: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    lifecycle_status: Mapped[ReceiptLifecycleStatus] = mapped_column(Enum(ReceiptLifecycleStatus, native_enum=False, length=24), default=ReceiptLifecycleStatus.ISSUED, index=True, nullable=False)
    process_status: Mapped[ReceiptProcessStatus] = mapped_column(Enum(ReceiptProcessStatus, native_enum=False, length=32), default=ReceiptProcessStatus.ISSUED, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    superseded_by_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("signed_receipts.id", ondelete="SET NULL"), nullable=True)
    last_evidence_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_evidence_integrity: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


_IMMUTABLE_RECEIPT_FIELDS = {
    "receipt_number", "lookup_token", "organization_id", "inspection_id", "session_id",
    "verification_result_id", "manifest_id", "schema_version", "receipt_type", "canonical_payload",
    "manifest_sha256", "payload_sha256", "score", "verdict", "confidence", "policy_version",
    "engine_version", "signature_algorithm", "signature_base64", "signing_key_id", "issued_at",
}


@event.listens_for(SignedReceipt, "before_update")
def prevent_signed_payload_mutation(_mapper, _connection, target: SignedReceipt) -> None:
    state = inspect(target)
    changed = [name for name in _IMMUTABLE_RECEIPT_FIELDS if state.attrs[name].history.has_changes()]
    if changed:
        raise ValueError(f"Issued receipt fields are immutable: {', '.join(sorted(changed))}")
