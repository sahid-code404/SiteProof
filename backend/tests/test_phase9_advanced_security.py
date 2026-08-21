from types import SimpleNamespace

import numpy as np

from app.models.advanced_security import RiskLevel
from app.models.fusion import ConsistencyStatus, MismatchReason, MotionDirection
from app.services.advanced_security_service import _fusion_row_replay_risk
from app.services.verification.advanced import replay_risk
from app.services.verification.advanced.device_metadata import analyze_device_metadata
from app.services.verification.advanced.location_risk import analyze_location_samples
from app.services.verification.advanced.replay_risk import analyze_frames
from app.services.verification.advanced.sensor_anomaly import analyze_sensor_stream


def test_mock_location_is_high_risk() -> None:
    result = analyze_location_samples(
        [
            {
                "relativeTimestampNs": 0,
                "latitude": 12.0,
                "longitude": 77.0,
                "accuracyMeters": 5.0,
                "isMock": True,
            }
        ]
    )
    assert result["risk_level"] == RiskLevel.HIGH
    assert result["mock_location_detected"] is True
    assert "MOCK_LOCATION_DETECTED" in result["reason_codes"]


def test_impossible_location_jump_is_high_risk() -> None:
    result = analyze_location_samples(
        [
            {
                "relativeTimestampNs": 0,
                "latitude": 12.0,
                "longitude": 77.0,
                "accuracyMeters": 3.0,
                "isMock": False,
            },
            {
                "relativeTimestampNs": 1_000_000_000,
                "latitude": 13.0,
                "longitude": 78.0,
                "accuracyMeters": 3.0,
                "isMock": False,
            },
        ]
    )
    assert result["risk_level"] == RiskLevel.HIGH
    assert result["impossible_jump_count"] == 1


def test_sensor_physical_range_violation_is_high_risk() -> None:
    rows = [
        {
            "type": "GYROSCOPE",
            "relativeTimestampNs": index * 10_000_000,
            "values": [150.0, 0.0, 0.0],
        }
        for index in range(50)
    ]
    result = analyze_sensor_stream(rows)
    assert result["risk_level"] == RiskLevel.HIGH
    assert "SENSOR_VALUE_OUT_OF_RANGE" in result["reason_codes"]


def test_display_rectangle_alone_cannot_trigger_high_replay_risk() -> None:
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[80:400, 100:540] = 255
    result = analyze_frames(
        [frame] * 6,
        fusion_mismatch_score=0.0,
        duplicate_frame_ratio=0.0,
        evidence_reuse_score=0.0,
    )
    assert result["risk_level"] != RiskLevel.HIGH
    assert result["metrics"]["rectangleAloneCannotTriggerHigh"] is True


def test_same_direction_fusion_gap_is_not_hard_replay_contradiction() -> None:
    row = SimpleNamespace(
        sensor_direction=MotionDirection.RIGHT,
        visual_direction=MotionDirection.RIGHT,
        consistency_status=ConsistencyStatus.MISMATCH,
        effective_consistency_score=0.53,
        mismatch_reasons_json=[
            MismatchReason.SENSOR_WITHOUT_VISUAL_MOTION.value,
            MismatchReason.MAGNITUDE_MISMATCH.value,
            MismatchReason.TEMPORAL_MISMATCH.value,
        ],
    )
    assert _fusion_row_replay_risk(row) == 0.47


def test_opposite_direction_remains_hard_replay_corroboration() -> None:
    row = SimpleNamespace(
        sensor_direction=MotionDirection.RIGHT,
        visual_direction=MotionDirection.LEFT,
        consistency_status=ConsistencyStatus.MISMATCH,
        effective_consistency_score=0.2,
        mismatch_reasons_json=[MismatchReason.OPPOSITE_DIRECTION.value],
    )
    assert _fusion_row_replay_risk(row) == 1.0


def test_banding_and_moire_are_one_artifact_family(monkeypatch) -> None:
    frame = np.zeros((240, 320, 3), dtype=np.uint8)
    monkeypatch.setattr(replay_risk, "display_rectangle_score", lambda _frame: 0.1)
    monkeypatch.setattr(replay_risk, "banding_score", lambda _frame: 0.95)
    monkeypatch.setattr(replay_risk, "moire_score", lambda _frame: 0.95)
    result = replay_risk.analyze_frames(
        [frame] * 8,
        fusion_mismatch_score=0.40,
        duplicate_frame_ratio=0.0,
        evidence_reuse_score=0.0,
    )
    assert result["risk_level"] == RiskLevel.MODERATE
    assert result["metrics"]["independentHighRiskFamilies"] == 1


def test_emulator_metadata_is_high_device_risk() -> None:
    result = analyze_device_metadata(
        {
            "device": {
                "manufacturer": "Google",
                "model": "sdk_gphone64_x86_64",
                "brand": "google",
                "product": "sdk_gphone64_x86_64",
                "hardware": "ranchu",
                "fingerprint": "google/sdk_gphone64_x86_64/emulator",
                "buildTags": "release-keys",
                "emulatorHeuristic": True,
            }
        },
        None,
    )
    assert result["status"] == "FAIL"
    assert result["risk_score"] >= 0.9
    assert "EMULATOR_OR_VIRTUAL_DEVICE" in result["reason_codes"]
