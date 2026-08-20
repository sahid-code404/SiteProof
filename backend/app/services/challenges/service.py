import hashlib
import hmac
import json
import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import SiteProofError
from app.models.challenge import (
    ChallengeResult,
    ChallengeStatus,
    ChallengeType,
    VerificationChallenge,
)
from app.models.user import User
from app.models.verification import VerificationSession, VerificationSessionStatus
from app.schemas.challenge import (
    ChallengeIssueResponse,
    ChallengeListResponse,
    ChallengeParameters,
    ChallengeStartRequest,
    ChallengeSubmitRequest,
    ChallengeTimelineItem,
    ChallengeValidationResponse,
)
from app.services.audit_service import record_audit
from app.services.challenges.generator import generate_definition, instruction_for
from app.services.challenges.validators.rotate import RotateChallengeValidator
from app.services.challenges.validators.tilt import TiltChallengeValidator
from app.services.session_common import aware, owned_session, utc_now, viewable_session

ACTIVE_CHALLENGE_STATES = {ChallengeStatus.ISSUED, ChallengeStatus.STARTED}
TERMINAL_CHALLENGE_STATES = {
    ChallengeStatus.PASSED,
    ChallengeStatus.FAILED,
    ChallengeStatus.INCONCLUSIVE,
    ChallengeStatus.EXPIRED,
    ChallengeStatus.CANCELLED,
}
RETRYABLE_CHALLENGE_RESULTS = {ChallengeResult.FAIL, ChallengeResult.INCONCLUSIVE}


def _challenge_rows(db: Session, session_id: uuid.UUID) -> list[VerificationChallenge]:
    return list(
        db.scalars(
            select(VerificationChallenge)
            .where(VerificationChallenge.session_id == session_id)
            .order_by(
                VerificationChallenge.sequence_number,
                VerificationChallenge.attempt_number,
            )
        ).all()
    )


def _challenge_for_update(db: Session, challenge_id: uuid.UUID) -> VerificationChallenge:
    challenge = db.scalar(
        select(VerificationChallenge)
        .where(VerificationChallenge.id == challenge_id)
        .with_for_update()
    )
    if challenge is None:
        raise SiteProofError(404, "CHALLENGE_NOT_FOUND", "Challenge was not found.")
    return challenge


def _retry_count(rows: list[VerificationChallenge], sequence_number: int) -> int:
    return sum(
        1
        for row in rows
        if row.sequence_number == sequence_number and row.attempt_number > 1
    )


def _latest_by_sequence(rows: list[VerificationChallenge]) -> dict[int, VerificationChallenge]:
    latest: dict[int, VerificationChallenge] = {}
    for row in rows:
        current = latest.get(row.sequence_number)
        if current is None or row.attempt_number > current.attempt_number:
            latest[row.sequence_number] = row
    return latest


def _mark_expired(db: Session, challenge: VerificationChallenge, current_user: User) -> None:
    if challenge.status not in ACTIVE_CHALLENGE_STATES:
        return
    now = utc_now()
    challenge.status = ChallengeStatus.EXPIRED
    challenge.result = ChallengeResult.INCONCLUSIVE
    challenge.completed_at = now
    challenge.failure_reason = "CHALLENGE_EXPIRED"
    challenge.reasons_json = ["Challenge expired before valid sensor evidence was submitted."]
    record_audit(
        db,
        organization_id=challenge.organization_id,
        actor_user_id=current_user.id,
        entity_type="VERIFICATION_CHALLENGE",
        entity_id=challenge.id,
        action="CHALLENGE_EXPIRED",
        metadata={
            "sessionId": str(challenge.session_id),
            "sequenceNumber": challenge.sequence_number,
        },
    )


def _issue_response(challenge: VerificationChallenge) -> ChallengeIssueResponse:
    settings = get_settings()
    return ChallengeIssueResponse(
        challenge_id=challenge.id,
        sequence_number=challenge.sequence_number,
        attempt_number=challenge.attempt_number,
        total_challenges=settings.challenge_count,
        type=challenge.challenge_type,
        instruction=instruction_for(challenge.challenge_type),
        parameters=ChallengeParameters.model_validate(challenge.parameters_json),
        issued_at=challenge.issued_at,
        expires_at=challenge.expires_at,
        server_time=utc_now(),
        nonce=challenge.nonce,
    )


