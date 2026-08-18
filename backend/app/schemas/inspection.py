import uuid
from datetime import datetime, timezone

from pydantic import Field, field_validator

from app.models.assignment import AssignmentStatus
from app.models.inspection import InspectionPriority, InspectionStatus, InspectionType
from app.schemas.base import APIModel
from app.schemas.inspector import InspectorResponse


class LocationInput(APIModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    name: str | None = Field(default=None, max_length=200)
    address: str | None = Field(default=None, max_length=500)


class InspectionCreate(APIModel):
    title: str = Field(min_length=3, max_length=150)
    description: str | None = Field(default=None, max_length=5000)
    inspection_type: InspectionType = InspectionType.GENERAL
    location: LocationInput
    allowed_radius_meters: int = Field(default=100, ge=10, le=5000)
    deadline: datetime
    priority: InspectionPriority = InspectionPriority.MEDIUM
    instructions: str | None = Field(default=None, max_length=5000)

    @field_validator("deadline")
    @classmethod
    def deadline_must_be_future(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        if value.astimezone(timezone.utc) <= datetime.now(timezone.utc):
            raise ValueError("deadline must be in the future")
        return value.astimezone(timezone.utc)


class InspectionUpdate(APIModel):
    title: str | None = Field(default=None, min_length=3, max_length=150)
    description: str | None = Field(default=None, max_length=5000)
    inspection_type: InspectionType | None = None
    location: LocationInput | None = None
    allowed_radius_meters: int | None = Field(default=None, ge=10, le=5000)
    deadline: datetime | None = None
    priority: InspectionPriority | None = None
    instructions: str | None = Field(default=None, max_length=5000)

    @field_validator("deadline")
    @classmethod
    def update_deadline_must_be_future(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        if value.astimezone(timezone.utc) <= datetime.now(timezone.utc):
            raise ValueError("deadline must be in the future")
        return value.astimezone(timezone.utc)


class AssignmentRequest(APIModel):
    inspector_id: uuid.UUID


class ReassignmentRequest(AssignmentRequest):
    reason: str = Field(min_length=3, max_length=500)


class CancelRequest(APIModel):
    reason: str = Field(min_length=3, max_length=500)


class AssignmentResponse(APIModel):
    id: uuid.UUID
    inspector: InspectorResponse
    status: AssignmentStatus
    assigned_at: datetime
    acknowledged_at: datetime | None = None
    unassigned_at: datetime | None = None
    reason: str | None = None


class InspectionResponse(APIModel):
    id: uuid.UUID
    title: str
    description: str | None
    inspection_type: InspectionType
    status: InspectionStatus
    expected_latitude: float
    expected_longitude: float
    allowed_radius_meters: int
    location_name: str | None
    location_address: str | None
    deadline: datetime
    priority: InspectionPriority
    instructions: str | None
    created_at: datetime
    updated_at: datetime
    cancelled_at: datetime | None
    is_overdue: bool
    active_assignment: AssignmentResponse | None = None


class InspectionDetail(InspectionResponse):
    assignment_history: list[AssignmentResponse] = Field(default_factory=list)
    created_by_name: str


class InspectionPage(APIModel):
    items: list[InspectionResponse]
    page: int
    page_size: int
    total_items: int
    total_pages: int


class DashboardSummary(APIModel):
    total: int
    draft: int
    assigned: int
    acknowledged: int
    ready: int
    cancelled: int
    due_today: int
    overdue: int
    high_priority: int
