import uuid

import pytest
from sqlalchemy import func, select

from app.models.fusion import ConsistencyStatus, VisualInertialResult
from app.models.trust import (
    ReviewDecision,
    VerificationPolicy,
    VerificationProcessingStatus,
    VerificationResult,
    VerificationSignalResult,
    VerificationSignalStatus,
    VerificationSignalType,
    VerificationVerdict,
)
from app.models.visual_motion import VisualAnalysisStatus, VisualMotionResult, VisualQuality
from app.services.fusion.service import analyze_session_fusion
from app.services.verification.domain import VerificationSignal
from app.services.verification.engine import VerificationEngine
from app.services.verification.hard_rules import evaluate_hard_rules
from app.services.verification.policy import (
    DEFAULT_HARD_RULES,
    DEFAULT_REQUIRED_SIGNALS,
    DEFAULT_WEIGHTS,
    ENGINE_VERSION,
    ResolvedPolicy,
    validate_policy_values,
)
from app.services.verification.scoring import calculate_score, threshold_verdict
from tests.test_phase6_fusion_service import _prepare_fusion_inputs


def _policy() -> ResolvedPolicy:
    return ResolvedPolicy(
        id=uuid.uuid4(),
        name="Test policy",
        version="test-1",
        verified_threshold=85.0,
        review_threshold=65.0,
        minimum_required_confidence=0.70,
        weights=dict(DEFAULT_WEIGHTS),
        required_signals=frozenset(DEFAULT_REQUIRED_SIGNALS),
        hard_rules=dict(DEFAULT_HARD_RULES),
    )


def _complete_fusion(client, db, tmp_path):
    data = _prepare_fusion_inputs(client, db, tmp_path)
    analyze_session_fusion(db, data["session"].id, storage=data["storage"])
    return data


def test_default_policy_validates_and_score_boundaries_are_stable():
    validate_policy_values(
        verified_threshold=85.0,
        review_threshold=65.0,
        minimum_required_confidence=0.70,
        weights=dict(DEFAULT_WEIGHTS),
        required_signals=list(DEFAULT_REQUIRED_SIGNALS),
        hard_rules=dict(DEFAULT_HARD_RULES),
    )
    assert sum(DEFAULT_WEIGHTS.values()) == 100.0
    policy = _policy()
    assert threshold_verdict(84.99, policy) == VerificationVerdict.REVIEW_REQUIRED
    assert threshold_verdict(85.00, policy) == VerificationVerdict.VERIFIED
    assert threshold_verdict(64.99, policy) == VerificationVerdict.FLAGGED
    assert threshold_verdict(65.00, policy) == VerificationVerdict.REVIEW_REQUIRED

    with pytest.raises(ValueError, match="total 100"):
        validate_policy_values(
            verified_threshold=85.0,
            review_threshold=65.0,
            minimum_required_confidence=0.70,
            weights={**DEFAULT_WEIGHTS, VerificationSignalType.LOCATION.value: 14.0},
            required_signals=list(DEFAULT_REQUIRED_SIGNALS),
            hard_rules=dict(DEFAULT_HARD_RULES),
        )


def test_confidence_is_separate_from_score_and_gates_auto_verified():
    policy = _policy()
    signals = [
        VerificationSignal(
            type=signal_type,
            status=VerificationSignalStatus.PASS,
            score=0.95,
            confidence=0.40,
            available=True,
            required=signal_type.value in policy.required_signals,
            reasons=["Synthetic strong score with deliberately weak confidence."],
        )
        for signal_type in VerificationSignalType
    ]
    score = calculate_score(signals, policy)
    assert score.final_score == pytest.approx(95.0)
    assert score.overall_confidence == pytest.approx(0.40)
    assert threshold_verdict(score.final_score, policy) == VerificationVerdict.VERIFIED
    assert score.overall_confidence < policy.minimum_required_confidence


