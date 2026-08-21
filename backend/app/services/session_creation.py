import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import SiteProofError
from app.models.inspection import Inspection, InspectionStatus
from app.models.user import User
from app.models.verification import VerificationSession, VerificationSessionStatus
from app.schemas.session import SessionCreateRequest, SessionCreateResponse
from app.services.audit_service import record_audit
from app.services.session_common import (
    ACTIVE_SESSION_STATES,
    active_assignment,
    aware,
    expire_if_needed,
    get_inspector_for_user,
    utc_now,
)


def _capture_contract(session: VerificationSession, inspection: Inspection) -> tuple[int, int, int, object]:
    settings = get_settings()
    snapshot = session.site_snapshot or {}
    required_seconds = int(snapshot.get("captureDurationSeconds", inspection.capture_duration_seconds))
    allowed_radius = int(snapshot.get("allowedRadiusMeters", inspection.allowed_radius_meters))
    deadline = aware(
        inspection.deadline
        if snapshot.get("deadline") is None
        else __import__("datetime").datetime.fromisoformat(str(snapshot["deadline"]))
    )
    maximum_seconds = min(
        max(settings.capture_max_seconds, required_seconds + 15),
        settings.vision_max_duration_seconds,
    )
    return required_seconds, maximum_seconds, allowed_radius, deadline


def _response(
    session: VerificationSession,
    inspection: Inspection,
    *,
    server_time,
    clock_offset_ms: float | None,
) -> SessionCreateResponse:
    required_seconds, maximum_seconds, allowed_radius, deadline = _capture_contract(session, inspection)
    return SessionCreateResponse(
        session_id=session.id,
        inspection_id=inspection.id,
        status=session.status,
        expires_at=session.expires_at,
        server_time=server_time,
        clock_offset_ms=clock_offset_ms,
        required_capture_duration_seconds=required_seconds,
        capture_maximum_seconds=maximum_seconds,
        allowed_radius_meters=allowed_radius,
        deadline=deadline,
    )


def create_verification_session(
    db: Session, current_user: User, inspection_id: uuid.UUID, payload: SessionCreateRequest
) -> SessionCreateResponse:
    settings = get_settings()
    inspector = get_inspector_for_user(db, current_user)
    inspection = db.scalar(
        select(Inspection)
        .where(
            Inspection.id == inspection_id,
            Inspection.organization_id == current_user.organization_id,
        )
        .with_for_update()
    )
    if inspection is None:
        raise SiteProofError(404, "INSPECTION_NOT_FOUND", "Inspection was not found.")
    if active_assignment(db, inspection.id, inspector.id) is None:
        raise SiteProofError(403, "NOT_ASSIGNED", "This inspection is not assigned to you.")
    if inspection.status == InspectionStatus.CANCELLED:
        raise SiteProofError(409, "INSPECTION_CANCELLED", "Cancelled inspections cannot be verified.")

    now = utc_now()
    same_device = db.scalar(
        select(VerificationSession).where(
            VerificationSession.organization_id == current_user.organization_id,
            VerificationSession.device_session_id == payload.device_session_id,
        )
    )
    if same_device is not None:
        if same_device.inspection_id != inspection.id or same_device.inspector_id != inspector.id:
            raise SiteProofError(409, "DEVICE_SESSION_CONFLICT", "Device session ID was already used.")
        if expire_if_needed(db, same_device, actor_user_id=current_user.id):
            db.commit()
            raise SiteProofError(409, "SESSION_EXPIRED", "Verification session expired.")
        return _response(
            same_device,
            inspection,
            server_time=now,
            clock_offset_ms=same_device.clock_offset_ms,
        )

    existing = db.scalar(
        select(VerificationSession).where(
            VerificationSession.inspection_id == inspection.id,
            VerificationSession.status.in_(ACTIVE_SESSION_STATES),
        )
    )
    if existing is not None:
        if expire_if_needed(db, existing, actor_user_id=current_user.id):
            db.flush()
        elif existing.inspector_id != inspector.id:
            existing.status = VerificationSessionStatus.ABORTED
            existing.abort_reason = "ASSIGNMENT_CHANGED"
            record_audit(
                db,
                organization_id=current_user.organization_id,
                actor_user_id=current_user.id,
                entity_type="VERIFICATION_SESSION",
                entity_id=existing.id,
                action="CAPTURE_ABORTED",
                metadata={"reason": "ASSIGNMENT_CHANGED"},
            )
            db.flush()
        else:
            raise SiteProofError(409, "ACTIVE_SESSION_EXISTS", "An active verification session already exists.")

    if inspection.status != InspectionStatus.READY:
        raise SiteProofError(409, "INSPECTION_NOT_READY", "Inspection must be READY before capture.")
    if aware(inspection.deadline) < now:
        raise SiteProofError(409, "INSPECTION_DEADLINE_PASSED", "Inspection deadline has passed.")

    client_time = aware(payload.client_time) if payload.client_time else None
    offset_ms = (now - client_time).total_seconds() * 1000.0 if client_time else None
    session = VerificationSession(
        organization_id=current_user.organization_id,
        inspection_id=inspection.id,
        inspector_id=inspector.id,
        status=VerificationSessionStatus.CREATED,
        expires_at=now + timedelta(minutes=settings.verification_session_ttl_minutes),
        device_session_id=payload.device_session_id,
        client_version=payload.client_version,
        android_version=payload.android_version,
        device_model=payload.device_model,
        client_wall_clock=client_time,
        client_monotonic_ns=payload.client_monotonic_ns,
        clock_offset_ms=offset_ms,
        site_snapshot={
            "latitude": inspection.expected_latitude,
            "longitude": inspection.expected_longitude,
            "allowedRadiusMeters": inspection.allowed_radius_meters,
            "captureDurationSeconds": inspection.capture_duration_seconds,
            "deadline": aware(inspection.deadline).isoformat(),
        },
        created_by_user_id=current_user.id,
    )
    db.add(session)
    db.flush()
    inspection.status = InspectionStatus.SESSION_STARTED
    record_audit(
        db,
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        entity_type="VERIFICATION_SESSION",
        entity_id=session.id,
        action="SESSION_CREATED",
        metadata={
            "inspectionId": str(inspection.id),
            "captureDurationSeconds": inspection.capture_duration_seconds,
        },
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise SiteProofError(409, "ACTIVE_SESSION_EXISTS", "An active verification session already exists.") from exc
    db.refresh(session)
    return _response(session, inspection, server_time=now, clock_offset_ms=offset_ms)
