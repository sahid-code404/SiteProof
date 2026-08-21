from dataclasses import dataclass

from app.core.config import Settings
from app.services.fusion.domain import MotionEstimate


@dataclass(frozen=True)
class MagnitudeComparison:
    score: float | None
    absolute_error_deg: float | None
    relative_error: float | None


@dataclass(frozen=True)
class TimingComparison:
    score: float | None
    start_offset_ms: int | None
    end_offset_ms: int | None


def direction_consistency(sensor: MotionEstimate, visual: MotionEstimate) -> float | None:
    if sensor.direction in {"NONE", "MIXED"} or visual.direction in {"NONE", "MIXED"}:
        return 0.5
    if not sensor.direction or not visual.direction:
        return None
    return 1.0 if sensor.direction == visual.direction else 0.0


def _absolute_angle_score(error: float, settings: Settings) -> float:
    strong = max(0.1, settings.fusion_strong_angle_error_deg)
    maximum = max(strong + 0.1, settings.fusion_max_angle_error_deg)
    if error <= strong:
        return 1.0
    if error >= maximum:
        return 0.0
    return max(0.0, 1.0 - (error - strong) / (maximum - strong))


def magnitude_consistency(
    sensor: MotionEstimate,
    visual: MotionEstimate,
    settings: Settings,
) -> MagnitudeComparison:
    if sensor.angular_change_deg is None or visual.angular_change_deg is None:
        return MagnitudeComparison(None, None, None)
    error = abs(sensor.angular_change_deg - visual.angular_change_deg)
    relative = error / max(abs(sensor.angular_change_deg), 1.0)
    absolute_score = _absolute_angle_score(error, settings)
    relative_score = max(0.0, 1.0 - relative / max(settings.fusion_relative_angle_error_full_penalty, 0.01))
    # Absolute error is more stable for the 25–55° challenge range; relative error is a
    # secondary guard for unexpectedly small/large movements.
    score = 0.70 * absolute_score + 0.30 * relative_score
    return MagnitudeComparison(max(0.0, min(1.0, score)), error, relative)


def _timing_piecewise(value_ms: int, settings: Settings) -> float:
    value = abs(value_ms)
    if value <= settings.fusion_timing_excellent_ms:
        return 1.0
    if value <= settings.fusion_timing_good_ms:
        span = max(1, settings.fusion_timing_good_ms - settings.fusion_timing_excellent_ms)
        return 1.0 - 0.20 * (value - settings.fusion_timing_excellent_ms) / span
    if value <= settings.fusion_timing_weak_ms:
        span = max(1, settings.fusion_timing_weak_ms - settings.fusion_timing_good_ms)
        return 0.80 - 0.45 * (value - settings.fusion_timing_good_ms) / span
    return max(0.0, 0.35 * (1.0 - (value - settings.fusion_timing_weak_ms) / max(settings.fusion_timing_weak_ms, 1)))


def temporal_consistency(
    sensor: MotionEstimate,
    visual: MotionEstimate,
    settings: Settings,
) -> TimingComparison:
    start_offset = (
        visual.start_ms - sensor.start_ms
        if sensor.start_ms is not None and visual.start_ms is not None
        else None
    )
    end_offset = (
        visual.end_ms - sensor.end_ms
        if sensor.end_ms is not None and visual.end_ms is not None
        else None
    )
    values = [
        _timing_piecewise(offset, settings)
        for offset in (start_offset, end_offset)
        if offset is not None
    ]
    score = sum(values) / len(values) if values else None
    return TimingComparison(score, start_offset, end_offset)


def duration_consistency(sensor: MotionEstimate, visual: MotionEstimate) -> float | None:
    sensor_duration = sensor.duration_ms
    visual_duration = visual.duration_ms
    if sensor_duration is None or visual_duration is None:
        return None
    error = abs(sensor_duration - visual_duration)
    relative = error / max(sensor_duration, visual_duration, 1)
    if relative <= 0.15:
        return 1.0
    if relative <= 0.30:
        return 0.85
    if relative <= 0.60:
        return 0.45
    return max(0.0, 1.0 - relative)


def correlation_consistency(correlation: float | None) -> float | None:
    if correlation is None:
        return None
    # Only positive shape correlation is evidence of agreement. Zero/negative correlation
    # is not rewarded with a neutral 0.5.
    return max(0.0, min(1.0, correlation))
