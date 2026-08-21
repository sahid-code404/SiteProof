import uuid

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.inspector import (
    InspectorCreate,
    InspectorPage,
    InspectorPasswordReset,
    InspectorResponse,
    InspectorUpdate,
)
from app.services.inspector_service import (
    create_inspector,
    list_inspectors,
    reset_inspector_password,
    update_inspector,
)

router = APIRouter(prefix="/inspectors", tags=["inspectors"])


@router.get("", response_model=InspectorPage)
def get_inspectors(
    search: str | None = None,
    active: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InspectorPage:
    return list_inspectors(
        db, current_user, search=search, active=active, page=page, page_size=page_size
    )


@router.post("", response_model=InspectorResponse, status_code=status.HTTP_201_CREATED)
def add_inspector(
    payload: InspectorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InspectorResponse:
    return create_inspector(db, current_user, payload)


@router.patch("/{inspector_id}", response_model=InspectorResponse)
def edit_inspector(
    inspector_id: uuid.UUID,
    payload: InspectorUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InspectorResponse:
    return update_inspector(db, current_user, inspector_id, payload)


@router.put("/{inspector_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def change_inspector_password(
    inspector_id: uuid.UUID,
    payload: InspectorPasswordReset,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    reset_inspector_password(db, current_user, inspector_id, payload)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
