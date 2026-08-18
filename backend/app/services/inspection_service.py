import math
import uuid
from datetime import datetime, time, timezone

from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import SiteProofError
from app.models.assignment import AssignmentStatus, InspectionAssignment
from app.models.inspection import Inspection, InspectionPriority, InspectionStatus
from app.models.inspector import Inspector
from app.models.user import User, UserRole
from app.schemas.inspection import (
    AssignmentResponse,
    CancelRequest,
    DashboardSummary,
    InspectionCreate,
    InspectionDetail,
    InspectionPage,
    InspectionResponse,
    InspectionUpdate,
    ReassignmentRequest,
)
from app.schemas.inspector import InspectorResponse
from app.services.audit_service import record_audit
from app.services.inspector_service import get_inspector_for_user, get_inspector_in_org


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _active_assignment(db: Session, inspection_id: uuid.UUID) -> InspectionAssignment | None:
    return db.scalar(
        select(InspectionAssignment).where(
            InspectionAssignment.inspection_id == inspection_id,
            InspectionAssignment.status == AssignmentStatus.ACTIVE,
        )
    )


def _assignment_response(db: Session, assignment: InspectionAssignment) -> AssignmentResponse:
    row = db.execute(
        select(Inspector, User)
        .join(User, User.id == Inspector.user_id)
        .where(Inspector.id == assignment.inspector_id)
    ).first()
    if row is None:
        raise SiteProofError(500, "ASSIGNMENT_DATA_INVALID", "Assignment inspector data is invalid.")
    inspector, user = row
    return AssignmentResponse(
        id=assignment.id,
        inspector=InspectorResponse(
            id=inspector.id,
            user_id=user.id,
            name=user.full_name,
            email=user.email,
            employee_code=inspector.employee_code,
            phone=inspector.phone,
            active=inspector.active and user.is_active,
        ),
        status=assignment.status,
        assigned_at=assignment.assigned_at,
        acknowledged_at=assignment.acknowledged_at,
        unassigned_at=assignment.unassigned_at,
        reason=assignment.reason,
    )


def _inspection_response(db: Session, inspection: Inspection) -> InspectionResponse:
    assignment = _active_assignment(db, inspection.id)
    deadline = _aware(inspection.deadline)
    return InspectionResponse(
        id=inspection.id,
        title=inspection.title,
        description=inspection.description,
        inspection_type=inspection.inspection_type,
        status=inspection.status,
        expected_latitude=inspection.expected_latitude,
        expected_longitude=inspection.expected_longitude,
        allowed_radius_meters=inspection.allowed_radius_meters,
        location_name=inspection.location_name,
        location_address=inspection.location_address,
        deadline=deadline,
        priority=inspection.priority,
        instructions=inspection.instructions,
        created_at=inspection.created_at,
        updated_at=inspection.updated_at,
        cancelled_at=inspection.cancelled_at,
        is_overdue=inspection.status != InspectionStatus.CANCELLED and deadline < _utc_now(),
        active_assignment=_assignment_response(db, assignment) if assignment else None,
    )


def _scoped_inspection(db: Session, current_user: User, inspection_id: uuid.UUID) -> Inspection:
    inspection = db.scalar(
        select(Inspection).where(
            Inspection.id == inspection_id,
            Inspection.organization_id == current_user.organization_id,
        )
    )
    if inspection is None:
        raise SiteProofError(404, "INSPECTION_NOT_FOUND", "Inspection was not found.")

    if current_user.role == UserRole.INSPECTOR:
        inspector = get_inspector_for_user(db, current_user.id)
        if inspector is None:
            raise SiteProofError(404, "INSPECTION_NOT_FOUND", "Inspection was not found.")
        assignment = db.scalar(
            select(InspectionAssignment).where(
                InspectionAssignment.inspection_id == inspection.id,
                InspectionAssignment.inspector_id == inspector.id,
                InspectionAssignment.status == AssignmentStatus.ACTIVE,
            )
        )
        if assignment is None:
            raise SiteProofError(404, "INSPECTION_NOT_FOUND", "Inspection was not found.")
    return inspection


