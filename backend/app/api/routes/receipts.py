from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_roles
from app.core.config import get_settings
from app.core.errors import SiteProofError
from app.db.session import get_db
from app.models.receipt import SignedReceipt, SigningKey
from app.models.trust import VerificationProcessingStatus
from app.models.user import User, UserRole
from app.models.verification import VerificationSession
from app.schemas.receipt import EvidenceHashCheckResponse, EvidenceIntegrityResponse, PublicKeyResponse, PublicReceiptResponse, ReceiptResponse, ReceiptRevokeRequest, ReceiptVerifyRequest
from app.services.receipt_service import deep_verify_receipt_evidence, issue_automated_receipt, overall_receipt_integrity, receipt_signature_state, revoke_receipt
from app.services.verification.service import get_scoped_result

router = APIRouter(tags=["receipts"])


def _key_response(key: SigningKey) -> PublicKeyResponse:
    return PublicKeyResponse(key_id=key.key_id, algorithm=key.algorithm, public_key=key.public_key_base64, status=key.status.value, active_from=key.active_from, retired_at=key.retired_at)


def _scoped_receipt(db: Session, current_user: User, receipt_id: uuid.UUID) -> SignedReceipt:
    receipt = db.get(SignedReceipt, receipt_id)
    if receipt is None or receipt.organization_id != current_user.organization_id:
        raise SiteProofError(404, "RECEIPT_NOT_FOUND", "Receipt was not found.")
    return receipt


def _receipt_response(db: Session, receipt: SignedReceipt, *, detailed: bool) -> ReceiptResponse:
    signature_state, signature_valid = receipt_signature_state(db, receipt)
    return ReceiptResponse(id=receipt.id, receipt_number=receipt.receipt_number, lookup_token=receipt.lookup_token if detailed else None, receipt_type=receipt.receipt_type.value, status=receipt.lifecycle_status.value, integrity_state=overall_receipt_integrity(db, receipt), signature_state=signature_state, signature_valid=signature_valid, manifest_sha256=receipt.manifest_sha256, payload_sha256=receipt.payload_sha256, score=receipt.score, verdict=receipt.verdict, confidence=receipt.confidence, policy_version=receipt.policy_version, engine_version=receipt.engine_version, signature_algorithm=receipt.signature_algorithm, signing_key_id=receipt.signing_key_id, issued_at=receipt.issued_at, revoked_at=receipt.revoked_at, revocation_reason=receipt.revocation_reason, last_evidence_check_at=receipt.last_evidence_check_at, last_evidence_integrity=receipt.last_evidence_integrity, canonical_payload=json.loads(receipt.canonical_payload) if detailed else None, signature=receipt.signature_base64 if detailed else None)


def _public_response(db: Session, receipt: SignedReceipt) -> PublicReceiptResponse:
    mode = get_settings().public_receipt_details.upper()
    if mode == "PRIVATE":
        raise SiteProofError(404, "RECEIPT_NOT_FOUND", "Public receipt verification is disabled.")
    signature_state, signature_valid = receipt_signature_state(db, receipt)
    disclose_result = mode == "STANDARD"
    return PublicReceiptResponse(receipt_id=receipt.id, receipt_number=receipt.receipt_number, signature_valid=signature_valid, signature_state=signature_state, receipt_status=receipt.lifecycle_status.value, integrity_state=overall_receipt_integrity(db, receipt), verdict=receipt.verdict if disclose_result else None, score=f"{receipt.score:.2f}" if disclose_result else None, issued_at=receipt.issued_at)


@router.get("/verification-keys", response_model=list[PublicKeyResponse])
def verification_keys(db: Session = Depends(get_db)) -> list[PublicKeyResponse]:
    return [_key_response(key) for key in db.scalars(select(SigningKey).order_by(SigningKey.active_from.desc())).all()]


@router.get("/verification-keys/{key_id}", response_model=PublicKeyResponse)
def verification_key(key_id: str, db: Session = Depends(get_db)) -> PublicKeyResponse:
    key = db.scalar(select(SigningKey).where(SigningKey.key_id == key_id))
    if key is None:
        raise SiteProofError(404, "SIGNING_KEY_NOT_FOUND", "Verification key was not found.")
    return _key_response(key)


