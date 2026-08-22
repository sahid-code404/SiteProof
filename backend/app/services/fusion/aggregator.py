import math

from app.core.config import Settings
from app.models.fusion import ConsistencyStatus, MismatchReason
from app.services.fusion.comparators import MagnitudeComparison, TimingComparison
from app.services.fusion.domain import CurveComparison, FusionDecision, MotionEstimate


_POOR_VISUAL_OVERRIDE_MIN_CONFIDENCE = 0.75
_POOR_VISUAL_OVERRIDE_MIN_CONTINUITY = 0.85


def _weighted_score(
    components: dict[str, float | None],
    weights: dict[str, float],
) -> tuple[float | None, float]:
    available = [(name, value) for name, value in components.items() if value is not None]
    if not available:
        return None, 0.0
    available_weight = sum(weights[name] for name, _ in available)
    if available_weight <= 0:
        return None, 0.0
    score = sum(weights[name] * float(value) for name, value in available) / available_weight
    return max(0.0, min(1.0, score)), min(1.0, available_weight)


def _source_confidence(sensor_confidence: float, visual_confidence: float, coverage: float) -> float:
    sensor = max(0.0, min(1.0, sensor_confidence))
    visual = max(0.0, min(1.0, visual_confidence))
    geometric = math.sqrt(sensor * visual)
    weakest = min(sensor, visual)
    # Confidence is intentionally separate from consistency. It combines source support,
    # the weaker source, and how much of the configured comparison could actually be used.
    return max(0.0, min(1.0, 0.60 * geometric + 0.25 * weakest + 0.15 * coverage))


