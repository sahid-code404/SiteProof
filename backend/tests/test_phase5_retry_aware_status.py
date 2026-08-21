import uuid
from types import SimpleNamespace

from app.models.visual_motion import VisualAnalysisStatus
from app.services.visual_analysis_status import retry_aware_status


def _challenge(sequence: int, attempt: int):
    return SimpleNamespace(
        id=uuid.uuid4(),
        sequence_number=sequence,
        attempt_number=attempt,
    )


def _item(challenge_id, status: VisualAnalysisStatus):
    return SimpleNamespace(challenge_id=challenge_id, status=status)


def test_superseded_inconclusive_retry_does_not_poison_overall_status():
    first = _challenge(1, 1)
    retry_old = _challenge(2, 1)
    retry_pass = _challenge(2, 2)
    third = _challenge(3, 1)

    challenges = [first, retry_old, retry_pass, third]
    items = [
        _item(first.id, VisualAnalysisStatus.SUCCESS),
        _item(retry_old.id, VisualAnalysisStatus.INCONCLUSIVE),
        _item(retry_pass.id, VisualAnalysisStatus.SUCCESS),
        _item(third.id, VisualAnalysisStatus.SUCCESS),
    ]

    assert retry_aware_status(challenges, items) == VisualAnalysisStatus.SUCCESS


def test_terminal_inconclusive_still_controls_overall_status():
    first = _challenge(1, 1)
    retry_old = _challenge(2, 1)
    retry_pass = _challenge(2, 2)
    third = _challenge(3, 1)

    challenges = [first, retry_old, retry_pass, third]
    items = [
        _item(first.id, VisualAnalysisStatus.SUCCESS),
        _item(retry_old.id, VisualAnalysisStatus.INCONCLUSIVE),
        _item(retry_pass.id, VisualAnalysisStatus.SUCCESS),
        _item(third.id, VisualAnalysisStatus.INCONCLUSIVE),
    ]

    assert retry_aware_status(challenges, items) == VisualAnalysisStatus.INCONCLUSIVE


def test_missing_terminal_retry_is_processing_not_false_success():
    first = _challenge(1, 1)
    retry_old = _challenge(2, 1)
    retry_latest = _challenge(2, 2)

    challenges = [first, retry_old, retry_latest]
    items = [
        _item(first.id, VisualAnalysisStatus.SUCCESS),
        _item(retry_old.id, VisualAnalysisStatus.SUCCESS),
    ]

    assert retry_aware_status(challenges, items) == VisualAnalysisStatus.PROCESSING
