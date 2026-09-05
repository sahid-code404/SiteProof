from datetime import datetime, timezone
from types import SimpleNamespace

import app.services.verification.autonomous_gate as gate_module
from app.models.autonomous_verification import AutonomousAnalysisStatus
from app.services.verification.autonomous_gate import (
    autonomous_audit_binding_issues,
    evaluate_autonomous_gate,
    frame_hash_diversity,
    frame_quality_issues,
    frame_quality_usable_ratio,
    independent_provider_ready,
    semantic_consensus_ready,
)


def _settings():
    return SimpleNamespace(
        autonomous_verification_enabled=True,
        autonomous_ai_base_url="https://primary.example/v1",
        autonomous_secondary_ai_base_url="https://secondary.example/v1",
        autonomous_contract_model="contract-model",
        autonomous_vlm_model="vlm-a",
        autonomous_secondary_vlm_model="vlm-b",
        autonomous_require_independent_provider=True,
        autonomous_hard_flag_confidence=0.90,
        autonomous_frame_count=12,
        autonomous_min_usable_frame_ratio=0.75,
        autonomous_task_mismatch_threshold=0.25,
        autonomous_review_task_threshold=0.70,
        autonomous_asset_mismatch_threshold=0.25,
        autonomous_min_coverage=0.85,
        autonomous_presentation_attack_flag_threshold=0.90,
        autonomous_live_scene_review_threshold=0.65,
    )


def _valid_hashes(count=12):
    return [f"{index + 1:064x}" for index in range(count)]


