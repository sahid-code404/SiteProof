from __future__ import annotations

import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import SiteProofError
from app.models.semantic_challenge import (
    SemanticCaptureChallenge,
    SemanticChallengeStatus,
    SemanticChallengeType,
)
from app.models.user import User
from app.models.verification import VerificationSession, VerificationSessionStatus
from app.schemas.semantic_challenge import (
    SemanticChallengeCompleteRequest,
    SemanticChallengeCompleteResponse,
    SemanticChallengeIssueResponse,
    SemanticChallengeListResponse,
    SemanticChallengeStartRequest,
    SemanticChallengeTimelineItem,
)
from app.services.audit_service import record_audit
from app.services.session_common import aware, owned_session, utc_now, viewable_session

ACTIVE_STATES = {SemanticChallengeStatus.ISSUED, SemanticChallengeStatus.STARTED}
PHYSICAL_CHALLENGE_TERMINAL_SESSION_STATES = {
    VerificationSessionStatus.CHALLENGES_COMPLETED,
    VerificationSessionStatus.CHALLENGE_FAILED,
}


@dataclass(frozen=True)
class SemanticChallengeDefinition:
    type: SemanticChallengeType
    instruction: str
    target: dict[str, str]


def _frozen_required_count(session: VerificationSession | None) -> int | None:
    if session is None:
        return None
    snapshot = session.site_snapshot or {}
    if "semanticChallengeCount" not in snapshot:
        return None
    return max(0, min(4, int(snapshot.get("semanticChallengeCount", 0) or 0)))


def semantic_challenges_enabled(
    settings: object | None = None,
    session: VerificationSession | None = None,
) -> bool:
    frozen = _frozen_required_count(session)
    if frozen is not None:
        return frozen > 0
    active = settings or get_settings()
    return bool(
        getattr(active, "autonomous_verification_enabled", False)
        and getattr(active, "autonomous_semantic_challenges_enabled", False)
    )


def semantic_challenge_required_count(
    settings: object | None = None,
    session: VerificationSession | None = None,
) -> int:
    frozen = _frozen_required_count(session)
    if frozen is not None:
        return frozen
    active = settings or get_settings()
    if not semantic_challenges_enabled(active):
        return 0
    return max(1, min(4, int(getattr(active, "autonomous_semantic_challenge_count", 2))))


def _timeout_seconds(settings: object) -> int:
    return max(
        8,
        min(60, int(getattr(settings, "autonomous_semantic_challenge_timeout_seconds", 25))),
    )


def _duration_bounds_ms(settings: object) -> tuple[int, int]:
    minimum = max(
        750,
        int(getattr(settings, "autonomous_semantic_challenge_min_duration_ms", 1500)),
    )
    maximum = max(
        minimum,
        int(getattr(settings, "autonomous_semantic_challenge_max_duration_ms", 12000)),
    )
    return minimum, min(maximum, 30000)


def _max_attempts(settings: object) -> int:
    retries = max(
        0,
        min(3, int(getattr(settings, "autonomous_semantic_challenge_max_retries", 2))),
    )
    return 1 + retries


def _rows(db: Session, session_id: uuid.UUID) -> list[SemanticCaptureChallenge]:
    return list(
        db.scalars(
            select(SemanticCaptureChallenge)
            .where(SemanticCaptureChallenge.session_id == session_id)
            .order_by(
                SemanticCaptureChallenge.sequence_number,
                SemanticCaptureChallenge.attempt_number,
            )
        ).all()
    )


def _for_update(db: Session, challenge_id: uuid.UUID) -> SemanticCaptureChallenge:
    challenge = db.scalar(
        select(SemanticCaptureChallenge)
        .where(SemanticCaptureChallenge.id == challenge_id)
        .with_for_update()
    )
    if challenge is None:
        raise SiteProofError(
            404,
            "SEMANTIC_CHALLENGE_NOT_FOUND",
            "Semantic challenge was not found.",
        )
    return challenge


