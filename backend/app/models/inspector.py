import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Inspector(Base):
    __tablename__ = "inspectors"
    __table_args__ = (UniqueConstraint("organization_id", "employee_code", name="uq_inspector_employee_code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), unique=True, index=True, nullable=False
    )
    employee_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
