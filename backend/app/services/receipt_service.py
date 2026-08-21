from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import SiteProofError
from app.models.receipt import EvidenceManifest, ReceiptLifecycleStatus, ReceiptProcessStatus, ReceiptType, SignedReceipt, SigningKey, SigningKeyStatus
from app.models.trust import VerificationProcessingStatus, VerificationResult, VerificationSignalResult
from app.models.verification import VerificationSession
from app.services.audit_service import record_audit
from app.services.receipt_crypto import SigningKeyProvider, canonical_json_bytes, fixed_decimal, sha256_hex, verify_ed25519_signature
from app.services.receipt_manifest import seal_evidence_manifest, verify_manifest_evidence
from app.services.receipt_signing import get_signing_key_provider
from app.services.storage_service import StorageService

RECEIPT_SCHEMA_VERSION = "1.0"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _receipt_number(now: datetime) -> str:
    return f"SPR-{now.year}-{secrets.token_hex(6).upper()}"


def _signal_summary(db: Session, result_id: uuid.UUID) -> list[dict[str, object]]:
    rows = list(db.scalars(select(VerificationSignalResult).where(VerificationSignalResult.verification_result_id == result_id).order_by(VerificationSignalResult.signal_type)).all())
    return [{"type": row.signal_type.value, "status": row.status.value, "score": fixed_decimal(row.score, 6), "confidence": fixed_decimal(row.confidence, 6), "weightedContribution": fixed_decimal(row.weighted_contribution, 6), "required": row.required} for row in rows]


def ensure_key_metadata(db: Session, provider: SigningKeyProvider, *, now: datetime | None = None) -> tuple[SigningKey, list[SigningKey]]:
    public = provider.get_public_key()
    instant = now or utc_now()
    existing = db.scalar(select(SigningKey).where(SigningKey.key_id == public.key_id))
    if existing is not None:
        if existing.algorithm != public.algorithm or existing.public_key_base64 != public.public_key_base64:
            raise SiteProofError(409, "SIGNING_KEY_ID_CONFLICT", "Signing key ID already refers to different public key material.")
        if existing.status != SigningKeyStatus.ACTIVE:
            raise SiteProofError(409, "SIGNING_KEY_NOT_ACTIVE", "Retired or compromised keys cannot issue new receipts.")
        return existing, []
    retired = list(db.scalars(select(SigningKey).where(SigningKey.status == SigningKeyStatus.ACTIVE)).all())
    for old in retired:
        old.status = SigningKeyStatus.RETIRED
        old.retired_at = instant
    row = SigningKey(key_id=public.key_id, algorithm=public.algorithm, public_key_base64=public.public_key_base64, status=SigningKeyStatus.ACTIVE, external_reference="external-secret", active_from=instant)
    db.add(row)
    db.flush()
    return row, retired


def issue_automated_receipt(db: Session, verification_result_id: uuid.UUID, *, provider: SigningKeyProvider | None = None, storage: StorageService | None = None, actor_user_id: uuid.UUID | None = None) -> SignedReceipt:
    result = db.get(VerificationResult, verification_result_id)
    if result is None:
        raise SiteProofError(404, "VERIFICATION_NOT_FOUND", "Verification result was not found.")
    if result.processing_status != VerificationProcessingStatus.COMPLETED or result.final_score is None or result.overall_confidence is None or result.verdict is None:
        raise SiteProofError(409, "VERIFICATION_NOT_COMPLETE", "A receipt can only seal a completed verification result.")
    existing = db.scalar(select(SignedReceipt).where(SignedReceipt.verification_result_id == result.id, SignedReceipt.receipt_type == ReceiptType.AUTOMATED_VERIFICATION))
    if existing is not None:
        return existing
    session = db.get(VerificationSession, result.session_id)
    if session is None or session.organization_id != result.organization_id:
        raise SiteProofError(409, "SESSION_NOT_FOUND", "Verification session is unavailable.")
    actor = actor_user_id or session.created_by_user_id
    signer = provider or get_signing_key_provider()
    key, retired_keys = ensure_key_metadata(db, signer)
    for retired in retired_keys:
        record_audit(db, organization_id=result.organization_id, actor_user_id=actor, entity_type="SIGNING_KEY", entity_id=retired.id, action="SIGNING_KEY_ROTATED", metadata={"retiredKeyId": retired.key_id, "activeKeyId": key.key_id})
    record_audit(db, organization_id=result.organization_id, actor_user_id=actor, entity_type="VERIFICATION_RESULT", entity_id=result.id, action="RECEIPT_GENERATION_STARTED", metadata={"receiptType": ReceiptType.AUTOMATED_VERIFICATION.value})
    manifest = seal_evidence_manifest(db, session, actor_user_id=actor, storage=storage)
    issued_at = utc_now()
    receipt_id = uuid.uuid4()
    receipt_number = _receipt_number(issued_at)
    payload = {"schemaVersion": RECEIPT_SCHEMA_VERSION, "receiptId": str(receipt_id), "receiptNumber": receipt_number, "receiptType": ReceiptType.AUTOMATED_VERIFICATION.value, "organizationId": str(result.organization_id), "inspectionId": str(result.inspection_id), "sessionId": str(result.session_id), "manifestSha256": manifest.sha256, "verificationResultId": str(result.id), "verification": {"score": fixed_decimal(result.final_score, 2), "confidence": fixed_decimal(result.overall_confidence, 6), "verdict": result.verdict.value, "policyId": str(result.policy_id), "policyName": result.policy_name, "policyVersion": result.policy_version, "engineVersion": result.engine_version, "signals": _signal_summary(db, result.id)}, "issuedAt": issued_at, "signing": {"algorithm": "Ed25519", "keyId": key.key_id}}
    canonical = canonical_json_bytes(payload)
    signature = signer.sign(canonical)
    if signature.key_id != key.key_id or signature.algorithm != key.algorithm:
        raise SiteProofError(500, "SIGNING_KEY_MISMATCH", "Signing provider metadata changed during issuance.")
    receipt = SignedReceipt(id=receipt_id, receipt_number=receipt_number, lookup_token=secrets.token_urlsafe(24), organization_id=result.organization_id, inspection_id=result.inspection_id, session_id=result.session_id, verification_result_id=result.id, manifest_id=manifest.id, schema_version=RECEIPT_SCHEMA_VERSION, receipt_type=ReceiptType.AUTOMATED_VERIFICATION, canonical_payload=canonical.decode("utf-8"), manifest_sha256=manifest.sha256, payload_sha256=signature.payload_sha256, score=result.final_score, verdict=result.verdict.value, confidence=result.overall_confidence, policy_version=result.policy_version, engine_version=result.engine_version, signature_algorithm=signature.algorithm, signature_base64=signature.signature_base64, signing_key_id=signature.key_id, lifecycle_status=ReceiptLifecycleStatus.ISSUED, process_status=ReceiptProcessStatus.ISSUED, issued_at=issued_at)
    db.add(receipt)
    db.flush()
    previous = list(db.scalars(select(SignedReceipt).where(SignedReceipt.session_id == result.session_id, SignedReceipt.receipt_type == ReceiptType.AUTOMATED_VERIFICATION, SignedReceipt.id != receipt.id, SignedReceipt.lifecycle_status == ReceiptLifecycleStatus.ISSUED)).all())
    for old in previous:
        old.lifecycle_status = ReceiptLifecycleStatus.SUPERSEDED
        old.superseded_by_id = receipt.id
        record_audit(db, organization_id=result.organization_id, actor_user_id=actor, entity_type="SIGNED_RECEIPT", entity_id=old.id, action="RECEIPT_SUPERSEDED", metadata={"supersededBy": str(receipt.id)})
    record_audit(db, organization_id=result.organization_id, actor_user_id=actor, entity_type="SIGNED_RECEIPT", entity_id=receipt.id, action="RECEIPT_ISSUED", metadata={"receiptNumber": receipt.receipt_number, "manifestSha256": receipt.manifest_sha256, "payloadSha256": receipt.payload_sha256, "algorithm": receipt.signature_algorithm, "keyId": receipt.signing_key_id})
    db.commit()
    db.refresh(receipt)
    return receipt