def test_perfect_upstream_evidence_produces_explainable_idempotent_verification(
    client, db, tmp_path
):
    data = _complete_fusion(client, db, tmp_path)
    engine = VerificationEngine()
    first = engine.calculate(db, data["session"].id)

    assert first.processing_status == VerificationProcessingStatus.COMPLETED
    assert first.verdict == VerificationVerdict.VERIFIED
    assert first.final_score is not None and first.final_score >= 85.0
    assert first.raw_score == first.final_score
    assert first.overall_confidence is not None and first.overall_confidence >= 0.70
    assert first.engine_version == ENGINE_VERSION
    assert first.policy_version == "1.0"
    assert first.summary
    assert first.summary_reasons_json
    assert any("legal certainty" in item for item in first.warnings_json)

    signals = list(
        db.scalars(
            select(VerificationSignalResult).where(
                VerificationSignalResult.verification_result_id == first.id
            )
        ).all()
    )
    assert len(signals) == 7
    assert sum(item.effective_weight for item in signals) == pytest.approx(100.0)
    assert all(0.0 <= item.score <= 1.0 for item in signals)
    assert all(0.0 <= item.confidence <= 1.0 for item in signals)

    second = engine.calculate(db, data["session"].id)
    assert second.id == first.id
    assert db.scalar(select(func.count()).select_from(VerificationResult)) == 1


def test_high_confidence_fusion_mismatch_blocks_verified_without_rewriting_score(
    client, db, tmp_path
):
    data = _complete_fusion(client, db, tmp_path)
    row = db.scalar(
        select(VisualInertialResult)
        .where(VisualInertialResult.session_id == data["session"].id)
        .order_by(VisualInertialResult.created_at)
    )
    assert row is not None
    row.consistency_status = ConsistencyStatus.MISMATCH
    row.effective_consistency_score = 0.95
    row.raw_consistency_score = 0.95
    row.fusion_confidence = 0.95
    row.mismatch_reasons_json = ["VISUAL_WITHOUT_SENSOR_MOTION"]
    db.commit()

    result = VerificationEngine().calculate(db, data["session"].id)
    assert result.verdict == VerificationVerdict.FLAGGED
    assert result.raw_score == result.final_score
    assert "HIGH_CONFIDENCE_FUSION_MISMATCH" in result.hard_rule_codes_json
    assert result.hard_rule_triggered is True


def test_wrong_location_hard_rule_and_poor_gps_inconclusive(client, db, tmp_path):
    data = _complete_fusion(client, db, tmp_path)
    session = data["session"]
    session.pre_capture_location = {
        **(session.pre_capture_location or {}),
        "distanceMeters": 800.0,
        "allowedRadiusMeters": 100,
        "accuracy_meters": 6.0,
    }
    db.commit()
    flagged = VerificationEngine().calculate(db, session.id)
    assert flagged.verdict == VerificationVerdict.FLAGGED
    assert "HIGH_CONFIDENCE_WRONG_LOCATION" in flagged.hard_rule_codes_json

    session.pre_capture_location = {
        **(session.pre_capture_location or {}),
        "distanceMeters": 80.0,
        "allowedRadiusMeters": 100,
        "accuracy_meters": 900.0,
    }
    db.commit()
    inconclusive = VerificationEngine().calculate(db, session.id, force=True)
    assert inconclusive.verdict == VerificationVerdict.INCONCLUSIVE
    location = db.scalar(
        select(VerificationSignalResult).where(
            VerificationSignalResult.verification_result_id == inconclusive.id,
            VerificationSignalResult.signal_type == VerificationSignalType.LOCATION,
        )
    )
    assert location is not None
    assert location.status == VerificationSignalStatus.INCONCLUSIVE


def test_required_visual_failure_cannot_produce_verified(client, db, tmp_path):
    data = _complete_fusion(client, db, tmp_path)
    rows = list(
        db.scalars(
            select(VisualMotionResult).where(
                VisualMotionResult.session_id == data["session"].id
            )
        ).all()
    )
    assert rows
    for row in rows:
        row.analysis_status = VisualAnalysisStatus.FAILED
        row.visual_quality = VisualQuality.POOR
        row.visual_confidence = 0.0
    db.commit()

    result = VerificationEngine().calculate(db, data["session"].id)
    assert result.verdict == VerificationVerdict.INCONCLUSIVE


