import logging
import uuid

from app.db.session import SessionLocal
from app.services.verification.service import calculate_verification

logger = logging.getLogger("siteproof.verification")


def run_verification_task(session_id: uuid.UUID, *, force: bool = False) -> None:
    db = SessionLocal()
    try:
        calculate_verification(db, session_id, force=force)
    except Exception:
        db.rollback()
        logger.exception("verification calculation failed for session %s", session_id)
    finally:
        db.close()
