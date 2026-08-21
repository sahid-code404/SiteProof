from __future__ import annotations

from statistics import median
from typing import Any

from app.models.fusion import MotionDirection, VisualInertialResult

ALGORITHM_VERSION = "statistical-anomaly-v1"


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _median_or_zero(values: list[float]) -> float:
    return float(median(values)) if values else 0.0


def analyze_statistical_anomaly(
    *,
    sensor_anomaly_score: float,
    location_risk_score: float,
    duplicate_frame_ratio: float,
    environment_risk_score: float,
    environment_confidence: float,
    fusion_rows: list[VisualInertialResult],
) -> dict[str, Any]:
    """Deterministic robust anomaly score; never replaces the explainable trust engine."""
    disagreements: list[float] = []
    timing_residuals: list[float] = []
    angle_residuals: list[float] = []

    for row in fusion_rows:
        if row.effective_consistency_score is not None:
            disagreements.append(_clamp(1.0 - float(row.effective_consistency_score)))

        offsets = [
            abs(float(value))
            for value in (row.start_offset_ms, row.end_offset_ms)
            if value is not None
        ]
        if offsets:
            timing_residuals.append(_clamp(max(offsets) / 1800.0))

        if row.angle_difference_deg is not None:
            same_direction = (
                row.sensor_direction == row.visual_direction
                and row.sensor_direction not in {MotionDirection.NONE, MotionDirection.MIXED}
            )
            normalized = _clamp(float(row.angle_difference_deg) / 60.0)
            # Projective camera-angle estimates are approximate. If both sources agree on
            # physical direction, keep magnitude disagreement from dominating the anomaly score.
            angle_residuals.append(min(normalized, 0.55) if same_direction else normalized)

    fusion_disagreement = _median_or_zero(disagreements)
    timing_residual = _median_or_zero(timing_residuals)
    angle_residual = _median_or_zero(angle_residuals)
    environment_component = _clamp(environment_risk_score) * _clamp(environment_confidence)

    components = {
        "sensorAnomaly": _clamp(sensor_anomaly_score),
        "fusionDisagreement": fusion_disagreement,
        "timingResidual": timing_residual,
        "angleResidual": angle_residual,
        "duplicateFrames": _clamp(duplicate_frame_ratio),
        "locationRisk": _clamp(location_risk_score),
        "environmentRisk": environment_component,
    }
    weights = {
        "sensorAnomaly": 0.26,
        "fusionDisagreement": 0.26,
        "timingResidual": 0.14,
        "angleResidual": 0.10,
        "duplicateFrames": 0.10,
        "locationRisk": 0.09,
        "environmentRisk": 0.05,
    }
    score = _clamp(sum(components[name] * weights[name] for name in components))

    if score >= 0.70:
        status = "HIGH"
    elif score >= 0.42:
        status = "ELEVATED"
    else:
        status = "NOMINAL"

    codes: list[str] = []
    reasons: list[str] = []
    if components["sensorAnomaly"] >= 0.45:
        codes.append("STAT_SENSOR_OUTLIER")
        reasons.append("Sensor-stream anomaly features contributed materially to the statistical score.")
    if components["fusionDisagreement"] >= 0.55:
        codes.append("STAT_FUSION_OUTLIER")
        reasons.append("The median camera-to-inertial disagreement was unusually high.")
    if components["timingResidual"] >= 0.60:
        codes.append("STAT_TIMING_OUTLIER")
        reasons.append("Camera and sensor motion timing offsets were unusually large.")
    if components["duplicateFrames"] >= 0.35:
        codes.append("STAT_DUPLICATE_FRAME_OUTLIER")
        reasons.append("Repeated-frame behavior contributed to the statistical anomaly score.")
    if components["locationRisk"] >= 0.45:
        codes.append("STAT_LOCATION_OUTLIER")
        reasons.append("Location-risk features contributed to the statistical anomaly score.")
    if environment_component >= 0.45:
        codes.append("STAT_ENVIRONMENT_OUTLIER")
        reasons.append("A confident environment discontinuity contributed to the statistical anomaly score.")
    if not reasons:
        reasons.append("No robust within-session feature combination reached the elevated anomaly threshold.")

    available_features = 5 + int(bool(fusion_rows)) + int(environment_confidence > 0.0)
    confidence = min(0.92, 0.50 + 0.05 * available_features)
    return {
        "status": status,
        "score": score,
        "confidence": confidence,
        "reason_codes": codes,
        "reasons": reasons,
        "metrics": {
            "algorithmVersion": ALGORITHM_VERSION,
            "components": {name: round(value, 6) for name, value in components.items()},
            "weights": weights,
            "fusionRowCount": len(fusion_rows),
            "modelType": "DETERMINISTIC_ROBUST_STATISTICS",
            "trainedModelUsed": False,
            "replacesVerificationEngine": False,
        },
    }
