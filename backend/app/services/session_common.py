import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import SiteProofError
from app.models.assignment import AssignmentStatus, InspectionAssignment
from app.models.inspection import Inspection, InspectionStatus
from app.models.inspector import Inspector
from app.models.user import User, UserRole
from app.models.verification import (
    EvidenceFile,
    EvidenceFileType,
    EvidenceUploadStatus,
    VerificationSession,
    VerificationSessionStatus,
)
from app.schemas.session import EvidencePresence, LocationSummary, SensorSummary, VerificationSessionResponse
from app.services.audit_service import record_audit

ACTIVE_SESSION_STATES = {
    VerificationSessionStatus.CREATED,
    VerificationSessionStatus.CAPTURING,
    VerificationSessionStatus.CHALLENGES_IN_PROGRESS,
    VerificationSessionStatus.CHALLENGES_COMPLETED,
    VerificationSessionStatus.CHALLENGE_FAILED,
    VerificationSessionStatus.CAPTURE_COMPLETED,
    VerificationSessionStatus.UPLOADING,
    VerificationSessionStatus.UPLOAD_FAILED,
}

# The short verification-session expiry protects the *live proof* stage. Once the server has
# accepted the complete challenge sequence, or once capture has been finalized, the Phase 3
# evidence transport may legitimately arrive later after a network gap. Expiring those states
# merely because an admin/inspector polls the session would destroy that recovery guarantee.
LIVE_EXPIRING_STATES = {
    VerificationSessionStatus.CREATED,
    VerificationSessionStatus.CAPTURING,
    VerificationSessionStatus.CHALLENGES_IN_PROGRESS,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_m = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    return 2 * radius_m * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_inspector_for_user(db: Session, current_user: User) -> Inspector:
    if current_user.role != UserRole.INSPECTOR:
        raise SiteProofError(403, "FORBIDDEN", "Only inspectors may capture verification evidence.")
    inspector = db.scalar(
        select(Inspector).where(
            Inspector.user_id == current_user.id,
            Inspector.organization_id == current_user.organization_id,
            Inspector.active.is_(True),
        )
    )
    if inspector is None:
        raise SiteProofError(403, "FORBIDDEN", "Active inspector profile is required.")
    return inspector


def active_assignment(
    db: Session, inspection_id: uuid.UUID, inspector_id: uuid.UUID | None = None
) -> InspectionAssignment | None:
    statement = select(InspectionAssignment).where(
        InspectionAssignment.inspection_id == inspection_id,
        InspectionAssignment.status == AssignmentStatus.ACTIVE,
    )
    if inspector_id is not None:
        statement = statement.where(InspectionAssignment.inspector_id == inspector_id)
    return db.scalar(statement)


def scoped_inspection(db: Session, current_user: User, inspection_id: uuid.UUID) -> Inspection:
    inspection = db.scalar(
        select(Inspection).where(
            Inspection.id == inspection_id,
            Inspection.organization_id == current_user.organization_id,
        )
    )
    if inspection is None:
        raise SiteProofError(404, "INSPECTION_NOT_FOUND", "Inspection was not found.")
    if current_user.role == UserRole.INSPECTOR:
        inspector = get_inspector_for_user(db, current_user)
        if active_assignment(db, inspection.id, inspector.id) is None:
            raise SiteProofError(404, "INSPECTION_NOT_FOUND", "Inspection was not found.")
    return inspection


def owned_session(
    db: Session,
    current_user: User,
    session_id: uuid.UUID,
    *,
    require_active_assignment: bool = True,
) -> VerificationSession:
    inspector = get_inspector_for_user(db, current_user)
    session = db.scalar(
        select(VerificationSession).where(
            VerificationSession.id == session_id,
            VerificationSession.organization_id == current_user.organization_id,
            VerificationSession.inspector_id == inspector.id,
        )
    )
    if session is None:
        raise SiteProofError(404, "SESSION_NOT_FOUND", "Verification session was not found.")
    if require_active_assignment and active_assignment(db, session.inspection_id, inspector.id) is None:
        raise SiteProofError(403, "NOT_ASSIGNED", "This inspection is no longer assigned to you.")
    return session


def viewable_session(db: Session, current_user: User, session_id: uuid.UUID) -> VerificationSession:
    session = db.scalar(
        select(VerificationSession).where(
            VerificationSession.id == session_id,
            VerificationSession.organization_id == current_user.organization_id,
        )
    )
    if session is None:
        raise SiteProofError(404, "SESSION_NOT_FOUND", "Verification session was not found.")
    if current_user.role == UserRole.INSPECTOR:
        inspector = get_inspector_for_user(db, current_user)
        if session.inspector_id != inspector.id:
            raise SiteProofError(404, "SESSION_NOT_FOUND", "Verification session was not found.")
    return session


def expire_if_needed(db: Session, session: VerificationSession, *, actor_user_id: uuid.UUID) -> bool:
    if session.status not in LIVE_EXPIRING_STATES or aware(session.expires_at) > utc_now():
        return False
    session.status = VerificationSessionStatus.EXPIRED
    inspection = db.get(Inspection, session.inspection_id)
    if inspection and inspection.status != InspectionStatus.CANCELLED:
        inspection.status = InspectionStatus.READY
    record_audit(
        db,
        organization_id=session.organization_id,
        actor_user_id=actor_user_id,
        entity_type="VERIFICATION_SESSION",
        entity_id=session.id,
        action="SESSION_EXPIRED",
    )
    return True


def session_response(db: Session, session: VerificationSession) -> VerificationSessionResponse:
    uploaded = set(
        db.scalars(
            select(EvidenceFile.file_type).where(
                EvidenceFile.session_id == session.id,
                EvidenceFile.upload_status == EvidenceUploadStatus.UPLOADED,
                EvidenceFile.hash_verified.is_(True),
            )
        ).all()
    )
    evidence = EvidencePresence(
        video=EvidenceFileType.VIDEO in uploaded,
        sensor_data=EvidenceFileType.SENSOR_DATA in uploaded,
        location_data=EvidenceFileType.LOCATION_DATA in uploaded,
        session_metadata=EvidenceFileType.SESSION_METADATA in uploaded,
        manifest=EvidenceFileType.MANIFEST in uploaded,
    )
    sensor_summary = SensorSummary.model_validate(session.sensor_summary) if session.sensor_summary else None
    location_summary = LocationSummary.model_validate(session.location_summary) if session.location_summary else None
    return VerificationSessionResponse(
        id=session.id,
        inspection_id=session.inspection_id,
        inspector_id=session.inspector_id,
        status=session.status,
        created_at=session.created_at,
        capture_started_at=session.capture_started_at,
        capture_ended_at=session.capture_ended_at,
        uploaded_at=session.uploaded_at,
        expires_at=session.expires_at,
        capture_duration_ms=session.capture_duration_ms,
        manifest_sha256=session.manifest_sha256,
        sensor_summary=sensor_summary,
        location_summary=location_summary,
        evidence=evidence,
    )
