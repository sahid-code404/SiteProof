from __future__ import annotations

import uuid

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.trust import VerificationProcessingStatus
from app.services.advanced_security_service import analyze_advanced_security
from app.services.advanced_signals_service import analyze_advanced_signals
from app.services.autonomous_verification_service import analyze_autonomous_verification
from app.services.fusion.service import analyze_session_fusion
from app.services.receipt_service import issue_automated_receipt
from app.services.receipt_signing import signing_enabled
from app.services.verification.service import calculate_verification
from app.services.verification.versions import AUTONOMOUS_ENGINE_VERSION, SECURITY_ENGINE_VERSION
from app.services.visual_analysis_service import analyze_session_visual_motion


def run_verification_pipeline(session_id: uuid.UUID) -> None:
    """Run one idempotent durable processing attempt and propagate failures to the queue.

    Physical motion/fusion and deterministic security run first. When autonomous verification is
    enabled, semantic contract/VLM analysis runs before the final trust decision. The AI layer is
    fail-closed and can only constrain the deterministic result; it never grants verification.
    """
    db = SessionLocal()
    try:
        analyze_session_visual_motion(db, session_id)
        analyze_session_fusion(db, session_id, force=True)
        analyze_advanced_security(db, session_id, force=True)
        analyze_advanced_signals(db, session_id, force=True)
        settings = get_settings()
        if settings.autonomous_verification_enabled:
            analyze_autonomous_verification(db, session_id, force=True)
        result = calculate_verification(db, session_id, force=True)
        expected_engine = (
            AUTONOMOUS_ENGINE_VERSION
            if settings.autonomous_verification_enabled
            else SECURITY_ENGINE_VERSION
        )
        if result.engine_version != expected_engine:
            raise RuntimeError(
                "Required verification analysis did not become authoritative; refusing to finalize a weaker engine verdict."
            )
        if result.processing_status != VerificationProcessingStatus.COMPLETED:
            raise RuntimeError(
                f"Verification pipeline did not reach a terminal result: {result.processing_status.value}."
            )
        if signing_enabled():
            issue_automated_receipt(db, result.id)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
