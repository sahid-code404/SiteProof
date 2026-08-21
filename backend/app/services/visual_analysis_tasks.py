import logging
import uuid

from app.db.session import SessionLocal
from app.services.fusion.service import run_fusion_analysis_task
from app.services.visual_analysis_service import analyze_session_visual_motion

logger = logging.getLogger("siteproof.vision")


def run_visual_analysis_retry_task(session_id: uuid.UUID) -> None:
    db = SessionLocal()
    try:
        analyze_session_visual_motion(db, session_id, force=True)
    except Exception:
        logger.exception("forced visual analysis failed for session %s", session_id)
    finally:
        db.close()

    # A Phase 5 retry can change the visual input for an existing Phase 6 result.
    # Re-run the same version idempotently after the visual attempt finishes.
    run_fusion_analysis_task(session_id, force=True)
