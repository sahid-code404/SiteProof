import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import require_roles
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.visual_analysis import VisualAnalysisResponse
from app.services.visual_analysis_status import get_retry_aware_visual_analysis
from app.services.visual_analysis_tasks import run_visual_analysis_retry_task

router = APIRouter(tags=["visual-analysis"])


@router.get(
    "/sessions/{session_id}/visual-analysis",
    response_model=VisualAnalysisResponse,
)
def visual_analysis(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER)),
) -> VisualAnalysisResponse:
    return get_retry_aware_visual_analysis(db, current_user, session_id)


@router.post(
    "/sessions/{session_id}/visual-analysis/retry",
    response_model=VisualAnalysisResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_visual_analysis(
    session_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.ADMIN, UserRole.REVIEWER)),
) -> VisualAnalysisResponse:
    response = get_retry_aware_visual_analysis(db, current_user, session_id)
    background_tasks.add_task(run_visual_analysis_retry_task, session_id)
    return response
