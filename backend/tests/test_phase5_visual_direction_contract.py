import numpy as np

from app.core.config import Settings
from app.models.challenge import ChallengeType
from app.models.visual_motion import VisualAnalysisStatus, VisualDirection
from app.services.vision.domain import VisualFrame
from app.services.vision.visual_challenge_analyzer import (
    analyze_visual_challenge,
    expected_visual_direction,
)


def test_expected_visual_direction_matches_phase4_phone_instructions():
    assert expected_visual_direction(ChallengeType.ROTATE_LEFT) == VisualDirection.LEFT
    assert expected_visual_direction(ChallengeType.ROTATE_RIGHT) == VisualDirection.RIGHT
    # Tilt challenge names describe the portrait phone's TOP EDGE movement. Rear-camera
    # optical pitch is opposite that label: top away => camera DOWN, top toward => camera UP.
    assert expected_visual_direction(ChallengeType.TILT_UP) == VisualDirection.DOWN
    assert expected_visual_direction(ChallengeType.TILT_DOWN) == VisualDirection.UP


def test_large_missing_frame_ratio_is_inconclusive_before_motion_scoring():
    image = np.full((120, 160, 3), 96, dtype=np.uint8)
    frames = [
        VisualFrame(frame_index=index, video_time_ms=index * 100, session_time_ms=index * 100, image=image)
        for index in range(3)
    ]
    outcome = analyze_visual_challenge(
        frames,
        challenge_type=ChallengeType.ROTATE_RIGHT,
        invalid_frame_ratio=0.55,
        settings=Settings(),
    )
    assert outcome.status == VisualAnalysisStatus.INCONCLUSIVE
    assert outcome.direction == VisualDirection.NONE
    assert any("temporal coverage" in reason.lower() for reason in outcome.reasons)