def test_recalculation_preserves_history_and_policy_version(client, db, tmp_path):
    data = _complete_fusion(client, db, tmp_path)
    engine = VerificationEngine()
    first = engine.calculate(db, data["session"].id)
    second = engine.calculate(db, data["session"].id, force=True)
    assert first.id != second.id
    assert first.calculation_revision == 1
    assert second.calculation_revision == 2

    v2 = VerificationPolicy(
        organization_id=data["session"].organization_id,
        name="Infrastructure Field Verification",
        version="2.0-test",
        active=True,
        verified_threshold=90.0,
        review_threshold=70.0,
        minimum_required_confidence=0.75,
        weights_json=dict(DEFAULT_WEIGHTS),
        required_signals_json=list(DEFAULT_REQUIRED_SIGNALS),
        hard_rules_json=dict(DEFAULT_HARD_RULES),
    )
    db.add(v2)
    db.commit()
    third = engine.calculate(
        db,
        data["session"].id,
        policy_version="2.0-test",
    )
    assert third.policy_version == "2.0-test"
    assert first.policy_version == "1.0"
    assert db.scalar(select(func.count()).select_from(VerificationResult)) == 3


def test_verification_api_masks_inspector_diagnostics_and_review_is_separate(
    client, db, tmp_path
):
    data = _complete_fusion(client, db, tmp_path)
    result = VerificationEngine().calculate(db, data["session"].id)

    reviewer = client.get(
        f"/api/v1/sessions/{data['session'].id}/verification",
        headers=data["reviewer_headers"],
    )
    assert reviewer.status_code == 200, reviewer.text
    reviewer_body = reviewer.json()
    assert reviewer_body["detailed"] is True
    assert reviewer_body["score"] is not None
    assert len(reviewer_body["signals"]) == 7
    assert reviewer_body["engineVersion"] == ENGINE_VERSION

    inspector = client.get(
        f"/api/v1/sessions/{data['session'].id}/verification",
        headers=data["inspector_headers"],
    )
    assert inspector.status_code == 200, inspector.text
    inspector_body = inspector.json()
    assert inspector_body["detailed"] is False
    assert inspector_body["score"] is None
    assert inspector_body["signals"] == []
    assert inspector_body["hardRules"] == []

    other_org = client.get(
        f"/api/v1/sessions/{data['session'].id}/verification",
        headers=data["other_admin_headers"],
    )
    assert other_org.status_code == 404

    review = client.post(
        f"/api/v1/inspections/{data['session'].inspection_id}/review",
        headers=data["reviewer_headers"],
        json={
            "sessionId": str(data["session"].id),
            "decision": "APPROVED",
            "reason": "Automated evidence and inspection context are acceptable.",
        },
    )
    assert review.status_code == 201, review.text
    assert review.json()["verificationResultId"] == str(result.id)
    assert review.json()["decision"] == "APPROVED"
    assert db.scalar(select(func.count()).select_from(ReviewDecision)) == 1

    invalid_reason = client.post(
        f"/api/v1/inspections/{data['session'].inspection_id}/review",
        headers=data["reviewer_headers"],
        json={
            "sessionId": str(data["session"].id),
            "decision": "REJECTED",
            "reason": "x",
        },
    )
    assert invalid_reason.status_code == 422


def test_hard_rule_evaluator_detects_multiple_challenge_failures():
    policy = _policy()
    signals = [
        VerificationSignal(
            type=VerificationSignalType.CHALLENGE_COMPLETION,
            status=VerificationSignalStatus.FAIL,
            score=0.2,
            confidence=0.95,
            available=True,
            required=True,
            reasons=["Two challenges failed."],
            metrics={"highConfidenceFailures": 2},
        )
    ]
    findings = evaluate_hard_rules(signals, policy)
    assert [item.code for item in findings] == [
        "MULTIPLE_HIGH_CONFIDENCE_CHALLENGE_FAILURES"
    ]
