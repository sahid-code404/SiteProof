import uuid
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import SiteProofError
from app.models.inspection import Inspection, InspectionStatus
from app.models.user import User
from app.models.verification import VerificationSessionStatus
from app.schemas.session import AbortRequest, CaptureCompleteRequest, StartCaptureRequest, VerificationSessionResponse
from app.services.audit_service import record_audit
from app.services.session_common import (
    ACTIVE_SESSION_STATES,
    aware,
    expire_if_needed,
    haversine_meters,
    owned_session,
    session_response,
    utc_now,
)


def start_capture(
    db: Session, current_user: User, session_id: uuid.UUID, payload: StartCaptureRequest
) -> VerificationSessionResponse:
    settings = get_settings()
    session = owned_session(db, current_user, session_id)
    if expire_if_needed(db, session, actor_user_id=current_user.id):
        db.commit()
        raise SiteProofError(409, "SESSION_EXPIRED", "Verification session expired.")
    if session.status != VerificationSessionStatus.CREATED:
        raise SiteProofError(409, "INVALID_STATUS_TRANSITION", "Only CREATED sessions can start capture.")
    inspection = db.get(Inspection, session.inspection_id)
    if inspection is None or inspection.status == InspectionStatus.CANCELLED:
        raise SiteProofError(409, "INSPECTION_UNAVAILABLE", "Inspection is unavailable.")

    now = utc_now()
    snapshot = session.site_snapshot or {
        "latitude": inspection.expected_latitude,
        "longitude": inspection.expected_longitude,
        "allowedRadiusMeters": inspection.allowed_radius_meters,
        "deadline": aware(inspection.deadline).isoformat(),
    }
    deadline = aware(datetime.fromisoformat(str(snapshot["deadline"])))
    if now > deadline + timedelta(seconds=settings.session_start_grace_seconds):
        session.status = VerificationSessionStatus.EXPIRED
        inspection.status = InspectionStatus.READY
        record_audit(
            db,
            organization_id=current_user.organization_id,
            actor_user_id=current_user.id,
            entity_type="VERIFICATION_SESSION",
            entity_id=session.id,
            action="SESSION_EXPIRED",
            metadata={"reason": "DEADLINE_GRACE_EXCEEDED"},
        )
        db.commit()
        raise SiteProofError(409, "SESSION_EXPIRED", "Capture start grace period has passed.")

    distance = haversine_meters(
        float(snapshot["latitude"]),
        float(snapshot["longitude"]),
        payload.location.latitude,
        payload.location.longitude,
    )
    radius = float(snapshot["allowedRadiusMeters"])
    uncertainty = max(payload.location.accuracy_meters, 0.0)
    if distance > radius + uncertainty:
        raise SiteProofError(
            409,
            "OUTSIDE_ALLOWED_LOCATION",
            f"Current location is approximately {round(distance)} m from the assigned site.",
        )
    if distance > radius:
        raise SiteProofError(
            409,
            "LOCATION_INCONCLUSIVE",
            "Location is near the allowed boundary but GPS uncertainty is too high. Retry for a more accurate position.",
        )

    session.status = VerificationSessionStatus.CAPTURING
    session.started_at = session.started_at or now
    session.capture_started_at = now
    session.capture_anchor_wall_clock = aware(payload.client_wall_clock)
    session.capture_anchor_monotonic_ns = payload.client_monotonic_ns
    session.pre_capture_location = {
        **payload.location.model_dump(mode="json"),
        "distanceMeters": distance,
        "allowedRadiusMeters": int(radius),
    }
    session.device_capabilities = payload.capabilities.model_dump()
    inspection.status = InspectionStatus.SESSION_STARTED
    record_audit(
        db,
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        entity_type="VERIFICATION_SESSION",
        entity_id=session.id,
        action="CAPTURE_STARTED",
        metadata={"distanceMeters": round(distance, 2), "locationAccuracyMeters": payload.location.accuracy_meters},
    )
    db.commit()
    db.refresh(session)
    return session_response(db, session)


