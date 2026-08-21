import logging
import uuid

from app.services.fusion.service import run_fusion_analysis_task
from app.services.visual_analysis_service import run_visual_analysis_task

logger = logging.getLogger("siteproof.fusion")


def run_visual_then_fusion_task(session_id: uuid.UUID) -> None:
    # Phase 5 remains the producer of visual evidence. It handles and records its own
    # failures; Phase 6 then observes the resulting terminal visual state and either
    # compares it or stores an INCONCLUSIVE cross-signal result.
    run_visual_analysis_task(session_id)
    run_fusion_analysis_task(session_id)


def run_fusion_analysis_retry_task(session_id: uuid.UUID) -> None:
    run_fusion_analysis_task(session_id, force=True)
