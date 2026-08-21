import gzip
import io
import json
from dataclasses import dataclass

from app.core.config import Settings
from app.models.challenge import ChallengeType, VerificationChallenge
from app.models.verification import EvidenceFile
from app.services.fusion.domain import MotionCurvePoint
from app.services.storage_service import StorageService


@dataclass(frozen=True)
class RawGyroSample:
    time_ms: int
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class SensorCurveExtraction:
    curve: tuple[MotionCurvePoint, ...]
    start_ms: int | None
    peak_ms: int | None
    end_ms: int | None
    sample_count: int
    max_gap_ms: float | None
    quality: str


def load_gyroscope_samples(
    storage: StorageService,
    record: EvidenceFile,
    settings: Settings,
) -> tuple[RawGyroSample, ...]:
    compressed = storage.read_bytes(record.storage_key, max_bytes=settings.max_sensor_bytes)
    output: list[RawGyroSample] = []
    decompressed_bytes = 0
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(compressed), mode="rb") as handle:
            for raw_line in handle:
                decompressed_bytes += len(raw_line)
                if decompressed_bytes > settings.fusion_max_sensor_uncompressed_bytes:
                    raise ValueError("Decompressed sensor evidence exceeds the Phase 6 safety limit")
                if not raw_line.strip():
                    continue
                try:
                    item = json.loads(raw_line.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise ValueError("Sensor evidence contains invalid NDJSON") from exc
                if item.get("type") != "GYROSCOPE":
                    continue
                timestamp_ns = item.get("relativeTimestampNs")
                values = item.get("values")
                if not isinstance(timestamp_ns, int) or not isinstance(values, list) or len(values) < 3:
                    raise ValueError("Gyroscope evidence contains an invalid sample")
                if not all(isinstance(value, (int, float)) for value in values[:3]):
                    raise ValueError("Gyroscope evidence contains non-numeric values")
                output.append(
                    RawGyroSample(
                        time_ms=int(round(timestamp_ns / 1_000_000.0)),
                        x=float(values[0]),
                        y=float(values[1]),
                        z=float(values[2]),
                    )
                )
    except OSError as exc:
        raise ValueError("Sensor evidence is not valid gzip data") from exc

    output.sort(key=lambda item: item.time_ms)
    return tuple(output)


def _axis_and_sign(challenge: VerificationChallenge, settings: Settings) -> tuple[int, float]:
    if challenge.challenge_type in {ChallengeType.ROTATE_LEFT, ChallengeType.ROTATE_RIGHT}:
        sign = settings.rotation_right_sign
        if challenge.challenge_type == ChallengeType.ROTATE_LEFT:
            sign *= -1.0
        return 1, sign
    sign = settings.tilt_down_sign
    if challenge.challenge_type == ChallengeType.TILT_UP:
        sign *= -1.0
    return 0, sign


def _axis_value(sample: RawGyroSample, index: int) -> float:
    return (sample.x, sample.y, sample.z)[index]


def extract_sensor_curve(
    samples: tuple[RawGyroSample, ...],
    *,
    challenge: VerificationChallenge,
    window_start_ms: int,
    window_end_ms: int,
    settings: Settings,
) -> SensorCurveExtraction:
    selected = [
        item for item in samples if window_start_ms <= item.time_ms <= window_end_ms
    ]
    if len(selected) < 3:
        return SensorCurveExtraction((), None, None, None, len(selected), None, "UNAVAILABLE")

    axis_index, expected_sign = _axis_and_sign(challenge, settings)
    baseline_end = window_start_ms + settings.challenge_baseline_ms
    baseline_values = [
        _axis_value(item, axis_index)
        for item in selected
        if item.time_ms <= baseline_end
    ]
    bias = sum(baseline_values) / len(baseline_values) if baseline_values else 0.0

    signed_rates = [
        (item.time_ms, (_axis_value(item, axis_index) - bias) * expected_sign)
        for item in selected
    ]
    curve = tuple(
        MotionCurvePoint(time_ms=time_ms, value=abs(rate))
        for time_ms, rate in signed_rates
    )
    gaps = [
        right.time_ms - left.time_ms for left, right in zip(selected, selected[1:])
    ]
    max_gap = float(max(gaps)) if gaps else 0.0
    quality = "GOOD" if len(selected) >= settings.challenge_min_gyro_samples and max_gap <= 150 else "DEGRADED"

    threshold = settings.challenge_movement_threshold_rad_s
    settle_threshold = settings.challenge_settle_threshold_rad_s
    active_indices = [
        index for index, (_, rate) in enumerate(signed_rates) if abs(rate) >= threshold
    ]
    if not active_indices:
        peak = max(curve, key=lambda item: item.value).time_ms if curve else None
        return SensorCurveExtraction(curve, None, peak, None, len(selected), max_gap, quality)

    onset = active_indices[0]
    end = active_indices[-1]
    settle_ms = settings.challenge_settling_ms
    settled_end: int | None = None
    for index in range(onset + 1, len(signed_rates)):
        if abs(signed_rates[index][1]) > settle_threshold:
            continue
        settle_start = signed_rates[index][0]
        cursor = index
        while cursor < len(signed_rates) and abs(signed_rates[cursor][1]) <= settle_threshold:
            if signed_rates[cursor][0] - settle_start >= settle_ms:
                settled_end = cursor
                break
            cursor += 1
        if settled_end is not None:
            end = settled_end
            break

    peak = max(curve[onset : end + 1], key=lambda item: item.value).time_ms
    return SensorCurveExtraction(
        curve=curve,
        start_ms=signed_rates[onset][0],
        peak_ms=peak,
        end_ms=signed_rates[end][0],
        sample_count=len(selected),
        max_gap_ms=max_gap,
        quality=quality,
    )


def challenge_window_ms(
    challenge: VerificationChallenge,
    visual_diagnostics: dict,
    *,
    capture_anchor_monotonic_ns: int | None,
    fallback_window_ms: int = 8000,
) -> tuple[int, int]:
    timeline = visual_diagnostics.get("timeline") if isinstance(visual_diagnostics, dict) else None
    if isinstance(timeline, dict):
        video_offset = timeline.get("videoStartRelativeMs")
        analysis_start = timeline.get("analysisVideoStartMs")
        analysis_end = timeline.get("analysisVideoEndMs")
        if (
            isinstance(video_offset, (int, float))
            and isinstance(analysis_start, (int, float))
            and isinstance(analysis_end, (int, float))
            and analysis_end > analysis_start
        ):
            return (
                int(round(video_offset + analysis_start)),
                int(round(video_offset + analysis_end)),
            )
        start = timeline.get("challengeStartSessionMs")
        end = timeline.get("challengeEndSessionMs")
        if isinstance(start, (int, float)) and isinstance(end, (int, float)) and end > start:
            return int(round(start)), int(round(end))

    if capture_anchor_monotonic_ns is None or challenge.client_start_monotonic_ns is None:
        raise ValueError("Challenge timing cannot be aligned to the session sensor timeline")
    start = int(round((challenge.client_start_monotonic_ns - capture_anchor_monotonic_ns) / 1_000_000.0))
    return start, start + fallback_window_ms