def _latest_by_sequence(
    rows: list[SemanticCaptureChallenge],
) -> dict[int, SemanticCaptureChallenge]:
    latest: dict[int, SemanticCaptureChallenge] = {}
    for row in rows:
        current = latest.get(row.sequence_number)
        if current is None or row.attempt_number > current.attempt_number:
            latest[row.sequence_number] = row
    return latest


def semantic_sequence_complete(rows: list[SemanticCaptureChallenge], required: int) -> bool:
    if required <= 0:
        return True
    latest = _latest_by_sequence(rows)
    return all(
        latest.get(sequence) is not None
        and latest[sequence].status == SemanticChallengeStatus.COMPLETED
        for sequence in range(1, required + 1)
    )


def _clean_text(value: object, *, limit: int) -> str:
    text = " ".join(str(value or "").split()).strip()
    return text[:limit]


def _definitions(session: VerificationSession) -> list[SemanticChallengeDefinition]:
    snapshot = session.site_snapshot or {}
    title = _clean_text(snapshot.get("title"), limit=180) or "the assigned inspection subject"
    description = _clean_text(snapshot.get("description"), limit=420)
    instructions = _clean_text(snapshot.get("instructions"), limit=420)
    task_text = _clean_text(
        " ".join(part for part in (description, instructions) if part),
        limit=650,
    )
    if not task_text:
        task_text = f"the required inspection evidence for {title}"

    definitions = [
        SemanticChallengeDefinition(
            type=SemanticChallengeType.SHOW_OVERVIEW,
            instruction=(
                f"Show the entire assigned subject, {title}, together with enough surroundings to "
                "establish its physical context. Keep the recording continuous."
            ),
            target={"proofKind": "overview", "subject": title},
        ),
        SemanticChallengeDefinition(
            type=SemanticChallengeType.SHOW_TASK_DETAIL,
            instruction=(
                f"Move closer and clearly show the task-relevant evidence for: {task_text}. "
                "Do not stop or switch the recording."
            ),
            target={
                "proofKind": "task_detail",
                "subject": title,
                "requirementText": task_text,
            },
        ),
        SemanticChallengeDefinition(
            type=SemanticChallengeType.SHOW_SITE_CONTEXT,
            instruction=(
                f"In one continuous view, show {title}, then nearby fixed surroundings, then return "
                "to the assigned subject."
            ),
            target={"proofKind": "site_context", "subject": title},
        ),
    ]

    identity_text = f"{title} {task_text}".lower()
    if any(
        marker in identity_text
        for marker in (
            "serial",
            "asset id",
            "asset number",
            "identifier",
            "qr",
            "barcode",
            "plate",
        )
    ):
        definitions.append(
            SemanticChallengeDefinition(
                type=SemanticChallengeType.SHOW_ASSET_IDENTITY,
                instruction=(
                    f"Show the identity label or identifier on {title}, then widen the view enough "
                    "to connect that identifier to the same physical asset."
                ),
                target={"proofKind": "asset_identity", "subject": title},
            )
        )
    return definitions


def _issue_response(
    challenge: SemanticCaptureChallenge,
    *,
    total: int,
) -> SemanticChallengeIssueResponse:
    return SemanticChallengeIssueResponse(
        challenge_id=challenge.id,
        sequence_number=challenge.sequence_number,
        attempt_number=challenge.attempt_number,
        total_challenges=total,
        type=challenge.challenge_type,
        instruction=challenge.instruction,
        target=challenge.target_json,
        issued_at=challenge.issued_at,
        expires_at=challenge.expires_at,
        server_time=utc_now(),
        nonce=challenge.nonce,
    )


def _completion_response(
    db: Session,
    challenge: SemanticCaptureChallenge,
    *,
    required: int,
) -> SemanticChallengeCompleteResponse:
    rows = _rows(db, challenge.session_id)
    return SemanticChallengeCompleteResponse(
        challenge_id=challenge.id,
        sequence_number=challenge.sequence_number,
        attempt_number=challenge.attempt_number,
        type=challenge.challenge_type,
        status=challenge.status,
        window_start_ms=int(challenge.window_start_ms or 0),
        window_end_ms=int(challenge.window_end_ms or 0),
        sequence_complete=semantic_sequence_complete(rows, required),
        server_time=utc_now(),
    )


