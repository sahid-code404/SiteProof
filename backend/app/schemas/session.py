import enum
import uuid
from datetime import datetime

from pydantic import Field, field_validator

from app.models.verification import (
    EvidenceFileType,
    EvidenceUploadStatus,
    VerificationSessionStatus,
)
from app.schemas.base import APIModel


class DeviceCapabilities(APIModel):
    accelerometer: bool
    gyroscope: bool
    rotation_vector: bool
    magnetometer: bool = False


class CaptureLocation(APIModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    accuracy_meters: float = Field(ge=0, le=10000)
    altitude_meters: float | None = None
    bearing_degrees: float | None = Field(default=None, ge=0, le=360)
    speed_meters_per_second: float | None = Field(default=None, ge=0)
    captured_at: datetime | None = None
    elapsed_realtime_ns: int | None = Field(default=None, ge=0)


class SessionCreateRequest(APIModel):
    device_session_id: str = Field(min_length=8, max_length=80)
    client_time: datetime | None = None
    client_monotonic_ns: int | None = Field(default=None, ge=0)
    client_version: str | None = Field(default=None, max_length=50)
    android_version: str | None = Field(default=None, max_length=50)
    device_model: str | None = Field(default=None, max_length=160)


class SessionCreateResponse(APIModel):
    session_id: uuid.UUID
    inspection_id: uuid.UUID
    status: VerificationSessionStatus
    expires_at: datetime
    server_time: datetime
    clock_offset_ms: float | None = None
    required_capture_duration_seconds: int = Field(ge=10, le=75)
    capture_maximum_seconds: int = Field(ge=10, le=90)
    allowed_radius_meters: int = Field(ge=10, le=5000)
    deadline: datetime


class StartCaptureRequest(APIModel):
    client_wall_clock: datetime
    client_monotonic_ns: int = Field(ge=0)
    location: CaptureLocation
    capabilities: DeviceCapabilities


class SensorSummary(APIModel):
    accelerometer_samples: int = Field(ge=0)
    gyroscope_samples: int = Field(ge=0)
    rotation_vector_samples: int = Field(ge=0)
    magnetometer_samples: int = Field(default=0, ge=0)


class LocationSummary(APIModel):
    location_samples: int = Field(ge=0)
    best_accuracy_meters: float | None = Field(default=None, ge=0)
    first_relative_timestamp_ns: int | None = Field(default=None, ge=0)
    last_relative_timestamp_ns: int | None = Field(default=None, ge=0)


class CaptureCompleteRequest(APIModel):
    capture_duration_ms: int = Field(gt=0)
    video_file_count: int = Field(default=1, ge=0, le=5)
    sensor_summary: SensorSummary
    location_summary: LocationSummary


class AbortReason(str, enum.Enum):
    USER_CANCELLED = "USER_CANCELLED"
    CAMERA_ERROR = "CAMERA_ERROR"
    LOCATION_LOST = "LOCATION_LOST"
    APP_INTERRUPTED = "APP_INTERRUPTED"
    SENSOR_ERROR = "SENSOR_ERROR"
    TIMEOUT = "TIMEOUT"
    UNKNOWN = "UNKNOWN"


class AbortRequest(APIModel):
    reason: AbortReason


class EvidenceFileRequest(APIModel):
    type: EvidenceFileType
    filename: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    mime_type: str = Field(min_length=3, max_length=100)

    @field_validator("sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return value.lower()


class EvidenceInitiateRequest(APIModel):
    idempotency_key: str = Field(min_length=8, max_length=120)
    files: list[EvidenceFileRequest] = Field(min_length=1, max_length=6)


class EvidenceUploadTarget(APIModel):
    file_id: uuid.UUID
    type: EvidenceFileType
    upload_path: str
    method: str = "PUT"
    already_uploaded: bool = False


class EvidenceInitiateResponse(APIModel):
    session_id: uuid.UUID
    status: VerificationSessionStatus
    targets: list[EvidenceUploadTarget]


class EvidenceCompleteRequest(APIModel):
    manifest_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")

    @field_validator("manifest_sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return value.lower()


class EvidenceFileResponse(APIModel):
    id: uuid.UUID
    type: EvidenceFileType
    filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    upload_status: EvidenceUploadStatus
    hash_verified: bool
    uploaded_at: datetime | None = None
    download_path: str | None = None


class EvidencePresence(APIModel):
    video: bool
    sensor_data: bool
    location_data: bool
    session_metadata: bool
    manifest: bool


class VerificationSessionResponse(APIModel):
    id: uuid.UUID
    inspection_id: uuid.UUID
    inspector_id: uuid.UUID
    status: VerificationSessionStatus
    created_at: datetime
    capture_started_at: datetime | None = None
    capture_ended_at: datetime | None = None
    uploaded_at: datetime | None = None
    expires_at: datetime
    capture_duration_ms: int | None = None
    manifest_sha256: str | None = None
    sensor_summary: SensorSummary | None = None
    location_summary: LocationSummary | None = None
    evidence: EvidencePresence


class EvidenceListResponse(APIModel):
    session_id: uuid.UUID
    items: list[EvidenceFileResponse]


class ManifestEntry(APIModel):
    type: EvidenceFileType
    name: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")

    @field_validator("sha256")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return value.lower()


class EvidenceManifestDocument(APIModel):
    session_id: uuid.UUID
    files: list[ManifestEntry] = Field(min_length=1, max_length=6)
