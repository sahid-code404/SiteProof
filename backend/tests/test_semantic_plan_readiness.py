import app.services.semantic_challenges as semantic_module
import app.services.session_creation as creation_module
from app.core.config import Settings
from tests.phase3_helpers import create_ready_inspection, create_session, login, seed_identities


def test_semantic_plan_is_readable_before_capture(client, db, monkeypatch):
    settings = Settings(
        autonomous_verification_enabled=True,
        autonomous_semantic_challenges_enabled=True,
        autonomous_semantic_challenge_count=2,
    )
    monkeypatch.setattr(semantic_module, "get_settings", lambda: settings)
    monkeypatch.setattr(creation_module, "get_settings", lambda: settings)

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
    assert created.json()["semanticChallengeCount"] == 2

    session_id = created.json()["sessionId"]
    timeline = client.get(
        f"/api/v1/sessions/{session_id}/semantic-challenges",
        headers=inspector_headers,
    )

    assert timeline.status_code == 200, timeline.text
    body = timeline.json()
    assert body["sessionId"] == session_id
    assert body["totalRequired"] == 2
    assert body["sequenceComplete"] is False
    assert body["items"] == []
