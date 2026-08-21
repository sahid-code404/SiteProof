import logging
import uuid

from app.db.session import SessionLocal
from app.services.advanced_security_service import analyze_advanced_security

logger = logging.getLogger("siteproof.advanced-security")


def run_advanced_security_task(session_id: uuid.UUID, *, force: bool = False) -> None:
    db = SessionLocal()
    try:
        analyze_advanced_security(db, session_id, force=force)
    except Exception:
        db.rollback()
        logger.exception("advanced security analysis failed for session %s", session_id)
    finally:
        db.close()