def create_inspection(db: Session, current_user: User, payload: InspectionCreate) -> InspectionResponse:
    if current_user.role != UserRole.ADMIN:
        raise SiteProofError(403, "FORBIDDEN", "Only administrators can create inspections.")
    inspection = Inspection(
        organization_id=current_user.organization_id,
        title=payload.title.strip(),
        description=payload.description,
        inspection_type=payload.inspection_type,
        expected_latitude=payload.location.latitude,
        expected_longitude=payload.location.longitude,
        allowed_radius_meters=payload.allowed_radius_meters,
        location_name=payload.location.name,
        location_address=payload.location.address,
        deadline=payload.deadline,
        priority=payload.priority,
        instructions=payload.instructions,
        created_by_user_id=current_user.id,
        status=InspectionStatus.DRAFT,
    )
    db.add(inspection)
    db.flush()
    record_audit(
        db,
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        entity_type="INSPECTION",
        entity_id=inspection.id,
        action="INSPECTION_CREATED",
    )
    db.commit()
    db.refresh(inspection)
    return _inspection_response(db, inspection)


def update_inspection(
    db: Session, current_user: User, inspection_id: uuid.UUID, payload: InspectionUpdate
) -> InspectionResponse:
    if current_user.role != UserRole.ADMIN:
        raise SiteProofError(403, "FORBIDDEN", "Only administrators can update inspections.")
    inspection = _scoped_inspection(db, current_user, inspection_id)
    if inspection.status == InspectionStatus.CANCELLED:
        raise SiteProofError(409, "INSPECTION_NOT_EDITABLE", "Cancelled inspections cannot be edited.")

    changes = payload.model_dump(exclude_unset=True)
    location = changes.pop("location", None)
    required = {"title", "inspection_type", "allowed_radius_meters", "deadline", "priority"}
    for field in required:
        if field in changes and changes[field] is None:
            raise SiteProofError(422, "VALIDATION_ERROR", f"{field} cannot be null.")
    for field, value in changes.items():
        setattr(inspection, field, value)
    if location is not None:
        inspection.expected_latitude = location["latitude"]
        inspection.expected_longitude = location["longitude"]
        inspection.location_name = location.get("name")
        inspection.location_address = location.get("address")

    record_audit(
        db,
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        entity_type="INSPECTION",
        entity_id=inspection.id,
        action="INSPECTION_UPDATED",
        metadata={"fields": sorted(payload.model_fields_set)},
    )
    db.commit()
    db.refresh(inspection)
    return _inspection_response(db, inspection)


def _locked_inspection(db: Session, current_user: User, inspection_id: uuid.UUID) -> Inspection:
    inspection = db.scalar(
        select(Inspection)
        .where(
            Inspection.id == inspection_id,
            Inspection.organization_id == current_user.organization_id,
        )
        .with_for_update()
    )
    if inspection is None:
        raise SiteProofError(404, "INSPECTION_NOT_FOUND", "Inspection was not found.")
    return inspection


