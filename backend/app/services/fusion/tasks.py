import logging
import uuid

from app.services.advanced_security_tasks import run_advanced_security_task
from app.services.fusion.service import run_fusion_analysis_task
from app.services.verification.tasks import run_verification_task
from app.services.visual_analysis_service import run_visual_analysis_task

logger = logging.getLogger("siteproof.fusion")


def run_visual_then_fusion_task(session_id: uuid.UUID) -> None:
    # Phase 5 produces camera evidence, Phase 6 compares it with physical motion,
    # Phase 7 calculates the explainable trust result, Phase 8 seals/signs that result,
    # and Phase 9 adds independent anti-spoofing risk analysis.
    run_visual_analysis_task(session_id)
    run_fusion_analysis_task(session_id)
    run_verification_task(session_id, force=True)
    run_advanced_security_task(session_id, force=True)


def run_fusion_analysis_retry_task(session_id: uuid.UUID) -> None:
    run_fusion_analysis_task(session_id, force=True)
    run_verification_task(session_id, force=True)
    run_advanced_security_task(session_id, force=True)
