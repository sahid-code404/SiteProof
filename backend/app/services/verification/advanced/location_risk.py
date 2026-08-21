from __future__ import annotations

import math
from statistics import fmean
from typing import Any

from app.models.advanced_security import AdvancedProcessStatus, RiskLevel

ALGORITHM_VERSION = "location-risk-v1"
IMPOSSIBLE_FIELD_SPEED_MPS = 55.0


def _haversine_meters(a: dict[str, Any], b: dict[str, Any]) -> float:
    radius = 6_371_000.0
    lat1 = math.radians(float(a["latitude"]))
    lat2 = math.radians(float(b["latitude"]))
    dlat = lat2 - lat1
    dlon = math.radians(float(b["longitude"]) - float(a["longitude"]))
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(h))


def _sensor_activity(sensor_rows: list[dict[str, Any]]) -> float | None:
    values: list[float] = []
    for row in sensor_rows:
        sensor_type = row.get("type")
        if sensor_type not in {"ACCELEROMETER", "GYROSCOPE"}:
            continue
        sample = row.get("values")
        if not isinstance(sample, list) or len(sample) < 3:
            continue
        try:
            x, y, z = map(float, sample[:3])
        except (TypeError, ValueError):
            continue
        magnitude = math.sqrt(x * x + y * y + z * z)
        if sensor_type == "ACCELEROMETER":
            values.append(abs(magnitude - 9.81) / 9.81)
        else:
            values.append(min(1.0, magnitude))
    return fmean(values) if values else None


