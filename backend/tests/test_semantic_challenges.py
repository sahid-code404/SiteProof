import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import app.services.semantic_challenges as semantic_module
import app.services.session_capture as capture_module
import app.services.session_creation as creation_module
from app.core.config import Settings
from app.models.semantic_challenge import SemanticCaptureChallenge, SemanticChallengeStatus
from app.models.verification import VerificationSession
from tests.phase3_helpers import (
    create_ready_inspection,
    create_session,
    login,
    seed_identities,
    start_capture,
)
from tests.phase4_helpers import CAPTURE_ANCHOR_NS, complete_required_challenges

SEMANTIC_START_RELATIVE_NS = 7_600_000_000
SEMANTIC_WINDOW_NS = 2_000_000_000


def _enabled_settings() -> Settings:
    return Settings(
        autonomous_verification_enabled=True,
        autonomous_semantic_challenges_enabled=True,
        autonomous_semantic_challenge_count=1,
        autonomous_semantic_challenge_timeout_seconds=25,
        autonomous_semantic_challenge_min_duration_ms=1500,
        autonomous_semantic_challenge_max_duration_ms=12000,
        autonomous_semantic_challenge_max_retries=2,
    )


def _enable_semantic_protocol(monkeypatch) -> Settings:
    settings = _enabled_settings()
    monkeypatch.setattr(semantic_module, "get_settings", lambda: settings)
    monkeypatch.setattr(capture_module, "get_settings", lambda: settings)
    monkeypatch.setattr(creation_module, "get_settings", lambda: settings)
    return settings


def _physical_sequence_complete(client, db):
    identities = seed_identities(db)
    admin_headers = login(client, identities["admin"])
    inspector_headers = login(client, identities["inspector"])
    inspection_id = create_ready_inspection(
        client,
        admin_headers,
        inspector_headers,
        identities["profile"].id,
    )
    session_id = create_session(client, inspector_headers, inspection_id).json()["sessionId"]
    started = start_capture(client, inspector_headers, session_id)
    assert started.status_code == 200, started.text
    complete_required_challenges(client, inspector_headers, session_id)
    return identities, admin_headers, inspector_headers, inspection_id, session_id


def _capture_complete_payload(capture_duration_ms: int = 10_000) -> dict:
    return {
        "captureDurationMs": capture_duration_ms,
        "videoFileCount": 1,
        "sensorSummary": {
            "accelerometerSamples": 3,
            "gyroscopeSamples": 2,
            "rotationVectorSamples": 2,
            "magnetometerSamples": 0,
        },
        "locationSummary": {
            "locationSamples": 2,
            "bestAccuracyMeters": 7.5,
            "firstRelativeTimestampNs": 1_000_000_000,
            "lastRelativeTimestampNs": 2_000_000_000,
        },
    }


def _issue(client, headers, session_id: str):
    return client.post(
        f"/api/v1/sessions/{session_id}/semantic-challenges/next",
        headers=headers,
    )


def _start(client, headers, challenge: dict, *, relative_ns: int = SEMANTIC_START_RELATIVE_NS):
    return client.post(
        f"/api/v1/semantic-challenges/{challenge['challengeId']}/start",
        headers=headers,
        json={
            "nonce": challenge["nonce"],
            "clientMonotonicNs": CAPTURE_ANCHOR_NS + relative_ns,
        },
    )


def _complete(
    client,
    headers,
    challenge: dict,
    *,
    relative_ns: int = SEMANTIC_START_RELATIVE_NS + SEMANTIC_WINDOW_NS,
):
    return client.post(
        f"/api/v1/semantic-challenges/{challenge['challengeId']}/complete",
        headers=headers,
        json={
            "nonce": challenge["nonce"],
            "clientMonotonicNs": CAPTURE_ANCHOR_NS + relative_ns,
        },
    )


def test_semantic_challenges_are_disabled_by_default(client, db):
    _, _, inspector_headers, _, session_id = _physical_sequence_complete(client, db)
    response = _issue(client, inspector_headers, session_id)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SEMANTIC_CHALLENGES_DISABLED"