@router.get("/sessions/{session_id}/receipt", response_model=ReceiptResponse | None)
def session_receipt(session_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> ReceiptResponse | None:
    session = db.get(VerificationSession, session_id)
    if session is None or session.organization_id != current_user.organization_id:
        raise SiteProofError(404, "SESSION_NOT_FOUND", "Verification session was not found.")
    receipt = db.scalar(select(SignedReceipt).where(SignedReceipt.session_id == session.id).order_by(SignedReceipt.issued_at.desc()))
    return _receipt_response(db, receipt, detailed=current_user.role in {UserRole.ADMIN, UserRole.REVIEWER}) if receipt else None


@router.post("/sessions/{session_id}/receipt/issue", response_model=ReceiptResponse)
def issue_session_receipt(session_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_roles(UserRole.ADMIN))) -> ReceiptResponse:
    result = get_scoped_result(db, current_user, session_id)
    if result is None or result.processing_status != VerificationProcessingStatus.COMPLETED:
        raise SiteProofError(409, "VERIFICATION_NOT_COMPLETE", "Completed verification result is required.")
    return _receipt_response(db, issue_automated_receipt(db, result.id, actor_user_id=current_user.id), detailed=True)


@router.get("/receipts/{receipt_id}", response_model=ReceiptResponse)
def receipt_detail(receipt_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER))) -> ReceiptResponse:
    return _receipt_response(db, _scoped_receipt(db, current_user, receipt_id), detailed=True)


def _lookup_receipt(db: Session, identifier: str) -> SignedReceipt | None:
    clauses = [SignedReceipt.receipt_number == identifier, SignedReceipt.lookup_token == identifier]
    try:
        clauses.append(SignedReceipt.id == uuid.UUID(identifier))
    except ValueError:
        pass
    return db.scalar(select(SignedReceipt).where(or_(*clauses)))


@router.post("/receipts/verify", response_model=PublicReceiptResponse)
def verify_receipt(payload: ReceiptVerifyRequest, db: Session = Depends(get_db)) -> PublicReceiptResponse:
    receipt = _lookup_receipt(db, payload.receipt_id)
    if receipt is None:
        raise SiteProofError(404, "RECEIPT_NOT_FOUND", "Receipt was not found.")
    return _public_response(db, receipt)


@router.get("/receipts/public/{token}", response_model=PublicReceiptResponse)
def public_receipt(token: str, db: Session = Depends(get_db)) -> PublicReceiptResponse:
    receipt = _lookup_receipt(db, token)
    if receipt is None:
        raise SiteProofError(404, "RECEIPT_NOT_FOUND", "Receipt was not found.")
    return _public_response(db, receipt)


@router.post("/receipts/{receipt_id}/verify-evidence", response_model=EvidenceIntegrityResponse)
def verify_receipt_evidence(receipt_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER))) -> EvidenceIntegrityResponse:
    receipt = _scoped_receipt(db, current_user, receipt_id)
    state, checks = deep_verify_receipt_evidence(db, receipt, actor_user_id=current_user.id)
    return EvidenceIntegrityResponse(receipt_id=receipt.id, state=state, checked_at=receipt.last_evidence_check_at, files=[EvidenceHashCheckResponse(evidence_file_id=check.evidence_file_id, type=check.file_type, state=check.state, expected_sha256=check.expected_sha256, observed_sha256=check.observed_sha256, expected_size_bytes=check.expected_size_bytes, observed_size_bytes=check.observed_size_bytes) for check in checks])


@router.post("/receipts/{receipt_id}/revoke", response_model=ReceiptResponse)
def revoke(receipt_id: uuid.UUID, payload: ReceiptRevokeRequest, db: Session = Depends(get_db), current_user: User = Depends(require_roles(UserRole.ADMIN))) -> ReceiptResponse:
    return _receipt_response(db, revoke_receipt(db, _scoped_receipt(db, current_user, receipt_id), actor_user_id=current_user.id, reason=payload.reason), detailed=True)
