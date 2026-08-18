from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.inspector import InspectorCreate, InspectorPage, InspectorResponse
from app.services.inspector_service import create_inspector, list_inspectors

router = APIRouter(prefix="/inspectors", tags=["inspectors"])


@router.get("", response_model=InspectorPage)
def get_inspectors(
    search: str | None = None,
    active: bool | None = True,
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
