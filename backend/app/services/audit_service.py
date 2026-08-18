import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditLog

logger = logging.getLogger("siteproof.audit")


def record_audit(
    db: Session,
    *,
    organization_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    metadata: dict[str, Any] | None = None,
) -> AuditLog:
    event = AuditLog(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        event_metadata=metadata or {},
    )
    db.add(event)
    logger.info(
        "audit action=%s organization_id=%s entity_type=%s entity_id=%s actor_user_id=%s",
        action,
        organization_id,
        entity_type,
        entity_id,
        actor_user_id,
    )
    return event
