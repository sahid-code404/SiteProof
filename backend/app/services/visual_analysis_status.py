import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.challenge import VerificationChallenge
from app.models.user import User
from app.models.visual_motion import VisualAnalysisStatus
from app.schemas.visual_analysis import VisualAnalysisResponse, VisualChallengeAnalysisItem
from app.services.visual_analysis_service import get_visual_analysis


def _overall_status(items: list[VisualChallengeAnalysisItem]) -> VisualAnalysisStatus:
    if not items:
        return VisualAnalysisStatus.PENDING
    statuses = {item.status for item in items}
    if (
        VisualAnalysisStatus.PROCESSING in statuses
        or VisualAnalysisStatus.PENDING in statuses
    ):
        return VisualAnalysisStatus.PROCESSING
    if VisualAnalysisStatus.FAILED in statuses:
        return VisualAnalysisStatus.FAILED
    if VisualAnalysisStatus.INCONCLUSIVE in statuses:
        return VisualAnalysisStatus.INCONCLUSIVE
    return VisualAnalysisStatus.SUCCESS


def _terminal_attempt_ids(challenges: list[VerificationChallenge]) -> set[uuid.UUID]:
    """Return only the final attempt for each logical challenge sequence.

    Failed/inconclusive attempts remain visible in the audit timeline, but once the inspector
    retries the same sequence, the older attempt must not poison the session-level visual
    result. The highest attempt number is the terminal attempt for that sequence.
    """
    latest_by_sequence: dict[int, VerificationChallenge] = {}
    for challenge in challenges:
        current = latest_by_sequence.get(challenge.sequence_number)
        if current is None or challenge.attempt_number > current.attempt_number:
            latest_by_sequence[challenge.sequence_number] = challenge
    return {challenge.id for challenge in latest_by_sequence.values()}


def retry_aware_status(
    challenges: list[VerificationChallenge],
    items: list[VisualChallengeAnalysisItem],
) -> VisualAnalysisStatus:
    terminal_ids = _terminal_attempt_ids(challenges)
    if not terminal_ids:
        return _overall_status(items)

    terminal_items = [item for item in items if item.challenge_id in terminal_ids]
    represented_ids = {item.challenge_id for item in terminal_items}
    if represented_ids != terminal_ids:
        # Analysis for the accepted/latest attempt has not finished yet. Never let an older
        # retry result make the session look successful while the terminal attempt is missing.
        return VisualAnalysisStatus.PROCESSING
    return _overall_status(terminal_items)


def get_retry_aware_visual_analysis(
    db: Session,
    current_user: User,
    session_id: uuid.UUID,
) -> VisualAnalysisResponse:
    response = get_visual_analysis(db, current_user, session_id)
    challenges = list(
        db.scalars(
            select(VerificationChallenge)
            .where(VerificationChallenge.session_id == response.session_id)
            .order_by(
                VerificationChallenge.sequence_number,
                VerificationChallenge.attempt_number,
            )
        ).all()
    )
    status = retry_aware_status(challenges, response.challenges)
    return response.model_copy(update={"status": status})
