from app.core.config import Settings
from app.models.challenge import VerificationChallenge
from app.services.challenges.service import _retry_count


def _row(sequence_number: int, attempt_number: int) -> VerificationChallenge:
    return VerificationChallenge(
        sequence_number=sequence_number,
        attempt_number=attempt_number,
    )


def test_phase4_retry_policy_has_at_least_three_reattempts():
    assert Settings(challenge_max_retries=1).challenge_max_retries == 3
    assert Settings().challenge_max_retries >= 3


def test_retry_budget_is_counted_per_challenge_sequence():
    rows = [
        _row(1, 1),
        _row(1, 2),
        _row(1, 3),
        _row(1, 4),
        _row(2, 1),
        _row(2, 2),
    ]

    assert _retry_count(rows, 1) == 3
    assert _retry_count(rows, 2) == 1
    assert _retry_count(rows, 3) == 0
