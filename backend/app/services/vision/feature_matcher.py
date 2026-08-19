from dataclasses import dataclass
import math

import cv2
import numpy as np

from app.core.config import Settings


@dataclass(frozen=True)
class FeatureMatchEstimate:
    detected_start: int
    detected_end: int
    good_matches: int
    inliers: int
    inlier_ratio: float
    rotation_degrees: float
    translation_x: float
    translation_y: float
    scale: float


def match_orb_affine(
    first_gray: np.ndarray,
    last_gray: np.ndarray,
    settings: Settings,
) -> FeatureMatchEstimate | None:
    """Match ORB descriptors and estimate a robust start/end partial-affine transform.

    This is deliberately a secondary diagnostic. The primary Phase 5 motion curve uses
    temporally ordered Lucas-Kanade tracks, while descriptor matching provides an independent
    start/end correspondence check that does not assume the same point survived every frame.
    """
    detector = cv2.ORB_create(nfeatures=settings.vision_max_features)
    start_keypoints, start_descriptors = detector.detectAndCompute(first_gray, None)
    end_keypoints, end_descriptors = detector.detectAndCompute(last_gray, None)
    detected_start = len(start_keypoints)
    detected_end = len(end_keypoints)
    if (
        start_descriptors is None
        or end_descriptors is None
        or detected_start < 6
        or detected_end < 6
    ):
        return None

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    pairs = matcher.knnMatch(start_descriptors, end_descriptors, k=2)
    good = []
    for pair in pairs:
        if len(pair) < 2:
            continue
        best, second = pair
        if best.distance < 0.75 * second.distance:
            good.append(best)
    if len(good) < 6:
        return None

    source = np.float32([start_keypoints[item.queryIdx].pt for item in good])
    target = np.float32([end_keypoints[item.trainIdx].pt for item in good])
    matrix, mask = cv2.estimateAffinePartial2D(
        source,
        target,
        method=cv2.RANSAC,
        ransacReprojThreshold=settings.vision_ransac_threshold_px,
        maxIters=3000,
        confidence=0.99,
        refineIters=10,
    )
    if matrix is None or mask is None:
        return None

    inliers = int(np.count_nonzero(mask))
    inlier_ratio = inliers / float(max(1, len(good)))
    a = float(matrix[0, 0])
    b = float(matrix[1, 0])
    return FeatureMatchEstimate(
        detected_start=detected_start,
        detected_end=detected_end,
        good_matches=len(good),
        inliers=inliers,
        inlier_ratio=inlier_ratio,
        rotation_degrees=math.degrees(math.atan2(b, a)),
        translation_x=float(matrix[0, 2]),
        translation_y=float(matrix[1, 2]),
        scale=math.sqrt(a * a + b * b),
    )