def decide_fusion(
    *,
    sensor: MotionEstimate,
    visual: MotionEstimate,
    direction_score: float | None,
    magnitude: MagnitudeComparison,
    timing: TimingComparison,
    duration_score: float | None,
    curves: CurveComparison,
    settings: Settings,
    scene_continuity_score: float,
    freeze_duration_ms: int,
    sensor_input_valid: bool = True,
    visual_input_valid: bool = True,
) -> FusionDecision:
    mismatch: list[str] = []
    explanations: list[str] = []

    components = {
        "direction": direction_score,
        "magnitude": magnitude.score,
        "timing": timing.score,
        "correlation": (
            max(0.0, min(1.0, curves.best_correlation))
            if curves.best_correlation is not None
            else None
        ),
        "duration": duration_score,
    }
    raw, coverage = _weighted_score(components, settings.fusion_score_weights)
    fusion_confidence = _source_confidence(sensor.confidence, visual.confidence, coverage)

    continuity_anomaly = (
        scene_continuity_score < settings.fusion_min_scene_continuity_score
        or freeze_duration_ms >= settings.fusion_scene_freeze_warning_ms
    )
    recoverable_poor_visual = (
        visual_input_valid
        and visual.quality == "POOR"
        and visual.confidence >= _POOR_VISUAL_OVERRIDE_MIN_CONFIDENCE
        and scene_continuity_score >= _POOR_VISUAL_OVERRIDE_MIN_CONTINUITY
        and freeze_duration_ms < settings.fusion_scene_freeze_warning_ms
    )

    low_sensor = (
        not sensor_input_valid
        or sensor.confidence < settings.fusion_min_sensor_confidence
        or sensor.quality == "UNAVAILABLE"
    )
    low_visual = (
        not visual_input_valid
        or visual.confidence < settings.fusion_min_visual_confidence
        or (visual.quality == "POOR" and not recoverable_poor_visual)
    )
    if low_sensor:
        mismatch.append(MismatchReason.LOW_SENSOR_QUALITY.value)
    if low_visual or recoverable_poor_visual:
        mismatch.append(MismatchReason.LOW_VISUAL_QUALITY.value)

    if recoverable_poor_visual:
        # The Phase 5 POOR label includes photometric sharpness/brightness checks. A clean,
        # high-confidence, continuous RANSAC motion estimate remains usable for consistency
        # comparison, but the warning is retained and confidence is slightly attenuated.
        fusion_confidence *= 0.95
        explanations.append(
            "Visual image quality was labeled poor, but motion confidence and scene "
            "continuity were strong enough to keep the camera signal comparable."
        )

    if continuity_anomaly:
        mismatch.append(MismatchReason.SCENE_CONTINUITY_ANOMALY.value)
        # Continuity is supporting evidence only; it lowers confidence rather than deciding
        # the cross-signal state by itself.
        fusion_confidence *= 0.90

    if curves.best_correlation is None:
        mismatch.append(MismatchReason.CURVE_UNAVAILABLE.value)

    high_confidence_pair = (
        sensor.confidence >= settings.fusion_strong_contradiction_confidence
        and visual.confidence >= settings.fusion_strong_contradiction_confidence
    )
    opposite = (
        sensor.direction not in {"NONE", "MIXED"}
        and visual.direction not in {"NONE", "MIXED"}
        and sensor.direction != visual.direction
    )
    if opposite and high_confidence_pair:
        mismatch.append(MismatchReason.OPPOSITE_DIRECTION.value)

    sensor_angle = sensor.angular_change_deg or 0.0
    visual_angle = visual.angular_change_deg or 0.0
    sensor_motion_absent = (
        sensor.direction == "NONE"
        and sensor_angle <= settings.fusion_motion_floor_deg
    )
    visual_motion_absent = (
        visual.direction == "NONE"
        and visual_angle <= settings.fusion_motion_floor_deg
    )
    if high_confidence_pair:
        # A low degree estimate by itself is not proof that a source saw no movement.
        # Stabilization and the approximate camera-FOV conversion can compress visual angle
        # magnitude while still leaving a coherent, correctly directed motion track. Reserve
        # the blocking "without motion" reasons for cases where the weak source also reports
        # no reliable direction. Large magnitude disagreement remains available separately as
        # MAGNITUDE_MISMATCH and can lower the consistency score without creating a false hard rule.
        if sensor_motion_absent and visual_angle >= settings.fusion_large_motion_deg:
            mismatch.append(MismatchReason.VISUAL_WITHOUT_SENSOR_MOTION.value)
        if visual_motion_absent and sensor_angle >= settings.fusion_large_motion_deg:
            mismatch.append(MismatchReason.SENSOR_WITHOUT_VISUAL_MOTION.value)

    if (
        magnitude.absolute_error_deg is not None
        and magnitude.absolute_error_deg > settings.fusion_max_angle_error_deg
    ):
        mismatch.append(MismatchReason.MAGNITUDE_MISMATCH.value)
    if any(
        offset is not None and abs(offset) > settings.fusion_timing_weak_ms
        for offset in (timing.start_offset_ms, timing.end_offset_ms)
    ):
        mismatch.append(MismatchReason.TEMPORAL_MISMATCH.value)
    if duration_score is not None and duration_score < settings.fusion_duration_mismatch_score:
        mismatch.append(MismatchReason.DURATION_MISMATCH.value)

    # Deduplicate while preserving diagnostic order.
    mismatch = list(dict.fromkeys(mismatch))

    if sensor.direction == visual.direction and sensor.direction not in {"NONE", "MIXED"}:
        explanations.append(
            f"Both sources detected {sensor.direction.lower()} physical camera movement."
        )
    elif opposite:
        explanations.append(
            f"Sensor motion was {sensor.direction.lower()} while camera motion was {visual.direction.lower()}."
        )
    if magnitude.absolute_error_deg is not None:
        explanations.append(
            f"Angular estimates differed by {magnitude.absolute_error_deg:.1f} degrees."
        )
    if timing.start_offset_ms is not None:
        explanations.append(
            f"Detected movement start times were {abs(timing.start_offset_ms)} ms apart."
        )
    if curves.best_correlation is not None:
        explanations.append(
            f"Normalized motion curves had {curves.best_correlation:.2f} best correlation "
            f"at {curves.best_lag_ms or 0:+d} ms lag."
        )

    if low_sensor or low_visual:
        status = ConsistencyStatus.INCONCLUSIVE
        effective = raw
        explanations.append("Source quality is insufficient for a reliable cross-signal decision.")
    elif any(
        reason in mismatch
        for reason in (
            MismatchReason.OPPOSITE_DIRECTION.value,
            MismatchReason.VISUAL_WITHOUT_SENSOR_MOTION.value,
            MismatchReason.SENSOR_WITHOUT_VISUAL_MOTION.value,
        )
    ):
        status = ConsistencyStatus.MISMATCH
        contradiction_cap = max(0.0, settings.fusion_partial_threshold - 0.01)
        effective = min(raw, contradiction_cap) if raw is not None else 0.0
        explanations.append("High-confidence sensor and visual evidence contain a strong contradiction.")
    elif raw is None:
        status = ConsistencyStatus.INCONCLUSIVE
        effective = None
        explanations.append("Insufficient comparable motion metrics were available.")
    else:
        # Source confidence moderately attenuates the numeric score without conflating
        # measurement agreement and confidence into one opaque number.
        effective = max(0.0, min(1.0, raw * (0.80 + 0.20 * fusion_confidence)))
        if effective >= settings.fusion_pass_threshold:
            status = ConsistencyStatus.CONSISTENT
        elif effective >= settings.fusion_partial_threshold:
            status = ConsistencyStatus.PARTIALLY_CONSISTENT
        else:
            status = ConsistencyStatus.MISMATCH

    return FusionDecision(
        consistency_status=status.value,
        raw_consistency_score=raw,
        effective_consistency_score=effective,
        fusion_confidence=max(0.0, min(1.0, fusion_confidence)),
        mismatch_reasons=tuple(mismatch),
        explanations=tuple(explanations),
        diagnostics={
            "componentCoverage": round(coverage, 4),
            "componentScores": {
                name: round(value, 4) if value is not None else None
                for name, value in components.items()
            },
        },
    )