def test_session_freezes_semantic_challenge_count(client, db, monkeypatch):
    settings = _enable_semantic_protocol(monkeypatch)
    identities = seed_identities(db)
    admin_headers = login(client, identities["admin"])
    inspector_headers = login(client, identities["inspector"])
    inspection_id = create_ready_inspection(
        client,
        admin_headers,
        inspector_headers,
        identities["profile"].id,
    )

    created = create_session(client, inspector_headers, inspection_id)
    assert created.status_code == 201, created.text
    assert created.json()["semanticChallengeCount"] == 1
    session_id = created.json()["sessionId"]
    row = db.get(VerificationSession, uuid.UUID(session_id))
    assert row is not None
    assert row.site_snapshot["semanticChallengeCount"] == 1

    # Turning the feature flag off after session creation must not weaken this session's frozen
    # proof contract. Existing sessions continue to require their originally assigned challenge.
    settings.autonomous_verification_enabled = False
    assert semantic_module.semantic_challenges_enabled(settings, row) is True
    assert semantic_module.semantic_challenge_required_count(settings, row) == 1


def test_next_is_idempotent_and_does_not_preload_future_semantic_challenges(client, db, monkeypatch):
    _enable_semantic_protocol(monkeypatch)
    _, _, headers, _, session_id = _physical_sequence_complete(client, db)

    first = _issue(client, headers, session_id)
    repeated = _issue(client, headers, session_id)

    assert first.status_code == repeated.status_code == 200
    assert repeated.json()["challengeId"] == first.json()["challengeId"]
    assert repeated.json()["nonce"] == first.json()["nonce"]
    assert first.json()["sequenceNumber"] == 1
    assert first.json()["attemptNumber"] == 1
    assert first.json()["totalChallenges"] == 1
    rows = db.query(SemanticCaptureChallenge).all()
    assert len(rows) == 1
    assert "repaired road" in first.json()["instruction"].lower()


def test_semantic_nonce_owner_and_monotonic_anchor_are_enforced(client, db, monkeypatch):
    _enable_semantic_protocol(monkeypatch)
    identities, _, headers, _, session_id = _physical_sequence_complete(client, db)
    other_headers = login(client, identities["inspector2"])
    challenge = _issue(client, headers, session_id).json()

    wrong_owner = _start(client, other_headers, challenge)
    assert wrong_owner.status_code in {403, 404}

    wrong_nonce = client.post(
        f"/api/v1/semantic-challenges/{challenge['challengeId']}/start",
        headers=headers,
        json={
            "nonce": "wrong-semantic-nonce-value-long-enough",
            "clientMonotonicNs": CAPTURE_ANCHOR_NS + SEMANTIC_START_RELATIVE_NS,
        },
    )
    assert wrong_nonce.status_code == 409
    assert wrong_nonce.json()["error"]["code"] == "SEMANTIC_CHALLENGE_NONCE_INVALID"

    before_capture_anchor = client.post(
        f"/api/v1/semantic-challenges/{challenge['challengeId']}/start",
        headers=headers,
        json={
            "nonce": challenge["nonce"],
            "clientMonotonicNs": CAPTURE_ANCHOR_NS - 1,
        },
    )
    assert before_capture_anchor.status_code == 422
    assert before_capture_anchor.json()["error"]["code"] == "SEMANTIC_CHALLENGE_TIMING_INVALID"


