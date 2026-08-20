import math
from dataclasses import dataclass
from statistics import fmean
from typing import Any

from app.core.config import Settings
from app.models.challenge import ChallengeResult, VerificationChallenge
from app.schemas.challenge import ChallengeSensorSample, ChallengeSensorType, ChallengeSubmitRequest
from app.services.challenges.validators.base import ChallengeValidationResult


@dataclass(frozen=True)
class AxisMotionSpec:
    axis_index: int
    expected_sign: float
    label: str


def _samples(payload: ChallengeSubmitRequest, sensor_type: ChallengeSensorType) -> list[ChallengeSensorSample]:
    return sorted(
        (sample for sample in payload.samples if sample.type == sensor_type),
        key=lambda sample: sample.relative_timestamp_ns,
    )


def _quality(samples: list[ChallengeSensorSample]) -> dict[str, Any]:
    if not samples:
        return {
            "samples": 0,
            "averageIntervalMs": None,
            "maxGapMs": None,
            "accuracyCounts": {},
            "quality": "UNAVAILABLE",
        }
    gaps = [
        (right.relative_timestamp_ns - left.relative_timestamp_ns) / 1_000_000.0
        for left, right in zip(samples, samples[1:])
    ]
    accuracy_counts: dict[str, int] = {}
    for sample in samples:
        key = str(sample.accuracy if sample.accuracy is not None else "unknown")
        accuracy_counts[key] = accuracy_counts.get(key, 0) + 1
    max_gap = max(gaps) if gaps else 0.0
    average = fmean(gaps) if gaps else 0.0
    quality = "GOOD" if len(samples) >= 12 and max_gap <= 150 else "DEGRADED"
    return {
        "samples": len(samples),
        "averageIntervalMs": round(average, 2),
        "maxGapMs": round(max_gap, 2),
        "accuracyCounts": accuracy_counts,
        "quality": quality,
    }


def _quaternion(values: list[float]) -> tuple[float, float, float, float]:
    x, y, z = values[0], values[1], values[2]
    if len(values) >= 4:
        w = values[3]
    else:
        w = math.sqrt(max(0.0, 1.0 - x * x - y * y - z * z))
    norm = math.sqrt(w * w + x * x + y * y + z * z)
    if norm < 1e-9:
        raise ValueError("Invalid zero-length rotation vector")
    return w / norm, x / norm, y / norm, z / norm