def complete_capture(
    db: Session, current_user: User, session_id: uuid.UUID, payload: CaptureCompleteRequest
) -> VerificationSessionResponse:
    settings = get_settings()
    session = owned_session(db, current_user, session_id)
    if expire_if_needed(db, session, actor_user_id=current_user.id):
        db.commit()
        raise SiteProofError(409, "SESSION_EXPIRED", "Verification session expired.")

    completed_states = {
        VerificationSessionStatus.CAPTURE_COMPLETED,
        VerificationSessionStatus.UPLOADING,
        VerificationSessionStatus.UPLOAD_FAILED,
        VerificationSessionStatus.UPLOADED,
    }
    if session.status in completed_states:
        same_payload = (
            session.capture_duration_ms == payload.capture_duration_ms
            and (session.sensor_summary or {}) == payload.sensor_summary.model_dump()
            and (session.location_summary or {}) == payload.location_summary.model_dump()
        )
        if same_payload:
            return session_response(db, session)
        raise SiteProofError(
            409,
            "CAPTURE_SUMMARY_CONFLICT",
            "Capture completion was already recorded with different metadata.",
        )

    if session.status != VerificationSessionStatus.CAPTURING:
        raise SiteProofError(409, "INVALID_STATUS_TRANSITION", "Only CAPTURING sessions can complete capture.")
    if payload.capture_duration_ms < settings.capture_min_seconds * 1000:
        raise SiteProofError(422, "CAPTURE_TOO_SHORT", f"Capture must be at least {settings.capture_min_seconds} seconds.")
    if payload.capture_duration_ms > settings.capture_max_seconds * 1000:
        raise SiteProofError(422, "CAPTURE_TOO_LONG", f"Capture cannot exceed {settings.capture_max_seconds} seconds.")
    if payload.video_file_count != 1:
        raise SiteProofError(422, "VIDEO_REQUIRED", "Exactly one live video capture is required.")
    if payload.sensor_summary.accelerometer_samples <= 0:
        raise SiteProofError(422, "SENSOR_DATA_REQUIRED", "Accelerometer samples are required.")
    capabilities = session.device_capabilities or {}
    if capabilities.get("gyroscope") and payload.sensor_summary.gyroscope_samples <= 0:
        raise SiteProofError(422, "SENSOR_DATA_REQUIRED", "Gyroscope samples are required.")
    if capabilities.get("rotation_vector") and payload.sensor_summary.rotation_vector_samples <= 0:
        raise SiteProofError(422, "SENSOR_DATA_REQUIRED", "Rotation-vector samples are required.")
    if payload.location_summary.location_samples <= 0:
        raise SiteProofError(422, "LOCATION_DATA_REQUIRED", "At least one location sample is required.")

    session.status = VerificationSessionStatus.CAPTURE_COMPLETED
    session.capture_ended_at = utc_now()
    session.capture_duration_ms = payload.capture_duration_ms
    session.sensor_summary = payload.sensor_summary.model_dump()
    session.location_summary = payload.location_summary.model_dump()
    inspection = db.get(Inspection, session.inspection_id)
    if inspection is not None and inspection.status != InspectionStatus.CANCELLED:
        inspection.status = InspectionStatus.EVIDENCE_UPLOADING
    record_audit(
        db,
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        entity_type="VERIFICATION_SESSION",
        entity_id=session.id,
        action="CAPTURE_COMPLETED",
        metadata={
            "durationMs": payload.capture_duration_ms,
            "sensorSummary": payload.sensor_summary.model_dump(),
            "locationSamples": payload.location_summary.location_samples,
        },
    )
    db.commit()
    db.refresh(session)
    return session_response(db, session)


def abort_session(
    db: Session, current_user: User, session_id: uuid.UUID, payload: AbortRequest
) -> VerificationSessionResponse:
    session = owned_session(db, current_user, session_id, require_active_assignment=False)
    if session.status not in ACTIVE_SESSION_STATES:
        raise SiteProofError(409, "INVALID_STATUS_TRANSITION", "This session can no longer be aborted.")
    session.status = VerificationSessionStatus.ABORTED
    session.abort_reason = payload.reason.value
    inspection = db.get(Inspection, session.inspection_id)
    if inspection is not None and inspection.status != InspectionStatus.CANCELLED:
        inspection.status = InspectionStatus.READY
    record_audit(
        db,
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        entity_type="VERIFICATION_SESSION",
        entity_id=session.id,
        action="CAPTURE_ABORTED",
        metadata={"reason": payload.reason.value},
    )
    db.commit()
    db.refresh(session)
    return session_response(db, session)
