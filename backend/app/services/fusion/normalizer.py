from statistics import fmean

from app.models.challenge import ChallengeType, VerificationChallenge
from app.models.fusion import MotionDirection
from app.models.visual_motion import VisualMotionResult
from app.services.fusion.domain import MotionCurvePoint, MotionEstimate, MotionKind, MotionSource


def motion_kind(challenge_type: ChallengeType) -> MotionKind:
    if challenge_type in {ChallengeType.ROTATE_LEFT, ChallengeType.ROTATE_RIGHT}:
        return MotionKind.ROTATION
    return MotionKind.TILT


def expected_direction(challenge_type: ChallengeType) -> MotionDirection:
    """Return the physical challenge direction used by Phase 4 sensor evidence."""
    return {
        ChallengeType.ROTATE_LEFT: MotionDirection.LEFT,
        ChallengeType.ROTATE_RIGHT: MotionDirection.RIGHT,
        ChallengeType.TILT_UP: MotionDirection.UP,
        ChallengeType.TILT_DOWN: MotionDirection.DOWN,
    }[challenge_type]


def opposite_direction(direction: MotionDirection) -> MotionDirection:
    return {
        MotionDirection.LEFT: MotionDirection.RIGHT,
        MotionDirection.RIGHT: MotionDirection.LEFT,
        MotionDirection.UP: MotionDirection.DOWN,
        MotionDirection.DOWN: MotionDirection.UP,
        MotionDirection.NONE: MotionDirection.NONE,
        MotionDirection.MIXED: MotionDirection.MIXED,
    }[direction]


def _uses_optical_tilt_labels(analysis_version: str) -> bool:
    """Phase 5 v1.2+ labels tilt using rear-camera optical pitch.

    The challenge name describes movement of the portrait phone's TOP EDGE, while the
    camera analyzer labels the rear-camera optical axis. Those are opposite for tilt:
    TILT_UP -> camera DOWN, TILT_DOWN -> camera UP. Fusion converts that representation
    back to the physical challenge convention before comparing it with sensor evidence.
    """
    prefix = "vision-v"
    if not analysis_version.startswith(prefix):
        return True
    try:
        return float(analysis_version[len(prefix) :]) >= 1.2
    except ValueError:
        return True


def normalize_visual_to_camera_motion(
    direction: str,
    *,
    challenge_type: ChallengeType,
    analysis_version: str,
) -> MotionDirection:
    try:
        normalized = MotionDirection(direction)
    except ValueError:
        return MotionDirection.NONE

    if (
        challenge_type in {ChallengeType.TILT_UP, ChallengeType.TILT_DOWN}
        and _uses_optical_tilt_labels(analysis_version)
        and normalized in {MotionDirection.UP, MotionDirection.DOWN}
    ):
        return opposite_direction(normalized)
    return normalized


def _peak(curve: tuple[MotionCurvePoint, ...]) -> int | None:
    if not curve:
        return None
    return max(curve, key=lambda item: item.value).time_ms


def normalize_sensor_motion(
    challenge: VerificationChallenge,
    *,
    curve: tuple[MotionCurvePoint, ...] = (),
    start_ms: int | None = None,
    end_ms: int | None = None,
    peak_ms: int | None = None,
    quality: str | None = None,
) -> MotionEstimate:
    metrics = challenge.metrics_json or {}
    values: list[float] = []
    gyro = metrics.get("observedGyroDegrees")
    rotation = metrics.get("observedRotationVectorDegrees")
    if isinstance(gyro, (int, float)):
        values.append(float(gyro))
    if isinstance(rotation, (int, float)):
        values.append(float(rotation))

    signed_relative_angle = fmean(values) if values else None
    expected = expected_direction(challenge.challenge_type)
    if signed_relative_angle is None or abs(signed_relative_angle) < 3.0:
        direction = MotionDirection.NONE
    elif signed_relative_angle > 0:
        direction = expected
    else:
        direction = opposite_direction(expected)

    gyro_quality = (challenge.sensor_quality_json or {}).get("gyroscope") or {}
    quality_value = quality or str(gyro_quality.get("quality") or "UNAVAILABLE")
    confidence = challenge.sensor_score
    if confidence is None:
        confidence = challenge.validation_score
    confidence = max(0.0, min(1.0, float(confidence or 0.0)))

    return MotionEstimate(
        direction=direction.value,
        angular_change_deg=abs(signed_relative_angle) if signed_relative_angle is not None else None,
        start_ms=start_ms,
        peak_ms=peak_ms if peak_ms is not None else _peak(curve),
        end_ms=end_ms,
        confidence=confidence,
        source=MotionSource.SENSOR,
        quality=quality_value,
        kind=motion_kind(challenge.challenge_type),
        curve=curve,
    )


def normalize_visual_motion(
    result: VisualMotionResult,
    challenge: VerificationChallenge,
) -> MotionEstimate:
    diagnostics = result.diagnostics_json or {}
    raw_curve = diagnostics.get("motionCurve") or []
    curve: list[MotionCurvePoint] = []
    for item in raw_curve:
        if not isinstance(item, dict):
            continue
        time_ms = item.get("timeMs")
        magnitude = item.get("magnitudePx")
        if isinstance(time_ms, (int, float)) and isinstance(magnitude, (int, float)):
            curve.append(
                MotionCurvePoint(
                    time_ms=int(round(time_ms)),
                    value=max(0.0, float(magnitude)),
                )
            )
    curve.sort(key=lambda item: item.time_ms)

    return MotionEstimate(
        direction=normalize_visual_to_camera_motion(
            result.visual_direction.value,
            challenge_type=challenge.challenge_type,
            analysis_version=result.analysis_version,
        ).value,
        angular_change_deg=(
            abs(float(result.estimated_rotation_degrees))
            if result.estimated_rotation_degrees is not None
            else None
        ),
        start_ms=result.motion_start_ms,
        peak_ms=_peak(tuple(curve)),
        end_ms=result.motion_end_ms,
        confidence=max(0.0, min(1.0, float(result.visual_confidence))),
        source=MotionSource.VISION,
        quality=result.visual_quality.value,
        kind=motion_kind(challenge.challenge_type),
        curve=tuple(curve),
    )
