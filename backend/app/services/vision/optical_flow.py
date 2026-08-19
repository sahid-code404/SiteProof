from dataclasses import dataclass

import cv2
import numpy as np

from app.core.config import Settings


@dataclass(frozen=True)
class FlowTracks:
    source: np.ndarray
    target: np.ndarray
    median_magnitude_px: float

    @property
    def count(self) -> int:
        return int(len(self.source))


def track_points(
    previous_gray: np.ndarray,
    current_gray: np.ndarray,
    points: np.ndarray,
    settings: Settings,
) -> FlowTracks:
    if points.size == 0:
        return FlowTracks(
            source=np.empty((0, 2), dtype=np.float32),
            target=np.empty((0, 2), dtype=np.float32),
            median_magnitude_px=0.0,
        )

    window = max(7, settings.vision_lk_window_size)
    next_points, forward_status, forward_error = cv2.calcOpticalFlowPyrLK(
        previous_gray,
        current_gray,
        points,
        None,
        winSize=(window, window),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
    )
    if next_points is None or forward_status is None:
        return FlowTracks(
            source=np.empty((0, 2), dtype=np.float32),
            target=np.empty((0, 2), dtype=np.float32),
            median_magnitude_px=0.0,
        )

    back_points, backward_status, _ = cv2.calcOpticalFlowPyrLK(
        current_gray,
        previous_gray,
        next_points,
        None,
        winSize=(window, window),
        maxLevel=3,
        criteria=(cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 0.01),
    )
    if back_points is None or backward_status is None:
        return FlowTracks(
            source=np.empty((0, 2), dtype=np.float32),
            target=np.empty((0, 2), dtype=np.float32),
            median_magnitude_px=0.0,
        )

    source = points.reshape(-1, 2)
    target = next_points.reshape(-1, 2)
    returned = back_points.reshape(-1, 2)
    status = (forward_status.reshape(-1) == 1) & (backward_status.reshape(-1) == 1)
    if forward_error is not None:
        status &= np.isfinite(forward_error.reshape(-1))

    fb_error = np.linalg.norm(source - returned, axis=1)
    status &= np.isfinite(fb_error)
    status &= fb_error <= settings.vision_forward_backward_max_error_px

    height, width = current_gray.shape[:2]
    status &= target[:, 0] >= 0
    status &= target[:, 0] < width
    status &= target[:, 1] >= 0
    status &= target[:, 1] < height

    displacement = np.linalg.norm(target - source, axis=1)
    diagonal = float(np.hypot(width, height))
    status &= np.isfinite(displacement)
    status &= displacement <= diagonal * 0.35

    filtered_source = source[status].astype(np.float32)
    filtered_target = target[status].astype(np.float32)
    median = (
        float(np.median(np.linalg.norm(filtered_target - filtered_source, axis=1)))
        if len(filtered_source)
        else 0.0
    )
    return FlowTracks(filtered_source, filtered_target, median)
