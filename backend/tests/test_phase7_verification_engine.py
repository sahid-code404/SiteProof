from dataclasses import replace

import pytest
from sqlalchemy import select

from app.models.fusion import ConsistencyStatus, VisualInertialResult
from app.models.inspection import Inspection, InspectionStatus
from app.models.trust import (
    VerificationSignalStatus,
    VerificationSignalType,
    VerificationVerdict,
)
from app.services.fusion.service import analyze_session_fusion
from app.services.verification.domain import VerificationSignal
from app.services.verification.policy import default_policy_definition, validate_policy
from app.services.verification.scoring import calculate_score, resolve_decision
from app.services.verification.service import calculate_verification
from tests.test_phase6_fusion_service import _prepare_fusion_inputs


def _signal(
    signal_type: VerificationSignalType,
    *,
    score: float = 0.95,
    confidence: float = 0.90,
    status: VerificationSignalStatus = VerificationSignalStatus.PASS,
    required: bool = True,
    metrics: dict | None = None,
) -> VerificationSignal:
    return VerificationSignal(
        type=signal_type,
        status=status,
        score=score,
        confidence=confidence,
        available=True,
        required=required,
        reasons=[f"{signal_type.value} synthetic evidence."],
        metrics=metrics or {},
        source_algorithm_version="test-v1",
    )


def _all_good() -> list[VerificationSignal]:
    policy = default_policy_definition()
    return [
        _signal(signal_type, required=signal_type in policy.required_signals)
        for signal_type in VerificationSignalType
    ]


def test_default_policy_is_valid_and_totals_100():
    policy = default_policy_definition()
    validate_policy(policy)
    assert sum(policy.weights.values()) == pytest.approx(100.0)
    assert policy.version == "1.3"
    assert policy.verified_threshold == 90.0
    assert policy.review_threshold == 65.0
    assert policy.weights[VerificationSignalType.CHALLENGE_COMPLETION] == 45.0
    assert policy.weights[VerificationSignalType.LOCATION] == 20.0
    assert policy.weights[VerificationSignalType.VISUAL_MOTION] == 20.0
    assert policy.weights[VerificationSignalType.VISUAL_INERTIAL_CONSISTENCY] == 1.0
    assert policy.weights[VerificationSignalType.SENSOR_QUALITY] == 1.0
    assert policy.required_signals == frozenset(
        {
            VerificationSignalType.LOCATION,
            VerificationSignalType.CHALLENGE_COMPLETION,
            VerificationSignalType.VISUAL_MOTION,
        }
    )


def test_invalid_policy_threshold_order_is_rejected():
    policy = default_policy_definition()
    invalid = replace(policy, verified_threshold=60.0, review_threshold=65.0)
    with pytest.raises(ValueError, match="lower"):
        validate_policy(invalid)


def test_perfect_signals_are_verified():
    decision = resolve_decision(_all_good(), default_policy_definition())
    assert decision.score == pytest.approx(95.0)
    assert decision.confidence == pytest.approx(0.90)
    assert decision.verdict == VerificationVerdict.VERIFIED
    assert decision.hard_rules == []


def test_90_is_auto_verify_boundary():
    policy = default_policy_definition()
    below = [replace(signal, score=0.899) for signal in _all_good()]
    at_threshold = [replace(signal, score=0.90) for signal in _all_good()]

    below_decision = resolve_decision(below, policy)
    threshold_decision = resolve_decision(at_threshold, policy)

    assert below_decision.score == pytest.approx(89.9)
    assert below_decision.verdict == VerificationVerdict.REVIEW_REQUIRED
    assert threshold_decision.score == pytest.approx(90.0)
    assert threshold_decision.verdict == VerificationVerdict.VERIFIED


def test_low_confidence_blocks_auto_verified_without_changing_score():
    signals = [replace(signal, confidence=0.45) for signal in _all_good()]
    decision = resolve_decision(signals, default_policy_definition())
    assert decision.score == pytest.approx(95.0)
    assert decision.verdict == VerificationVerdict.REVIEW_REQUIRED
    assert any("confidence" in warning.lower() for warning in decision.warnings)


def test_missing_required_signal_is_inconclusive_not_zero_scored_fraud():
    policy = default_policy_definition()
    signals = [
        replace(signal, available=False, status=VerificationSignalStatus.UNAVAILABLE, score=0.0, confidence=0.0)
        if signal.type == VerificationSignalType.VISUAL_MOTION
        else signal
        for signal in _all_good()
    ]
    decision = resolve_decision(signals, policy)
    assert decision.verdict == VerificationVerdict.INCONCLUSIVE


