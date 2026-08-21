import logging
import uuid

from app.db.session import SessionLocal
from app.models.trust import VerificationProcessingStatus
from app.services.receipt_service import issue_automated_receipt
from app.services.receipt_signing import signing_enabled
from app.services.verification.service import calculate_verification

logger = logging.getLogger("siteproof.verification")


def run_verification_task(session_id: uuid.UUID, *, force: bool = False) -> None:
    db = SessionLocal()
    try:
        result = calculate_verification(db, session_id, force=force)
        if (
            result.processing_status == VerificationProcessingStatus.COMPLETED
            and signing_enabled()
        ):
            issue_automated_receipt(db, result.id)
    except Exception:
        db.rollback()
        logger.exception(
            "verification calculation or receipt issuance failed for session %s",
            session_id,
        )
    finally:
        db.close()
