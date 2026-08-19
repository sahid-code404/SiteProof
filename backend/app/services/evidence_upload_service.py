import hashlib
import os
import tempfile
import uuid
from pathlib import Path

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import SiteProofError
from app.models.inspection import Inspection, InspectionStatus
from app.models.user import User
from app.models.verification import EvidenceFile, EvidenceFileType, EvidenceUploadStatus, VerificationSessionStatus
from app.schemas.session import EvidenceCompleteRequest, EvidenceFileResponse, VerificationSessionResponse
from app.services.audit_service import record_audit
from app.services.evidence_common import REQUIRED_EVIDENCE, evidence_response, size_limit
from app.services.manifest_service import validate_uploaded_evidence
from app.services.session_service import owned_session, session_response, utc_now
from app.services.storage_service import StorageService, get_storage_service


def mark_upload_failed(db: Session, current_user: User, record: EvidenceFile, code: str) -> None:
    record.upload_status = EvidenceUploadStatus.FAILED
    record.hash_verified = False
    session = owned_session(db, current_user, record.session_id, require_active_assignment=False)
    session.status = VerificationSessionStatus.UPLOAD_FAILED
    record_audit(
        db,
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        entity_type="EVIDENCE_FILE",
        entity_id=record.id,
        action="EVIDENCE_FILE_UPLOAD_FAILED",
        metadata={"type": record.file_type.value, "code": code},
    )
    db.commit()


async def accept_evidence_upload(
    db: Session,
    current_user: User,
    session_id: uuid.UUID,
    file_id: uuid.UUID,
    request: Request,
    storage: StorageService | None = None,
) -> EvidenceFileResponse:
    session = owned_session(db, current_user, session_id)
    if session.status not in {VerificationSessionStatus.UPLOADING, VerificationSessionStatus.UPLOAD_FAILED}:
        raise SiteProofError(409, "INVALID_STATUS_TRANSITION", "Session is not accepting uploads.")
    record = db.scalar(
        select(EvidenceFile).where(
            EvidenceFile.id == file_id,
            EvidenceFile.session_id == session.id,
            EvidenceFile.organization_id == current_user.organization_id,
        )
    )
    if record is None:
        raise SiteProofError(404, "EVIDENCE_FILE_NOT_FOUND", "Evidence file was not found.")
    if record.upload_status == EvidenceUploadStatus.UPLOADED and record.hash_verified:
        return evidence_response(record)

    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type and content_type != record.mime_type:
        raise SiteProofError(415, "CONTENT_TYPE_MISMATCH", "Uploaded content type does not match.")
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) != record.size_bytes:
                raise SiteProofError(422, "SIZE_MISMATCH", "Uploaded file size does not match.")
        except ValueError as exc:
            raise SiteProofError(400, "INVALID_CONTENT_LENGTH", "Content-Length is invalid.") from exc

    record.upload_status = EvidenceUploadStatus.UPLOADING
    db.commit()
    temp_path: Path | None = None
    try:
        hasher = hashlib.sha256()
        total = 0
        with tempfile.NamedTemporaryFile(prefix="siteproof-upload-", delete=False) as temp_file:
            temp_path = Path(temp_file.name)
            async for chunk in request.stream():
                if not chunk:
                    continue
                total += len(chunk)
                if total > record.size_bytes or total > size_limit(record.file_type):
                    raise SiteProofError(413, "EVIDENCE_FILE_TOO_LARGE", "Upload exceeds declared size.")
                hasher.update(chunk)
                temp_file.write(chunk)
        digest = hasher.hexdigest()
        if total != record.size_bytes:
            mark_upload_failed(db, current_user, record, "SIZE_MISMATCH")
            raise SiteProofError(422, "SIZE_MISMATCH", "Uploaded file size does not match.")
        if digest != record.sha256:
            mark_upload_failed(db, current_user, record, "HASH_MISMATCH")
            raise SiteProofError(422, "HASH_MISMATCH", "Uploaded file hash does not match.")

        object_storage = storage or get_storage_service()
        metadata = object_storage.put_file(temp_path, record.storage_key, record.mime_type)
        if metadata.size_bytes != record.size_bytes:
            mark_upload_failed(db, current_user, record, "STORAGE_SIZE_MISMATCH")
            raise SiteProofError(500, "STORAGE_SIZE_MISMATCH", "Stored object size does not match.")
        record.upload_status = EvidenceUploadStatus.UPLOADED
        record.hash_verified = True
        record.uploaded_at = utc_now()
        session.status = VerificationSessionStatus.UPLOADING
        record_audit(
            db,
            organization_id=current_user.organization_id,
            actor_user_id=current_user.id,
            entity_type="EVIDENCE_FILE",
            entity_id=record.id,
            action="EVIDENCE_FILE_UPLOADED",
            metadata={"type": record.file_type.value, "sizeBytes": record.size_bytes},
        )
        db.commit()
        db.refresh(record)
        return evidence_response(record)
    except SiteProofError:
        raise
    except Exception as exc:
        if record.upload_status != EvidenceUploadStatus.FAILED:
            mark_upload_failed(db, current_user, record, "STORAGE_ERROR")
        raise SiteProofError(503, "STORAGE_ERROR", "Evidence storage is temporarily unavailable.") from exc
    finally:
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass


def complete_evidence_upload(
    db: Session,
    current_user: User,
    session_id: uuid.UUID,
    payload: EvidenceCompleteRequest,
    storage: StorageService | None = None,
) -> VerificationSessionResponse:
    session = owned_session(db, current_user, session_id)
    # Phase 5 may move an already-uploaded session into PROCESSING immediately. Preserve
    # Phase 3's idempotent completion receipt so a delayed/retried Android request does not
    # become an invalid state transition merely because background analysis has started.
    if session.status in {VerificationSessionStatus.UPLOADED, VerificationSessionStatus.PROCESSING}:
        if session.manifest_sha256 == payload.manifest_sha256:
            return session_response(db, session)
        raise SiteProofError(409, "UPLOAD_ALREADY_COMPLETED", "Evidence upload is already complete.")
    if session.status not in {VerificationSessionStatus.UPLOADING, VerificationSessionStatus.UPLOAD_FAILED}:
        raise SiteProofError(409, "INVALID_STATUS_TRANSITION", "Session is not completing upload.")

    records = {
        item.file_type: item for item in db.scalars(select(EvidenceFile).where(EvidenceFile.session_id == session.id)).all()
    }
    missing = REQUIRED_EVIDENCE - set(records)
    if missing:
        raise SiteProofError(422, "MISSING_REQUIRED_EVIDENCE", "Required evidence records are missing.", {"types": sorted(item.value for item in missing)})
    not_uploaded = [
        item.file_type.value
        for item in records.values()
        if item.file_type in REQUIRED_EVIDENCE
        and not (item.upload_status == EvidenceUploadStatus.UPLOADED and item.hash_verified)
    ]
    if not_uploaded:
        raise SiteProofError(409, "EVIDENCE_NOT_UPLOADED", "Not all required evidence files are uploaded.", {"types": sorted(not_uploaded)})
    manifest = records[EvidenceFileType.MANIFEST]
    if manifest.sha256 != payload.manifest_sha256:
        raise SiteProofError(422, "MANIFEST_HASH_MISMATCH", "Manifest SHA-256 does not match.")

    validate_uploaded_evidence(storage or get_storage_service(), session, records)
    session.status = VerificationSessionStatus.UPLOADED
    session.uploaded_at = utc_now()
    session.manifest_sha256 = payload.manifest_sha256
    inspection = db.get(Inspection, session.inspection_id)
    if inspection is not None and inspection.status != InspectionStatus.CANCELLED:
        inspection.status = InspectionStatus.PROCESSING
    record_audit(
        db,
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        entity_type="VERIFICATION_SESSION",
        entity_id=session.id,
        action="EVIDENCE_UPLOAD_COMPLETED",
        metadata={"manifestSha256": payload.manifest_sha256},
    )
    db.commit()
    db.refresh(session)
    return session_response(db, session)