def test_inconclusive_fusion_is_supporting_and_does_not_block_genuine_capture():
    signals = [
        replace(
            signal,
            status=VerificationSignalStatus.INCONCLUSIVE,
            score=0.83,
            confidence=0.75,
            metrics={
                "consistencyStatus": "INCONCLUSIVE",
                "mismatchReasons": [],
                "strongContradictionCount": 0,
            },
        )
        if signal.type == VerificationSignalType.VISUAL_INERTIAL_CONSISTENCY
        else signal
        for signal in _all_good()
    ]
    decision = resolve_decision(signals, default_policy_definition())
    assert decision.score > 90
    assert decision.confidence > 0.80
    assert decision.verdict == VerificationVerdict.VERIFIED
    assert decision.hard_rules == []


def test_genuine_three_pass_capture_below_90_routes_to_review():
    """A genuine but weaker handheld capture is reviewable rather than auto-approved."""
    replacements = {
        VerificationSignalType.CHALLENGE_COMPLETION: dict(
            score=0.813,
            confidence=0.581,
            status=VerificationSignalStatus.PASS,
            metrics={"passed": 3, "failed": 0, "inconclusive": 0},
        ),
        VerificationSignalType.LOCATION: dict(
            score=0.971,
            confidence=0.94,
            status=VerificationSignalStatus.PASS,
        ),
        VerificationSignalType.SCENE_CONTINUITY: dict(
            score=1.0,
            confidence=0.879,
            status=VerificationSignalStatus.PASS,
            metrics={"majorDiscontinuity": False},
        ),
        VerificationSignalType.SENSOR_QUALITY: dict(
            score=0.581,
            confidence=0.685,
            status=VerificationSignalStatus.PARTIAL,
        ),
        VerificationSignalType.SESSION_TIME: dict(
            score=1.0,
            confidence=0.90,
            status=VerificationSignalStatus.PASS,
        ),
        VerificationSignalType.VISUAL_INERTIAL_CONSISTENCY: dict(
            score=0.665,
            confidence=0.718,
            status=VerificationSignalStatus.INCONCLUSIVE,
            metrics={
                "consistencyStatus": "INCONCLUSIVE",
                "mismatchReasons": ["MAGNITUDE_MISMATCH", "TEMPORAL_MISMATCH"],
                "strongContradictionCount": 0,
            },
        ),
        VerificationSignalType.VISUAL_MOTION: dict(
            score=0.741,
            confidence=0.879,
            status=VerificationSignalStatus.PARTIAL,
        ),
    }
    signals = [
        replace(signal, **replacements.get(signal.type, {}))
        for signal in _all_good()
    ]
    decision = resolve_decision(signals, default_policy_definition())
    assert 85.0 <= decision.score < 90.0
    assert decision.confidence >= 0.70
    assert decision.verdict == VerificationVerdict.REVIEW_REQUIRED
    assert decision.hard_rules == []


def test_optional_unavailable_signal_renormalizes_available_weight():
    policy = default_policy_definition()
    signals = [
        replace(signal, available=False, status=VerificationSignalStatus.UNAVAILABLE, score=0.0, confidence=0.0)
        if signal.type == VerificationSignalType.SCENE_CONTINUITY
        else signal
        for signal in _all_good()
    ]
    score = calculate_score(signals, policy)
    assert score.available_weight == pytest.approx(90.0)
    assert score.raw_score == pytest.approx(95.0)


def test_high_confidence_fusion_physical_contradiction_forces_flagged():
    signals = [
        replace(
            signal,
            status=VerificationSignalStatus.FAIL,
            score=0.75,
            confidence=0.95,
            metrics={
                "consistencyStatus": "MISMATCH",
                "mismatchReasons": ["OPPOSITE_DIRECTION"],
                "strongContradictionCount": 1,
            },
        )
        if signal.type == VerificationSignalType.VISUAL_INERTIAL_CONSISTENCY
        else signal
        for signal in _all_good()
    ]
    decision = resolve_decision(signals, default_policy_definition())
    assert decision.score > 90
    assert decision.verdict == VerificationVerdict.FLAGGED
    assert "HIGH_CONFIDENCE_FUSION_MISMATCH" in {rule.code for rule in decision.hard_rules}


def test_same_direction_timing_magnitude_mismatch_does_not_force_flagged():
    signals = [
        replace(
            signal,
            status=VerificationSignalStatus.FAIL,
            score=0.75,
            confidence=0.95,
            metrics={
                "consistencyStatus": "MISMATCH",
                "mismatchReasons": ["TEMPORAL_MISMATCH", "DURATION_MISMATCH", "MAGNITUDE_MISMATCH"],
            },
        )
        if signal.type == VerificationSignalType.VISUAL_INERTIAL_CONSISTENCY
        else signal
        for signal in _all_good()
    ]
    decision = resolve_decision(signals, default_policy_definition())
    assert decision.score > 90
    assert decision.verdict == VerificationVerdict.VERIFIED
    assert "HIGH_CONFIDENCE_FUSION_MISMATCH" not in {rule.code for rule in decision.hard_rules}