def _strong_result(*, primary="vlm-a", secondary="vlm-b", hashes=None):
    return SimpleNamespace(
        status=AutonomousAnalysisStatus.COMPLETE,
        analysis_version="autonomous-v2-test",
        contract_version="contract-v1",
        contract_prompt_version="contract-prompt-v1",
        vision_prompt_version="vision-prompt-v1",
        compiler_model="contract-model",
        contract_source_hash="d" * 64,
        contract_confidence=0.95,
        primary_vlm_model=primary,
        secondary_vlm_model=secondary,
        sampled_frame_count=12,
        frame_hashes_json=hashes or _valid_hashes(),
        raw_response_hashes_json={
            "contract": "a" * 64,
            "primaryVlm": "b" * 64,
            "secondaryVlm": "c" * 64,
        },
        task_match_score=0.96,
        task_match_confidence=0.95,
        contract_json={"assetIdentity": {"required": False}},
        observations_json={
            "frameQuality": {
                "total": 12,
                "sharpCount": 12,
                "exposureAcceptableCount": 12,
                "usableCount": 12,
                "sharpRatio": 1.0,
                "exposureAcceptableRatio": 1.0,
                "usableRatio": 1.0,
            },
            "primary": {"taskMatch": {"score": 0.96}},
        },
        analyzed_at=datetime(2026, 9, 5, 8, 0, tzinfo=timezone.utc),
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


def _codes(monkeypatch, result, settings=None):
    active_settings = settings or _settings()
    monkeypatch.setattr(gate_module, "get_settings", lambda: active_settings)
    monkeypatch.setattr(gate_module, "get_autonomous_result", lambda db, session_id: result)
    return {item.code for item in evaluate_autonomous_gate(None, None)}


def test_semantic_consensus_requires_two_distinct_models():
    assert semantic_consensus_ready(None, None) is False
    assert semantic_consensus_ready("vlm-a", None) is False
    assert semantic_consensus_ready("vlm-a", "vlm-a") is False
    assert semantic_consensus_ready("vlm-a", "vlm-b") is True


def test_independent_provider_requires_distinct_models_and_endpoints():
    settings = _settings()
    assert independent_provider_ready(settings) is True
    settings.autonomous_secondary_ai_base_url = settings.autonomous_ai_base_url
    assert independent_provider_ready(settings) is False
    settings.autonomous_secondary_ai_base_url = "https://secondary.example/v1"
    settings.autonomous_secondary_vlm_model = settings.autonomous_vlm_model
    assert independent_provider_ready(settings) is False


def test_single_model_can_never_auto_approve(monkeypatch):
    result = _strong_result(secondary=None)
    result.raw_response_hashes_json.pop("secondaryVlm")
    codes = _codes(monkeypatch, result)
    assert "AUTONOMOUS_TWO_MODEL_CONSENSUS_REQUIRED" in codes


def test_same_model_twice_is_not_treated_as_consensus(monkeypatch):
    codes = _codes(monkeypatch, _strong_result(primary="same-model", secondary="same-model"))
    assert "AUTONOMOUS_TWO_MODEL_CONSENSUS_REQUIRED" in codes


def test_same_provider_endpoint_blocks_unattended_approval(monkeypatch):
    settings = _settings()
    settings.autonomous_secondary_ai_base_url = settings.autonomous_ai_base_url
    codes = _codes(monkeypatch, _strong_result(), settings)
    assert "AUTONOMOUS_INDEPENDENT_PROVIDER_REQUIRED" in codes


def test_distinct_models_with_strong_evidence_have_complete_audit_chain(monkeypatch):
    result = _strong_result()
    codes = _codes(monkeypatch, result)
    assert "AUTONOMOUS_TWO_MODEL_CONSENSUS_REQUIRED" not in codes
    assert "AUTONOMOUS_INDEPENDENT_PROVIDER_REQUIRED" not in codes
    assert "AUTONOMOUS_AUDIT_BINDING_INCOMPLETE" not in codes
    assert "AUTONOMOUS_FRAME_QUALITY_UNAVAILABLE" not in codes
    assert "AUTONOMOUS_FRAME_QUALITY_INSUFFICIENT" not in codes
    assert autonomous_audit_binding_issues(result) == []
    assert frame_quality_issues(result) == []
    assert frame_quality_usable_ratio(result) == 1.0


def test_frame_hash_diversity_blocks_exactly_repeated_evidence(monkeypatch):
    hashes = ["a" * 64] * 9 + ["b" * 64, "c" * 64, "d" * 64]
    assert frame_hash_diversity(hashes) == 4 / 12
    codes = _codes(monkeypatch, _strong_result(hashes=hashes))
    assert "AUTONOMOUS_FRAME_DIVERSITY_INSUFFICIENT" in codes


def test_temporal_sampling_floor_blocks_too_few_video_moments(monkeypatch):
    result = _strong_result()
    result.sampled_frame_count = 4
    result.frame_hashes_json = _valid_hashes(4)
    result.observations_json["frameQuality"].update(
        total=4,
        sharpCount=4,
        exposureAcceptableCount=4,
        usableCount=4,
        sharpRatio=1.0,
        exposureAcceptableRatio=1.0,
        usableRatio=1.0,
    )
    codes = _codes(monkeypatch, result)
    assert "AUTONOMOUS_TEMPORAL_COVERAGE_INSUFFICIENT" in codes


def test_low_usable_frame_ratio_blocks_unattended_approval(monkeypatch):
    result = _strong_result()
    result.observations_json["frameQuality"].update(
        sharpCount=8,
        exposureAcceptableCount=9,
        usableCount=8,
        sharpRatio=8 / 12,
        exposureAcceptableRatio=9 / 12,
        usableRatio=8 / 12,
    )
    codes = _codes(monkeypatch, result)
    assert frame_quality_usable_ratio(result) == 8 / 12
    assert "AUTONOMOUS_FRAME_QUALITY_INSUFFICIENT" in codes
    assert "AUTONOMOUS_FRAME_QUALITY_UNAVAILABLE" not in codes


def test_missing_frame_quality_fails_closed(monkeypatch):
    result = _strong_result()
    result.observations_json.pop("frameQuality")
    codes = _codes(monkeypatch, result)
    assert frame_quality_issues(result) == ["missing:frameQuality"]
    assert frame_quality_usable_ratio(result) is None
    assert "AUTONOMOUS_FRAME_QUALITY_UNAVAILABLE" in codes


def test_tampered_frame_quality_ratio_fails_closed(monkeypatch):
    result = _strong_result()
    result.observations_json["frameQuality"]["usableCount"] = 12
    result.observations_json["frameQuality"]["usableRatio"] = 0.50
    issues = frame_quality_issues(result)
    codes = _codes(monkeypatch, result)
    assert "invalid:frameQualityRatioBinding" in issues
    assert "AUTONOMOUS_FRAME_QUALITY_UNAVAILABLE" in codes


def test_malformed_semantic_provenance_blocks_unattended_approval(monkeypatch):
    result = _strong_result()
    result.contract_source_hash = "not-a-hash"
    result.raw_response_hashes_json["primaryVlm"] = "broken"
    result.frame_hashes_json[0] = "invalid"
    result.analyzed_at = None

    issues = autonomous_audit_binding_issues(result)
    codes = _codes(monkeypatch, result)

    assert "invalid:contractSourceHash" in issues
    assert "invalid:rawResponseHash:primaryVlm" in issues
    assert "invalid:frameHash" in issues
    assert "missing:analyzedAt" in issues
    assert "AUTONOMOUS_AUDIT_BINDING_INCOMPLETE" in codes
