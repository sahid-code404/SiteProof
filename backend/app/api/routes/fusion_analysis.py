import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.fusion_analysis import FusionAnalysisResponse
from app.services.fusion.service import get_fusion_analysis
from app.services.fusion.tasks import run_fusion_analysis_retry_task

router = APIRouter(tags=["fusion-analysis"])


@router.get(
    "/sessions/{session_id}/fusion-analysis",
    response_model=FusionAnalysisResponse,
)
def fusion_analysis(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER)),
) -> FusionAnalysisResponse:
    return get_fusion_analysis(db, current_user, session_id)


@router.post(
    "/sessions/{session_id}/fusion-analysis/retry",
    response_model=FusionAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_fusion_analysis(
    session_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER)),
) -> FusionAnalysisResponse:
    response = get_fusion_analysis(db, current_user, session_id)
    background_tasks.add_task(run_fusion_analysis_retry_task, session_id)
    return response