def test_clear_wrong_location_forces_flagged():
    signals = [
        replace(signal, status=VerificationSignalStatus.FAIL, score=0.0, confidence=0.95, metrics={"clearlyOutside": True})
        if signal.type == VerificationSignalType.LOCATION
        else signal
        for signal in _all_good()
    ]
    decision = resolve_decision(signals, default_policy_definition())
    assert decision.verdict == VerificationVerdict.FLAGGED
    assert "CLEAR_WRONG_LOCATION" in {rule.code for rule in decision.hard_rules}


def test_major_scene_discontinuity_caps_verified_to_review():
    signals = [
        replace(signal, status=VerificationSignalStatus.FAIL, score=0.75, confidence=0.95, metrics={"majorDiscontinuity": True})
        if signal.type == VerificationSignalType.SCENE_CONTINUITY
        else signal
        for signal in _all_good()
    ]
    decision = resolve_decision(signals, default_policy_definition())
    assert decision.score >= 90
    assert decision.verdict == VerificationVerdict.REVIEW_REQUIRED
    assert "MAJOR_SCENE_DISCONTINUITY" in {rule.code for rule in decision.hard_rules}


def test_phase6_inputs_flow_into_persisted_verification_api_and_review(client, db, tmp_path):
    data = _prepare_fusion_inputs(client, db, tmp_path)
    session = data["session"]
    analyze_session_fusion(db, session.id, storage=data["storage"])

    result = calculate_verification(db, session.id, actor_user_id=data["identities"]["admin"].id)
    assert result.processing_status.value == "COMPLETED"
    assert result.final_score is not None
    assert result.overall_confidence is not None
    assert result.verdict in {VerificationVerdict.VERIFIED, VerificationVerdict.REVIEW_REQUIRED}

    reviewer = client.get(f"/api/v1/sessions/{session.id}/verification", headers=data["reviewer_headers"])
    assert reviewer.status_code == 200, reviewer.text
    body = reviewer.json()
    assert body["status"] == "COMPLETED"
    assert body["policy"]["version"] == "1.3"
    assert body["policy"]["engineVersion"] == "verification-engine-v1.1"
    assert len(body["signals"]) == 7

    inspector = client.get(f"/api/v1/sessions/{session.id}/verification", headers=data["inspector_headers"])
    assert inspector.status_code == 200, inspector.text
    assert inspector.json()["signals"] == []
    assert inspector.json()["hardRules"] == []

    denied = client.get(f"/api/v1/sessions/{session.id}/verification", headers=data["other_admin_headers"])
    assert denied.status_code == 404

    review = client.post(
        f"/api/v1/inspections/{session.inspection_id}/review",
        headers=data["reviewer_headers"],
        json={"sessionId": str(session.id), "decision": "APPROVED", "reason": "Evidence meets the inspection requirements."},
    )
    assert review.status_code == 200, review.text
    assert review.json()["decision"] == "APPROVED"
    inspection = db.get(Inspection, session.inspection_id)
    assert inspection is not None
    assert inspection.status == InspectionStatus.APPROVED


def test_persisted_high_confidence_fusion_physical_contradiction_is_flagged(client, db, tmp_path):
    data = _prepare_fusion_inputs(client, db, tmp_path)
    session = data["session"]
    analyze_session_fusion(db, session.id, storage=data["storage"])
    rows = list(db.scalars(select(VisualInertialResult).where(VisualInertialResult.session_id == session.id)).all())
    assert rows
    rows[0].consistency_status = ConsistencyStatus.MISMATCH
    rows[0].effective_consistency_score = 0.55
    rows[0].raw_consistency_score = 0.55
    rows[0].fusion_confidence = 0.95
    rows[0].mismatch_reasons_json = ["VISUAL_WITHOUT_SENSOR_MOTION"]
    db.commit()

    result = calculate_verification(db, session.id, actor_user_id=data["identities"]["admin"].id)
    assert result.verdict == VerificationVerdict.FLAGGED
    assert "HIGH_CONFIDENCE_FUSION_MISMATCH" in result.hard_rule_codes_json


def test_persisted_same_direction_quality_mismatch_is_not_hard_flagged(client, db, tmp_path):
    data = _prepare_fusion_inputs(client, db, tmp_path)
    session = data["session"]
    analyze_session_fusion(db, session.id, storage=data["storage"])
    rows = list(db.scalars(select(VisualInertialResult).where(VisualInertialResult.session_id == session.id)).all())
    assert rows
    rows[0].consistency_status = ConsistencyStatus.MISMATCH
    rows[0].effective_consistency_score = 0.55
    rows[0].raw_consistency_score = 0.55
    rows[0].fusion_confidence = 0.95
    rows[0].mismatch_reasons_json = ["TEMPORAL_MISMATCH", "DURATION_MISMATCH"]
    db.commit()

    result = calculate_verification(db, session.id, actor_user_id=data["identities"]["admin"].id)
    assert "HIGH_CONFIDENCE_FUSION_MISMATCH" not in result.hard_rule_codes_json
    assert result.verdict in {VerificationVerdict.VERIFIED, VerificationVerdict.REVIEW_REQUIRED}
