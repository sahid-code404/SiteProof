import cv2
import numpy as np


def preprocess_frame(image: np.ndarray, max_width: int) -> np.ndarray:
    if image is None or image.size == 0:
        raise ValueError("Cannot preprocess an empty frame")
    height, width = image.shape[:2]
    if width > max_width:
        scale = max_width / float(width)
        image = cv2.resize(
            image,
            (max_width, max(1, int(round(height * scale)))),
            interpolation=cv2.INTER_AREA,
        )
    if image.ndim == 3:
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return image.copy()


def brightness(gray: np.ndarray) -> float:
    return float(np.mean(gray))


def sharpness(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())
