import logging
import uuid

from app.services.fusion.service import run_fusion_analysis_task
from app.services.verification.tasks import run_verification_task
from app.services.visual_analysis_service import run_visual_analysis_task

logger = logging.getLogger("siteproof.fusion")


def run_visual_then_fusion_task(session_id: uuid.UUID) -> None:
    # Phase 5 produces camera evidence, Phase 6 compares it with physical motion,
    # then Phase 7 calculates the explainable final trust result from terminal evidence.
    run_visual_analysis_task(session_id)
    run_fusion_analysis_task(session_id)
    run_verification_task(session_id, force=True)


def run_fusion_analysis_retry_task(session_id: uuid.UUID) -> None:
    run_fusion_analysis_task(session_id, force=True)
    run_verification_task(session_id, force=True)
