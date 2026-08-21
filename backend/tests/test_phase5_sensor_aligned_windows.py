from types import SimpleNamespace

from app.schemas.challenge import ChallengeSensorSample, ChallengeSensorType
from app.services.challenges.validators.motion_math import _integrate_gyro
from app.services.visual_analysis_service import _sensor_motion_window_ms


def _gyro_sample(timestamp_ns: int, value: float) -> ChallengeSensorSample:
    return ChallengeSensorSample(
        type=ChallengeSensorType.GYROSCOPE,
        relative_timestamp_ns=timestamp_ns,
        values=[0.0, value, 0.0],
        accuracy=3,
    )


def test_integrated_gyro_exposes_exact_motion_bounds():
    start_ns = 1_000_000_000
    samples = []
    for index in range(21):
        timestamp_ns = start_ns + index * 100_000_000
        if 6 <= index <= 15:
            value = 0.5
        else:
            value = 0.0
        samples.append(_gyro_sample(timestamp_ns, value))

    (
        degrees,
        _bias,
        duration_ms,
        _average_rate,
        movement_samples,
        motion_start_ns,
        motion_end_ns,
    ) = _integrate_gyro(
        samples,
        1,
        baseline_ms=500,
        movement_threshold=0.18,
        settle_threshold=0.10,
        settling_ms=300,
    )

    assert degrees > 0
    assert movement_samples > 0
    assert duration_ms == 1300.0
    assert motion_start_ns == start_ns + 600_000_000
    assert motion_end_ns == start_ns + 1_900_000_000


def test_visual_window_prefers_server_validated_sensor_motion_bounds():
    challenge = SimpleNamespace(
        metrics_json={
            "motionStartRelativeNs": 1_800_000_000,
            "motionEndRelativeNs": 3_200_000_000,
        }
    )
    item = {
        "issuedRelativeMs": 900,
        "startedRelativeMs": 1000,
        "completedRelativeMs": 5000,
    }

    assert _sensor_motion_window_ms(challenge, item) == (1800, 3200)


def test_visual_window_rejects_sensor_bounds_outside_protocol_window():
    item = {
        "issuedRelativeMs": 900,
        "startedRelativeMs": 1000,
        "completedRelativeMs": 5000,
    }
    before_start = SimpleNamespace(
        metrics_json={
            "motionStartRelativeNs": 900_000_000,
            "motionEndRelativeNs": 3_000_000_000,
        }
    )
    after_end = SimpleNamespace(
        metrics_json={
            "motionStartRelativeNs": 2_000_000_000,
            "motionEndRelativeNs": 5_100_000_000,
        }
    )
    legacy = SimpleNamespace(metrics_json={"movementDurationMs": 1800.0})

    assert _sensor_motion_window_ms(before_start, item) is None
    assert _sensor_motion_window_ms(after_end, item) is None
    assert _sensor_motion_window_ms(legacy, item) is None
