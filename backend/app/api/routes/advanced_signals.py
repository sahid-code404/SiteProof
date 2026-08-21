from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_roles
from app.core.errors import SiteProofError
from app.db.session import get_db
from app.models.advanced_signals import AdvancedSignalResult
from app.models.user import User, UserRole
from app.models.verification import VerificationSession
from app.schemas.advanced_signals import AdvancedSignalsResponse
from app.services.advanced_signals_service import ANALYSIS_VERSION, analyze_advanced_signals

router = APIRouter(tags=["advanced-signals"])


def _session(db: Session, current_user: User, session_id: uuid.UUID) -> VerificationSession:
    session = db.get(VerificationSession, session_id)
    if session is None or session.organization_id != current_user.organization_id:
        raise SiteProofError(404, "SESSION_NOT_FOUND", "Verification session was not found.")
    return session


def _response(row: AdvancedSignalResult) -> AdvancedSignalsResponse:
    return AdvancedSignalsResponse(
        session_id=row.session_id,
        algorithm_version=row.algorithm_version,
        process_status=row.process_status,
        environment_status=row.environment_status,
        environment_consistency_score=row.environment_consistency_score,
        environment_risk_score=row.environment_risk_score,
        environment_confidence=row.environment_confidence,
        statistical_anomaly_status=row.statistical_anomaly_status,
        statistical_anomaly_score=row.statistical_anomaly_score,
        statistical_anomaly_confidence=row.statistical_anomaly_confidence,
        reason_codes=row.reason_codes_json or [],
        reasons=row.reasons_json or [],
        metrics=row.metrics_json or {},
    )


@router.get("/sessions/{session_id}/advanced-signals", response_model=AdvancedSignalsResponse | None)
def get_advanced_signals(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AdvancedSignalsResponse | None:
    session = _session(db, current_user, session_id)
    row = db.scalar(
        select(AdvancedSignalResult).where(
            AdvancedSignalResult.session_id == session.id,
            AdvancedSignalResult.algorithm_version == ANALYSIS_VERSION,
        )
    )
    return _response(row) if row is not None else None


@router.post("/sessions/{session_id}/advanced-signals/analyze", response_model=AdvancedSignalsResponse)
def run_advanced_signals(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER)),
) -> AdvancedSignalsResponse:
    session = _session(db, current_user, session_id)
    return _response(analyze_advanced_signals(db, session.id, force=True))
