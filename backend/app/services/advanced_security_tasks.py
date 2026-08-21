import logging
import uuid

from app.db.session import SessionLocal
from app.services.advanced_security_service import analyze_advanced_security
from app.services.advanced_signals_service import analyze_advanced_signals

logger = logging.getLogger("siteproof.advanced-security")


def run_advanced_security_task(session_id: uuid.UUID, *, force: bool = False) -> None:
    db = SessionLocal()
    try:
        analyze_advanced_security(db, session_id, force=force)
        analyze_advanced_signals(db, session_id, force=force)
    except Exception:
        db.rollback()
        logger.exception("advanced security/signals analysis failed for session %s", session_id)
    finally:
        db.close()
