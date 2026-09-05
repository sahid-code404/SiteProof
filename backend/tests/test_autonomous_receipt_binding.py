from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import app.services.receipt_service as receipt_module
from app.core.errors import SiteProofError
from app.models.autonomous_verification import AutonomousAnalysisStatus
from app.services.receipt_crypto import canonical_json_bytes, sha256_hex
from app.services.receipt_service import _autonomous_receipt_binding
from app.services.verification.versions import AUTONOMOUS_ENGINE_VERSION


def _autonomous_row():
    return SimpleNamespace(
        status=AutonomousAnalysisStatus.COMPLETE,
        analysis_version="autonomous-v2-test",
        contract_version="contract-v1",
        contract_prompt_version="contract-prompt-v1",
        vision_prompt_version="vision-prompt-v1",
        compiler_model="contract-model",
        primary_vlm_model="vlm-a",
        secondary_vlm_model="vlm-b",
        contract_source_hash="a" * 64,
        contract_json={"inspectionIntent": "Verify repaired pothole"},
        observations_json={"primary": {"taskMatch": {"score": 0.95}}},
        raw_response_hashes_json={"contract": "b" * 64, "primaryVlm": "c" * 64},
        sampled_frame_count=12,
        frame_hashes_json=[f"frame-{index}" for index in range(12)],
        task_match_score=0.95,
        task_match_confidence=0.94,
        asset_identity_score=0.91,
        asset_identity_confidence=0.90,
        evidence_coverage_score=0.96,
        evidence_coverage_confidence=0.93,
        live_scene_score=0.97,
        live_scene_confidence=0.95,
        presentation_attack_score=0.02,
        presentation_attack_confidence=0.92,
        mandatory_failures_json=[],
        model_disagreement=False,
        analyzed_at=datetime(2026, 9, 5, 8, 0, tzinfo=timezone.utc),
    )


def test_non_autonomous_engine_has_no_semantic_receipt_binding():
    result = SimpleNamespace(engine_version="verification-engine-v2.0", session_id="session")
    assert _autonomous_receipt_binding(None, result) is None


def test_autonomous_receipt_binds_contract_observations_models_and_frames(monkeypatch):
    autonomous = _autonomous_row()
    monkeypatch.setattr(receipt_module, "get_autonomous_result", lambda db, session_id: autonomous)
    result = SimpleNamespace(engine_version=AUTONOMOUS_ENGINE_VERSION, session_id="session")

    binding = _autonomous_receipt_binding(None, result)

    assert binding is not None
    assert binding["primaryVlmModel"] == "vlm-a"
    assert binding["secondaryVlmModel"] == "vlm-b"
    assert binding["sampledFrameCount"] == 12
    assert binding["frameHashes"] == autonomous.frame_hashes_json
    assert binding["contractSha256"] == sha256_hex(canonical_json_bytes(autonomous.contract_json))
    assert binding["observationsSha256"] == sha256_hex(
        canonical_json_bytes(autonomous.observations_json)
    )

    binding_without_digest = dict(binding)
    digest = binding_without_digest.pop("bindingSha256")
    assert digest == sha256_hex(canonical_json_bytes(binding_without_digest))


def test_autonomous_receipt_refuses_missing_or_incomplete_semantic_analysis(monkeypatch):
    result = SimpleNamespace(engine_version=AUTONOMOUS_ENGINE_VERSION, session_id="session")
    monkeypatch.setattr(receipt_module, "get_autonomous_result", lambda db, session_id: None)
    with pytest.raises(SiteProofError) as missing:
        _autonomous_receipt_binding(None, result)
    assert missing.value.code == "AUTONOMOUS_EVIDENCE_NOT_COMPLETE"

    failed = _autonomous_row()
    failed.status = AutonomousAnalysisStatus.FAILED
    monkeypatch.setattr(receipt_module, "get_autonomous_result", lambda db, session_id: failed)
    with pytest.raises(SiteProofError) as incomplete:
        _autonomous_receipt_binding(None, result)
    assert incomplete.value.code == "AUTONOMOUS_EVIDENCE_NOT_COMPLETE"