def _mark_expired(
    db: Session,
    challenge: SemanticCaptureChallenge,
    current_user: User,
) -> None:
    if challenge.status not in ACTIVE_STATES:
        return
    challenge.status = SemanticChallengeStatus.EXPIRED
    challenge.completed_at = utc_now()
    record_audit(
        db,
        organization_id=challenge.organization_id,
        actor_user_id=current_user.id,
        entity_type="SEMANTIC_CAPTURE_CHALLENGE",
        entity_id=challenge.id,
        action="SEMANTIC_CHALLENGE_EXPIRED",
        metadata={
            "sessionId": str(challenge.session_id),
            "sequenceNumber": challenge.sequence_number,
            "attemptNumber": challenge.attempt_number,
        },
    )


def issue_next_semantic_challenge(
    db: Session,
    current_user: User,
    session_id: uuid.UUID,
) -> SemanticChallengeIssueResponse:
    settings = get_settings()
    session = owned_session(db, current_user, session_id)
    if not semantic_challenges_enabled(settings, session):
        raise SiteProofError(
            409,
            "SEMANTIC_CHALLENGES_DISABLED",
            "Task-specific semantic capture challenges are not enabled for this session.",
        )
    if session.status not in PHYSICAL_CHALLENGE_TERMINAL_SESSION_STATES:
        raise SiteProofError(
            409,
            "SEMANTIC_CHALLENGE_NOT_READY",
            "Finish the required movement challenge sequence before semantic proof challenges.",
        )
    if aware(session.expires_at) <= utc_now():
        raise SiteProofError(409, "SESSION_NOT_ACTIVE", "Verification session expired.")
    if session.capture_anchor_monotonic_ns is None:
        raise SiteProofError(409, "SESSION_NOT_ACTIVE", "Capture monotonic anchor is missing.")

    required = semantic_challenge_required_count(settings, session)
    rows = _rows(db, session.id)
    active = next((row for row in reversed(rows) if row.status in ACTIVE_STATES), None)
    if active is not None:
        if aware(active.expires_at) > utc_now():
            return _issue_response(active, total=required)
        _mark_expired(db, active, current_user)
        db.flush()
        rows = _rows(db, session.id)

    if semantic_sequence_complete(rows, required):
        raise SiteProofError(
            409,
            "SEMANTIC_CHALLENGES_COMPLETE",
            "All required semantic capture challenges are already complete.",
        )

    latest = _latest_by_sequence(rows)
    sequence_number = next(
        sequence
        for sequence in range(1, required + 1)
        if latest.get(sequence) is None
        or latest[sequence].status != SemanticChallengeStatus.COMPLETED
    )
    attempts = [row for row in rows if row.sequence_number == sequence_number]
    attempt_number = max((row.attempt_number for row in attempts), default=0) + 1
    if attempt_number > _max_attempts(settings):
        raise SiteProofError(
            409,
            "SEMANTIC_CHALLENGE_RETRY_LIMIT",
            "Semantic challenge retry limit was reached; start a new capture.",
        )

    definitions = _definitions(session)
    previous_types = {row.challenge_type for row in attempts}
    available = [item for item in definitions if item.type not in previous_types] or definitions
    definition = secrets.choice(available)
    now = utc_now()
    challenge = SemanticCaptureChallenge(
        organization_id=session.organization_id,
        inspection_id=session.inspection_id,
        session_id=session.id,
        sequence_number=sequence_number,
        attempt_number=attempt_number,
        challenge_type=definition.type,
        instruction=definition.instruction,
        target_json=definition.target,
        nonce=secrets.token_urlsafe(32),
        status=SemanticChallengeStatus.ISSUED,
        issued_at=now,
        expires_at=now + timedelta(seconds=_timeout_seconds(settings)),
    )
    db.add(challenge)
    db.flush()
    record_audit(
        db,
        organization_id=session.organization_id,
        actor_user_id=current_user.id,
        entity_type="SEMANTIC_CAPTURE_CHALLENGE",
        entity_id=challenge.id,
        action="SEMANTIC_CHALLENGE_ISSUED",
        metadata={
            "sessionId": str(session.id),
            "sequenceNumber": sequence_number,
            "attemptNumber": attempt_number,
            "type": definition.type.value,
        },
    )
    db.commit()
    db.refresh(challenge)
    return _issue_response(challenge, total=required)


