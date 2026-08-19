import logging
import uuid

from app.services.fusion.service import run_fusion_analysis_task
from app.services.verification.tasks import run_verification_task
from app.services.visual_analysis_service import run_visual_analysis_task

logger = logging.getLogger("siteproof.fusion")


def run_visual_then_fusion_task(session_id: uuid.UUID) -> None:
    # Phase 5 remains the producer of visual evidence. Phase 6 then compares it with the
    # independent sensor evidence, and Phase 7 consumes only those persisted terminal inputs.
    run_visual_analysis_task(session_id)
    run_fusion_analysis_task(session_id)
    run_verification_task(session_id)


def run_fusion_analysis_retry_task(session_id: uuid.UUID) -> None:
    run_fusion_analysis_task(session_id, force=True)
    # A changed Phase 6 result creates a new Phase 7 calculation revision rather than
    # silently overwriting the historical trust result.
    run_verification_task(session_id, force=True)
