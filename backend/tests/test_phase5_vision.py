from pathlib import Path

import cv2
import numpy as np
import pytest

from app.core.config import Settings
from app.models.challenge import ChallengeType
from app.models.visual_motion import VisualAnalysisStatus, VisualDirection
from app.services.vision.continuity import analyze_continuity
from app.services.vision.domain import VisualFrame
from app.services.vision.motion_estimator import estimate_global_motion
from app.services.vision.optical_flow import FlowTracks
from app.services.vision.timeline import map_challenge_window, validate_client_server_start_alignment
from app.services.vision.video_reader import VideoDecodeError, inspect_video, sample_window
from app.services.vision.visual_challenge_analyzer import analyze_visual_challenge


def _feature_image(width: int = 640, height: int = 360) -> np.ndarray:
    image = np.full((height, width, 3), 32, dtype=np.uint8)
    for y in range(30, height, 45):
        for x in range(30, width, 50):
            value = 100 + ((x + y) % 140)
            cv2.circle(image, (x, y), 6, (value, 255 - value // 2, 180), -1)
            cv2.rectangle(image, (x - 11, y - 11), (x + 11, y + 11), (220, 90, value), 1)
    cv2.putText(
        image,
        "SITEPROOF PHASE 5",
        (80, height // 2),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.0,
        (240, 240, 240),
        2,
        cv2.LINE_AA,
    )
    return image


def _translated_frames(dx_per_frame: float, dy_per_frame: float) -> list[VisualFrame]:
    base = _feature_image()
    height, width = base.shape[:2]
    frames: list[VisualFrame] = []
    for index in range(8):
        matrix = np.float32([[1, 0, dx_per_frame * index], [0, 1, dy_per_frame * index]])
        image = cv2.warpAffine(base, matrix, (width, height), borderMode=cv2.BORDER_REFLECT)
        frames.append(
            VisualFrame(
                frame_index=index,
                video_time_ms=index * 100,
                session_time_ms=1000 + index * 100,
                image=image,
            )
        )
    return frames


def _rotated_frames(total_degrees: float) -> list[VisualFrame]:
    base = _feature_image()
    height, width = base.shape[:2]
    center = (width / 2.0, height / 2.0)
    frames: list[VisualFrame] = []
    for index in range(8):
        angle = total_degrees * index / 7.0
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        image = cv2.warpAffine(base, matrix, (width, height), borderMode=cv2.BORDER_REFLECT)
        frames.append(
            VisualFrame(
                frame_index=index,
                video_time_ms=index * 100,
                session_time_ms=2000 + index * 100,
                image=image,
            )
        )
    return frames


def test_challenge_window_maps_common_monotonic_timeline_to_video():
    metadata = {
        "capture": {"videoStartRelativeNs": 20_000_000},
        "challenges": [
            {
                "id": "challenge-1",
                "type": "ROTATE_RIGHT",
                "issuedRelativeMs": 4100,
                "startedRelativeMs": 4200,
                "completedRelativeMs": 5900,
            }
        ],
    }
    window = map_challenge_window(
        metadata,
        challenge_id="challenge-1",
        challenge_type="ROTATE_RIGHT",
        pre_padding_ms=500,
        post_padding_ms=500,
        video_duration_ms=10_000,
    )
    assert window.analysis_start_session_ms == 3700
    assert window.analysis_end_session_ms == 6400
    assert window.video_start_ms == 3680
    assert window.video_end_ms == 6380

    difference = validate_client_server_start_alignment(
        capture_anchor_monotonic_ns=1_000_000_000,
        challenge_client_start_monotonic_ns=5_200_000_000,
        challenge_started_relative_ms=4200,
        tolerance_ms=50,
    )
    assert difference == pytest.approx(0.0)


def test_visual_yaw_direction_uses_opposite_scene_translation():
    settings = Settings(vision_min_features=20, vision_analysis_fps=10)
    right = analyze_visual_challenge(
        _translated_frames(dx_per_frame=-5.0, dy_per_frame=0.0),
        challenge_type=ChallengeType.ROTATE_RIGHT,
        invalid_frame_ratio=0.0,
        settings=settings,
    )
    left = analyze_visual_challenge(
        _translated_frames(dx_per_frame=5.0, dy_per_frame=0.0),
        challenge_type=ChallengeType.ROTATE_LEFT,
        invalid_frame_ratio=0.0,
        settings=settings,
    )
    assert right.status == VisualAnalysisStatus.SUCCESS
    assert right.direction == VisualDirection.RIGHT
    assert right.estimated_rotation_degrees is not None
    assert right.estimated_rotation_degrees > 2.0
    assert left.status == VisualAnalysisStatus.SUCCESS
    assert left.direction == VisualDirection.LEFT


def test_visual_tilt_direction_uses_vertical_scene_motion():
    settings = Settings(vision_min_features=20)
    up = analyze_visual_challenge(
        _translated_frames(dx_per_frame=0.0, dy_per_frame=5.0),
        challenge_type=ChallengeType.TILT_UP,
        invalid_frame_ratio=0.0,
        settings=settings,
    )
    down = analyze_visual_challenge(
        _translated_frames(dx_per_frame=0.0, dy_per_frame=-5.0),
        challenge_type=ChallengeType.TILT_DOWN,
        invalid_frame_ratio=0.0,
        settings=settings,
    )
    assert up.status == VisualAnalysisStatus.SUCCESS
    assert up.direction == VisualDirection.UP
    assert down.status == VisualAnalysisStatus.SUCCESS
    assert down.direction == VisualDirection.DOWN


@pytest.mark.parametrize(
    ("image_rotation", "expected_camera_direction"),
    [(20.0, VisualDirection.RIGHT), (-20.0, VisualDirection.LEFT)],
)
def test_synthetic_image_rotation_is_estimated_with_documented_fallback(
    image_rotation,
    expected_camera_direction,
):
    settings = Settings(vision_min_features=20)
    outcome = analyze_visual_challenge(
        _rotated_frames(image_rotation),
        challenge_type=ChallengeType.ROTATE_RIGHT,
        invalid_frame_ratio=0.0,
        settings=settings,
    )
    assert outcome.status == VisualAnalysisStatus.SUCCESS
    assert outcome.direction == expected_camera_direction
    assert outcome.estimated_rotation_degrees is not None
    assert 12.0 <= outcome.estimated_rotation_degrees <= 28.0
    assert outcome.diagnostics["directionSignal"] == "AFFINE_ROTATION_FALLBACK"


def test_blank_scene_is_inconclusive_instead_of_fabricating_motion():
    blank = np.full((360, 640, 3), 128, dtype=np.uint8)
    frames = [
        VisualFrame(index, index * 100, index * 100, blank.copy())
        for index in range(6)
    ]
    outcome = analyze_visual_challenge(
        frames,
        challenge_type=ChallengeType.ROTATE_RIGHT,
        invalid_frame_ratio=0.0,
        settings=Settings(),
    )
    assert outcome.status == VisualAnalysisStatus.INCONCLUSIVE
    assert outcome.direction == VisualDirection.NONE
    assert outcome.feature_count < 40
    assert any("Insufficient stable visual features" in reason for reason in outcome.reasons)


def test_scene_cut_and_duplicate_freeze_metrics_are_measured():
    settings = Settings()
    road = _feature_image()
    room = cv2.bitwise_not(road)
    cut_frames = [
        VisualFrame(0, 0, 0, road),
        VisualFrame(1, 100, 100, road.copy()),
        VisualFrame(2, 200, 200, room),
        VisualFrame(3, 300, 300, room.copy()),
    ]
    cut = analyze_continuity(cut_frames, invalid_frame_ratio=0.0, settings=settings)
    assert cut.scene_cut_detected
    assert cut.scene_cut_count >= 1

    repeated = [VisualFrame(index, index * 100, index * 100, road.copy()) for index in range(5)]
    frozen = analyze_continuity(repeated, invalid_frame_ratio=0.0, settings=settings)
    assert frozen.duplicate_frame_ratio == pytest.approx(1.0)
    assert frozen.freeze_duration_ms >= 400


def test_ransac_rejects_independent_foreground_outliers():
    rng = np.random.default_rng(7)
    source = rng.uniform([40.0, 40.0], [600.0, 320.0], size=(100, 2)).astype(np.float32)
    target = source.copy()
    target[:80, 0] -= 18.0
    target[:80, 1] += 3.0
    target[80:] += rng.uniform(-80.0, 80.0, size=(20, 2)).astype(np.float32)
    tracks = FlowTracks(
        source=source,
        target=target,
        median_magnitude_px=float(np.median(np.linalg.norm(target - source, axis=1))),
    )
    estimate = estimate_global_motion(
        tracks,
        timestamp_ms=500,
        frame_width=640,
        frame_height=360,
        settings=Settings(),
    )
    assert estimate is not None
    assert estimate.inlier_ratio >= 0.70
    assert estimate.translation_x == pytest.approx(-18.0, abs=2.0)
    assert estimate.translation_y == pytest.approx(3.0, abs=2.0)


def test_corrupted_video_fails_cleanly(tmp_path: Path):
    path = tmp_path / "broken.mp4"
    path.write_bytes(b"not-a-real-video-container" * 100)
    with pytest.raises(VideoDecodeError):
        inspect_video(path, Settings())


def test_video_metadata_and_frame_sampling_keep_timestamps(tmp_path: Path):
    path = tmp_path / "synthetic.avi"
    width, height, fps = 320, 240, 10.0
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"MJPG"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        pytest.skip("OpenCV build does not provide the MJPG test encoder")
    try:
        base = _feature_image(width, height)
        for index in range(20):
            matrix = np.float32([[1, 0, -2 * index], [0, 1, 0]])
            writer.write(cv2.warpAffine(base, matrix, (width, height), borderMode=cv2.BORDER_REFLECT))
    finally:
        writer.release()

    settings = Settings(vision_analysis_fps=5.0)
    metadata = inspect_video(path, settings)
    assert metadata.width == width
    assert metadata.height == height
    assert metadata.fps == pytest.approx(fps, rel=0.1)
    assert 1800 <= metadata.duration_ms <= 2200

    frames, invalid_ratio = sample_window(
        path,
        metadata=metadata,
        start_ms=200,
        end_ms=1200,
        video_start_relative_ms=25,
        settings=settings,
    )
    assert len(frames) >= 4
    assert invalid_ratio == pytest.approx(0.0)
    assert frames[0].video_time_ms >= 100
    assert frames[0].session_time_ms == frames[0].video_time_ms + 25
    assert all(left.video_time_ms < right.video_time_ms for left, right in zip(frames, frames[1:]))
