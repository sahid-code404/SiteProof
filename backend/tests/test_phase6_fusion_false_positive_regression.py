from app.core.config import Settings
from app.models.fusion import ConsistencyStatus, MismatchReason
from app.services.fusion.aggregator import decide_fusion
from app.services.fusion.comparators import (
    direction_consistency,
    duration_consistency,
    magnitude_consistency,
    temporal_consistency,
)
from app.services.fusion.domain import CurveComparison, MotionEstimate, MotionKind, MotionSource


def _motion(*, source: MotionSource, direction: str, angle: float) -> MotionEstimate:
    return MotionEstimate(
        direction=direction,
        angular_change_deg=angle,
        start_ms=1000,
        peak_ms=1500,
        end_ms=2000,
        confidence=0.90,
        source=source,
        quality="GOOD",
        kind=MotionKind.ROTATION,
        curve=(),
    )


def _decision(sensor: MotionEstimate, visual: MotionEstimate):
    settings = Settings()
    return decide_fusion(
        sensor=sensor,
        visual=visual,
        direction_score=direction_consistency(sensor, visual),
        magnitude=magnitude_consistency(sensor, visual, settings),
        timing=temporal_consistency(sensor, visual, settings),
        duration_score=duration_consistency(sensor, visual),
        curves=CurveComparison(None, None, None),
        settings=settings,
        scene_continuity_score=0.95,
        freeze_duration_ms=0,
    )


def test_small_but_coherent_visual_angle_is_not_treated_as_no_visual_motion():
    sensor = _motion(source=MotionSource.SENSOR, direction="RIGHT", angle=35.0)
    visual = _motion(source=MotionSource.VISION, direction="RIGHT", angle=3.5)

    decision = _decision(sensor, visual)

    assert MismatchReason.SENSOR_WITHOUT_VISUAL_MOTION.value not in decision.mismatch_reasons
    assert MismatchReason.OPPOSITE_DIRECTION.value not in decision.mismatch_reasons
    assert MismatchReason.MAGNITUDE_MISMATCH.value in decision.mismatch_reasons


def test_small_but_coherent_sensor_angle_is_not_treated_as_no_sensor_motion():
    sensor = _motion(source=MotionSource.SENSOR, direction="RIGHT", angle=3.5)
    visual = _motion(source=MotionSource.VISION, direction="RIGHT", angle=35.0)

    decision = _decision(sensor, visual)

    assert MismatchReason.VISUAL_WITHOUT_SENSOR_MOTION.value not in decision.mismatch_reasons
    assert MismatchReason.OPPOSITE_DIRECTION.value not in decision.mismatch_reasons
    assert MismatchReason.MAGNITUDE_MISMATCH.value in decision.mismatch_reasons


def test_true_missing_visual_motion_still_blocks_high_confidence_sensor_motion():
    sensor = _motion(source=MotionSource.SENSOR, direction="RIGHT", angle=35.0)
    visual = _motion(source=MotionSource.VISION, direction="NONE", angle=2.0)

    decision = _decision(sensor, visual)

    assert decision.consistency_status == ConsistencyStatus.MISMATCH.value
    assert MismatchReason.SENSOR_WITHOUT_VISUAL_MOTION.value in decision.mismatch_reasons


def test_true_opposite_direction_remains_a_strong_contradiction():
    sensor = _motion(source=MotionSource.SENSOR, direction="RIGHT", angle=35.0)
    visual = _motion(source=MotionSource.VISION, direction="LEFT", angle=34.0)

    decision = _decision(sensor, visual)

    assert decision.consistency_status == ConsistencyStatus.MISMATCH.value
    assert MismatchReason.OPPOSITE_DIRECTION.value in decision.mismatch_reasons