def assign_inspector(
    db: Session, current_user: User, inspection_id: uuid.UUID, inspector_id: uuid.UUID
) -> InspectionResponse:
    if current_user.role != UserRole.ADMIN:
        raise SiteProofError(403, "FORBIDDEN", "Only administrators can assign inspections.")
    inspection = _locked_inspection(db, current_user, inspection_id)
    if inspection.status == InspectionStatus.CANCELLED:
        raise SiteProofError(409, "INSPECTION_NOT_ASSIGNABLE", "Cancelled inspections cannot be assigned.")
    if inspection.status != InspectionStatus.DRAFT or _active_assignment(db, inspection.id) is not None:
        raise SiteProofError(409, "INSPECTION_NOT_ASSIGNABLE", "Use reassignment for an assigned inspection.")

    inspector, inspector_user = get_inspector_in_org(db, current_user.organization_id, inspector_id)
    if not inspector.active or not inspector_user.is_active:
        raise SiteProofError(409, "INSPECTOR_INACTIVE", "The selected inspector is inactive.")

    assignment = InspectionAssignment(
        organization_id=current_user.organization_id,
        inspection_id=inspection.id,
        inspector_id=inspector.id,
        assigned_by_user_id=current_user.id,
        status=AssignmentStatus.ACTIVE,
    )
    db.add(assignment)
    inspection.status = InspectionStatus.ASSIGNED
    record_audit(
        db,
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        entity_type="INSPECTION",
        entity_id=inspection.id,
        action="INSPECTION_ASSIGNED",
        metadata={"inspectorId": str(inspector.id)},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise SiteProofError(409, "ASSIGNMENT_CONFLICT", "Inspection already has an active assignment.") from exc
    db.refresh(inspection)
    return _inspection_response(db, inspection)


def reassign_inspector(
    db: Session,
    current_user: User,
    inspection_id: uuid.UUID,
    payload: ReassignmentRequest,
) -> InspectionResponse:
    if current_user.role != UserRole.ADMIN:
        raise SiteProofError(403, "FORBIDDEN", "Only administrators can reassign inspections.")
    inspection = _locked_inspection(db, current_user, inspection_id)
    if inspection.status == InspectionStatus.CANCELLED:
        raise SiteProofError(409, "INSPECTION_NOT_ASSIGNABLE", "Cancelled inspections cannot be reassigned.")
    old_assignment = _active_assignment(db, inspection.id)
    if old_assignment is None:
        raise SiteProofError(409, "NO_ACTIVE_ASSIGNMENT", "Inspection has no active assignment to replace.")

    inspector, inspector_user = get_inspector_in_org(
        db, current_user.organization_id, payload.inspector_id
    )
    if not inspector.active or not inspector_user.is_active:
        raise SiteProofError(409, "INSPECTOR_INACTIVE", "The selected inspector is inactive.")
    if old_assignment.inspector_id == inspector.id:
        raise SiteProofError(409, "SAME_INSPECTOR", "Inspection is already assigned to this inspector.")

    now = _utc_now()
    old_id = old_assignment.inspector_id
    old_assignment.status = AssignmentStatus.REASSIGNED
    old_assignment.unassigned_at = now
    old_assignment.reason = payload.reason
    db.flush()
    db.add(
        InspectionAssignment(
            organization_id=current_user.organization_id,
            inspection_id=inspection.id,
            inspector_id=inspector.id,
            assigned_by_user_id=current_user.id,
            status=AssignmentStatus.ACTIVE,
            reason=payload.reason,
        )
    )
    inspection.status = InspectionStatus.ASSIGNED
    record_audit(
        db,
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        entity_type="INSPECTION",
        entity_id=inspection.id,
        action="INSPECTION_REASSIGNED",
        metadata={
            "previousInspectorId": str(old_id),
            "newInspectorId": str(inspector.id),
            "reason": payload.reason,
        },
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise SiteProofError(409, "ASSIGNMENT_CONFLICT", "Inspection assignment changed concurrently.") from exc
    db.refresh(inspection)
    return _inspection_response(db, inspection)


def _require_active_assignee(
    db: Session, current_user: User, inspection: Inspection
) -> InspectionAssignment:
    if current_user.role != UserRole.INSPECTOR:
        raise SiteProofError(403, "FORBIDDEN", "Only the assigned inspector may perform this action.")
    inspector = get_inspector_for_user(db, current_user.id)
    if inspector is None:
        raise SiteProofError(403, "FORBIDDEN", "Inspector profile is missing.")
    assignment = _active_assignment(db, inspection.id)
    if assignment is None or assignment.inspector_id != inspector.id:
        raise SiteProofError(403, "NOT_ASSIGNED", "This inspection is not assigned to you.")
    return assignment


def acknowledge_inspection(db: Session, current_user: User, inspection_id: uuid.UUID) -> InspectionResponse:
    inspection = _scoped_inspection(db, current_user, inspection_id)
    assignment = _require_active_assignee(db, current_user, inspection)
    if inspection.status != InspectionStatus.ASSIGNED:
        raise SiteProofError(409, "INVALID_STATUS_TRANSITION", "Only assigned inspections can be acknowledged.")
    inspection.status = InspectionStatus.ACKNOWLEDGED
    assignment.acknowledged_at = _utc_now()
    record_audit(
        db,
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        entity_type="INSPECTION",
        entity_id=inspection.id,
        action="INSPECTION_ACKNOWLEDGED",
    )
    db.commit()
    db.refresh(inspection)
    return _inspection_response(db, inspection)


def mark_ready(db: Session, current_user: User, inspection_id: uuid.UUID) -> InspectionResponse:
    inspection = _scoped_inspection(db, current_user, inspection_id)
    _require_active_assignee(db, current_user, inspection)
    if inspection.status != InspectionStatus.ACKNOWLEDGED:
        raise SiteProofError(409, "INVALID_STATUS_TRANSITION", "Only acknowledged inspections can be marked ready.")
    inspection.status = InspectionStatus.READY
    record_audit(
        db,
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        entity_type="INSPECTION",
        entity_id=inspection.id,
        action="INSPECTION_READY",
    )
    db.commit()
    db.refresh(inspection)
    return _inspection_response(db, inspection)


def cancel_inspection(
    db: Session, current_user: User, inspection_id: uuid.UUID, payload: CancelRequest
) -> InspectionResponse:
    if current_user.role != UserRole.ADMIN:
        raise SiteProofError(403, "FORBIDDEN", "Only administrators can cancel inspections.")
    inspection = _locked_inspection(db, current_user, inspection_id)
    if inspection.status == InspectionStatus.CANCELLED:
        raise SiteProofError(409, "INVALID_STATUS_TRANSITION", "Inspection is already cancelled.")
    assignment = _active_assignment(db, inspection.id)
    if assignment:
        assignment.status = AssignmentStatus.CANCELLED
        assignment.unassigned_at = _utc_now()
        assignment.reason = payload.reason
    inspection.status = InspectionStatus.CANCELLED
    inspection.cancelled_at = _utc_now()
    record_audit(
        db,
        organization_id=current_user.organization_id,
        actor_user_id=current_user.id,
        entity_type="INSPECTION",
        entity_id=inspection.id,
        action="INSPECTION_CANCELLED",
        metadata={"reason": payload.reason},
    )
    db.commit()
    db.refresh(inspection)
    return _inspection_response(db, inspection)


def get_inspection(db: Session, current_user: User, inspection_id: uuid.UUID) -> InspectionDetail:
    inspection = _scoped_inspection(db, current_user, inspection_id)
    creator = db.get(User, inspection.created_by_user_id)
    history: list[AssignmentResponse] = []
    if current_user.role in {UserRole.ADMIN, UserRole.REVIEWER}:
        assignments = db.scalars(
            select(InspectionAssignment)
            .where(InspectionAssignment.inspection_id == inspection.id)
            .order_by(InspectionAssignment.assigned_at.desc())
        ).all()
        history = [_assignment_response(db, item) for item in assignments]
    base = _inspection_response(db, inspection).model_dump()
    return InspectionDetail(
        **base,
        assignment_history=history,
        created_by_name=creator.full_name if creator else "Unknown",
    )


def list_inspections(
    db: Session,
    current_user: User,
    *,
    page: int,
    page_size: int,
    status: InspectionStatus | None,
    priority: InspectionPriority | None,
    inspector_id: uuid.UUID | None,
    search: str | None,
    deadline_from: datetime | None,
    deadline_to: datetime | None,
    sort_by: str | None,
    sort_order: str,
) -> InspectionPage:
    filters = [Inspection.organization_id == current_user.organization_id]
    query = select(Inspection)

    if current_user.role == UserRole.INSPECTOR:
        inspector = get_inspector_for_user(db, current_user.id)
        if inspector is None:
            return InspectionPage(items=[], page=page, page_size=page_size, total_items=0, total_pages=0)
        query = query.join(
            InspectionAssignment,
            (InspectionAssignment.inspection_id == Inspection.id)
            & (InspectionAssignment.status == AssignmentStatus.ACTIVE),
        )
        filters.append(InspectionAssignment.inspector_id == inspector.id)
    elif inspector_id is not None:
        query = query.join(
            InspectionAssignment,
            (InspectionAssignment.inspection_id == Inspection.id)
            & (InspectionAssignment.status == AssignmentStatus.ACTIVE),
        )
        filters.append(InspectionAssignment.inspector_id == inspector_id)

    if status is not None:
        filters.append(Inspection.status == status)
    if priority is not None:
        filters.append(Inspection.priority == priority)
    if search:
        pattern = f"%{search.strip()}%"
        filters.append(
            or_(
                Inspection.title.ilike(pattern),
                Inspection.location_name.ilike(pattern),
                Inspection.location_address.ilike(pattern),
            )
        )
    if deadline_from:
        filters.append(Inspection.deadline >= deadline_from)
    if deadline_to:
        filters.append(Inspection.deadline <= deadline_to)

    query = query.where(*filters)
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery())) or 0

    descending = sort_order.lower() != "asc"
    sort_map = {
        "createdAt": Inspection.created_at,
        "deadline": Inspection.deadline,
        "status": Inspection.status,
        "priority": Inspection.priority,
    }
    if current_user.role == UserRole.INSPECTOR and sort_by is None:
        priority_rank = case(
            (Inspection.priority == InspectionPriority.CRITICAL, 0),
            (Inspection.priority == InspectionPriority.HIGH, 1),
            (Inspection.priority == InspectionPriority.MEDIUM, 2),
            else_=3,
        )
        query = query.order_by(priority_rank.asc(), Inspection.deadline.asc())
    else:
        sort_column = sort_map.get(sort_by or "createdAt", Inspection.created_at)
        query = query.order_by(sort_column.desc() if descending else sort_column.asc())

    inspections = db.scalars(
        query.offset((page - 1) * page_size).limit(page_size)
    ).all()
    return InspectionPage(
        items=[_inspection_response(db, item) for item in inspections],
        page=page,
        page_size=page_size,
        total_items=total,
        total_pages=math.ceil(total / page_size) if total else 0,
    )


