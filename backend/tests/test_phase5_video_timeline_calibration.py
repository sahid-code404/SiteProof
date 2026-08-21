from app.services.vision.timeline import map_challenge_window


def test_dual_anchor_mapping_keeps_late_challenge_inside_video() -> None:
    metadata = {
        "capture": {
            "videoStartRelativeNs": 500_000_000,
            # CameraX was active for 12.0 s of wall time while the encoded MP4 is 11.0 s.
            "videoEndRelativeNs": 12_500_000_000,
        },
        "challenges": [
            {
                "id": "late",
                "type": "ROTATE_LEFT",
                "startedRelativeMs": 10_900,
                "completedRelativeMs": 12_000,
            }
        ],
    }

    window = map_challenge_window(
        metadata,
        challenge_id="late",
        challenge_type="ROTATE_LEFT",
        pre_padding_ms=500,
        post_padding_ms=500,
        video_duration_ms=11_000,
    )

    assert 0 <= window.video_start_ms < 11_000
    assert window.video_start_ms < window.video_end_ms <= 11_000
    assert window.video_end_ms == 11_000


def test_legacy_start_only_mapping_remains_supported() -> None:
    metadata = {
        "capture": {"videoStartRelativeNs": 500_000_000},
        "challenges": [
            {
                "id": "legacy",
                "type": "ROTATE_RIGHT",
                "startedRelativeMs": 1_500,
                "completedRelativeMs": 2_500,
            }
        ],
    }

    window = map_challenge_window(
        metadata,
        challenge_id="legacy",
        challenge_type="ROTATE_RIGHT",
        pre_padding_ms=500,
        post_padding_ms=500,
        video_duration_ms=5_000,
    )

    assert window.video_start_ms == 500
    assert window.video_end_ms == 2_500
