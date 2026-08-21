from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from statistics import fmean, pstdev
from typing import Any

from app.models.advanced_security import AdvancedProcessStatus, RiskLevel

ALGORITHM_VERSION = "sensor-anomaly-v1"
WINDOW = 12


def _magnitude(values: list[Any]) -> float | None:
    if len(values) < 3:
        return None
    try:
        x, y, z = map(float, values[:3])
    except (TypeError, ValueError):
        return None
    return math.sqrt(x * x + y * y + z * z)


def _hash_window(rows: list[dict[str, Any]]) -> str:
    normalized = [
        (
            str(row.get("type")),
            tuple(round(float(value), 4) for value in (row.get("values") or [])[:4]),
        )
        for row in rows
    ]
    return hashlib.sha256(repr(normalized).encode()).hexdigest()


def analyze_sensor_stream(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "process_status": AdvancedProcessStatus.UNAVAILABLE,
            "risk_level": RiskLevel.INCONCLUSIVE,
            "status": "UNAVAILABLE",
            "anomaly_score": 0.5,
            "confidence": 0.0,
            "duplicate_sequence_score": 0.0,
            "timestamp_anomaly_score": 0.0,
            "range_anomaly_score": 0.0,
            "cross_sensor_conflict_score": 0.0,
            "reason_codes": ["SENSOR_STREAM_UNAVAILABLE"],
            "reasons": ["No sensor stream was available for anomaly analysis."],
            "metrics": {},
            "algorithm_version": ALGORITHM_VERSION,
        }

    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    malformed = 0
    for row in rows:
        sensor_type = str(row.get("type") or "")
        if sensor_type not in {"ACCELEROMETER", "GYROSCOPE", "ROTATION_VECTOR", "MAGNETOMETER"}:
            malformed += 1
            continue
        if not isinstance(row.get("values"), list):
            malformed += 1
            continue
        by_type[sensor_type].append(row)

    reversals = 0
    large_gaps = 0
    interval_variation: list[float] = []
    for sensor_rows in by_type.values():
        timestamps: list[int] = []
        for row in sensor_rows:
            try:
                timestamps.append(int(row["relativeTimestampNs"]))
            except (KeyError, TypeError, ValueError):
                malformed += 1
        intervals: list[float] = []
        for first, second in zip(timestamps, timestamps[1:]):
            delta = second - first
            if delta <= 0:
                reversals += 1
            else:
                intervals.append(delta / 1e6)
                if delta > 1_000_000_000:
                    large_gaps += 1
        if len(intervals) >= 20 and fmean(intervals) > 0:
            interval_variation.append(pstdev(intervals) / fmean(intervals))

    codes: list[str] = []
    reasons: list[str] = []
    timestamp_score = 0.0
    if reversals:
        timestamp_score = max(timestamp_score, min(1.0, 0.75 + 0.05 * reversals))
        codes.append("SENSOR_TIMESTAMP_REVERSAL")
        reasons.append("One or more sensor timestamps moved backwards or were duplicated.")
    if large_gaps:
        timestamp_score = max(timestamp_score, min(0.75, 0.35 + 0.08 * large_gaps))
        codes.append("SENSOR_SAMPLE_GAP")
        reasons.append("The sensor stream contained unusually large sampling gaps.")
    perfectly_regular = bool(interval_variation) and min(interval_variation) < 1e-6
    if perfectly_regular:
        timestamp_score = max(timestamp_score, 0.18)
        codes.append("EXACT_SENSOR_INTERVAL_REGULARITY")
        reasons.append("At least one sensor stream had perfectly regular intervals; treated as weak evidence only.")

    magnitudes: dict[str, list[float]] = defaultdict(list)
    range_hits = 0
    zero_streams = 0
    for sensor_type, sensor_rows in by_type.items():
        for row in sensor_rows:
            magnitude = _magnitude(row.get("values") or [])
            if magnitude is None:
                continue
            magnitudes[sensor_type].append(magnitude)
            if sensor_type == "GYROSCOPE" and magnitude > 100:
                range_hits += 1
            elif sensor_type == "ACCELEROMETER" and magnitude > 500:
                range_hits += 1
            elif sensor_type == "MAGNETOMETER" and magnitude > 2500:
                range_hits += 1
        if len(sensor_rows) >= 40 and magnitudes[sensor_type] and max(magnitudes[sensor_type]) < 1e-9:
            zero_streams += 1

    range_score = 0.0
    if range_hits:
        range_score = min(1.0, 0.88 + 0.02 * range_hits)
        codes.append("SENSOR_VALUE_OUT_OF_RANGE")
        reasons.append("Sensor values exceeded conservative physical plausibility bounds.")
    if zero_streams:
        range_score = max(range_score, 0.60)
        codes.append("CONSTANT_ZERO_SENSOR_STREAM")
        reasons.append("A long sensor stream remained exactly zero throughout capture.")

    hashes: dict[str, int] = defaultdict(int)
    eligible_windows = 0
    for sensor_type, sensor_rows in by_type.items():
        if sensor_type == "MAGNETOMETER":
            continue
        for start in range(0, max(0, len(sensor_rows) - WINDOW + 1), WINDOW):
            window = sensor_rows[start : start + WINDOW]
            if len(window) < WINDOW:
                continue
            eligible_windows += 1
            hashes[_hash_window(window)] += 1
    repeated_windows = sum(max(0, count - 1) for count in hashes.values())
    duplicate_score = (
        min(1.0, repeated_windows / max(1, eligible_windows // 2)) if eligible_windows else 0.0
    )
    if repeated_windows >= 2:
        duplicate_score = max(duplicate_score, 0.55)
        codes.append("SENSOR_SEQUENCE_REPETITION")
        reasons.append("Quantized sensor windows repeated exactly later in the session.")

    conflict_score = 0.0
    gyro = magnitudes.get("GYROSCOPE", [])
    rotation_rows = by_type.get("ROTATION_VECTOR", [])
    if len(gyro) >= 20 and len(rotation_rows) >= 20:
        gyro_rms = math.sqrt(fmean([value * value for value in gyro]))
        rotation_values: list[tuple[float, float, float]] = []
        for row in rotation_rows:
            try:
                values = row["values"]
                rotation_values.append(tuple(float(value) for value in values[:3]))
            except (KeyError, TypeError, ValueError):
                pass
        if rotation_values:
            ranges = [
                max(value[index] for value in rotation_values)
                - min(value[index] for value in rotation_values)
                for index in range(3)
            ]
            if gyro_rms > 0.8 and max(ranges) < 1e-4:
                conflict_score = 0.85
                codes.append("SENSOR_CONTRADICTION")
                reasons.append("Gyroscope motion conflicted with an effectively static rotation vector.")

    anomaly_score = max(range_score, conflict_score, 0.85 * timestamp_score, 0.75 * duplicate_score)
    if malformed > max(5, len(rows) // 20):
        anomaly_score = max(anomaly_score, 0.45)
        codes.append("MALFORMED_SENSOR_SAMPLES")
        reasons.append("A meaningful fraction of sensor samples could not be interpreted.")

    risk_level = (
        RiskLevel.HIGH
        if anomaly_score >= 0.75
        else RiskLevel.MODERATE
        if anomaly_score >= 0.35
        else RiskLevel.LOW
    )
    status = "FAIL" if risk_level == RiskLevel.HIGH else "PARTIAL" if risk_level == RiskLevel.MODERATE else "PASS"
    if not reasons:
        reasons.append("No repeated, impossible, or contradictory sensor-stream pattern was detected.")

    sample_count = sum(len(values) for values in by_type.values())
    confidence = min(0.95, 0.45 + min(0.45, sample_count / 1000.0))
    return {
        "process_status": AdvancedProcessStatus.COMPLETE,
        "risk_level": risk_level,
        "status": status,
        "anomaly_score": min(1.0, anomaly_score),
        "confidence": confidence,
        "duplicate_sequence_score": duplicate_score,
        "timestamp_anomaly_score": timestamp_score,
        "range_anomaly_score": range_score,
        "cross_sensor_conflict_score": conflict_score,
        "reason_codes": sorted(set(codes)),
        "reasons": reasons,
        "metrics": {
            "sampleCount": sample_count,
            "malformedSampleCount": malformed,
            "timestampReversalCount": reversals,
            "largeGapCount": large_gaps,
            "repeatedWindowCount": repeated_windows,
            "eligibleWindowCount": eligible_windows,
            "outOfRangeSampleCount": range_hits,
            "constantZeroStreamCount": zero_streams,
            "perfectIntervalRegularityWeakIndicator": perfectly_regular,
        },
        "algorithm_version": ALGORITHM_VERSION,
    }