def _multiply(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    w1, x1, y1, z1 = left
    w2, x2, y2, z2 = right
    return (
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
    )


def _relative_rotation_component(samples: list[ChallengeSensorSample], axis_index: int) -> float | None:
    if len(samples) < 2:
        return None
    first = _quaternion(samples[0].values)
    last = _quaternion(samples[-1].values)
    inverse_first = (first[0], -first[1], -first[2], -first[3])
    relative = _multiply(inverse_first, last)
    w, x, y, z = relative
    if w < 0:
        w, x, y, z = -w, -x, -y, -z
    w = max(-1.0, min(1.0, w))
    angle = 2.0 * math.acos(w)
    sine = math.sqrt(max(0.0, 1.0 - w * w))
    if sine < 1e-7 or abs(angle) < 1e-7:
        return 0.0
    axis = (x / sine, y / sine, z / sine)
    return math.degrees(angle) * axis[axis_index]


def _integrate_gyro(
    samples: list[ChallengeSensorSample],
    axis_index: int,
    *,
    baseline_ms: int,
    movement_threshold: float,
    settle_threshold: float,
    settling_ms: int,
) -> tuple[float, float, float, float, int]:
    if len(samples) < 2:
        return 0.0, 0.0, 0.0, 0.0, 0
    first_ns = samples[0].relative_timestamp_ns
    baseline_end = first_ns + baseline_ms * 1_000_000
    baseline_values = [
        sample.values[axis_index]
        for sample in samples
        if sample.relative_timestamp_ns <= baseline_end
    ]
    bias = fmean(baseline_values) if baseline_values else 0.0
    corrected = [(sample.relative_timestamp_ns, sample.values[axis_index] - bias) for sample in samples]
    onset_index = next(
        (index for index, (_, value) in enumerate(corrected) if abs(value) >= movement_threshold),
        None,
    )
    if onset_index is None:
        return 0.0, bias, 0.0, 0.0, 0

    end_index = len(corrected) - 1
    settle_ns = settling_ms * 1_000_000
    for index in range(onset_index + 1, len(corrected)):
        start_ns = corrected[index][0]
        if abs(corrected[index][1]) > settle_threshold:
            continue
        cursor = index
        while cursor < len(corrected) and abs(corrected[cursor][1]) <= settle_threshold:
            if corrected[cursor][0] - start_ns >= settle_ns:
                end_index = cursor
                break
            cursor += 1
        if end_index != len(corrected) - 1:
            break

    selected = corrected[onset_index : end_index + 1]
    radians = 0.0
    for (left_ns, left_value), (right_ns, right_value) in zip(selected, selected[1:]):
        dt = max(0.0, (right_ns - left_ns) / 1_000_000_000.0)
        radians += ((left_value + right_value) / 2.0) * dt
    duration_ms = (selected[-1][0] - selected[0][0]) / 1_000_000.0 if len(selected) > 1 else 0.0
    movement_values = [value for _, value in selected]
    return math.degrees(radians), bias, duration_ms, fmean(abs(value) for value in movement_values), len(selected)


def _angle_score(observed: float, target: float, minimum: float, maximum: float) -> float:
    if observed <= 0:
        return 0.0
    if observed < minimum:
        return max(0.0, min(0.7, 0.7 * observed / max(minimum, 1.0)))
    if observed > maximum:
        overshoot = (observed - maximum) / max(maximum, 1.0)
        return max(0.0, 0.75 - overshoot)
    span = max(maximum - minimum, 1.0)
    closeness = 1.0 - min(1.0, abs(observed - target) / span)
    return 0.8 + 0.2 * closeness


def validate_axis_motion(
    challenge: VerificationChallenge,
    payload: ChallengeSubmitRequest,
    *,
    spec: AxisMotionSpec,
    capabilities: dict[str, Any],
    settings: Settings,
) -> ChallengeValidationResult:
    gyro = _samples(payload, ChallengeSensorType.GYROSCOPE)
    rotation = _samples(payload, ChallengeSensorType.ROTATION_VECTOR)
    gyro_quality = _quality(gyro)
    rotation_quality = _quality(rotation)
    sensor_quality = {"gyroscope": gyro_quality, "rotationVector": rotation_quality}

    if not capabilities.get("gyroscope") or len(gyro) < settings.challenge_min_gyro_samples:
        return ChallengeValidationResult(
            result=ChallengeResult.INCONCLUSIVE,
            score=0.0,
            sensor_score=0.0,
            reasons=["Gyroscope evidence was unavailable or too sparse for authoritative validation."],
            metrics={},
            sensor_quality=sensor_quality,
            failure_reason="GYROSCOPE_UNAVAILABLE",
        )

    gyro_degrees, gyro_bias, movement_duration_ms, average_rate, movement_samples = _integrate_gyro(
        gyro,
        spec.axis_index,
        baseline_ms=settings.challenge_baseline_ms,
        movement_threshold=settings.challenge_movement_threshold_rad_s,
        settle_threshold=settings.challenge_settle_threshold_rad_s,
        settling_ms=settings.challenge_settling_ms,
    )
    signed_gyro = gyro_degrees * spec.expected_sign
    rotation_component = _relative_rotation_component(rotation, spec.axis_index)
    signed_rotation = rotation_component * spec.expected_sign if rotation_component is not None else None

    target = float(challenge.parameters_json["targetDegrees"])
    minimum = float(challenge.parameters_json["minDegrees"])
    maximum = float(challenge.parameters_json["maxDegrees"])
    observed_candidates = [signed_gyro]
    if signed_rotation is not None:
        observed_candidates.append(signed_rotation)
    observed = fmean(observed_candidates)

    direction_score = 1.0 if observed >= 5.0 else (0.0 if observed <= -5.0 else 0.35)
    angle_score = _angle_score(max(0.0, observed), target, minimum, maximum)
    if signed_rotation is None:
        agreement_score = 0.5
    else:
        difference = abs(signed_gyro - signed_rotation)
        agreement_score = max(
            0.0,
            1.0 - difference / max(settings.challenge_sensor_agreement_tolerance_degrees, 1.0),
        )
    timing_score = 1.0 if 250 <= movement_duration_ms <= 5_000 else 0.55

    expected_raw_sign = 1.0 if spec.expected_sign > 0 else -1.0
    movement_axis_values = [sample.values[spec.axis_index] for sample in gyro]
    matching = sum(1 for value in movement_axis_values if value * expected_raw_sign >= -0.03)
    smoothness_score = matching / max(len(movement_axis_values), 1)

    weights = settings.challenge_score_weights
    score = (
        weights["direction"] * direction_score
        + weights["angle"] * angle_score
        + weights["agreement"] * agreement_score
        + weights["timing"] * timing_score
        + weights["smoothness"] * smoothness_score
    )
    quality_score = 1.0 if gyro_quality["quality"] == "GOOD" else 0.6
    sensor_score = 0.6 * agreement_score + 0.4 * quality_score

    reasons = []
    if direction_score == 1.0:
        reasons.append(f"{spec.label} direction matched the requested movement.")
    elif direction_score == 0.0:
        reasons.append(f"Detected movement was strongly opposite to the requested {spec.label.lower()} direction.")
    else:
        reasons.append("Movement direction was too small to determine reliably.")
    reasons.append(f"Observed gyroscope angle was {signed_gyro:.1f} degrees.")
    if signed_rotation is not None:
        reasons.append(f"Rotation-vector delta was {signed_rotation:.1f} degrees.")

    metrics = {
        "targetDegrees": round(target, 2),
        "minDegrees": round(minimum, 2),
        "maxDegrees": round(maximum, 2),
        "observedGyroDegrees": round(signed_gyro, 2),
        "observedRotationVectorDegrees": round(signed_rotation, 2) if signed_rotation is not None else None,
        "sensorDifferenceDegrees": round(abs(signed_gyro - signed_rotation), 2) if signed_rotation is not None else None,
        "movementDurationMs": round(movement_duration_ms, 1),
        "gyroBiasRadPerSecond": round(gyro_bias, 5),
        "averageMovementRateRadPerSecond": round(average_rate, 4),
        "movementSamples": movement_samples,
        "directionScore": round(direction_score, 4),
        "angleScore": round(angle_score, 4),
        "sensorAgreement": round(agreement_score, 4),
        "timingScore": round(timing_score, 4),
        "smoothnessScore": round(smoothness_score, 4),
    }

    # Weighted scoring is useful near the requested range, but it must never let a tiny
    # movement pass merely because timing and sensor agreement look clean. Sensor conflict
    # is evaluated first so contradictory strong sensors remain INCONCLUSIVE rather than
    # being misreported as a simple magnitude failure.
    minimum_clear_motion = minimum * 0.65
    if direction_score == 0.0:
        result = ChallengeResult.FAIL
        failure_reason = "WRONG_DIRECTION"
    elif signed_rotation is not None and abs(signed_gyro - signed_rotation) > settings.challenge_sensor_conflict_degrees:
        result = ChallengeResult.INCONCLUSIVE
        failure_reason = "SENSOR_CONFLICT"
        reasons.append("Gyroscope and rotation-vector evidence conflict beyond the configured tolerance.")
    elif max(0.0, observed) < minimum_clear_motion:
        result = ChallengeResult.FAIL
        failure_reason = "INSUFFICIENT_MOVEMENT"
        reasons.append("Observed movement was clearly below the minimum challenge magnitude.")
    elif score >= settings.challenge_pass_threshold:
        result = ChallengeResult.PASS
        failure_reason = None
    elif score >= settings.challenge_inconclusive_threshold:
        result = ChallengeResult.INCONCLUSIVE
        failure_reason = "LOW_CONFIDENCE"
    else:
        result = ChallengeResult.FAIL
        failure_reason = "INSUFFICIENT_MOVEMENT"

    return ChallengeValidationResult(
        result=result,
        score=max(0.0, min(1.0, score)),
        sensor_score=max(0.0, min(1.0, sensor_score)),
        reasons=reasons,
        metrics=metrics,
        sensor_quality=sensor_quality,
        failure_reason=failure_reason,
    )
