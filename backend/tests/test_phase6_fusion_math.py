import math

from app.core.config import Settings
from app.models.fusion import ConsistencyStatus, MismatchReason
from app.services.fusion.aggregator import decide_fusion
from app.services.fusion.comparators import (
    direction_consistency,
    duration_consistency,
    magnitude_consistency,
    temporal_consistency,
)
from app.services.fusion.domain import CurveComparison, MotionCurvePoint, MotionEstimate, MotionKind, MotionSource
from app.services.fusion.temporal import compare_motion_curves


def _motion(
    *,
    source: MotionSource,
    direction: str = "RIGHT",
    angle: float = 40.0,
    start: int = 4000,
    end: int = 5500,
    confidence: float = 0.9,
    quality: str = "GOOD",
    curve=(),
):
    return MotionEstimate(
        direction=direction,
        angular_change_deg=angle,
        start_ms=start,
        peak_ms=(start + end) // 2,
        end_ms=end,
        confidence=confidence,
        source=source,
        quality=quality,
        kind=MotionKind.ROTATION,
        curve=tuple(curve),
    )


def _curve(delay_ms: int = 0, scale: float = 1.0, noise: float = 0.0):
    values = [0.0, 0.1, 0.45, 1.0, 0.65, 0.2, 0.0]
    return tuple(
        MotionCurvePoint(
            time_ms=4000 + delay_ms + index * 100,
            value=max(0.0, value * scale + (noise * math.sin(index))),
        )
        for index, value in enumerate(values)
    )


def _decision(sensor, visual, settings=None, curves=None):
    settings = settings or Settings()
    magnitude = magnitude_consistency(sensor, visual, settings)
    timing = temporal_consistency(sensor, visual, settings)
    curve_result = curves or compare_motion_curves(
        sensor.curve,
        visual.curve,
        sample_hz=settings.fusion_resample_hz,
        max_lag_ms=settings.fusion_max_alignment_lag_ms,
    )
    return decide_fusion(
        sensor=sensor,
        visual=visual,
        direction_score=direction_consistency(sensor, visual),
        magnitude=magnitude,
        timing=timing,
        duration_score=duration_consistency(sensor, visual),
        curves=curve_result,
        settings=settings,
        scene_continuity_score=0.95,
        freeze_duration_ms=0,
    )


def test_direction_comparator_same_uncertain_and_opposite():
    sensor = _motion(source=MotionSource.SENSOR)
    assert direction_consistency(sensor, _motion(source=MotionSource.VISION)) == 1.0
    assert direction_consistency(
        sensor,
        _motion(source=MotionSource.VISION, direction="NONE"),
    ) == 0.5
    assert direction_consistency(
        sensor,
        _motion(source=MotionSource.VISION, direction="LEFT"),
    ) == 0.0


def test_magnitude_comparator_combines_absolute_and_relative_error():
    settings = Settings()
    sensor = _motion(source=MotionSource.SENSOR, angle=41.0)
    close = magnitude_consistency(
        sensor,
        _motion(source=MotionSource.VISION, angle=37.0),
        settings,
    )
    far = magnitude_consistency(
        sensor,
        _motion(source=MotionSource.VISION, angle=10.0),
        settings,
    )
    assert close.absolute_error_deg == 4.0
    assert close.relative_error is not None and 0.09 < close.relative_error < 0.10
    assert close.score is not None and close.score > 0.85
    assert far.score is not None and far.score < 0.35


def test_temporal_and_duration_comparators_keep_signed_offsets():
    settings = Settings()
    sensor = _motion(source=MotionSource.SENSOR, start=4200, end=5600)
    visual = _motion(source=MotionSource.VISION, start=4290, end=5710)
    timing = temporal_consistency(sensor, visual, settings)
    assert timing.start_offset_ms == 90
    assert timing.end_offset_ms == 110
    assert timing.score is not None and timing.score > 0.95
    assert duration_consistency(sensor, visual) >= 0.85


def test_limited_lag_cross_correlation_finds_delayed_visual_curve():
    settings = Settings(fusion_resample_hz=20, fusion_max_alignment_lag_ms=500)
    result = compare_motion_curves(
        _curve(),
        _curve(delay_ms=200, scale=0.7),
        sample_hz=settings.fusion_resample_hz,
        max_lag_ms=settings.fusion_max_alignment_lag_ms,
    )
    assert result.best_correlation is not None and result.best_correlation > 0.95
    assert result.best_lag_ms is not None
    assert abs(result.best_lag_ms - 200) <= 50