def _finalize_sequence(
    db: Session,
    current_user: User,
    session: VerificationSession,
    rows: list[VerificationChallenge],
) -> None:
    settings = get_settings()
    latest = _latest_by_sequence(rows)
    if len(latest) < settings.challenge_count:
        return
    explicit_failures = sum(1 for row in latest.values() if row.result == ChallengeResult.FAIL)
    session.status = (
        VerificationSessionStatus.CHALLENGE_FAILED
        if explicit_failures >= settings.challenge_failure_limit
        else VerificationSessionStatus.CHALLENGES_COMPLETED
    )
    record_audit(
        db,
        organization_id=session.organization_id,
        actor_user_id=current_user.id,
        entity_type="VERIFICATION_SESSION",
        entity_id=session.id,
        action="CHALLENGE_SEQUENCE_COMPLETED",
        metadata={
            "required": settings.challenge_count,
            "explicitFailures": explicit_failures,
            "sessionChallengeState": session.status.value,
        },
    )


def issue_next_challenge(
    db: Session,
    current_user: User,
    session_id: uuid.UUID,
) -> ChallengeIssueResponse:
    settings = get_settings()
    session = owned_session(db, current_user, session_id)
    if aware(session.expires_at) <= utc_now():
        raise SiteProofError(409, "SESSION_NOT_ACTIVE", "Verification session expired.")
    if session.status not in {
        VerificationSessionStatus.CAPTURING,
        VerificationSessionStatus.CHALLENGES_IN_PROGRESS,
    }:
        raise SiteProofError(409, "SESSION_NOT_ACTIVE", "Session is not accepting challenges.")

    rows = _challenge_rows(db, session.id)
    active = next((row for row in reversed(rows) if row.status in ACTIVE_CHALLENGE_STATES), None)
    if active is not None:
        if aware(active.expires_at) > utc_now():
            return _issue_response(active)
        _mark_expired(db, active, current_user)
        rows = _challenge_rows(db, session.id)

    session.status = VerificationSessionStatus.CHALLENGES_IN_PROGRESS
    latest = _latest_by_sequence(rows)
    previous = rows[-1] if rows else None
    retries_used = _retry_count(rows, previous.sequence_number) if previous else 0

    if previous and previous.result in RETRYABLE_CHALLENGE_RESULTS and retries_used < settings.challenge_max_retries:
        sequence_number = previous.sequence_number
        attempt_number = previous.attempt_number + 1
        audit_action = "CHALLENGE_RETRY_ISSUED"
    else:
        sequence_number = max(latest.keys(), default=0) + 1
        attempt_number = 1
        audit_action = "CHALLENGE_ISSUED"

    if sequence_number > settings.challenge_count:
        _finalize_sequence(db, current_user, session, rows)
        db.commit()
        raise SiteProofError(
            409,
            "CHALLENGE_LIMIT_REACHED",
            "Required challenge sequence is already complete.",
        )

    definition = generate_definition(
        sequence_number=sequence_number,
        previous_type=previous.challenge_type if previous else None,
        settings=settings,
    )
    now = utc_now()
    challenge = VerificationChallenge(
        organization_id=session.organization_id,
        inspection_id=session.inspection_id,
        session_id=session.id,
        sequence_number=sequence_number,
        challenge_type=definition.challenge_type,
        parameters_json=definition.parameters,
        nonce=definition.nonce,
        status=ChallengeStatus.ISSUED,
        issued_at=now,
        expires_at=now + timedelta(seconds=settings.challenge_timeout_seconds),
        attempt_number=attempt_number,
    )
    db.add(challenge)
    db.flush()
    record_audit(
        db,
        organization_id=challenge.organization_id,
        actor_user_id=current_user.id,
        entity_type="VERIFICATION_CHALLENGE",
        entity_id=challenge.id,
        action=audit_action,
        metadata={
            "sessionId": str(session.id),
            "sequenceNumber": sequence_number,
            "attemptNumber": attempt_number,
            "type": challenge.challenge_type.value,
        },
    )
    db.commit()
    db.refresh(challenge)
    return _issue_response(challenge)


