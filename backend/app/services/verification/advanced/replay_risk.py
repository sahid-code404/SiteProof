from __future__ import annotations

from statistics import fmean
from typing import Any

import cv2
import numpy as np

from app.models.advanced_security import AdvancedProcessStatus, RiskLevel

ALGORITHM_VERSION = "replay-risk-v1"


def _right_angle_score(points: np.ndarray) -> float:
    values = points.reshape(-1, 2).astype(np.float32)
    if len(values) != 4:
        return 0.0
    scores: list[float] = []
    for index in range(4):
        first = values[(index - 1) % 4] - values[index]
        second = values[(index + 1) % 4] - values[index]
        denominator = max(float(np.linalg.norm(first) * np.linalg.norm(second)), 1e-6)
        scores.append(max(0.0, 1.0 - abs(float(np.dot(first, second)) / denominator)))
    return fmean(scores)


def display_rectangle_score(frame: np.ndarray) -> float:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 70, 160)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    frame_area = float(frame.shape[0] * frame.shape[1])
    best = 0.0
    for contour in contours:
        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 0:
            continue
        polygon = cv2.approxPolyDP(contour, 0.025 * perimeter, True)
        if len(polygon) != 4 or not cv2.isContourConvex(polygon):
            continue
        polygon_area = abs(float(cv2.contourArea(polygon)))
        fraction = polygon_area / max(frame_area, 1.0)
        if fraction < 0.20 or fraction > 0.98:
            continue
        _, _, width, height = cv2.boundingRect(polygon)
        rectangularity = polygon_area / max(float(width * height), 1.0)
        size_score = min(1.0, max(0.0, (fraction - 0.20) / 0.55))
        score = 0.45 * size_score + 0.30 * rectangularity + 0.25 * _right_angle_score(polygon)
        best = max(best, min(1.0, score))
    return best


def banding_score(frame: np.ndarray) -> float:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)

    def periodic(values: np.ndarray) -> float:
        centered = values - float(values.mean())
        if float(np.std(centered)) < 1.0:
            return 0.0
        spectrum = np.abs(np.fft.rfft(centered))
        spectrum[:2] = 0
        if len(spectrum) < 8:
            return 0.0
        return min(1.0, float(np.max(spectrum)) / (float(np.sum(spectrum)) + 1e-6) * 8.0)

    return max(periodic(gray.mean(axis=1)), periodic(gray.mean(axis=0)))


def moire_score(frame: np.ndarray) -> float:
    gray = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32), (256, 256))
    spectrum = np.abs(np.fft.fftshift(np.fft.fft2(gray)))
    height, width = spectrum.shape
    yy, xx = np.ogrid[:height, :width]
    radius = np.sqrt((yy - height / 2) ** 2 + (xx - width / 2) ** 2)
    high = spectrum[(radius > min(height, width) * 0.22) & (radius < min(height, width) * 0.46)]
    concentration = float(np.sum(high)) / (float(np.sum(spectrum)) + 1e-6)
    return min(1.0, max(0.0, (concentration - 0.12) / 0.20))


def analyze_frames(
    frames: list[np.ndarray],
    *,
    fusion_mismatch_score: float,
    duplicate_frame_ratio: float,
    evidence_reuse_score: float,
) -> dict[str, Any]:
    if not frames:
        return {
            "process_status": AdvancedProcessStatus.UNAVAILABLE,
            "risk_level": RiskLevel.INCONCLUSIVE,
            "score": 0.5,
            "confidence": 0.0,
            "display_rectangle_score": 0.0,
            "moire_score": 0.0,
            "banding_score": 0.0,
            "evidence_reuse_score": evidence_reuse_score,
            "fusion_mismatch_score": fusion_mismatch_score,
            "reason_codes": ["VIDEO_ANALYSIS_UNAVAILABLE"],
            "reasons": ["Replay analysis was unavailable because usable video frames were not present."],
            "metrics": {"frameCount": 0},
            "algorithm_version": ALGORITHM_VERSION,
        }

    rectangle_scores = [display_rectangle_score(frame) for frame in frames]
    band_scores = [banding_score(frame) for frame in frames]
    moire_scores = [moire_score(frame) for frame in frames]
    rectangle = max(0.0, min(1.0, 0.6 * fmean(rectangle_scores) + 0.4 * min(rectangle_scores)))
    banding = fmean(band_scores)
    moire = fmean(moire_scores)
    artifact = max(0.65 * rectangle + 0.20 * banding + 0.15 * moire, banding, moire)
    mismatch = max(0.0, min(1.0, fusion_mismatch_score))
    duplicate = max(0.0, min(1.0, duplicate_frame_ratio))
    reuse = max(0.0, min(1.0, evidence_reuse_score))
    combined = max(
        reuse,
        0.45 * artifact + 0.40 * mismatch + 0.15 * duplicate,
        0.58 * artifact + 0.42 * duplicate,
    )

    # A rectangular object alone is not enough to call replay: real sites can contain screens,
    # doors, signs and windows. High risk requires corroboration or exact evidence reuse.
    if rectangle > 0.75 and mismatch < 0.30 and banding < 0.35 and moire < 0.35:
        combined = min(combined, 0.55)
    if reuse >= 0.98:
        combined = max(combined, 0.98)

    codes: list[str] = []
    reasons: list[str] = []
    if rectangle >= 0.65:
        codes.append("DISPLAY_LIKE_RECTANGLE")
        reasons.append("A large display-like rectangular boundary persisted across sampled frames.")
    if banding >= 0.55:
        codes.append("DISPLAY_BANDING")
        reasons.append("Periodic luminance banding was present as a weak display-artifact indicator.")
    if moire >= 0.55:
        codes.append("MOIRE_PATTERN")
        reasons.append("Frequency analysis found a possible moire-like pattern; this heuristic is experimental.")
    if mismatch >= 0.65:
        codes.append("VISUAL_SENSOR_MISMATCH")
        reasons.append("Phase 6 reported strong disagreement between visual and physical motion.")
    if duplicate >= 0.45:
        codes.append("REPEATED_FRAMES")
        reasons.append("The visual stream contained a high repeated-frame ratio.")
    if reuse >= 0.80:
        codes.append("EVIDENCE_REUSE")
        reasons.append("Evidence hashes matched content from another live verification session.")
    if not reasons:
        reasons.append("No combination of replay indicators reached a meaningful risk threshold.")

    strong_indicators = sum(
        value >= 0.55 for value in [rectangle, banding, moire, mismatch, duplicate]
    )
    risk_level = (
        RiskLevel.HIGH
        if combined >= 0.72 and (reuse >= 0.80 or strong_indicators >= 2)
        else RiskLevel.MODERATE
        if combined >= 0.38
        else RiskLevel.LOW
    )
    confidence = min(0.93, 0.45 + 0.04 * len(frames) + 0.18 * max(mismatch, reuse))
    return {
        "process_status": AdvancedProcessStatus.COMPLETE,
        "risk_level": risk_level,
        "score": min(1.0, combined),
        "confidence": confidence,
        "display_rectangle_score": rectangle,
        "moire_score": moire,
        "banding_score": banding,
        "evidence_reuse_score": reuse,
        "fusion_mismatch_score": mismatch,
        "reason_codes": sorted(set(codes)),
        "reasons": reasons,
        "metrics": {
            "frameCount": len(frames),
            "duplicateFrameRatio": duplicate,
            "moireExperimental": True,
            "rectangleAloneCannotTriggerHigh": True,
        },
        "algorithm_version": ALGORITHM_VERSION,
    }
