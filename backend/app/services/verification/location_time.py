from datetime import datetime, timezone

from app.core.config import get_settings
from app.models.challenge import VerificationChallenge
from app.models.trust import VerificationSignalStatus, VerificationSignalType
from app.models.verification import VerificationSession
from app.services.verification.domain import VerificationSignal, clamp01
from app.services.verification.policy import ResolvedPolicy


def _required(policy: ResolvedPolicy, kind: VerificationSignalType) -> bool:
    return kind.value in policy.required_signals


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def location_signal(session: VerificationSession, policy: ResolvedPolicy) -> VerificationSignal:
    kind = VerificationSignalType.LOCATION
    data = session.pre_capture_location or {}
    distance = data.get("distanceMeters", data.get("distance_meters"))
    radius = data.get("allowedRadiusMeters", data.get("allowed_radius_meters"))
    accuracy = data.get("accuracy_meters", data.get("accuracyMeters"))
    if not all(isinstance(value, (int, float)) for value in (distance, radius, accuracy)):
        return VerificationSignal(kind, VerificationSignalStatus.UNAVAILABLE, 0, 0, False, _required(policy, kind), ["Capture location evidence is unavailable."])

    distance, radius, accuracy = max(0.0, float(distance)), max(1.0, float(radius)), max(0.0, float(accuracy))
    preferred = get_settings().preferred_location_accuracy_meters
    unusable = max(150.0, radius * 2.0)
    if accuracy <= preferred:
        confidence = 1.0
    elif accuracy >= unusable:
        confidence = 0.20
    else:
        confidence = clamp01(1.0 - 0.8 * ((accuracy - preferred) / max(unusable - preferred, 1.0)))
    metrics = {"distanceMeters": round(distance, 2), "allowedRadiusMeters": round(radius, 2), "accuracyMeters": round(accuracy, 2)}
    if accuracy >= unusable:
        return VerificationSignal(kind, VerificationSignalStatus.INCONCLUSIVE, 0.5, confidence, True, _required(policy, kind), ["GPS uncertainty is too large for a reliable location decision."], metrics, "location-v1.0")
    if distance - accuracy > radius:
        if accuracy <= radius * 0.25:
            confidence = max(confidence, 0.80)
        return VerificationSignal(kind, VerificationSignalStatus.FAIL, 0, confidence, True, _required(policy, kind), ["Capture location is clearly outside the configured inspection radius."], metrics, "location-v1.0")
    if distance > radius:
        return VerificationSignal(kind, VerificationSignalStatus.PARTIAL, 0.5, confidence, True, _required(policy, kind), ["Capture location is near the boundary and GPS uncertainty overlaps the allowed radius."], metrics, "location-v1.0")
    score = 1.0 - 0.15 * min(1.0, distance / radius)
    return VerificationSignal(kind, VerificationSignalStatus.PASS, score, confidence, True, _required(policy, kind), [f"Capture was within the allowed location radius ({distance:.0f} m from target)."], metrics, "location-v1.0")


def session_time_signal(session: VerificationSession, challenges: list[VerificationChallenge], policy: ResolvedPolicy) -> VerificationSignal:
    kind = VerificationSignalType.SESSION_TIME
    if session.capture_started_at is None or session.capture_ended_at is None:
        return VerificationSignal(kind, VerificationSignalStatus.UNAVAILABLE, 0, 0, False, _required(policy, kind), ["Capture timing anchors are incomplete."])
    violations: list[str] = []
    notes: list[str] = []
    start, end = _aware(session.capture_started_at), _aware(session.capture_ended_at)
    if end <= start:
        violations.append("Capture end time does not follow capture start time.")
    deadline_text = (session.site_snapshot or {}).get("deadline")
    if deadline_text:
        try:
            if end > _aware(datetime.fromisoformat(str(deadline_text))):
                violations.append("Capture completed after the inspection deadline.")
        except ValueError:
            violations.append("Stored inspection deadline is malformed.")
    previous_completed = None
    for challenge in challenges:
        if challenge.started_at and challenge.completed_at:
            started, completed = _aware(challenge.started_at), _aware(challenge.completed_at)
            if completed < started or (previous_completed and started < previous_completed):
                violations.append("Challenge timestamps are not monotonically ordered.")
                break
            previous_completed = completed
    summary = session.location_summary or {}
    first = summary.get("first_relative_timestamp_ns", summary.get("firstRelativeTimestampNs"))
    last = summary.get("last_relative_timestamp_ns", summary.get("lastRelativeTimestampNs"))
    if isinstance(first, int) and isinstance(last, int) and last < first:
        violations.append("Location evidence timestamps are not monotonic.")
    offset = abs(float(session.clock_offset_ms or 0.0))
    if offset > 300_000:
        notes.append("Client wall clock differed substantially from server time; server timing remained authoritative.")
    metrics = {"clockOffsetMs": session.clock_offset_ms, "captureDurationMs": session.capture_duration_ms}
    if violations:
        return VerificationSignal(kind, VerificationSignalStatus.FAIL, 0, 0.95, True, _required(policy, kind), violations + notes, metrics, "session-time-v1.0")
    confidence = 0.95 if offset <= 300_000 else 0.75
    return VerificationSignal(kind, VerificationSignalStatus.PASS, 1, confidence, True, _required(policy, kind), ["Server-recorded capture and challenge timestamps were internally consistent."] + notes, metrics, "session-time-v1.0")