def test_semantic_window_duration_is_server_bounded_and_completion_is_idempotent(client, db, monkeypatch):
    _enable_semantic_protocol(monkeypatch)
    _, _, headers, _, session_id = _physical_sequence_complete(client, db)
    challenge = _issue(client, headers, session_id).json()

    started = _start(client, headers, challenge)
    assert started.status_code == 200, started.text

    too_short = _complete(
        client,
        headers,
        challenge,
        relative_ns=SEMANTIC_START_RELATIVE_NS + 500_000_000,
    )
    assert too_short.status_code == 422
    assert too_short.json()["error"]["code"] == "SEMANTIC_CHALLENGE_DURATION_INVALID"

    completed = _complete(client, headers, challenge)
    assert completed.status_code == 200, completed.text
    body = completed.json()
    assert body["status"] == "COMPLETED"
    assert body["sequenceComplete"] is True
    assert body["windowStartMs"] == SEMANTIC_START_RELATIVE_NS // 1_000_000
    assert body["windowEndMs"] == (SEMANTIC_START_RELATIVE_NS + SEMANTIC_WINDOW_NS) // 1_000_000

    duplicate = _complete(client, headers, challenge)
    assert duplicate.status_code == 200
    assert duplicate.json()["windowEndMs"] == body["windowEndMs"]

    changed = _complete(
        client,
        headers,
        challenge,
        relative_ns=SEMANTIC_START_RELATIVE_NS + SEMANTIC_WINDOW_NS + 1_000_000,
    )
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "SEMANTIC_CHALLENGE_ALREADY_COMPLETED"


def test_expired_semantic_challenge_retries_without_preloading(client, db, monkeypatch):
    _enable_semantic_protocol(monkeypatch)
    _, _, headers, _, session_id = _physical_sequence_complete(client, db)
    first = _issue(client, headers, session_id)
    assert first.status_code == 200
    first_body = first.json()

    row = db.query(SemanticCaptureChallenge).filter_by(id=uuid.UUID(first_body["challengeId"])).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    replacement = _issue(client, headers, session_id)
    assert replacement.status_code == 200, replacement.text
    replacement_body = replacement.json()
    assert replacement_body["challengeId"] != first_body["challengeId"]
    assert replacement_body["sequenceNumber"] == 1
    assert replacement_body["attemptNumber"] == 2

    db.expire_all()
    rows = (
        db.query(SemanticCaptureChallenge)
        .filter_by(session_id=uuid.UUID(session_id))
        .order_by(SemanticCaptureChallenge.attempt_number)
        .all()
    )
    assert len(rows) == 2
    assert rows[0].status == SemanticChallengeStatus.EXPIRED
    assert rows[1].status == SemanticChallengeStatus.ISSUED


def test_capture_completion_fails_closed_until_semantic_sequence_finishes(client, db, monkeypatch):
    _enable_semantic_protocol(monkeypatch)
    _, _, headers, _, session_id = _physical_sequence_complete(client, db)

    blocked = client.post(
        f"/api/v1/sessions/{session_id}/capture-complete",
        headers=headers,
        json=_capture_complete_payload(),
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["code"] == "SEMANTIC_CHALLENGES_REQUIRED"

    challenge = _issue(client, headers, session_id).json()
    assert _start(client, headers, challenge).status_code == 200
    assert _complete(client, headers, challenge).status_code == 200

    completed = client.post(
        f"/api/v1/sessions/{session_id}/capture-complete",
        headers=headers,
        json=_capture_complete_payload(),
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "CAPTURE_COMPLETED"


def test_semantic_sequence_helper_requires_latest_attempt_to_complete():
    settings = SimpleNamespace(
        autonomous_verification_enabled=True,
        autonomous_semantic_challenges_enabled=True,
        autonomous_semantic_challenge_count=2,
    )
    assert semantic_module.semantic_challenges_enabled(settings) is True
    assert semantic_module.semantic_challenge_required_count(settings) == 2

    rows = [
        SimpleNamespace(sequence_number=1, attempt_number=1, status=SemanticChallengeStatus.COMPLETED),
        SimpleNamespace(sequence_number=2, attempt_number=1, status=SemanticChallengeStatus.EXPIRED),
        SimpleNamespace(sequence_number=2, attempt_number=2, status=SemanticChallengeStatus.COMPLETED),
    ]
    assert semantic_module.semantic_sequence_complete(rows, 2) is True

    rows.append(
        SimpleNamespace(sequence_number=2, attempt_number=3, status=SemanticChallengeStatus.EXPIRED)
    )
    assert semantic_module.semantic_sequence_complete(rows, 2) is False
