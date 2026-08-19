import math
from statistics import median

import numpy as np

from app.core.config import Settings
from app.models.challenge import ChallengeType
from app.models.visual_motion import VisualAnalysisStatus, VisualDirection, VisualQuality
from app.services.vision.continuity import analyze_continuity
from app.services.vision.domain import AnalysisOutcome, MotionEstimate, VisualFrame
from app.services.vision.feature_detector import detect_orb_count, detect_tracking_points
from app.services.vision.motion_estimator import estimate_global_motion, physical_angle_from_translation
from app.services.vision.optical_flow import track_points
from app.services.vision.preprocessing import preprocess_frame


def _quality(
    *,
    feature_count: int,
    continuity_score: float,
    brightness_value: float,
    sharpness_value: float,
    settings: Settings,
) -> VisualQuality:
    if (
        feature_count >= settings.vision_min_features * 2
        and continuity_score >= 0.80
        and 20.0 <= brightness_value <= 235.0
        and sharpness_value >= 30.0
    ):
        return VisualQuality.GOOD
    if (
        feature_count >= settings.vision_min_features
        and continuity_score >= 0.55
        and 10.0 <= brightness_value <= 245.0
        and sharpness_value >= 10.0
    ):
        return VisualQuality.FAIR
    return VisualQuality.POOR


def _direction_from_angle(angle: float, horizontal: bool) -> VisualDirection:
    if abs(angle) < 1.5:
        return VisualDirection.NONE
    if horizontal:
        return VisualDirection.RIGHT if angle > 0 else VisualDirection.LEFT
    return VisualDirection.UP if angle > 0 else VisualDirection.DOWN


def _empty_outcome(
    *,
    continuity,
    reason: str,
    quality: VisualQuality = VisualQuality.POOR,
) -> AnalysisOutcome:
    return AnalysisOutcome(
        status=VisualAnalysisStatus.INCONCLUSIVE,
        direction=VisualDirection.NONE,
        quality=quality,
        estimated_rotation_degrees=None,
        translation_x=None,
        translation_y=None,
        scale_change=None,
        motion_start_ms=None,
        motion_end_ms=None,
        feature_count=0,
        tracked_feature_count=0,
        inlier_ratio=0.0,
        confidence=0.0,
        continuity=continuity,
        reasons=[reason],
        diagnostics={},
    )


