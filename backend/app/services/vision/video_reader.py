from pathlib import Path

import cv2

from app.core.config import Settings
from app.services.vision.domain import VideoMetadata, VisualFrame


class VideoDecodeError(RuntimeError):
    pass


def _fourcc_text(value: float) -> str:
    code = int(value)
    chars = [chr((code >> (8 * index)) & 0xFF) for index in range(4)]
    return "".join(chars).strip("\x00") or "UNKNOWN"


def inspect_video(path: Path, settings: Settings) -> VideoMetadata:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise VideoDecodeError("OpenCV could not open the uploaded video")
    try:
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        codec = _fourcc_text(capture.get(cv2.CAP_PROP_FOURCC))
    finally:
        capture.release()

    if width <= 0 or height <= 0 or fps <= 0 or frame_count <= 0:
        raise VideoDecodeError("Video metadata is incomplete or invalid")
    if width * height > settings.vision_max_resolution_pixels:
        raise VideoDecodeError("Video resolution exceeds the configured analysis limit")
    if frame_count > settings.vision_max_frame_count:
        raise VideoDecodeError("Video frame count exceeds the configured analysis limit")
    duration_ms = int(round(frame_count / fps * 1000.0))
    if duration_ms <= 0 or duration_ms > settings.vision_max_duration_seconds * 1000:
        raise VideoDecodeError("Video duration is outside the configured analysis limit")

    return VideoMetadata(
        codec=codec,
        width=width,
        height=height,
        fps=fps,
        duration_ms=duration_ms,
        frame_count=frame_count,
    )


def sample_window(
    path: Path,
    *,
    metadata: VideoMetadata,
    start_ms: int,
    end_ms: int,
    video_start_relative_ms: int,
    settings: Settings,
) -> tuple[list[VisualFrame], float]:
    if end_ms <= start_ms:
        raise ValueError("Video sample window must have positive duration")

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise VideoDecodeError("OpenCV could not reopen the uploaded video")

    source_fps = metadata.fps
    analysis_fps = min(max(settings.vision_analysis_fps, 1.0), source_fps)
    step = max(1, int(round(source_fps / analysis_fps)))
    start_frame = max(0, int(start_ms / 1000.0 * source_fps))
    end_frame = min(metadata.frame_count - 1, int(end_ms / 1000.0 * source_fps) + 1)
    capture.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    frames: list[VisualFrame] = []
    attempted = 0
    failed = 0
    frame_index = start_frame
    try:
        while frame_index <= end_frame:
            ok, image = capture.read()
            if not ok or image is None or image.size == 0:
                failed += 1
                frame_index += 1
                if failed > 5:
                    break
                continue
            if (frame_index - start_frame) % step == 0:
                attempted += 1
                video_time_ms = int(round(frame_index / source_fps * 1000.0))
                if video_time_ms > end_ms:
                    break
                frames.append(
                    VisualFrame(
                        frame_index=frame_index,
                        video_time_ms=video_time_ms,
                        session_time_ms=video_start_relative_ms + video_time_ms,
                        image=image,
                    )
                )
            frame_index += 1
    finally:
        capture.release()

    invalid_ratio = failed / max(1, attempted + failed)
    if len(frames) < 2:
        raise VideoDecodeError("Too few valid frames were decoded from the challenge window")
    return frames, min(1.0, invalid_ratio)
