from dataclasses import dataclass

import numpy as np

from app.services.fusion.domain import CurveComparison, MotionCurvePoint


@dataclass(frozen=True)
class ResampledCurves:
    times_ms: np.ndarray
    sensor_values: np.ndarray
    visual_values: np.ndarray


def normalize_curve(points: tuple[MotionCurvePoint, ...]) -> tuple[MotionCurvePoint, ...]:
    if len(points) < 2:
        return ()
    values = np.asarray([max(0.0, item.value) for item in points], dtype=float)
    baseline_count = max(1, min(len(values), max(2, int(round(len(values) * 0.15)))))
    baseline = float(np.median(values[:baseline_count]))
    adjusted = np.clip(values - baseline, 0.0, None)
    maximum = float(np.max(adjusted))
    if maximum <= 1e-9:
        return tuple(MotionCurvePoint(item.time_ms, 0.0) for item in points)
    normalized = adjusted / maximum
    return tuple(
        MotionCurvePoint(time_ms=item.time_ms, value=float(value))
        for item, value in zip(points, normalized, strict=True)
    )


def _pearson(left: np.ndarray, right: np.ndarray) -> float | None:
    if left.size < 3 or right.size < 3 or left.size != right.size:
        return None
    if float(np.std(left)) <= 1e-9 or float(np.std(right)) <= 1e-9:
        return None
    value = float(np.corrcoef(left, right)[0, 1])
    if not np.isfinite(value):
        return None
    return max(-1.0, min(1.0, value))


def _interpolate(
    points: tuple[MotionCurvePoint, ...],
    query_times: np.ndarray,
) -> np.ndarray:
    times = np.asarray([item.time_ms for item in points], dtype=float)
    values = np.asarray([item.value for item in points], dtype=float)
    return np.interp(query_times, times, values)


def resample_curves(
    sensor: tuple[MotionCurvePoint, ...],
    visual: tuple[MotionCurvePoint, ...],
    *,
    sample_hz: float,
    visual_lag_ms: int = 0,
) -> ResampledCurves | None:
    if len(sensor) < 2 or len(visual) < 2 or sample_hz <= 0:
        return None
    step_ms = 1000.0 / sample_hz
    sensor_start = sensor[0].time_ms
    sensor_end = sensor[-1].time_ms
    # A positive lag means visual motion occurred later. Compare sensor(t) with visual(t + lag).
    start = max(sensor_start, visual[0].time_ms - visual_lag_ms)
    end = min(sensor_end, visual[-1].time_ms - visual_lag_ms)
    if end - start < step_ms * 2:
        return None
    times = np.arange(float(start), float(end) + 0.1, step_ms)
    if times.size < 3:
        return None
    return ResampledCurves(
        times_ms=times,
        sensor_values=_interpolate(sensor, times),
        visual_values=_interpolate(visual, times + visual_lag_ms),
    )


def compare_motion_curves(
    sensor: tuple[MotionCurvePoint, ...],
    visual: tuple[MotionCurvePoint, ...],
    *,
    sample_hz: float,
    max_lag_ms: int,
) -> CurveComparison:
    sensor_norm = normalize_curve(sensor)
    visual_norm = normalize_curve(visual)
    aligned = resample_curves(sensor_norm, visual_norm, sample_hz=sample_hz)
    base_corr = _pearson(aligned.sensor_values, aligned.visual_values) if aligned else None

    if len(sensor_norm) < 2 or len(visual_norm) < 2:
        return CurveComparison(
            pearson_correlation=base_corr,
            best_correlation=base_corr,
            best_lag_ms=0 if base_corr is not None else None,
            sensor_curve=sensor_norm,
            visual_curve=visual_norm,
        )

    step_ms = max(1, int(round(1000.0 / sample_hz)))
    lags = range(-max_lag_ms, max_lag_ms + 1, step_ms)
    best_corr: float | None = None
    best_lag: int | None = None
    for lag in lags:
        candidate = resample_curves(
            sensor_norm,
            visual_norm,
            sample_hz=sample_hz,
            visual_lag_ms=lag,
        )
        if candidate is None:
            continue
        corr = _pearson(candidate.sensor_values, candidate.visual_values)
        if corr is None:
            continue
        if best_corr is None or corr > best_corr:
            best_corr = corr
            best_lag = lag

    return CurveComparison(
        pearson_correlation=base_corr,
        best_correlation=best_corr,
        best_lag_ms=best_lag,
        sensor_curve=sensor_norm,
        visual_curve=visual_norm,
    )
