import hashlib
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import pytest
from sqlalchemy import select

from app.models.challenge import ChallengeType, VerificationChallenge
from app.models.verification import (
    EvidenceFile,
    EvidenceFileType,
    EvidenceUploadStatus,
    VerificationSession,
    VerificationSessionStatus,
)
from app.models.visual_motion import VisualAnalysisStatus, VisualMotionResult
from app.services.storage_service import LocalObjectStorage
from app.services.visual_analysis_service import analyze_session_visual_motion
from tests.phase3_helpers import (
    create_ready_inspection,
    create_session,
    finish_capture,
    login,
    seed_identities,
    start_capture,
)


def _feature_image(width: int, height: int) -> np.ndarray:
    image = np.full((height, width, 3), 36, dtype=np.uint8)
    for y in range(24, height, 36):
        for x in range(24, width, 42):
            color = (80 + (x % 150), 90 + (y % 140), 210)
            cv2.circle(image, (x, y), 5, color, -1)
            cv2.rectangle(image, (x - 9, y - 9), (x + 9, y + 9), (235, 180, 70), 1)
    cv2.putText(
        image,
        "SITEPROOF REAL PIPELINE TEST",
        (35, height // 2),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (245, 245, 245),
        2,
        cv2.LINE_AA,
    )
    return image


def _movement_offset(
    challenges: list[tuple[ChallengeType, int, int]],
    time_ms: float,
) -> tuple[float, float]:
    x = 0.0
    y = 0.0
    amplitude = 45.0
    for challenge_type, start_ms, end_ms in challenges:
        if time_ms <= start_ms:
            progress = 0.0
        elif time_ms >= end_ms:
            progress = 1.0
        else:
            progress = (time_ms - start_ms) / float(end_ms - start_ms)
        delta = amplitude * progress
        if challenge_type == ChallengeType.ROTATE_RIGHT:
            x -= delta
        elif challenge_type == ChallengeType.ROTATE_LEFT:
            x += delta
        elif challenge_type == ChallengeType.TILT_UP:
            # Phase 5 v1.2+ labels rear-camera optical pitch: physical top-edge UP
            # (away from the user) is camera DOWN, so scene content moves upward.
            y -= delta
        elif challenge_type == ChallengeType.TILT_DOWN:
            # Physical top-edge DOWN (toward the user) is camera UP.
            y += delta
    return x, y


def _write_video(
    path: Path,
    challenges: list[tuple[ChallengeType, int, int]],
    *,
    duration_ms: int = 9000,
    fps: float = 10.0,
) -> None:
    width, height = 640, 360
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        pytest.skip("OpenCV build does not provide an MP4 test encoder")
    base = _feature_image(width, height)
    try:
        frame_count = int(duration_ms / 1000.0 * fps)
        for index in range(frame_count):
            time_ms = index / fps * 1000.0
            x, y = _movement_offset(challenges, time_ms)
            matrix = np.float32([[1, 0, x], [0, 1, y]])
            frame = cv2.warpAffine(
                base,
                matrix,
                (width, height),
                borderMode=cv2.BORDER_REFLECT,
            )
            writer.write(frame)
    finally:
        writer.release()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def test_visual_analysis_service_processes_stored_video_and_is_idempotent(
    client,
    db,
    tmp_path,
):
    identities = seed_identities(db)
    admin_headers = login(client, identities["admin"])
    inspector_headers = login(client, identities["inspector"])
    inspection_id = create_ready_inspection(
        client,
        admin_headers,
        inspector_headers,
        identities["profile"].id,
    )
    created = create_session(client, inspector_headers, inspection_id)
    assert created.status_code == 201, created.text
    session_id = created.json()["sessionId"]
    assert start_capture(client, inspector_headers, session_id).status_code == 200
    completed = finish_capture(client, inspector_headers, session_id)
    assert completed.status_code == 200, completed.text

    session = db.get(VerificationSession, session_id)
    assert session is not None
    assert session.capture_anchor_monotonic_ns is not None
    challenges = list(
        db.scalars(
            select(VerificationChallenge)
            .where(VerificationChallenge.session_id == session.id)
            .order_by(
                VerificationChallenge.sequence_number,
                VerificationChallenge.attempt_number,
            )
        ).all()
    )
    # Only the terminal attempt for each sequence belongs in the Android evidence timeline.
    terminal_by_sequence: dict[int, VerificationChallenge] = {}
    for challenge in challenges:
        terminal_by_sequence[challenge.sequence_number] = challenge
    terminal_challenges = [
        terminal_by_sequence[key] for key in sorted(terminal_by_sequence)
    ]
    assert len(terminal_challenges) == 3

    # API helpers execute challenges almost instantly in unit tests. Real phone challenges
    # are separated in time, and vision-v1.4 intentionally adds a 200 ms guard band around
    # each motion. Put synthetic challenges on realistic non-overlapping timeline slots so
    # one generated motion cannot contaminate another and make this test random/flaky.
    video_windows: list[tuple[ChallengeType, int, int]] = []
    metadata_challenges = []
    for index, challenge in enumerate(terminal_challenges):
        start_ms = 1000 + index * 2500
        end_ms = start_ms + 2000
        challenge.client_start_monotonic_ns = (
            session.capture_anchor_monotonic_ns + start_ms * 1_000_000
        )
        video_windows.append((challenge.challenge_type, start_ms, end_ms))
        metadata_challenges.append(
            {
                "id": str(challenge.id),
                "type": challenge.challenge_type.value,
                "issuedRelativeMs": max(0, start_ms - 50),
                "startedRelativeMs": start_ms,
                "completedRelativeMs": end_ms,
                "result": challenge.result.value if challenge.result else None,
            }
        )
    db.commit()

    video_path = tmp_path / "capture.mp4"
    _write_video(video_path, video_windows)
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(
        __import__("json").dumps(
            {
                "sessionId": str(session.id),
                "inspectionId": str(session.inspection_id),
                "capture": {
                    "durationMs": 9000,
                    "videoStartRelativeNs": 0,
                },
                "challenges": metadata_challenges,
            },
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    storage = LocalObjectStorage(str(tmp_path / "objects"))
    video_key = f"{session.organization_id}/{session.id}/capture.mp4"
    metadata_key = f"{session.organization_id}/{session.id}/metadata.json"
    storage.put_file(video_path, video_key, "video/mp4")
    storage.put_file(metadata_path, metadata_key, "application/json")

    now = datetime.now(timezone.utc)
    session.status = VerificationSessionStatus.UPLOADED
    session.uploaded_at = now
    session.capture_duration_ms = 9000
    db.add_all(
        [
            EvidenceFile(
                organization_id=session.organization_id,
                inspection_id=session.inspection_id,
                session_id=session.id,
                file_type=EvidenceFileType.VIDEO,
                storage_key=video_key,
                original_filename="capture.mp4",
                mime_type="video/mp4",
                size_bytes=video_path.stat().st_size,
                sha256=_sha256(video_path),
                upload_status=EvidenceUploadStatus.UPLOADED,
                hash_verified=True,
                uploaded_at=now,
            ),
            EvidenceFile(
                organization_id=session.organization_id,
                inspection_id=session.inspection_id,
                session_id=session.id,
                file_type=EvidenceFileType.SESSION_METADATA,
                storage_key=metadata_key,
                original_filename="metadata.json",
                mime_type="application/json",
                size_bytes=metadata_path.stat().st_size,
                sha256=_sha256(metadata_path),
                upload_status=EvidenceUploadStatus.UPLOADED,
                hash_verified=True,
                uploaded_at=now,
            ),
        ]
    )
    db.commit()

    analyze_session_visual_motion(db, session.id, storage=storage)
    db.refresh(session)
    assert session.status == VerificationSessionStatus.UPLOADED

    results = list(
        db.scalars(
            select(VisualMotionResult)
            .where(VisualMotionResult.session_id == session.id)
            .order_by(VisualMotionResult.created_at)
        ).all()
    )
    assert len(results) == 3
    assert all(
        result.analysis_status
        in {VisualAnalysisStatus.SUCCESS, VisualAnalysisStatus.INCONCLUSIVE}
        for result in results
    )
    assert any(
        result.analysis_status == VisualAnalysisStatus.SUCCESS for result in results
    )
    by_challenge = {result.challenge_id: result for result in results}
    for challenge in terminal_challenges:
        result = by_challenge[challenge.id]
        if result.analysis_status != VisualAnalysisStatus.SUCCESS:
            continue
        assert result.visual_confidence > 0.0
        assert result.feature_count > 0
        assert result.tracked_feature_count > 0
        assert result.diagnostics_json["timeline"]["videoStartRelativeMs"] == 0
        assert result.diagnostics_json["sampledFrames"] >= 2

    # Running the same version again without force must not create conflicting duplicates.
    analyze_session_visual_motion(db, session.id, storage=storage)
    count_after_second_run = len(
        list(
            db.scalars(
                select(VisualMotionResult).where(
                    VisualMotionResult.session_id == session.id
                )
            ).all()
        )
    )
    assert count_after_second_run == 3
