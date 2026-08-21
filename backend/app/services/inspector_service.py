import math
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.errors import SiteProofError
from app.core.security import hash_password
from app.models.inspector import Inspector
from app.models.user import User, UserRole
from app.schemas.inspector import (
    InspectorCreate,
    InspectorPage,
    InspectorPasswordReset,
    InspectorResponse,
    InspectorUpdate,
)


def _to_response(inspector: Inspector, user: User) -> InspectorResponse:
    return InspectorResponse(
        id=inspector.id,
        user_id=user.id,
        name=user.full_name,
        email=user.email,
        employee_code=inspector.employee_code,
        phone=inspector.phone,
        active=inspector.active and user.is_active,
    )


def _require_admin(current_user: User) -> None:
    if current_user.role != UserRole.ADMIN:
        raise SiteProofError(403, "FORBIDDEN", "Administrator access is required.")


def get_inspector_for_user(db: Session, user_id: uuid.UUID) -> Inspector | None:
    return db.scalar(select(Inspector).where(Inspector.user_id == user_id))


def get_inspector_in_org(
    db: Session, organization_id: uuid.UUID, inspector_id: uuid.UUID
) -> tuple[Inspector, User]:
    row = db.execute(
        select(Inspector, User)
        .join(User, User.id == Inspector.user_id)
        .where(
            Inspector.id == inspector_id,
            Inspector.organization_id == organization_id,
            User.organization_id == organization_id,
        )
    ).first()
    if row is None:
        raise SiteProofError(404, "INSPECTOR_NOT_FOUND", "Inspector was not found.")
    return row[0], row[1]


def create_inspector(db: Session, current_user: User, payload: InspectorCreate) -> InspectorResponse:
    _require_admin(current_user)
    normalized_email = str(payload.email).lower()
    if db.scalar(select(User).where(User.email == normalized_email)) is not None:
        raise SiteProofError(409, "EMAIL_ALREADY_EXISTS", "A user with this email already exists.")

    user = User(
        organization_id=current_user.organization_id,
        email=normalized_email,
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
        role=UserRole.INSPECTOR,
        is_active=True,
    )
    db.add(user)
    db.flush()
    inspector = Inspector(
        organization_id=current_user.organization_id,
        user_id=user.id,
        employee_code=payload.employee_code,
        phone=payload.phone,
        active=True,
    )
    db.add(inspector)
    db.commit()
    db.refresh(inspector)
    return _to_response(inspector, user)


def update_inspector(
    db: Session,
    current_user: User,
    inspector_id: uuid.UUID,
    payload: InspectorUpdate,
) -> InspectorResponse:
    _require_admin(current_user)
    inspector, user = get_inspector_in_org(db, current_user.organization_id, inspector_id)

    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
    if "employee_code" in payload.model_fields_set:
        inspector.employee_code = payload.employee_code
    if "phone" in payload.model_fields_set:
        inspector.phone = payload.phone
    if payload.active is not None:
        inspector.active = payload.active
        user.is_active = payload.active

    db.commit()
    db.refresh(inspector)
    db.refresh(user)
    return _to_response(inspector, user)


def reset_inspector_password(
    db: Session,
    current_user: User,
    inspector_id: uuid.UUID,
    payload: InspectorPasswordReset,
) -> None:
    _require_admin(current_user)
    _, user = get_inspector_in_org(db, current_user.organization_id, inspector_id)
    user.hashed_password = hash_password(payload.password)
    db.commit()


def list_inspectors(
    db: Session,
    current_user: User,
    *,
    search: str | None,
    active: bool | None,
    page: int,
    page_size: int,
) -> InspectorPage:
    if current_user.role not in {UserRole.ADMIN, UserRole.REVIEWER}:
        raise SiteProofError(403, "FORBIDDEN", "Administrator or reviewer access is required.")

    filters = [
        Inspector.organization_id == current_user.organization_id,
        User.organization_id == current_user.organization_id,
    ]
    if active is not None:
        filters.append(Inspector.active.is_(active))
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                User.full_name.ilike(pattern),
                User.email.ilike(pattern),
                Inspector.employee_code.ilike(pattern),
            )
        )

    total = db.scalar(
        select(func.count())
        .select_from(Inspector)
        .join(User, User.id == Inspector.user_id)
        .where(*filters)
    ) or 0
    rows = db.execute(
        select(Inspector, User)
        .join(User, User.id == Inspector.user_id)
        .where(*filters)
        .order_by(User.full_name.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return InspectorPage(
        items=[_to_response(inspector, user) for inspector, user in rows],
        page=page,
        page_size=page_size,
        total_items=total,
        total_pages=math.ceil(total / page_size) if total else 0,
    )
