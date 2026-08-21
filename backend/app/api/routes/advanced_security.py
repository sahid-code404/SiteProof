from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, require_roles
from app.core.errors import SiteProofError
from app.db.session import get_db
from app.models.advanced_security import AdvancedSecurityResult
from app.models.user import User, UserRole
from app.models.verification import VerificationSession
from app.schemas.advanced_security import AdvancedSecurityResponse
from app.services.advanced_security_service import ANALYSIS_VERSION, analyze_advanced_security

router = APIRouter(tags=["advanced-security"])


def _session(db: Session, current_user: User, session_id: uuid.UUID) -> VerificationSession:
    session = db.get(VerificationSession, session_id)
    if session is None or session.organization_id != current_user.organization_id:
        raise SiteProofError(404, "SESSION_NOT_FOUND", "Verification session was not found.")
    return session


def _response(row: AdvancedSecurityResult) -> AdvancedSecurityResponse:
    return AdvancedSecurityResponse(
        session_id=row.session_id,
        algorithm_version=row.algorithm_version,
        process_status=row.process_status.value,
        overall_risk=row.overall_risk.value,
        confidence=row.confidence,
        location_risk_score=row.location_risk_score,
        sensor_anomaly_score=row.sensor_anomaly_score,
        replay_risk_score=row.replay_risk_score,
        evidence_reuse_score=row.evidence_reuse_score,
        device_integrity_status=row.device_integrity_status,
        device_risk_score=row.device_risk_score,
        reason_codes=row.reason_codes_json or [],
        reasons=row.reasons_json or [],
        metrics=row.metrics_json or {},
    )


@router.get("/sessions/{session_id}/advanced-security", response_model=AdvancedSecurityResponse | None)
def get_advanced_security(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AdvancedSecurityResponse | None:
    session = _session(db, current_user, session_id)
    row = db.scalar(
        select(AdvancedSecurityResult).where(
            AdvancedSecurityResult.session_id == session.id,
            AdvancedSecurityResult.algorithm_version == ANALYSIS_VERSION,
        )
    )
    return _response(row) if row is not None else None


@router.post("/sessions/{session_id}/advanced-security/analyze", response_model=AdvancedSecurityResponse)
def run_advanced_security(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER)),
) -> AdvancedSecurityResponse:
    session = _session(db, current_user, session_id)
    return _response(analyze_advanced_security(db, session.id, force=True))
