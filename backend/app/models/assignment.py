import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AssignmentStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    REASSIGNED = "REASSIGNED"
    CANCELLED = "CANCELLED"


class InspectionAssignment(Base):
    __tablename__ = "inspection_assignments"
    __table_args__ = (
        Index(
            "uq_active_assignment_per_inspection",
            "inspection_id",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
            sqlite_where=text("status = 'ACTIVE'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    inspection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("inspections.id", ondelete="CASCADE"), index=True, nullable=False
    )
    inspector_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("inspectors.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    assigned_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[AssignmentStatus] = mapped_column(
        Enum(AssignmentStatus, native_enum=False, length=20),
        default=AssignmentStatus.ACTIVE,
        index=True,
        nullable=False,
    )
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unassigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
