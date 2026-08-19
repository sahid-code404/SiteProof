from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.challenge import VerificationChallenge
from app.models.inspection import Inspection
from app.models.verification import VerificationSession
from app.services.verification.challenge_sensor import challenge_signal, sensor_signal
from app.services.verification.domain import VerificationSignal
from app.services.verification.location_time import location_signal, session_time_signal
from app.services.verification.policy import ResolvedPolicy
from app.services.verification.visual_fusion import (
    continuity_signal,
    fusion_rows,
    fusion_signal,
    visual_rows,
    visual_signal,
)


def _latest_challenges(db: Session, session_id) -> list[VerificationChallenge]:
    rows = list(db.scalars(select(VerificationChallenge).where(VerificationChallenge.session_id == session_id).order_by(VerificationChallenge.sequence_number, VerificationChallenge.attempt_number)).all())
    latest: dict[int, VerificationChallenge] = {}
    for row in rows:
        if row.sequence_number not in latest or row.attempt_number > latest[row.sequence_number].attempt_number:
            latest[row.sequence_number] = row
    return [latest[key] for key in sorted(latest)]


def collect_signals(db: Session, session: VerificationSession, policy: ResolvedPolicy) -> tuple[list[VerificationSignal], bool]:
    inspection = db.get(Inspection, session.inspection_id)
    if inspection is None or inspection.organization_id != session.organization_id:
        raise ValueError("Verification session inspection is unavailable or cross-organization.")
    challenges = _latest_challenges(db, session.id)
    visual = visual_rows(db, challenges)
    fusion = fusion_rows(db, challenges)
    signals = [
        location_signal(session, policy),
        session_time_signal(session, challenges, policy),
        challenge_signal(challenges, policy),
        sensor_signal(challenges, session, policy),
        visual_signal(visual, challenges, policy),
        continuity_signal(visual, challenges, policy),
        fusion_signal(fusion, challenges, policy),
    ]
    return signals, any(signal.metrics.get("processing") is True for signal in signals)
