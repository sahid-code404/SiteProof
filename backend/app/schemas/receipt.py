from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.base import APIModel


class PublicKeyResponse(APIModel):
    key_id: str
    algorithm: str
    public_key: str
    status: str
    active_from: datetime
    retired_at: datetime | None = None


class ReceiptVerifyRequest(APIModel):
    receipt_id: str = Field(min_length=8, max_length=180)


class ReceiptResponse(APIModel):
    id: uuid.UUID
    receipt_number: str
    lookup_token: str | None = None
    receipt_type: str
    status: str
    integrity_state: str
    signature_state: str
    signature_valid: bool
    manifest_sha256: str
    payload_sha256: str
    score: float
    verdict: str
    confidence: float
    policy_version: str
    engine_version: str
    signature_algorithm: str
    signing_key_id: str
    issued_at: datetime
    revoked_at: datetime | None = None
    revocation_reason: str | None = None
    last_evidence_check_at: datetime | None = None
    last_evidence_integrity: str | None = None
    canonical_payload: dict[str, Any] | None = None
    signature: str | None = None


class PublicReceiptResponse(APIModel):
    receipt_id: uuid.UUID
    receipt_number: str
    signature_valid: bool
    signature_state: str
    receipt_status: str
    integrity_state: str
    verdict: str | None = None
    score: str | None = None
    issued_at: datetime


class EvidenceHashCheckResponse(APIModel):
    evidence_file_id: uuid.UUID
    type: str
    state: str
    expected_sha256: str
    observed_sha256: str | None = None
    expected_size_bytes: int
    observed_size_bytes: int | None = None


class EvidenceIntegrityResponse(APIModel):
    receipt_id: uuid.UUID
    state: str
    checked_at: datetime
    files: list[EvidenceHashCheckResponse]


class ReceiptRevokeRequest(APIModel):
    reason: str = Field(min_length=3, max_length=1000)