def start_semantic_challenge(
    db: Session,
    current_user: User,
    challenge_id: uuid.UUID,
    payload: SemanticChallengeStartRequest,
) -> SemanticChallengeIssueResponse:
    settings = get_settings()
    challenge = _for_update(db, challenge_id)
    session = owned_session(db, current_user, challenge.session_id)
    if challenge.status != SemanticChallengeStatus.ISSUED:
        raise SiteProofError(
            409,
            "SEMANTIC_CHALLENGE_NOT_ACTIVE",
            "Semantic challenge has already been started or completed.",
        )
    if aware(challenge.expires_at) <= utc_now():
        _mark_expired(db, challenge, current_user)
        db.commit()
        raise SiteProofError(409, "SEMANTIC_CHALLENGE_EXPIRED", "Semantic challenge expired.")
    if not hmac.compare_digest(challenge.nonce, payload.nonce):
        raise SiteProofError(
            409,
            "SEMANTIC_CHALLENGE_NONCE_INVALID",
            "Semantic challenge nonce is invalid.",
        )
    anchor = session.capture_anchor_monotonic_ns
    if anchor is None or payload.client_monotonic_ns < anchor:
        raise SiteProofError(
            422,
            "SEMANTIC_CHALLENGE_TIMING_INVALID",
            "Semantic challenge start does not align with the active capture timeline.",
        )
    start_ms = (payload.client_monotonic_ns - anchor) // 1_000_000
    if start_ms > int(getattr(settings, "vision_max_duration_seconds", 90)) * 1000:
        raise SiteProofError(
            422,
            "SEMANTIC_CHALLENGE_TIMING_INVALID",
            "Semantic challenge start falls outside the bounded capture timeline.",
        )

    challenge.status = SemanticChallengeStatus.STARTED
    challenge.started_at = utc_now()
    challenge.client_start_monotonic_ns = payload.client_monotonic_ns
    challenge.window_start_ms = int(start_ms)
    record_audit(
        db,
        organization_id=session.organization_id,
        actor_user_id=current_user.id,
        entity_type="SEMANTIC_CAPTURE_CHALLENGE",
        entity_id=challenge.id,
        action="SEMANTIC_CHALLENGE_STARTED",
        metadata={
            "sequenceNumber": challenge.sequence_number,
            "attemptNumber": challenge.attempt_number,
            "windowStartMs": int(start_ms),
        },
    )
    db.commit()
    db.refresh(challenge)
    return _issue_response(
        challenge,
        total=semantic_challenge_required_count(settings, session),
    )