def start_challenge(
    db: Session,
    current_user: User,
    challenge_id: uuid.UUID,
    payload: ChallengeStartRequest,
) -> ChallengeIssueResponse:
    challenge = _challenge_for_update(db, challenge_id)
    session = owned_session(db, current_user, challenge.session_id)
    if challenge.organization_id != current_user.organization_id:
        raise SiteProofError(404, "CHALLENGE_NOT_FOUND", "Challenge was not found.")
    if session.status != VerificationSessionStatus.CHALLENGES_IN_PROGRESS:
        raise SiteProofError(409, "SESSION_NOT_ACTIVE", "Session is not in challenge mode.")
    if aware(challenge.expires_at) <= utc_now():
        _mark_expired(db, challenge, current_user)
        db.commit()
        raise SiteProofError(409, "CHALLENGE_EXPIRED", "Challenge expired.")
    if challenge.status != ChallengeStatus.ISSUED:
        raise SiteProofError(409, "CHALLENGE_NOT_ACTIVE", "Challenge has already been started or completed.")
    if not hmac.compare_digest(challenge.nonce, payload.nonce):
        raise SiteProofError(409, "CHALLENGE_NONCE_INVALID", "Challenge nonce is invalid.")
    if session.capture_anchor_monotonic_ns is None:
        raise SiteProofError(409, "SESSION_NOT_ACTIVE", "Capture monotonic anchor is missing.")
    if payload.client_monotonic_ns < session.capture_anchor_monotonic_ns:
        raise SiteProofError(422, "SENSOR_EVIDENCE_INVALID", "Challenge start precedes capture start.")

    challenge.status = ChallengeStatus.STARTED
    challenge.started_at = utc_now()
    challenge.client_start_monotonic_ns = payload.client_monotonic_ns
    record_audit(
        db,
        organization_id=challenge.organization_id,
        actor_user_id=current_user.id,
        entity_type="VERIFICATION_CHALLENGE",
        entity_id=challenge.id,
        action="CHALLENGE_STARTED",
        metadata={
            "sessionId": str(session.id),
            "sequenceNumber": challenge.sequence_number,
        },
    )
    db.commit()
    db.refresh(challenge)
    return _issue_response(challenge)


def _evidence_hash(payload: ChallengeSubmitRequest) -> str:
    document = payload.model_dump(
        mode="json",
        by_alias=True,
        exclude={"nonce", "idempotency_key", "sensor_summary"},
    )
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _validate_structure(
    session: VerificationSession,
    challenge: VerificationChallenge,
    payload: ChallengeSubmitRequest,
) -> None:
    settings = get_settings()
    window = payload.sensor_window
    if window.end_relative_ns <= window.start_relative_ns:
        raise SiteProofError(422, "SENSOR_EVIDENCE_INVALID", "Sensor window end must follow start.")
    if len(payload.samples) > settings.challenge_max_sensor_samples:
        raise SiteProofError(422, "SENSOR_EVIDENCE_INVALID", "Challenge sensor slice is too large.")
    timestamps = [sample.relative_timestamp_ns for sample in payload.samples]
    if timestamps != sorted(timestamps):
        raise SiteProofError(422, "SENSOR_EVIDENCE_INVALID", "Sensor timestamps must be monotonic.")
    if any(timestamp < window.start_relative_ns or timestamp > window.end_relative_ns for timestamp in timestamps):
        raise SiteProofError(422, "SENSOR_EVIDENCE_INVALID", "Sensor samples fall outside the declared window.")
    if session.capture_anchor_monotonic_ns is None or challenge.client_start_monotonic_ns is None:
        raise SiteProofError(409, "SESSION_NOT_ACTIVE", "Capture or challenge timing anchor is missing.")

    expected_relative_start = challenge.client_start_monotonic_ns - session.capture_anchor_monotonic_ns
    if abs(window.start_relative_ns - expected_relative_start) > settings.challenge_window_start_tolerance_ms * 1_000_000:
        raise SiteProofError(422, "SENSOR_EVIDENCE_INVALID", "Sensor window does not align with challenge start.")
    evidence_end_monotonic_ns = session.capture_anchor_monotonic_ns + window.end_relative_ns
    physical_elapsed_ns = evidence_end_monotonic_ns - challenge.client_start_monotonic_ns
    if physical_elapsed_ns < 0:
        raise SiteProofError(422, "SENSOR_EVIDENCE_INVALID", "Sensor evidence precedes challenge start.")
    physical_end_server = aware(challenge.started_at) + timedelta(microseconds=physical_elapsed_ns / 1000)
    if physical_end_server > aware(challenge.expires_at) + timedelta(milliseconds=settings.challenge_end_tolerance_ms):
        raise SiteProofError(409, "CHALLENGE_EXPIRED", "Sensor evidence ended after the challenge deadline.")


