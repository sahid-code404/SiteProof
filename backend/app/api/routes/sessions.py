import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from fastapi.responses import FileResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.session import (
    AbortRequest,
    CaptureCompleteRequest,
    EvidenceCompleteRequest,
    EvidenceFileResponse,
    EvidenceInitiateRequest,
    EvidenceInitiateResponse,
    EvidenceListResponse,
    SessionCreateRequest,
    SessionCreateResponse,
    StartCaptureRequest,
    VerificationSessionResponse,
)
from app.services.evidence_service import (
    get_evidence_for_download,
    initiate_evidence_upload,
    list_evidence,
)
from app.services.evidence_upload_service import (
    accept_evidence_upload,
    complete_evidence_upload,
)
from app.services.fusion.tasks import run_visual_then_fusion_task
from app.services.session_service import (
    abort_session,
    complete_capture,
    create_verification_session,
    get_session,
    latest_session_for_inspection,
    start_capture,
)
from app.services.storage_service import get_storage_service

router = APIRouter(tags=["verification-sessions"])


@router.post(
    "/inspections/{inspection_id}/sessions",
    response_model=SessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_session(
    inspection_id: uuid.UUID,
    payload: SessionCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionCreateResponse:
    return create_verification_session(db, current_user, inspection_id, payload)


@router.get(
    "/inspections/{inspection_id}/sessions/latest",
    response_model=VerificationSessionResponse | None,
)
def latest_session(
    inspection_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VerificationSessionResponse | None:
    return latest_session_for_inspection(db, current_user, inspection_id)


@router.get("/sessions/{session_id}", response_model=VerificationSessionResponse)
def session_detail(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VerificationSessionResponse:
    return get_session(db, current_user, session_id)


@router.post("/sessions/{session_id}/start-capture", response_model=VerificationSessionResponse)
def begin_capture(
    session_id: uuid.UUID,
    payload: StartCaptureRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VerificationSessionResponse:
    return start_capture(db, current_user, session_id, payload)


@router.post("/sessions/{session_id}/capture-complete", response_model=VerificationSessionResponse)
def finish_capture(
    session_id: uuid.UUID,
    payload: CaptureCompleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VerificationSessionResponse:
    return complete_capture(db, current_user, session_id, payload)


@router.post("/sessions/{session_id}/abort", response_model=VerificationSessionResponse)
def abort(
    session_id: uuid.UUID,
    payload: AbortRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VerificationSessionResponse:
    return abort_session(db, current_user, session_id, payload)


@router.post(
    "/sessions/{session_id}/evidence/initiate",
    response_model=EvidenceInitiateResponse,
)
def initiate_upload(
    session_id: uuid.UUID,
    payload: EvidenceInitiateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EvidenceInitiateResponse:
    return initiate_evidence_upload(db, current_user, session_id, payload)


@router.put(
    "/sessions/{session_id}/evidence/{file_id}/content",
    response_model=EvidenceFileResponse,
)
async def upload_content(
    session_id: uuid.UUID,
    file_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EvidenceFileResponse:
    return await accept_evidence_upload(db, current_user, session_id, file_id, request)


@router.post(
    "/sessions/{session_id}/evidence/complete",
    response_model=VerificationSessionResponse,
)
def complete_upload(
    session_id: uuid.UUID,
    payload: EvidenceCompleteRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> VerificationSessionResponse:
    response = complete_evidence_upload(db, current_user, session_id, payload)
    background_tasks.add_task(run_visual_then_fusion_task, session_id)
    return response


@router.get("/sessions/{session_id}/evidence", response_model=EvidenceListResponse)
def evidence_list(
    session_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EvidenceListResponse:
    return list_evidence(db, current_user, session_id)


@router.get("/sessions/{session_id}/evidence/{file_id}/content")
def download_content(
    session_id: uuid.UUID,
    file_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = get_evidence_for_download(db, current_user, session_id, file_id)
    storage = get_storage_service()
    local_path = storage.local_path(record.storage_key)
    if local_path is not None:
        return FileResponse(
            path=local_path,
            media_type=record.mime_type,
            headers={"Cache-Control": "private, no-store"},
        )
    url = storage.presigned_download_url(record.storage_key, expires_seconds=300)
    if url is None:
        raise RuntimeError("Storage backend cannot create a download response")
    return RedirectResponse(url=url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)
