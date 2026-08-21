from types import SimpleNamespace

from app.models.fusion import MotionDirection
from app.services.verification.advanced.environment_signal import analyze_environment_metadata
from app.services.verification.advanced.statistical_anomaly import analyze_statistical_anomaly


def _snapshot(*access_points: tuple[str, int, int]):
    return {
        "wifiEnabled": True,
        "permissionGranted": True,
        "accessPoints": [
            {"apHash": ap_hash, "rssiDbm": rssi, "frequencyMhz": frequency}
            for ap_hash, rssi, frequency in access_points
        ],
    }


def _hash(value: str) -> str:
    return (value * 64)[:64]


def test_environment_continuity_uses_session_scoped_hashes_without_raw_wifi_identity() -> None:
    metadata = {
        "environment": {
            "version": "wifi-environment-v1",
            "snapshots": [
                _snapshot((_hash("a"), -52, 2412), (_hash("b"), -67, 5180)),
                _snapshot((_hash("a"), -54, 2412), (_hash("b"), -65, 5180)),
            ],
        }
    }
    result = analyze_environment_metadata(metadata)
    assert result["status"] == "CONSISTENT"
    assert result["consistency_score"] is not None and result["consistency_score"] > 0.95
    assert result["risk_score"] < 0.05
    assert result["metrics"]["ssidStored"] is False
    assert result["metrics"]["rawBssidStored"] is False
    assert result["metrics"]["hashScope"] == "SESSION"


def test_missing_wifi_is_supporting_evidence_not_a_failure() -> None:
    result = analyze_environment_metadata({})
    assert result["status"] == "UNAVAILABLE"
    assert result["risk_score"] == 0.0
    assert result["confidence"] == 0.0
    assert "ENVIRONMENT_EVIDENCE_UNAVAILABLE" in result["reason_codes"]


def test_same_direction_camera_metrology_noise_stays_nominal() -> None:
    row = SimpleNamespace(
        effective_consistency_score=0.72,
        start_offset_ms=700,
        end_offset_ms=500,
        angle_difference_deg=50.0,
        sensor_direction=MotionDirection.RIGHT,
        visual_direction=MotionDirection.RIGHT,
    )
    result = analyze_statistical_anomaly(
        sensor_anomaly_score=0.15,
        location_risk_score=0.0,
        duplicate_frame_ratio=0.0,
        environment_risk_score=0.1,
        environment_confidence=0.8,
        fusion_rows=[row],
    )
    assert result["status"] == "NOMINAL"
    assert result["score"] < 0.42
    assert result["metrics"]["trainedModelUsed"] is False


def test_multiple_independent_outliers_produce_high_statistical_anomaly() -> None:
    row = SimpleNamespace(
        effective_consistency_score=0.08,
        start_offset_ms=2400,
        end_offset_ms=2200,
        angle_difference_deg=95.0,
        sensor_direction=MotionDirection.RIGHT,
        visual_direction=MotionDirection.LEFT,
    )
    result = analyze_statistical_anomaly(
        sensor_anomaly_score=0.9,
        location_risk_score=0.8,
        duplicate_frame_ratio=0.6,
        environment_risk_score=0.9,
        environment_confidence=0.9,
        fusion_rows=[row],
    )
    assert result["status"] == "HIGH"
    assert result["score"] >= 0.70
    assert "STAT_SENSOR_OUTLIER" in result["reason_codes"]
    assert "STAT_FUSION_OUTLIER" in result["reason_codes"]