def _validator_for(challenge_type: ChallengeType):
    if challenge_type in {ChallengeType.ROTATE_LEFT, ChallengeType.ROTATE_RIGHT}:
        return RotateChallengeValidator()
    if challenge_type in {ChallengeType.TILT_UP, ChallengeType.TILT_DOWN}:
        return TiltChallengeValidator()
    raise SiteProofError(422, "CHALLENGE_NOT_SUPPORTED", "Challenge type is not supported.")


def _result_response(
    db: Session,
    session: VerificationSession,
    challenge: VerificationChallenge,
) -> ChallengeValidationResponse:
    settings = get_settings()
    rows = _challenge_rows(db, session.id)
    retry_allowed = (
        challenge.result in RETRYABLE_CHALLENGE_RESULTS
        and _retry_count(rows, challenge.sequence_number) < settings.challenge_max_retries
        and challenge.sequence_number <= settings.challenge_count
    )
    sequence_complete = session.status in {
        VerificationSessionStatus.CHALLENGES_COMPLETED,
        VerificationSessionStatus.CHALLENGE_FAILED,
    }
    return ChallengeValidationResponse(
        challenge_id=challenge.id,
        sequence_number=challenge.sequence_number,
        type=challenge.challenge_type,
        result=challenge.result or ChallengeResult.INCONCLUSIVE,
        score=challenge.validation_score or 0.0,
        reasons=challenge.reasons_json or [],
        metrics=challenge.metrics_json or {},
        sensor_quality=challenge.sensor_quality_json or {},
        retry_allowed=retry_allowed,
        sequence_complete=sequence_complete,
        session_status=session.status,
        server_time=utc_now(),
    )


