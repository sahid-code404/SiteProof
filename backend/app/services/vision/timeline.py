from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ChallengeVideoWindow:
    challenge_id: str
    challenge_type: str
    challenge_start_session_ms: int
    challenge_end_session_ms: int
    analysis_start_session_ms: int
    analysis_end_session_ms: int
    video_start_ms: int
    video_end_ms: int


def video_start_relative_ms(metadata: dict[str, Any]) -> int:
    capture = metadata.get("capture") or {}
    value = capture.get("videoStartRelativeNs")
    if value is None:
        raise ValueError("Evidence metadata does not contain videoStartRelativeNs")
    value = int(value)
    if value < 0:
        raise ValueError("videoStartRelativeNs cannot be negative")
    return value // 1_000_000


def challenge_metadata_by_id(metadata: dict[str, Any]) -> dict[str, dict[str, Any]]:
    items = metadata.get("challenges")
    if not isinstance(items, list):
        raise ValueError("Evidence metadata does not contain a challenge timeline")
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        result[str(item["id"])] = item
    return result


def map_challenge_window(
    metadata: dict[str, Any],
    *,
    challenge_id: str,
    challenge_type: str,
    pre_padding_ms: int,
    post_padding_ms: int,
    video_duration_ms: int,
) -> ChallengeVideoWindow:
    challenge_item = challenge_metadata_by_id(metadata).get(challenge_id)
    if challenge_item is None:
        raise ValueError(f"Challenge {challenge_id} is missing from evidence metadata")

    start_value = challenge_item.get("startedRelativeMs", challenge_item.get("issuedRelativeMs"))
    end_value = challenge_item.get("completedRelativeMs")
    if start_value is None or end_value is None:
        raise ValueError(f"Challenge {challenge_id} does not have a complete monotonic time window")

    challenge_start = int(start_value)
    challenge_end = int(end_value)
    if challenge_start < 0 or challenge_end <= challenge_start:
        raise ValueError(f"Challenge {challenge_id} has an invalid monotonic time window")

    video_offset_ms = video_start_relative_ms(metadata)
    analysis_start_session = max(0, challenge_start - max(0, pre_padding_ms))
    analysis_end_session = challenge_end + max(0, post_padding_ms)
    video_start = max(0, analysis_start_session - video_offset_ms)
    video_end = min(video_duration_ms, analysis_end_session - video_offset_ms)
    if video_end <= video_start:
        raise ValueError(f"Challenge {challenge_id} does not overlap the uploaded video")

    return ChallengeVideoWindow(
        challenge_id=challenge_id,
        challenge_type=challenge_type,
        challenge_start_session_ms=challenge_start,
        challenge_end_session_ms=challenge_end,
        analysis_start_session_ms=analysis_start_session,
        analysis_end_session_ms=analysis_end_session,
        video_start_ms=video_start,
        video_end_ms=video_end,
    )


def validate_client_server_start_alignment(
    *,
    capture_anchor_monotonic_ns: int | None,
    challenge_client_start_monotonic_ns: int | None,
    challenge_started_relative_ms: int,
    tolerance_ms: int,
) -> float | None:
    if capture_anchor_monotonic_ns is None or challenge_client_start_monotonic_ns is None:
        return None
    server_relative_ms = (
        challenge_client_start_monotonic_ns - capture_anchor_monotonic_ns
    ) / 1_000_000.0
    difference_ms = abs(server_relative_ms - challenge_started_relative_ms)
    if difference_ms > tolerance_ms:
        raise ValueError(
            "Challenge/client video timeline mismatch: "
            f"difference {difference_ms:.1f} ms exceeds {tolerance_ms} ms"
        )
    return difference_ms
