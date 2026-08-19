import logging
import uuid

from app.db.session import SessionLocal
from app.services.verification.engine import VerificationEngine

logger = logging.getLogger("siteproof.verification")


def run_verification_task(
    session_id: uuid.UUID,
    *,
    force: bool = False,
    policy_version: str | None = None,
) -> None:
    db = SessionLocal()
    try:
        VerificationEngine().calculate(
            db,
            session_id,
            force=force,
            policy_version=policy_version,
        )
    except Exception:
        db.rollback()
        logger.exception("verification calculation failed for session %s", session_id)
    finally:
        db.close()