def dashboard_summary(db: Session, current_user: User) -> DashboardSummary:
    if current_user.role not in {UserRole.ADMIN, UserRole.REVIEWER}:
        raise SiteProofError(403, "FORBIDDEN", "Dashboard summary is not available for this role.")
    org_filter = Inspection.organization_id == current_user.organization_id

    def count_status(value: InspectionStatus) -> int:
        return db.scalar(select(func.count()).select_from(Inspection).where(org_filter, Inspection.status == value)) or 0

    now = _utc_now()
    today_end = datetime.combine(now.date(), time.max, tzinfo=timezone.utc)
    total = db.scalar(select(func.count()).select_from(Inspection).where(org_filter)) or 0
    due_today = db.scalar(
        select(func.count()).select_from(Inspection).where(
            org_filter,
            Inspection.deadline >= now,
            Inspection.deadline <= today_end,
            Inspection.status != InspectionStatus.CANCELLED,
        )
    ) or 0
    overdue = db.scalar(
        select(func.count()).select_from(Inspection).where(
            org_filter,
            Inspection.deadline < now,
            Inspection.status != InspectionStatus.CANCELLED,
        )
    ) or 0
    high_priority = db.scalar(
        select(func.count()).select_from(Inspection).where(
            org_filter,
            Inspection.priority.in_([InspectionPriority.HIGH, InspectionPriority.CRITICAL]),
            Inspection.status != InspectionStatus.CANCELLED,
        )
    ) or 0
    return DashboardSummary(
        total=total,
        draft=count_status(InspectionStatus.DRAFT),
        assigned=count_status(InspectionStatus.ASSIGNED),
        acknowledged=count_status(InspectionStatus.ACKNOWLEDGED),
        ready=count_status(InspectionStatus.READY),
        cancelled=count_status(InspectionStatus.CANCELLED),
        due_today=due_today,
        overdue=overdue,
        high_priority=high_priority,
    )
