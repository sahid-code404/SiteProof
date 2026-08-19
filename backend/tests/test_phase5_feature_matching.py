import cv2
import numpy as np

from app.core.config import Settings
from app.services.vision.feature_matcher import match_orb_affine


def _feature_image(width: int = 640, height: int = 360) -> np.ndarray:
    image = np.full((height, width), 30, dtype=np.uint8)
    rng = np.random.default_rng(42)
    for index in range(75):
        x = int(rng.integers(25, width - 25))
        y = int(rng.integers(25, height - 25))
        value = int(rng.integers(80, 245))
        radius = int(rng.integers(3, 9))
        if index % 3 == 0:
            cv2.circle(image, (x, y), radius, value, -1)
        elif index % 3 == 1:
            cv2.rectangle(
                image,
                (x - radius, y - radius),
                (x + radius, y + radius),
                value,
                -1,
            )
        else:
            cv2.line(
                image,
                (x - radius * 2, y - radius),
                (x + radius * 2, y + radius),
                value,
                2,
            )
    cv2.putText(
        image,
        "SITEPROOF ORB 5",
        (105, 185),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.1,
        245,
        2,
        cv2.LINE_AA,
    )
    return image


def test_orb_descriptor_matching_estimates_start_end_transform():
    first = _feature_image()
    height, width = first.shape
    transform = cv2.getRotationMatrix2D((width / 2.0, height / 2.0), 12.0, 1.0)
    transform[0, 2] += 8.0
    transform[1, 2] -= 4.0
    last = cv2.warpAffine(
        first,
        transform,
        (width, height),
        borderMode=cv2.BORDER_REFLECT,
    )

    estimate = match_orb_affine(first, last, Settings(vision_max_features=900))
    assert estimate is not None
    assert estimate.good_matches >= 12
    assert estimate.inlier_ratio >= 0.5
    assert 8.0 <= abs(estimate.rotation_degrees) <= 16.0
