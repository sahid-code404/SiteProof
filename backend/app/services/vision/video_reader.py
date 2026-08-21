import math
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


def _presentation_time_ms(capture: cv2.VideoCapture, frame_index: int, source_fps: float) -> float:
    """Return the decoded frame's real presentation time when OpenCV exposes it.

    CAP_PROP_POS_MSEC is backed by FFmpeg timestamps for CameraX MP4/H.264 on the field
    devices we support. Falling back to frame_index/FPS keeps analysis operational on an
    OpenCV backend that does not expose timestamps, but normal evidence processing uses PTS.
    """
    reported = float(capture.get(cv2.CAP_PROP_POS_MSEC))
    if math.isfinite(reported) and reported >= 0.0:
        return reported
    return frame_index / source_fps * 1000.0


def _decode_window_attempt(
    path: Path,
    *,
    start_frame: int,
    end_frame: int,
    start_ms: int,
    end_ms: int,
    source_fps: float,
    analysis_fps: float,
    video_start_relative_ms: int,
    seek_frame: int,
) -> tuple[list[VisualFrame], float]:
    """Decode using real MP4 presentation timestamps and measure missing source frames.

    Android CameraX commonly writes H.264/H.265 MP4s with sparse keyframes. Seeking
    directly to a late challenge frame can leave some OpenCV/FFmpeg builds without
    enough decoder reference frames, so decoding begins from a safe pre-roll.

    Critically, challenge membership and timestamps are based on decoded PTS, not
    frame_index/FPS. A real multi-second encoder stall therefore remains visible to the
    evidence pipeline instead of being compressed away by frame-number arithmetic.
    """
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise VideoDecodeError("OpenCV could not reopen the uploaded video")

    if seek_frame > 0:
        capture.set(cv2.CAP_PROP_POS_FRAMES, seek_frame)
        reported = int(round(capture.get(cv2.CAP_PROP_POS_FRAMES)))
        frame_index = reported if 0 <= reported <= seek_frame else seek_frame
    else:
        frame_index = 0

    frames: list[VisualFrame] = []
    failed_reads = 0
    consecutive_failures = 0
    source_frames_in_window = 0
    estimated_missing_frames = 0
    nominal_interval_ms = 1000.0 / source_fps
    sample_interval_ms = 1000.0 / max(1.0, analysis_fps)
    next_sample_ms = float(start_ms)
    previous_pts_ms: float | None = None

    try:
        while frame_index <= end_frame:
            ok, image = capture.read()
            if not ok or image is None or image.size == 0:
                failed_reads += 1
                consecutive_failures += 1
                frame_index += 1
                if consecutive_failures > 5:
                    break
                continue

            consecutive_failures = 0
            video_time = _presentation_time_ms(capture, frame_index, source_fps)

            if previous_pts_ms is not None and video_time > previous_pts_ms:
                if previous_pts_ms >= start_ms and video_time <= end_ms + nominal_interval_ms:
                    delta_ms = video_time - previous_pts_ms
                    if delta_ms > nominal_interval_ms * 2.5:
                        estimated_missing_frames += max(
                            1,
                            int(round(delta_ms / nominal_interval_ms)) - 1,
                        )
            previous_pts_ms = video_time

            if video_time > end_ms + nominal_interval_ms:
                break

            if start_ms <= video_time <= end_ms:
                source_frames_in_window += 1
                if video_time + 0.001 >= next_sample_ms:
                    rounded_time_ms = int(round(video_time))
                    frames.append(
                        VisualFrame(
                            frame_index=frame_index,
                            video_time_ms=rounded_time_ms,
                            session_time_ms=video_start_relative_ms + rounded_time_ms,
                            image=image,
                        )
                    )
                    while next_sample_ms <= video_time + 0.001:
                        next_sample_ms += sample_interval_ms

            frame_index += 1
    finally:
        capture.release()

    denominator = max(
        1,
        source_frames_in_window + estimated_missing_frames + failed_reads,
    )
    invalid_ratio = (estimated_missing_frames + failed_reads) / float(denominator)
    return frames, min(1.0, invalid_ratio)


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

    source_fps = metadata.fps
    analysis_fps = min(max(settings.vision_analysis_fps, 1.0), source_fps)
    start_frame = min(
        metadata.frame_count - 1,
        max(0, int(start_ms / 1000.0 * source_fps)),
    )
    end_frame = min(
        metadata.frame_count - 1,
        max(start_frame, int(end_ms / 1000.0 * source_fps) + 1),
    )

    # A very short window at the encoded tail can mathematically collapse to one frame.
    # Include one immediately preceding frame so optical flow still has a pair to inspect.
    if end_frame == start_frame and start_frame > 0:
        start_frame -= 1

    preroll_frames = max(1, int(round(source_fps * 2.0)))
    seek_frame = max(0, start_frame - preroll_frames)
    frames, invalid_ratio = _decode_window_attempt(
        path,
        start_frame=start_frame,
        end_frame=end_frame,
        start_ms=start_ms,
        end_ms=end_ms,
        source_fps=source_fps,
        analysis_fps=analysis_fps,
        video_start_relative_ms=video_start_relative_ms,
        seek_frame=seek_frame,
    )

    if len(frames) < 2 and seek_frame > 0:
        # Final fallback for devices/codecs whose random access is unreliable near EOF.
        # Full forward decoding is slower but deterministic and only used on a failed seek.
        frames, invalid_ratio = _decode_window_attempt(
            path,
            start_frame=start_frame,
            end_frame=end_frame,
            start_ms=start_ms,
            end_ms=end_ms,
            source_fps=source_fps,
            analysis_fps=analysis_fps,
            video_start_relative_ms=video_start_relative_ms,
            seek_frame=0,
        )

    if len(frames) < 2:
        raise VideoDecodeError("Too few valid frames were decoded from the challenge window")
    return frames, invalid_ratio
