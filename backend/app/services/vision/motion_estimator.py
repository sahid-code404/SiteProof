import math

import cv2
import numpy as np

from app.core.config import Settings
from app.services.vision.domain import MotionEstimate
from app.services.vision.feature_detector import feature_coverage
from app.services.vision.optical_flow import FlowTracks


def estimate_global_motion(
    tracks: FlowTracks,
    *,
    timestamp_ms: int,
    frame_width: int,
    frame_height: int,
    settings: Settings,
) -> MotionEstimate | None:
    if tracks.count < 6:
        return None

    matrix, inlier_mask = cv2.estimateAffinePartial2D(
        tracks.source,
        tracks.target,
        method=cv2.RANSAC,
        ransacReprojThreshold=settings.vision_ransac_threshold_px,
        maxIters=2000,
        confidence=0.99,
        refineIters=10,
    )
    if matrix is None or inlier_mask is None:
        return None

    inliers = int(np.count_nonzero(inlier_mask))
    inlier_ratio = inliers / float(max(1, tracks.count))
    a = float(matrix[0, 0])
    b = float(matrix[1, 0])
    translation_x = float(matrix[0, 2])
    translation_y = float(matrix[1, 2])
    scale = math.sqrt(a * a + b * b)
    rotation_degrees = math.degrees(math.atan2(b, a))

    homography_ratio: float | None = None
    if tracks.count >= 12:
        _, homography_mask = cv2.findHomography(
            tracks.source,
            tracks.target,
            cv2.RANSAC,
            settings.vision_ransac_threshold_px,
        )
        if homography_mask is not None:
            homography_ratio = float(np.count_nonzero(homography_mask) / max(1, tracks.count))

    coverage = feature_coverage(
        tracks.source,
        frame_width,
        frame_height,
        settings.vision_grid_rows,
        settings.vision_grid_cols,
    )
    return MotionEstimate(
        timestamp_ms=timestamp_ms,
        rotation_degrees=rotation_degrees,
        translation_x=translation_x,
        translation_y=translation_y,
        scale=scale,
        tracked_points=tracks.count,
        inliers=inliers,
        inlier_ratio=inlier_ratio,
        median_flow_px=tracks.median_magnitude_px,
        feature_coverage=coverage,
        homography_inlier_ratio=homography_ratio,
    )


def physical_angle_from_translation(
    motion: MotionEstimate,
    *,
    frame_width: int,
    frame_height: int,
    horizontal: bool,
    horizontal_fov_degrees: float,
) -> float:
    hfov_radians = math.radians(max(20.0, min(150.0, horizontal_fov_degrees)))
    focal_px = (frame_width / 2.0) / math.tan(hfov_radians / 2.0)
    if horizontal:
        # Static scene content moves opposite a camera yaw. Positive physical angle means RIGHT.
        return math.degrees(math.atan2(-motion.translation_x, focal_px))
    # The same focal length in pixel units is sufficient for a rough pitch estimate.
    # Image +Y is downward: scene content moving down corresponds to camera tilt UP.
    return math.degrees(math.atan2(motion.translation_y, focal_px))
