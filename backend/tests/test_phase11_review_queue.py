from app.services.fusion.service import analyze_session_fusion
from app.services.verification.service import calculate_verification
from tests.test_phase6_fusion_service import _prepare_fusion_inputs


def test_reviewer_queue_uses_current_result_and_tracks_separate_human_review(client, db, tmp_path):
    data = _prepare_fusion_inputs(client, db, tmp_path)
    session = data["session"]
    analyze_session_fusion(db, session.id, storage=data["storage"])
    result = calculate_verification(
        db,
        session.id,
        actor_user_id=data["identities"]["admin"].id,
    )

    response = client.get("/api/v1/review-queue", headers=data["reviewer_headers"])
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["inspectionId"] == str(session.inspection_id)
    assert item["sessionId"] == str(session.id)
    assert item["resultId"] == str(result.id)
    assert item["verdict"] == result.verdict.value
    assert item["engineVersion"] == result.engine_version
    assert isinstance(item["latitude"], float)
    assert isinstance(item["longitude"], float)
    assert item["latestReview"] is None

    verdict_filter = client.get(
        f"/api/v1/review-queue?verdict={result.verdict.value}",
        headers=data["reviewer_headers"],
    )
    assert verdict_filter.status_code == 200, verdict_filter.text
    assert verdict_filter.json()["total"] == 1

    pending = client.get(
        "/api/v1/review-queue?reviewed=false",
        headers=data["reviewer_headers"],
    )
    assert pending.status_code == 200
    assert pending.json()["total"] == 1

    review = client.post(
        f"/api/v1/inspections/{session.inspection_id}/review",
        headers=data["reviewer_headers"],
        json={
            "sessionId": str(session.id),
            "decision": "APPROVED",
            "reason": "Evidence meets the inspection requirements.",
        },
    )
    assert review.status_code == 200, review.text

    reviewed = client.get(
        "/api/v1/review-queue?reviewed=true",
        headers=data["reviewer_headers"],
    )
    assert reviewed.status_code == 200, reviewed.text
    reviewed_body = reviewed.json()
    assert reviewed_body["total"] == 1
    assert reviewed_body["items"][0]["latestReview"]["decision"] == "APPROVED"
    assert reviewed_body["items"][0]["verdict"] == result.verdict.value

    no_longer_pending = client.get(
        "/api/v1/review-queue?reviewed=false",
        headers=data["reviewer_headers"],
    )
    assert no_longer_pending.status_code == 200
    assert no_longer_pending.json()["total"] == 0

    inspector = client.get("/api/v1/review-queue", headers=data["inspector_headers"])
    assert inspector.status_code == 403

    other_org = client.get("/api/v1/review-queue", headers=data["other_admin_headers"])
    assert other_org.status_code == 200
    assert other_org.json()["total"] == 0
