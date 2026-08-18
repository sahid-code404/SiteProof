import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, JSON, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True, nullable=False
    )
    event_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