def submit_challenge(
    db: Session,
    current_user: User,
    challenge_id: uuid.UUID,
    payload: ChallengeSubmitRequest,
) -> ChallengeValidationResponse:
    settings = get_settings()
    challenge = _challenge_for_update(db, challenge_id)
    session = owned_session(db, current_user, challenge.session_id)
    if challenge.organization_id != current_user.organization_id:
        raise SiteProofError(404, "CHALLENGE_NOT_FOUND", "Challenge was not found.")
    if aware(session.expires_at) <= utc_now():
        raise SiteProofError(409, "SESSION_NOT_ACTIVE", "Verification session expired.")

    evidence_hash = _evidence_hash(payload)
    if challenge.status in TERMINAL_CHALLENGE_STATES:
        if (
            challenge.submission_idempotency_key == payload.idempotency_key
            and challenge.evidence_sha256 == evidence_hash
            and hmac.compare_digest(challenge.nonce, payload.nonce)
        ):
            return _result_response(db, session, challenge)
        raise SiteProofError(409, "CHALLENGE_ALREADY_COMPLETED", "Challenge was already completed.")

    if session.status != VerificationSessionStatus.CHALLENGES_IN_PROGRESS:
        raise SiteProofError(409, "SESSION_NOT_ACTIVE", "Session is not accepting challenge evidence.")
    if challenge.status != ChallengeStatus.STARTED:
        raise SiteProofError(409, "CHALLENGE_NOT_ACTIVE", "Challenge must be started before submission.")
    if challenge.nonce_consumed_at is not None or not hmac.compare_digest(challenge.nonce, payload.nonce):
        raise SiteProofError(409, "CHALLENGE_NONCE_INVALID", "Challenge nonce is invalid or already consumed.")
    duplicate_key = db.scalar(
        select(VerificationChallenge).where(
            VerificationChallenge.session_id == challenge.session_id,
            VerificationChallenge.submission_idempotency_key == payload.idempotency_key,
            VerificationChallenge.id != challenge.id,
        )
    )
    if duplicate_key is not None:
        raise SiteProofError(409, "CHALLENGE_ALREADY_COMPLETED", "Submission idempotency key was already used.")

    _validate_structure(session, challenge, payload)
    validator = _validator_for(challenge.challenge_type)
    outcome = validator.validate(
        challenge,
        payload,
        capabilities=session.device_capabilities or {},
        settings=settings,
    )

    challenge.status = {
        ChallengeResult.PASS: ChallengeStatus.PASSED,
        ChallengeResult.FAIL: ChallengeStatus.FAILED,
        ChallengeResult.INCONCLUSIVE: ChallengeStatus.INCONCLUSIVE,
    }[outcome.result]
    challenge.result = outcome.result
    challenge.sensor_score = outcome.sensor_score
    challenge.validation_score = outcome.score
    challenge.reasons_json = outcome.reasons
    challenge.metrics_json = outcome.metrics
    challenge.sensor_quality_json = outcome.sensor_quality
    challenge.failure_reason = outcome.failure_reason
    challenge.evidence_sha256 = evidence_hash
    challenge.submission_idempotency_key = payload.idempotency_key
    challenge.nonce_consumed_at = utc_now()
    challenge.completed_at = challenge.nonce_consumed_at

    record_audit(
        db,
        organization_id=challenge.organization_id,
        actor_user_id=current_user.id,
        entity_type="VERIFICATION_CHALLENGE",
        entity_id=challenge.id,
        action="CHALLENGE_SUBMITTED",
        metadata={
            "sessionId": str(session.id),
            "sequenceNumber": challenge.sequence_number,
            "sensorSampleCount": len(payload.samples),
        },
    )
    result_action = {
        ChallengeResult.PASS: "CHALLENGE_PASSED",
        ChallengeResult.FAIL: "CHALLENGE_FAILED",
        ChallengeResult.INCONCLUSIVE: "CHALLENGE_INCONCLUSIVE",
    }[outcome.result]
    record_audit(
        db,
        organization_id=challenge.organization_id,
        actor_user_id=current_user.id,
        entity_type="VERIFICATION_CHALLENGE",
        entity_id=challenge.id,
        action=result_action,
        metadata={
            "sessionId": str(session.id),
            "sequenceNumber": challenge.sequence_number,
            "score": round(outcome.score, 4),
            "failureReason": outcome.failure_reason,
        },
    )

    rows = _challenge_rows(db, session.id)
    retry_allowed = (
        outcome.result in RETRYABLE_CHALLENGE_RESULTS
        and _retry_count(rows, challenge.sequence_number) < settings.challenge_max_retries
    )
    if challenge.sequence_number >= settings.challenge_count and not retry_allowed:
        _finalize_sequence(db, current_user, session, rows)

    db.commit()
    db.refresh(challenge)
    db.refresh(session)
    return _result_response(db, session, challenge)


def list_challenges(
    db: Session,
    current_user: User,
    session_id: uuid.UUID,
) -> ChallengeListResponse:
    settings = get_settings()
    session = viewable_session(db, current_user, session_id)
    rows = _challenge_rows(db, session.id)
    items = [
        ChallengeTimelineItem(
            id=row.id,
            sequence_number=row.sequence_number,
            attempt_number=row.attempt_number,
            type=row.challenge_type,
            status=row.status,
            result=row.result,
            parameters=ChallengeParameters.model_validate(row.parameters_json),
            issued_at=row.issued_at,
            started_at=row.started_at,
            completed_at=row.completed_at,
            expires_at=row.expires_at,
            score=row.validation_score,
            sensor_score=row.sensor_score,
            failure_reason=row.failure_reason,
            reasons=row.reasons_json or [],
            metrics=row.metrics_json or {},
            sensor_quality=row.sensor_quality_json or {},
        )
        for row in rows
    ]
    return ChallengeListResponse(
        session_id=session.id,
        total_required=settings.challenge_count,
        items=items,
    )
