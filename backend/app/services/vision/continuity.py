import cv2
import numpy as np

from app.core.config import Settings
from app.services.vision.domain import ContinuityMetrics, VisualFrame
from app.services.vision.preprocessing import brightness, preprocess_frame, sharpness


def analyze_continuity(
    frames: list[VisualFrame],
    *,
    invalid_frame_ratio: float,
    settings: Settings,
) -> ContinuityMetrics:
    if not frames:
        return ContinuityMetrics(
            score=0.0,
            scene_cut_detected=False,
            scene_cut_count=0,
            duplicate_frame_ratio=0.0,
            freeze_duration_ms=0,
            invalid_frame_ratio=invalid_frame_ratio,
            black_frame_ratio=1.0,
            mean_brightness=0.0,
            mean_sharpness=0.0,
        )

    grays = [preprocess_frame(frame.image, settings.vision_max_width) for frame in frames]
    brightness_values = [brightness(gray) for gray in grays]
    sharpness_values = [sharpness(gray) for gray in grays]
    black_count = sum(value < 8.0 for value in brightness_values)

    duplicate_pairs = 0
    scene_cut_count = 0
    max_freeze_ms = 0
    freeze_start_ms: int | None = None

    for index in range(1, len(grays)):
        previous = grays[index - 1]
        current = grays[index]
        if previous.shape != current.shape:
            current = cv2.resize(current, (previous.shape[1], previous.shape[0]))
        difference = float(np.mean(cv2.absdiff(previous, current)))
        duplicate = difference <= settings.vision_duplicate_mean_absdiff
        if duplicate:
            duplicate_pairs += 1
            if freeze_start_ms is None:
                freeze_start_ms = frames[index - 1].session_time_ms
            max_freeze_ms = max(
                max_freeze_ms,
                frames[index].session_time_ms - freeze_start_ms,
            )
        else:
            freeze_start_ms = None

        hist_a = cv2.calcHist([previous], [0], None, [64], [0, 256])
        hist_b = cv2.calcHist([current], [0], None, [64], [0, 256])
        cv2.normalize(hist_a, hist_a)
        cv2.normalize(hist_b, hist_b)
        distance = float(cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_BHATTACHARYYA))
        if distance >= settings.vision_scene_cut_hist_distance:
            scene_cut_count += 1

    pair_count = max(1, len(grays) - 1)
    duplicate_ratio = duplicate_pairs / float(pair_count)
    black_ratio = black_count / float(max(1, len(grays)))
    cut_penalty = min(1.0, scene_cut_count / float(max(1, pair_count // 3 or 1)))
    continuity_score = max(
        0.0,
        min(
            1.0,
            1.0
            - 0.45 * duplicate_ratio
            - 0.30 * cut_penalty
            - 0.15 * black_ratio
            - 0.10 * invalid_frame_ratio,
        ),
    )

    return ContinuityMetrics(
        score=continuity_score,
        scene_cut_detected=scene_cut_count > 0,
        scene_cut_count=scene_cut_count,
        duplicate_frame_ratio=duplicate_ratio,
        freeze_duration_ms=max_freeze_ms,
        invalid_frame_ratio=invalid_frame_ratio,
        black_frame_ratio=black_ratio,
        mean_brightness=float(np.mean(brightness_values)),
        mean_sharpness=float(np.mean(sharpness_values)),
    )
