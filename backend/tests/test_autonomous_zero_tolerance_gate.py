from types import SimpleNamespace

import app.services.verification.autonomous_gate as gate_module
from app.models.autonomous_verification import AutonomousAnalysisStatus
from app.services.verification.autonomous_gate import (
    evaluate_autonomous_gate,
    frame_hash_diversity,
    semantic_consensus_ready,
)


def _settings():
    return SimpleNamespace(
        autonomous_verification_enabled=True,
        autonomous_hard_flag_confidence=0.90,
        autonomous_frame_count=12,
        autonomous_task_mismatch_threshold=0.25,
        autonomous_review_task_threshold=0.70,
        autonomous_asset_mismatch_threshold=0.25,
        autonomous_min_coverage=0.85,
        autonomous_presentation_attack_flag_threshold=0.90,
        autonomous_live_scene_review_threshold=0.65,
    )


def _strong_result(*, primary="vlm-a", secondary="vlm-b", hashes=None):
    return SimpleNamespace(
        status=AutonomousAnalysisStatus.COMPLETE,
        contract_confidence=0.95,
        primary_vlm_model=primary,
        secondary_vlm_model=secondary,
        sampled_frame_count=12,
        frame_hashes_json=hashes or [f"hash-{index}" for index in range(12)],
        task_match_score=0.96,
        task_match_confidence=0.95,
        contract_json={"assetIdentity": {"required": False}},
        asset_identity_score=0.95,
        asset_identity_confidence=0.95,
        evidence_coverage_score=0.95,
        evidence_coverage_confidence=0.95,
        mandatory_failures_json=[],
        presentation_attack_score=0.02,
        presentation_attack_confidence=0.95,
        live_scene_score=0.97,
        live_scene_confidence=0.95,
        model_disagreement=False,
    )


def _codes(monkeypatch, result):
    monkeypatch.setattr(gate_module, "get_settings", _settings)
    monkeypatch.setattr(gate_module, "get_autonomous_result", lambda db, session_id: result)
    return {item.code for item in evaluate_autonomous_gate(None, None)}


def test_semantic_consensus_requires_two_distinct_models():
    assert semantic_consensus_ready(None, None) is False
    assert semantic_consensus_ready("vlm-a", None) is False
    assert semantic_consensus_ready("vlm-a", "vlm-a") is False
    assert semantic_consensus_ready("vlm-a", "vlm-b") is True


def test_single_model_can_never_auto_approve(monkeypatch):
    codes = _codes(monkeypatch, _strong_result(secondary=None))
    assert "AUTONOMOUS_TWO_MODEL_CONSENSUS_REQUIRED" in codes


def test_same_model_twice_is_not_treated_as_consensus(monkeypatch):
    codes = _codes(monkeypatch, _strong_result(primary="same-model", secondary="same-model"))
    assert "AUTONOMOUS_TWO_MODEL_CONSENSUS_REQUIRED" in codes


def test_distinct_models_with_strong_evidence_do_not_trigger_consensus_rule(monkeypatch):
    codes = _codes(monkeypatch, _strong_result())
    assert "AUTONOMOUS_TWO_MODEL_CONSENSUS_REQUIRED" not in codes


def test_frame_hash_diversity_blocks_exactly_repeated_evidence(monkeypatch):
    hashes = ["same"] * 9 + ["different-a", "different-b", "different-c"]
    assert frame_hash_diversity(hashes) == 4 / 12
    codes = _codes(monkeypatch, _strong_result(hashes=hashes))
    assert "AUTONOMOUS_FRAME_DIVERSITY_INSUFFICIENT" in codes


def test_temporal_sampling_floor_blocks_too_few_video_moments(monkeypatch):
    result = _strong_result()
    result.sampled_frame_count = 4
    result.frame_hashes_json = ["a", "b", "c", "d"]
    codes = _codes(monkeypatch, result)
    assert "AUTONOMOUS_TEMPORAL_COVERAGE_INSUFFICIENT" in codes
