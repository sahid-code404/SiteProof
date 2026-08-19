import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from app.models.challenge import ChallengeResult, ChallengeStatus, ChallengeType
from app.models.verification import VerificationSessionStatus
from app.schemas.base import APIModel


class ChallengeSensorType(str, enum.Enum):
    ACCELEROMETER = "ACCELEROMETER"
    GYROSCOPE = "GYROSCOPE"
    ROTATION_VECTOR = "ROTATION_VECTOR"


class ChallengeParameters(APIModel):
    target_degrees: float
    min_degrees: float
    max_degrees: float


class ChallengeIssueResponse(APIModel):
    challenge_id: uuid.UUID
    sequence_number: int
    attempt_number: int
    total_challenges: int
    type: ChallengeType
    instruction: str
    parameters: ChallengeParameters
    issued_at: datetime
    expires_at: datetime
    server_time: datetime
    nonce: str


class ChallengeStartRequest(APIModel):
    nonce: str = Field(min_length=16, max_length=128)
    client_monotonic_ns: int = Field(ge=0)


class ChallengeSensorWindow(APIModel):
    start_relative_ns: int = Field(ge=0)
    end_relative_ns: int = Field(gt=0)

    @field_validator("end_relative_ns")
    @classmethod
    def end_is_positive(cls, value: int) -> int:
        return value


class ChallengeSensorSample(APIModel):
    type: ChallengeSensorType
    relative_timestamp_ns: int = Field(ge=0)
    values: list[float] = Field(min_length=3, max_length=5)
    accuracy: int | None = None


class ClientSensorSummary(APIModel):
    gyro_samples: int = Field(default=0, ge=0)
    rotation_vector_samples: int = Field(default=0, ge=0)
    accelerometer_samples: int = Field(default=0, ge=0)


class ChallengeSubmitRequest(APIModel):
    nonce: str = Field(min_length=16, max_length=128)
    idempotency_key: str = Field(min_length=8, max_length=120)
    sensor_window: ChallengeSensorWindow
    samples: list[ChallengeSensorSample] = Field(min_length=2, max_length=5000)
    sensor_summary: ClientSensorSummary | None = None


class ChallengeValidationResponse(APIModel):
    challenge_id: uuid.UUID
    sequence_number: int
    type: ChallengeType
    result: ChallengeResult
    score: float = Field(ge=0, le=1)
    reasons: list[str]
    metrics: dict[str, Any]
    sensor_quality: dict[str, Any]
    retry_allowed: bool
    sequence_complete: bool
    session_status: VerificationSessionStatus
    server_time: datetime


class ChallengeTimelineItem(APIModel):
    id: uuid.UUID
    sequence_number: int
    attempt_number: int
    type: ChallengeType
    status: ChallengeStatus
    result: ChallengeResult | None = None
    parameters: ChallengeParameters
    issued_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    expires_at: datetime
    score: float | None = None
    sensor_score: float | None = None
    failure_reason: str | None = None
    reasons: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    sensor_quality: dict[str, Any] = Field(default_factory=dict)


class ChallengeListResponse(APIModel):
    session_id: uuid.UUID
    total_required: int
    items: list[ChallengeTimelineItem]