def analyze_location_samples(
    location_rows: list[dict[str, Any]],
    sensor_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not location_rows:
        return {
            "process_status": AdvancedProcessStatus.UNAVAILABLE,
            "risk_level": RiskLevel.INCONCLUSIVE,
            "score": 0.5,
            "confidence": 0.0,
            "mock_location_detected": False,
            "max_implied_speed": None,
            "impossible_jump_count": 0,
            "sensor_location_consistency": None,
            "reason_codes": ["LOCATION_STREAM_UNAVAILABLE"],
            "reasons": ["No location stream was available for spoof-risk analysis."],
            "metrics": {},
            "algorithm_version": ALGORITHM_VERSION,
        }

    valid: list[dict[str, Any]] = []
    mock_detected = False
    mock_flag_count = 0
    high_reported_speed_count = 0
    accuracies: list[float] = []

    for row in location_rows:
        try:
            float(row["latitude"])
            float(row["longitude"])
            int(row["relativeTimestampNs"])
        except (KeyError, TypeError, ValueError):
            continue
        valid.append(row)
        if "isMock" in row:
            mock_flag_count += 1
            mock_detected = mock_detected or bool(row.get("isMock"))
        try:
            speed = float(row.get("speedMetersPerSecond") or 0.0)
            high_reported_speed_count += int(speed > IMPOSSIBLE_FIELD_SPEED_MPS)
        except (TypeError, ValueError):
            pass
        try:
            accuracies.append(float(row.get("accuracyMeters")))
        except (TypeError, ValueError):
            pass

    if not valid:
        return {
            "process_status": AdvancedProcessStatus.INCONCLUSIVE,
            "risk_level": RiskLevel.INCONCLUSIVE,
            "score": 0.5,
            "confidence": 0.2,
            "mock_location_detected": False,
            "max_implied_speed": None,
            "impossible_jump_count": 0,
            "sensor_location_consistency": None,
            "reason_codes": ["LOCATION_STREAM_MALFORMED"],
            "reasons": ["Location samples were present but could not be interpreted reliably."],
            "metrics": {"sampleCount": len(location_rows), "validSampleCount": 0},
            "algorithm_version": ALGORITHM_VERSION,
        }

    jumps = 0
    reversals = 0
    max_speed = 0.0
    total_distance = 0.0
    previous = valid[0]
    for current in valid[1:]:
        dt = (int(current["relativeTimestampNs"]) - int(previous["relativeTimestampNs"])) / 1e9
        if dt <= 0:
            reversals += 1
            previous = current
            continue
        distance = _haversine_meters(previous, current)
        total_distance += distance
        implied_speed = distance / dt
        max_speed = max(max_speed, implied_speed)
        previous_accuracy = max(0.0, float(previous.get("accuracyMeters") or 0.0))
        current_accuracy = max(0.0, float(current.get("accuracyMeters") or 0.0))
        significant_distance = max(30.0, 2.0 * (previous_accuracy + current_accuracy))
        if dt >= 0.5 and distance > significant_distance and implied_speed > IMPOSSIBLE_FIELD_SPEED_MPS:
            jumps += 1
        previous = current

    codes: list[str] = []
    reasons: list[str] = []
    score = 0.0
    confidence = 0.65 if mock_flag_count else 0.50

    if mock_detected:
        score = 1.0
        confidence = 0.98
        codes.append("MOCK_LOCATION_DETECTED")
        reasons.append("Android marked at least one captured location sample as mock-provided.")
    if jumps:
        score = max(score, min(1.0, 0.78 + 0.08 * jumps))
        confidence = max(confidence, 0.90)
        codes.append("IMPOSSIBLE_LOCATION_JUMP")
        reasons.append("Sequential GPS samples imply movement beyond plausible field-inspection speed.")
    if high_reported_speed_count:
        score = max(score, 0.72)
        confidence = max(confidence, 0.78)
        codes.append("REPORTED_SPEED_IMPLAUSIBLE")
        reasons.append("The location provider reported implausibly high speed during capture.")
    if reversals:
        score = max(score, 0.58)
        confidence = max(confidence, 0.65)
        codes.append("LOCATION_TIMESTAMP_REVERSAL")
        reasons.append("One or more location timestamps moved backwards or were duplicated.")

    activity = _sensor_activity(sensor_rows or [])
    sensor_consistency: float | None = None
    if activity is not None:
        if total_distance >= 40.0 and activity < 0.03:
            sensor_consistency = 0.25
            score = max(score, 0.65)
            confidence = max(confidence, 0.72)
            codes.append("LOCATION_SENSOR_MISMATCH")
            reasons.append("GPS indicated substantial translation while motion sensors were nearly stationary.")
        else:
            sensor_consistency = 0.85

    repeated_accuracy = len(accuracies) >= 8 and len({round(value, 3) for value in accuracies}) == 1
    if repeated_accuracy:
        score = max(score, 0.22)
        codes.append("UNNATURALLY_STABLE_ACCURACY")
        reasons.append("GPS accuracy stayed exactly unchanged across many samples; this is weak evidence only.")

    if not reasons:
        reasons.append("No strong mock-location, impossible-jump, or location/sensor conflict was detected.")

    risk_level = RiskLevel.HIGH if score >= 0.75 else RiskLevel.MODERATE if score >= 0.35 else RiskLevel.LOW
    if mock_flag_count == 0:
        confidence = min(confidence, 0.72)

    return {
        "process_status": AdvancedProcessStatus.COMPLETE,
        "risk_level": risk_level,
        "score": min(1.0, score),
        "confidence": min(1.0, confidence),
        "mock_location_detected": mock_detected,
        "max_implied_speed": max_speed if len(valid) > 1 else None,
        "impossible_jump_count": jumps,
        "sensor_location_consistency": sensor_consistency,
        "reason_codes": sorted(set(codes)),
        "reasons": reasons,
        "metrics": {
            "sampleCount": len(location_rows),
            "validSampleCount": len(valid),
            "mockFlagObservedCount": mock_flag_count,
            "reportedHighSpeedCount": high_reported_speed_count,
            "timestampReversalCount": reversals,
            "totalDisplacementMeters": round(total_distance, 3),
            "repeatedAccuracyWeakIndicator": repeated_accuracy,
            "sensorActivityScore": None if activity is None else round(activity, 5),
        },
        "algorithm_version": ALGORITHM_VERSION,
    }
