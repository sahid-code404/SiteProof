from __future__ import annotations

import uuid
from typing import Any

from app.schemas.base import APIModel


class AdvancedSignalsResponse(APIModel):
    session_id: uuid.UUID
    algorithm_version: str
    process_status: str
    environment_status: str
    environment_consistency_score: float | None
    environment_risk_score: float
    environment_confidence: float
    statistical_anomaly_status: str
    statistical_anomaly_score: float
    statistical_anomaly_confidence: float
    reason_codes: list[str]
    reasons: list[str]
    metrics: dict[str, Any]
