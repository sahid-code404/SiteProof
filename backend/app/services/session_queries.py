import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.verification import VerificationSession
from app.schemas.session import VerificationSessionResponse
from app.services.session_common import expire_if_needed, scoped_inspection, session_response, viewable_session


def get_session(db: Session, current_user: User, session_id: uuid.UUID) -> VerificationSessionResponse:
    session = viewable_session(db, current_user, session_id)
    if expire_if_needed(db, session, actor_user_id=current_user.id):
        db.commit()
        db.refresh(session)
    return session_response(db, session)


def latest_session_for_inspection(
    db: Session, current_user: User, inspection_id: uuid.UUID
) -> VerificationSessionResponse | None:
    scoped_inspection(db, current_user, inspection_id)
    session = db.scalar(
        select(VerificationSession)
        .where(
            VerificationSession.inspection_id == inspection_id,
            VerificationSession.organization_id == current_user.organization_id,
        )
        .order_by(VerificationSession.created_at.desc())
        .limit(1)
    )
    if session is None:
        return None
    if expire_if_needed(db, session, actor_user_id=current_user.id):
        db.commit()
        db.refresh(session)
    return session_response(db, session)