def complete_semantic_challenge(
    db: Session,
    current_user: User,
    challenge_id: uuid.UUID,
    payload: SemanticChallengeCompleteRequest,
) -> SemanticChallengeCompleteResponse:
    settings = get_settings()
    challenge = _for_update(db, challenge_id)
    session = owned_session(db, current_user, challenge.session_id)
    required = semantic_challenge_required_count(settings, session)

    if challenge.status == SemanticChallengeStatus.COMPLETED:
        if (
            hmac.compare_digest(challenge.nonce, payload.nonce)
            and challenge.client_complete_monotonic_ns == payload.client_monotonic_ns
        ):
            return _completion_response(db, challenge, required=required)
        raise SiteProofError(
            409,
            "SEMANTIC_CHALLENGE_ALREADY_COMPLETED",
            "Semantic challenge was already completed with different timing metadata.",
        )
    if challenge.status != SemanticChallengeStatus.STARTED:
        raise SiteProofError(
            409,
            "SEMANTIC_CHALLENGE_NOT_ACTIVE",
            "Semantic challenge must be started before it can be completed.",
        )
    if aware(challenge.expires_at) <= utc_now():
        _mark_expired(db, challenge, current_user)
        db.commit()
        raise SiteProofError(409, "SEMANTIC_CHALLENGE_EXPIRED", "Semantic challenge expired.")
    if not hmac.compare_digest(challenge.nonce, payload.nonce):
        raise SiteProofError(
            409,
            "SEMANTIC_CHALLENGE_NONCE_INVALID",
            "Semantic challenge nonce is invalid.",
        )

    start_ns = challenge.client_start_monotonic_ns
    anchor = session.capture_anchor_monotonic_ns
    if start_ns is None or anchor is None or payload.client_monotonic_ns <= start_ns:
        raise SiteProofError(
            422,
            "SEMANTIC_CHALLENGE_TIMING_INVALID",
            "Semantic challenge completion must occur after its capture-window start.",
        )
    duration_ms = (payload.client_monotonic_ns - start_ns) // 1_000_000
    minimum_ms, maximum_ms = _duration_bounds_ms(settings)
    if duration_ms < minimum_ms or duration_ms > maximum_ms:
        raise SiteProofError(
            422,
            "SEMANTIC_CHALLENGE_DURATION_INVALID",
            f"Semantic proof window must be between {minimum_ms} and {maximum_ms} milliseconds.",
        )
    end_ms = (payload.client_monotonic_ns - anchor) // 1_000_000
    if end_ms > int(getattr(settings, "vision_max_duration_seconds", 90)) * 1000:
        raise SiteProofError(
            422,
            "SEMANTIC_CHALLENGE_TIMING_INVALID",
            "Semantic challenge completion falls outside the bounded capture timeline.",
        )

    challenge.status = SemanticChallengeStatus.COMPLETED
    challenge.completed_at = utc_now()
    challenge.client_complete_monotonic_ns = payload.client_monotonic_ns
    challenge.window_end_ms = int(end_ms)
    db.flush()
    sequence_complete = semantic_sequence_complete(_rows(db, session.id), required)
    record_audit(
        db,
        organization_id=session.organization_id,
        actor_user_id=current_user.id,
        entity_type="SEMANTIC_CAPTURE_CHALLENGE",
        entity_id=challenge.id,
        action="SEMANTIC_CHALLENGE_COMPLETED",
        metadata={
            "sequenceNumber": challenge.sequence_number,
            "attemptNumber": challenge.attempt_number,
            "type": challenge.challenge_type.value,
            "windowStartMs": challenge.window_start_ms,
            "windowEndMs": challenge.window_end_ms,
            "sequenceComplete": sequence_complete,
        },
    )
    db.commit()
    db.refresh(challenge)
    return _completion_response(db, challenge, required=required)


def list_semantic_challenges(
    db: Session,
    current_user: User,
    session_id: uuid.UUID,
) -> SemanticChallengeListResponse:
    session = viewable_session(db, current_user, session_id)
    required = semantic_challenge_required_count(session=session)
    rows = _rows(db, session_id)
    return SemanticChallengeListResponse(
        session_id=session_id,
        total_required=required,
        sequence_complete=semantic_sequence_complete(rows, required),
        items=[
            SemanticChallengeTimelineItem(
                id=row.id,
                sequence_number=row.sequence_number,
                attempt_number=row.attempt_number,
                type=row.challenge_type,
                instruction=row.instruction,
                target=row.target_json,
                status=row.status,
                issued_at=row.issued_at,
                started_at=row.started_at,
                completed_at=row.completed_at,
                expires_at=row.expires_at,
                window_start_ms=row.window_start_ms,
                window_end_ms=row.window_end_ms,
            )
            for row in rows
        ],
    )
