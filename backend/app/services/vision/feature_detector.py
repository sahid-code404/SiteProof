import cv2
import numpy as np

from app.core.config import Settings


def detect_orb_count(gray: np.ndarray, max_features: int) -> int:
    detector = cv2.ORB_create(nfeatures=max_features)
    keypoints = detector.detect(gray, None)
    return len(keypoints)


def detect_tracking_points(gray: np.ndarray, settings: Settings) -> np.ndarray:
    height, width = gray.shape[:2]
    rows = max(1, settings.vision_grid_rows)
    cols = max(1, settings.vision_grid_cols)
    per_cell = max(4, settings.vision_max_features // (rows * cols))
    points: list[np.ndarray] = []

    for row in range(rows):
        y0 = int(row * height / rows)
        y1 = int((row + 1) * height / rows)
        for col in range(cols):
            x0 = int(col * width / cols)
            x1 = int((col + 1) * width / cols)
            cell = gray[y0:y1, x0:x1]
            if cell.size == 0:
                continue
            found = cv2.goodFeaturesToTrack(
                cell,
                maxCorners=per_cell,
                qualityLevel=0.01,
                minDistance=7,
                blockSize=7,
                useHarrisDetector=False,
            )
            if found is None:
                continue
            found = found.reshape(-1, 2)
            found[:, 0] += x0
            found[:, 1] += y0
            points.append(found)

    if not points:
        return np.empty((0, 1, 2), dtype=np.float32)
    combined = np.concatenate(points, axis=0)
    if len(combined) > settings.vision_max_features:
        combined = combined[: settings.vision_max_features]
    return combined.astype(np.float32).reshape(-1, 1, 2)


def feature_coverage(points: np.ndarray, width: int, height: int, rows: int, cols: int) -> float:
    if points.size == 0 or width <= 0 or height <= 0:
        return 0.0
    occupied: set[tuple[int, int]] = set()
    flat = points.reshape(-1, 2)
    for x, y in flat:
        col = min(cols - 1, max(0, int(float(x) / width * cols)))
        row = min(rows - 1, max(0, int(float(y) / height * rows)))
        occupied.add((row, col))
    return len(occupied) / float(max(1, rows * cols))
