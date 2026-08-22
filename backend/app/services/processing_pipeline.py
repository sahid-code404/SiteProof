from __future__ import annotations

import uuid

from app.db.session import SessionLocal
from app.models.trust import VerificationProcessingStatus
from app.services.advanced_security_service import analyze_advanced_security
from app.services.advanced_signals_service import analyze_advanced_signals
from app.services.fusion.service import analyze_session_fusion
from app.services.receipt_service import issue_automated_receipt
from app.services.receipt_signing import signing_enabled
from app.services.verification.security_gate import SECURITY_ENGINE_VERSION
from app.services.verification.service import calculate_verification
from app.services.visual_analysis_service import analyze_session_visual_motion


def run_verification_pipeline(session_id: uuid.UUID) -> None:
    """Run one idempotent durable processing attempt and propagate failures to the queue.

    Order matters: visual motion and fusion establish physical consistency; Phase 9 and Phase 10
    then calculate security/supporting signals; only after those rows exist does the v2 trust
    engine produce an automated decision and, when enabled, a signed receipt.
    """
    db = SessionLocal()
    try:
        analyze_session_visual_motion(db, session_id)
        analyze_session_fusion(db, session_id, force=True)
        analyze_advanced_security(db, session_id, force=True)
        analyze_advanced_signals(db, session_id, force=True)
        result = calculate_verification(db, session_id, force=True)
        if result.engine_version != SECURITY_ENGINE_VERSION:
            raise RuntimeError(
                "Security analysis did not become authoritative; refusing to finalize a legacy verdict."
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
