import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class InspectionType(str, enum.Enum):
    ROAD_REPAIR = "ROAD_REPAIR"
    INFRASTRUCTURE = "INFRASTRUCTURE"
    CONSTRUCTION = "CONSTRUCTION"
    UTILITY = "UTILITY"
    GENERAL = "GENERAL"


class InspectionPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class InspectionStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ASSIGNED = "ASSIGNED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    READY = "READY"
    SESSION_STARTED = "SESSION_STARTED"
    EVIDENCE_UPLOADING = "EVIDENCE_UPLOADING"
    PROCESSING = "PROCESSING"
    CANCELLED = "CANCELLED"


class Inspection(Base):
    __tablename__ = "inspections"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(150), index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    inspection_type: Mapped[InspectionType] = mapped_column(
        Enum(InspectionType, native_enum=False, length=32), index=True, nullable=False
    )
    status: Mapped[InspectionStatus] = mapped_column(
        Enum(InspectionStatus, native_enum=False, length=32),
        default=InspectionStatus.DRAFT,
        index=True,
        nullable=False,
    )
    expected_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    expected_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    allowed_radius_meters: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    location_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    location_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    priority: Mapped[InspectionPriority] = mapped_column(
        Enum(InspectionPriority, native_enum=False, length=20),
        default=InspectionPriority.MEDIUM,
        index=True,
        nullable=False,
    )
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