def test_perfect_and_noisy_legitimate_motion_are_not_unnecessarily_rejected():
    settings = Settings()
    sensor = _motion(source=MotionSource.SENSOR, angle=40.0, curve=_curve())
    visual = _motion(
        source=MotionSource.VISION,
        angle=38.0,
        start=4080,
        end=5580,
        curve=_curve(delay_ms=100, scale=0.8, noise=0.03),
    )
    decision = _decision(sensor, visual, settings)
    assert decision.consistency_status in {
        ConsistencyStatus.CONSISTENT.value,
        ConsistencyStatus.PARTIALLY_CONSISTENT.value,
    }
    assert decision.effective_consistency_score is not None
    assert decision.effective_consistency_score >= settings.fusion_partial_threshold


def test_high_confidence_poor_visual_label_remains_comparable_with_clean_scene():
    settings = Settings()
    sensor = _motion(source=MotionSource.SENSOR, angle=40.0, curve=_curve())
    visual = _motion(
        source=MotionSource.VISION,
        angle=37.0,
        start=4080,
        end=5580,
        confidence=0.88,
        quality="POOR",
        curve=_curve(delay_ms=100, scale=0.8),
    )
    decision = _decision(sensor, visual, settings)
    assert decision.consistency_status in {
        ConsistencyStatus.CONSISTENT.value,
        ConsistencyStatus.PARTIALLY_CONSISTENT.value,
    }
    assert MismatchReason.LOW_VISUAL_QUALITY.value in decision.mismatch_reasons
    assert decision.effective_consistency_score is not None
    assert decision.effective_consistency_score >= settings.fusion_partial_threshold


def test_high_confidence_opposite_direction_is_strong_mismatch():
    sensor = _motion(source=MotionSource.SENSOR, direction="RIGHT", curve=_curve())
    visual = _motion(source=MotionSource.VISION, direction="LEFT", angle=39, curve=_curve())
    decision = _decision(sensor, visual)
    assert decision.consistency_status == ConsistencyStatus.MISMATCH.value
    assert MismatchReason.OPPOSITE_DIRECTION.value in decision.mismatch_reasons
    assert decision.effective_consistency_score is not None
    assert decision.effective_consistency_score < Settings().fusion_partial_threshold


def test_visual_without_sensor_motion_is_structured_mismatch():
    sensor = _motion(source=MotionSource.SENSOR, angle=2.0, direction="NONE", curve=_curve(scale=0.05))
    visual = _motion(source=MotionSource.VISION, angle=40.0, direction="RIGHT", curve=_curve())
    decision = _decision(sensor, visual)
    assert decision.consistency_status == ConsistencyStatus.MISMATCH.value
    assert MismatchReason.VISUAL_WITHOUT_SENSOR_MOTION.value in decision.mismatch_reasons


def test_sensor_without_visual_motion_is_structured_mismatch_when_visual_quality_is_high():
    sensor = _motion(source=MotionSource.SENSOR, angle=40.0, direction="RIGHT", curve=_curve())
    visual = _motion(source=MotionSource.VISION, angle=2.0, direction="NONE", curve=_curve(scale=0.05))
    decision = _decision(sensor, visual)
    assert decision.consistency_status == ConsistencyStatus.MISMATCH.value
    assert MismatchReason.SENSOR_WITHOUT_VISUAL_MOTION.value in decision.mismatch_reasons


def test_low_visual_confidence_forces_inconclusive_not_accusation():
    sensor = _motion(source=MotionSource.SENSOR, angle=40.0, curve=_curve())
    visual = _motion(
        source=MotionSource.VISION,
        angle=2.0,
        direction="NONE",
        confidence=0.2,
        quality="POOR",
        curve=_curve(scale=0.05),
    )
    decision = _decision(sensor, visual)
    assert decision.consistency_status == ConsistencyStatus.INCONCLUSIVE.value
    assert MismatchReason.LOW_VISUAL_QUALITY.value in decision.mismatch_reasons


def test_large_timing_offset_is_reported():
    sensor = _motion(source=MotionSource.SENSOR, curve=_curve())
    visual = _motion(
        source=MotionSource.VISION,
        start=6500,
        end=8000,
        curve=_curve(delay_ms=2500),
    )
    decision = _decision(sensor, visual)
    assert MismatchReason.TEMPORAL_MISMATCH.value in decision.mismatch_reasons
    assert decision.consistency_status in {
        ConsistencyStatus.MISMATCH.value,
        ConsistencyStatus.PARTIALLY_CONSISTENT.value,
    }


def test_curve_unavailable_does_not_fake_a_correlation():
    sensor = _motion(source=MotionSource.SENSOR, curve=())
    visual = _motion(source=MotionSource.VISION, curve=())
    empty = CurveComparison(None, None, None)
    decision = _decision(sensor, visual, curves=empty)
    assert MismatchReason.CURVE_UNAVAILABLE.value in decision.mismatch_reasons
