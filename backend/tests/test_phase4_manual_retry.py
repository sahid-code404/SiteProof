from tests.phase3_helpers import create_ready_inspection, create_session, login, seed_identities, start_capture
from tests.phase4_helpers import perform_current_challenge


def _started_session(client, db):
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
    return inspector_headers, session_id


def test_failed_challenge_can_receive_one_fresh_retry(client, db):
    headers, session_id = _started_session(client, db)
    first, _, submitted = perform_current_challenge(
        client,
        headers,
        session_id,
        start_relative_ns=500_000_000,
        wrong_direction=True,
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["result"] == "FAIL"
    assert submitted.json()["retryAllowed"] is True

    replacement = client.post(
        f"/api/v1/sessions/{session_id}/challenges/next",
        headers=headers,
    )
    assert replacement.status_code == 200, replacement.text
    body = replacement.json()
    assert body["sequenceNumber"] == first["sequenceNumber"]
    assert body["attemptNumber"] == first["attemptNumber"] + 1
    assert body["challengeId"] != first["challengeId"]
    assert body["nonce"] != first["nonce"]
