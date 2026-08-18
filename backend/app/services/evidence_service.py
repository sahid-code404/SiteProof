import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import SiteProofError
from app.models.inspection import Inspection, InspectionStatus
from app.models.user import User
from app.models.verification import EvidenceFile, EvidenceUploadStatus, VerificationSessionStatus
from app.schemas.session import EvidenceInitiateRequest, EvidenceInitiateResponse, EvidenceListResponse, EvidenceUploadTarget
from app.services.audit_service import record_audit
from app.services.evidence_common import REQUIRED_EVIDENCE, evidence_response, storage_key, validate_file_descriptor
from app.services.session_service import owned_session, viewable_session


def initiate_evidence_upload(
    db: Session, current_user: User, session_id: uuid.UUID, payload: EvidenceInitiateRequest
) -> EvidenceInitiateResponse:
    session = owned_session(db, current_user, session_id)
    if session.status not in {
        VerificationSessionStatus.CAPTURE_COMPLETED,
        VerificationSessionStatus.UPLOADING,
        VerificationSessionStatus.UPLOAD_FAILED,
        VerificationSessionStatus.UPLOADED,
    }:
        raise SiteProofError(409, "INVALID_STATUS_TRANSITION", "Evidence upload requires a completed capture.")
    types = [item.type for item in payload.files]
    if len(types) != len(set(types)):
        raise SiteProofError(422, "DUPLICATE_EVIDENCE_TYPE", "Each evidence type may appear once.")
    if not REQUIRED_EVIDENCE.issubset(set(types)):
        raise SiteProofError(422, "MISSING_REQUIRED_EVIDENCE", "Upload initiation is missing required evidence files.")
    for item in payload.files:
        validate_file_descriptor(item)

    if session.upload_idempotency_key and session.upload_idempotency_key != payload.idempotency_key:
        raise SiteProofError(409, "UPLOAD_ALREADY_INITIALIZED", "This capture already has a different upload batch.")
    session.upload_idempotency_key = session.upload_idempotency_key or payload.idempotency_key
    existing = {
        item.file_type: item
        for item in db.scalars(select(EvidenceFile).where(EvidenceFile.session_id == session.id)).all()
    }
    targets: list[EvidenceUploadTarget] = []
    for descriptor in payload.files:
        record = existing.get(descriptor.type)
        if record is not None:
            same = (
                record.original_filename == descriptor.filename
                and record.mime_type == descriptor.mime_type.lower()
                and record.size_bytes == descriptor.size_bytes
                and record.sha256 == descriptor.sha256
            )
            if not same:
                raise SiteProofError(
                    409,
                    "EVIDENCE_DESCRIPTOR_CONFLICT",
                    f"{descriptor.type.value} was already initialized with different metadata.",
                )
        else:
            record = EvidenceFile(
                organization_id=session.organization_id,
                inspection_id=session.inspection_id,
                session_id=session.id,
                file_type=descriptor.type,
                storage_key=storage_key(session.organization_id, session.inspection_id, session.id, descriptor.type),
                original_filename=descriptor.filename,
                mime_type=descriptor.mime_type.lower(),
                size_bytes=descriptor.size_bytes,
                sha256=descriptor.sha256,
                upload_status=EvidenceUploadStatus.PENDING,
            )
            db.add(record)
            db.flush()
            existing[descriptor.type] = record
        targets.append(
            EvidenceUploadTarget(
                file_id=record.id,
                type=record.file_type,
                upload_path=f"sessions/{session.id}/evidence/{record.id}/content",
                already_uploaded=record.upload_status == EvidenceUploadStatus.UPLOADED and record.hash_verified,
            )
        )

    if session.status != VerificationSessionStatus.UPLOADED:
        session.status = VerificationSessionStatus.UPLOADING
        inspection = db.get(Inspection, session.inspection_id)
        if inspection is not None and inspection.status != InspectionStatus.CANCELLED:
            inspection.status = InspectionStatus.EVIDENCE_UPLOADING
    record_audit(
        db,
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        entity_type="VERIFICATION_SESSION",
        entity_id=session.id,
        action="EVIDENCE_UPLOAD_STARTED",
        metadata={"fileCount": len(payload.files)},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise SiteProofError(409, "EVIDENCE_UPLOAD_CONFLICT", "Evidence upload was initialized concurrently.") from exc
    return EvidenceInitiateResponse(session_id=session.id, status=session.status, targets=targets)


def list_evidence(db: Session, current_user: User, session_id: uuid.UUID) -> EvidenceListResponse:
    session = viewable_session(db, current_user, session_id)
    records = db.scalars(
        select(EvidenceFile).where(EvidenceFile.session_id == session.id).order_by(EvidenceFile.created_at.asc())
    ).all()
    return EvidenceListResponse(session_id=session.id, items=[evidence_response(item) for item in records])


def get_evidence_for_download(
    db: Session, current_user: User, session_id: uuid.UUID, file_id: uuid.UUID
) -> EvidenceFile:
    session = viewable_session(db, current_user, session_id)
    record = db.scalar(
        select(EvidenceFile).where(
            EvidenceFile.id == file_id,
            EvidenceFile.session_id == session.id,
            EvidenceFile.organization_id == current_user.organization_id,
        )
    )
    if record is None or record.upload_status != EvidenceUploadStatus.UPLOADED:
        raise SiteProofError(404, "EVIDENCE_FILE_NOT_FOUND", "Evidence file was not found.")
    return record
