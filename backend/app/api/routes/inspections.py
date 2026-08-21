import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.inspection import InspectionPriority, InspectionStatus
from app.models.user import User
from app.schemas.inspection import (
    AssignmentRequest,
    CancelRequest,
    DashboardSummary,
    InspectionCreate,
    InspectionDetail,
    InspectionPage,
    InspectionResponse,
    InspectionUpdate,
    ReassignmentRequest,
)
from app.services.dashboard_service import dashboard_summary
from app.services.inspection_service import (
    acknowledge_inspection,
    assign_inspector,
    cancel_inspection,
    create_inspection,
    get_inspection,
    list_inspections,
    mark_ready,
    reassign_inspector,
    update_inspection,
)

router = APIRouter(prefix="/inspections", tags=["inspections"])


@router.get("/summary", response_model=DashboardSummary)
def summary(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> DashboardSummary:
    return dashboard_summary(db, current_user)


@router.get("", response_model=InspectionPage)
def get_inspections(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
    status_filter: InspectionStatus | None = Query(default=None, alias="status"),
    priority: InspectionPriority | None = None,
    inspector_id: uuid.UUID | None = Query(default=None, alias="inspectorId"),
    search: str | None = None,
    deadline_from: datetime | None = Query(default=None, alias="deadlineFrom"),
    deadline_to: datetime | None = Query(default=None, alias="deadlineTo"),
    sort_by: str | None = Query(default=None, alias="sortBy"),
    sort_order: str = Query(default="desc", alias="sortOrder", pattern="^(asc|desc)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InspectionPage:
    return list_inspections(
        db,
        current_user,
        page=page,
        page_size=page_size,
        status=status_filter,
        priority=priority,
        inspector_id=inspector_id,
        search=search,
        deadline_from=deadline_from,
        deadline_to=deadline_to,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.post("", response_model=InspectionResponse, status_code=status.HTTP_201_CREATED)
def add_inspection(
    payload: InspectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InspectionResponse:
    return create_inspection(db, current_user, payload)


@router.get("/{inspection_id}", response_model=InspectionDetail)
def inspection_detail(
    inspection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InspectionDetail:
    return get_inspection(db, current_user, inspection_id)


@router.patch("/{inspection_id}", response_model=InspectionResponse)
def edit_inspection(
    inspection_id: uuid.UUID,
    payload: InspectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InspectionResponse:
    return update_inspection(db, current_user, inspection_id, payload)


@router.post("/{inspection_id}/assign", response_model=InspectionResponse)
def assign(
    inspection_id: uuid.UUID,
    payload: AssignmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InspectionResponse:
    return assign_inspector(db, current_user, inspection_id, payload.inspector_id)


@router.post("/{inspection_id}/reassign", response_model=InspectionResponse)
def reassign(
    inspection_id: uuid.UUID,
    payload: ReassignmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InspectionResponse:
    return reassign_inspector(db, current_user, inspection_id, payload)


@router.post("/{inspection_id}/acknowledge", response_model=InspectionResponse)
def acknowledge(
    inspection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InspectionResponse:
    return acknowledge_inspection(db, current_user, inspection_id)


@router.post("/{inspection_id}/ready", response_model=InspectionResponse)
def ready(
    inspection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InspectionResponse:
    return mark_ready(db, current_user, inspection_id)


@router.post("/{inspection_id}/cancel", response_model=InspectionResponse)
def cancel(
    inspection_id: uuid.UUID,
    payload: CancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InspectionResponse:
    return cancel_inspection(db, current_user, inspection_id, payload)
