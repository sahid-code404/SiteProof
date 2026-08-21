from __future__ import annotations

import uuid
from typing import Any

from app.schemas.base import APIModel


class AdvancedSecurityResponse(APIModel):
    session_id: uuid.UUID
    algorithm_version: str
    process_status: str
    overall_risk: str
    confidence: float
    location_risk_score: float
    sensor_anomaly_score: float
    replay_risk_score: float
    evidence_reuse_score: float
    device_integrity_status: str
    device_risk_score: float
    reason_codes: list[str]
    reasons: list[str]
    metrics: dict[str, Any]