def receipt_signature_state(db: Session, receipt: SignedReceipt) -> tuple[str, bool]:
    payload = receipt.canonical_payload.encode("utf-8")
    if sha256_hex(payload) != receipt.payload_sha256:
        return "INVALID_PAYLOAD_HASH", False
    if receipt.signature_algorithm != "Ed25519":
        return "UNSUPPORTED_ALGORITHM", False
    key = db.scalar(select(SigningKey).where(SigningKey.key_id == receipt.signing_key_id))
    if key is None:
        return "UNKNOWN_KEY", False
    valid = verify_ed25519_signature(payload=payload, signature_base64=receipt.signature_base64, public_key_base64=key.public_key_base64)
    if not valid:
        return "INVALID", False
    if key.status == SigningKeyStatus.COMPROMISED:
        return "COMPROMISED_KEY", True
    return "VALID", True


def overall_receipt_integrity(db: Session, receipt: SignedReceipt) -> str:
    signature_state, valid = receipt_signature_state(db, receipt)
    if not valid:
        return "UNKNOWN_SIGNING_KEY" if signature_state == "UNKNOWN_KEY" else "INVALID_SIGNATURE"
    if receipt.lifecycle_status == ReceiptLifecycleStatus.REVOKED:
        return "REVOKED"
    if receipt.lifecycle_status == ReceiptLifecycleStatus.SUPERSEDED:
        return "SUPERSEDED"
    if signature_state == "COMPROMISED_KEY":
        return "COMPROMISED_SIGNING_KEY"
    return "VALID"


def deep_verify_receipt_evidence(db: Session, receipt: SignedReceipt, *, storage: StorageService | None = None, actor_user_id: uuid.UUID) -> tuple[str, list[object]]:
    manifest = db.get(EvidenceManifest, receipt.manifest_id)
    if manifest is None or manifest.sha256 != receipt.manifest_sha256:
        state, checks = "MISMATCH", []
    else:
        integrity = verify_manifest_evidence(db, manifest, storage=storage)
        state, checks = integrity.state, integrity.checks
    receipt.last_evidence_check_at = utc_now()
    receipt.last_evidence_integrity = state
    record_audit(db, organization_id=receipt.organization_id, actor_user_id=actor_user_id, entity_type="SIGNED_RECEIPT", entity_id=receipt.id, action="EVIDENCE_HASH_VERIFIED" if state == "MATCH" else "EVIDENCE_HASH_MISMATCH", metadata={"state": state})
    db.commit()
    return state, checks


def revoke_receipt(db: Session, receipt: SignedReceipt, *, actor_user_id: uuid.UUID, reason: str) -> SignedReceipt:
    if receipt.lifecycle_status == ReceiptLifecycleStatus.REVOKED:
        return receipt
    receipt.lifecycle_status = ReceiptLifecycleStatus.REVOKED
    receipt.revoked_at = utc_now()
    receipt.revocation_reason = reason.strip()
    record_audit(db, organization_id=receipt.organization_id, actor_user_id=actor_user_id, entity_type="SIGNED_RECEIPT", entity_id=receipt.id, action="RECEIPT_REVOKED", metadata={"reason": receipt.revocation_reason})
    db.commit()
    db.refresh(receipt)
    return receipt