def analyze_visual_challenge(
    frames: list[VisualFrame],
    *,
    challenge_type: ChallengeType,
    invalid_frame_ratio: float,
    settings: Settings,
) -> AnalysisOutcome:
    continuity = analyze_continuity(
        frames,
        invalid_frame_ratio=invalid_frame_ratio,
        settings=settings,
    )
    if len(frames) < 3:
        return _empty_outcome(continuity=continuity, reason="Too few decoded frames for motion analysis.")

    grays = [preprocess_frame(frame.image, settings.vision_max_width) for frame in frames]
    orb_counts = [detect_orb_count(gray, settings.vision_max_features) for gray in grays]
    motion_estimates: list[MotionEstimate] = []
    raw_tracked_counts: list[int] = []

    for index in range(1, len(grays)):
        previous = grays[index - 1]
        current = grays[index]
        if previous.shape != current.shape:
            continue
        points = detect_tracking_points(previous, settings)
        raw_tracked_counts.append(int(len(points)))
        tracks = track_points(previous, current, points, settings)
        estimate = estimate_global_motion(
            tracks,
            timestamp_ms=frames[index].session_time_ms,
            frame_width=previous.shape[1],
            frame_height=previous.shape[0],
            settings=settings,
        )
        if estimate is not None:
            motion_estimates.append(estimate)

    feature_count = int(round(median(orb_counts))) if orb_counts else 0
    tracked_count = (
        int(round(median([item.tracked_points for item in motion_estimates])))
        if motion_estimates
        else 0
    )
    quality = _quality(
        feature_count=feature_count,
        continuity_score=continuity.score,
        brightness_value=continuity.mean_brightness,
        sharpness_value=continuity.mean_sharpness,
        settings=settings,
    )

    if feature_count < settings.vision_min_features:
        outcome = _empty_outcome(
            continuity=continuity,
            reason="Insufficient stable visual features.",
            quality=quality,
        )
        return AnalysisOutcome(
            **{**outcome.__dict__, "feature_count": feature_count, "tracked_feature_count": tracked_count}
        )
    if len(motion_estimates) < 2:
        outcome = _empty_outcome(
            continuity=continuity,
            reason="A dominant global transform could not be estimated reliably.",
            quality=quality,
        )
        return AnalysisOutcome(
            **{**outcome.__dict__, "feature_count": feature_count, "tracked_feature_count": tracked_count}
        )

    horizontal = challenge_type in {ChallengeType.ROTATE_LEFT, ChallengeType.ROTATE_RIGHT}
    usable = [
        item
        for item in motion_estimates
        if item.inlier_ratio >= settings.vision_min_inlier_ratio
    ]
    if len(usable) < 2:
        outcome = _empty_outcome(
            continuity=continuity,
            reason="Global motion had too few RANSAC-supported frame pairs.",
            quality=quality,
        )
        return AnalysisOutcome(
            **{**outcome.__dict__, "feature_count": feature_count, "tracked_feature_count": tracked_count}
        )

    frame_height, frame_width = grays[0].shape[:2]
    signed_angles = [
        physical_angle_from_translation(
            item,
            frame_width=frame_width,
            frame_height=frame_height,
            horizontal=horizontal,
            horizontal_fov_degrees=settings.vision_assumed_horizontal_fov_degrees,
        )
        for item in usable
    ]
    total_signed_angle = float(sum(signed_angles))
    direction = _direction_from_angle(total_signed_angle, horizontal)

    dominant_sign = 1.0 if total_signed_angle >= 0 else -1.0
    sign_support = [
        value for value in signed_angles if abs(value) >= 0.05 and math.copysign(1.0, value) == dominant_sign
    ]
    consistency = len(sign_support) / float(max(1, len([v for v in signed_angles if abs(v) >= 0.05])))
    inlier_ratio = float(np.mean([item.inlier_ratio for item in usable]))
    coverage = float(np.mean([item.feature_coverage for item in usable]))
    feature_quality = min(1.0, feature_count / float(max(1, settings.vision_min_features * 2)))

    weights = settings.vision_confidence_weights
    confidence = (
        weights["feature"] * feature_quality
        + weights["inlier"] * min(1.0, inlier_ratio)
        + weights["consistency"] * consistency
        + weights["coverage"] * min(1.0, coverage)
        + weights["continuity"] * continuity.score
    )
    confidence = max(0.0, min(1.0, confidence))

    motion_pairs = [item for item in usable if item.median_flow_px >= settings.vision_motion_threshold_px]
    motion_start_ms = motion_pairs[0].timestamp_ms if motion_pairs else None
    motion_end_ms = motion_pairs[-1].timestamp_ms if motion_pairs else None
    translation_x = float(sum(item.translation_x for item in usable))
    translation_y = float(sum(item.translation_y for item in usable))
    scale_product = float(np.prod([item.scale for item in usable]))

    reasons: list[str] = []
    status = VisualAnalysisStatus.SUCCESS
    if direction == VisualDirection.NONE or abs(total_signed_angle) < 2.0:
        status = VisualAnalysisStatus.INCONCLUSIVE
        reasons.append("Global visual movement was too small to assign a reliable direction.")
    elif confidence < 0.45:
        status = VisualAnalysisStatus.INCONCLUSIVE
        reasons.append("Visual motion confidence is below the analysis threshold.")
    else:
        reasons.append("Visual motion was estimated from a dominant RANSAC-supported scene transform.")
    if continuity.scene_cut_detected:
        reasons.append("An abrupt scene-continuity change was detected inside the analyzed window.")
    if continuity.freeze_duration_ms > 0:
        reasons.append("Repeated-frame behavior was measured in the analyzed window.")
    if quality == VisualQuality.POOR:
        reasons.append("Visual quality is poor; interpret the motion estimate cautiously.")

    motion_curve = [
        {"timeMs": item.timestamp_ms, "magnitudePx": round(item.median_flow_px, 3)}
        for item in usable
    ]
    pair_diagnostics = [
        {
            "timestampMs": item.timestamp_ms,
            "affineRotationDegrees": round(item.rotation_degrees, 3),
            "translationX": round(item.translation_x, 3),
            "translationY": round(item.translation_y, 3),
            "scale": round(item.scale, 5),
            "trackedPoints": item.tracked_points,
            "inliers": item.inliers,
            "inlierRatio": round(item.inlier_ratio, 4),
            "featureCoverage": round(item.feature_coverage, 4),
            "homographyInlierRatio": (
                round(item.homography_inlier_ratio, 4)
                if item.homography_inlier_ratio is not None
                else None
            ),
        }
        for item in usable
    ]
    diagnostics = {
        "framePairsAnalyzed": len(motion_estimates),
        "ransacSupportedPairs": len(usable),
        "motionConsistency": round(consistency, 4),
        "featureCoverage": round(coverage, 4),
        "foregroundOutlierRatio": round(max(0.0, 1.0 - inlier_ratio), 4),
        "sceneCutDetected": continuity.scene_cut_detected,
        "sceneCutCount": continuity.scene_cut_count,
        "blackFrameRatio": round(continuity.black_frame_ratio, 4),
        "meanBrightness": round(continuity.mean_brightness, 3),
        "meanSharpness": round(continuity.mean_sharpness, 3),
        "motionCurve": motion_curve,
        "pairEstimates": pair_diagnostics,
        "rawTrackingPointMedian": int(round(median(raw_tracked_counts))) if raw_tracked_counts else 0,
        "coordinateConvention": (
            "RIGHT/LEFT infer physical camera yaw opposite horizontal image translation; "
            "UP/DOWN infer physical pitch from vertical image translation."
        ),
    }

    return AnalysisOutcome(
        status=status,
        direction=direction,
        quality=quality,
        estimated_rotation_degrees=abs(total_signed_angle),
        translation_x=translation_x,
        translation_y=translation_y,
        scale_change=scale_product - 1.0,
        motion_start_ms=motion_start_ms,
        motion_end_ms=motion_end_ms,
        feature_count=feature_count,
        tracked_feature_count=tracked_count,
        inlier_ratio=inlier_ratio,
        confidence=confidence,
        continuity=continuity,
        reasons=reasons,
        diagnostics=diagnostics,
    )
