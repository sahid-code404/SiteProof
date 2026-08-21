from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.assignment import AssignmentStatus, InspectionAssignment
from app.models.inspection import Inspection
from app.models.inspector import Inspector
from app.models.trust import VerificationProcessingStatus, VerificationResult, VerificationVerdict
from app.models.user import User
from app.models.verification import VerificationSession
from app.schemas.verification_result import (
    ReviewDecisionResponse,
    ReviewQueueItem,
    ReviewQueueResponse,
)
from app.services.verification.review import latest_review_for_result


def _timestamp(value: datetime | None) -> float:
    if value is None:
        return 0.0
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.timestamp()


def list_review_queue(
    db: Session,
    current_user: User,
    *,
    search: str | None = None,
    inspector: str | None = None,
    verdict: VerificationVerdict | None = None,
    reviewed: bool | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 100,
) -> ReviewQueueResponse:
    """Return the latest immutable verification result for each inspection.

    Historical engine results stay in the database for auditability but are intentionally
    excluded from this operational reviewer view once a newer result exists.
    """

    rows = db.scalars(
        select(VerificationResult)
        .where(VerificationResult.organization_id == current_user.organization_id)
        .order_by(
            func.coalesce(VerificationResult.calculated_at, VerificationResult.created_at).desc(),
            VerificationResult.created_at.desc(),
        )
    ).all()

    latest: dict[object, VerificationResult] = {}
    for row in rows:
        latest.setdefault(row.inspection_id, row)

    results = [
        row
        for row in latest.values()
        if row.processing_status == VerificationProcessingStatus.COMPLETED and row.verdict is not None
    ]

    inspection_ids = [row.inspection_id for row in results]
    inspections = {
        item.id: item
        for item in db.scalars(
            select(Inspection).where(
                Inspection.organization_id == current_user.organization_id,
                Inspection.id.in_(inspection_ids),
            )
        ).all()
    } if inspection_ids else {}

    session_ids = [row.session_id for row in results]
    sessions = {
        item.id: item
        for item in db.scalars(
            select(VerificationSession).where(
                VerificationSession.organization_id == current_user.organization_id,
                VerificationSession.id.in_(session_ids),
            )
        ).all()
    } if session_ids else {}

    inspector_names: dict[object, str] = {}
    if inspection_ids:
        assignment_rows = db.execute(
            select(InspectionAssignment.inspection_id, User.full_name)
            .join(Inspector, Inspector.id == InspectionAssignment.inspector_id)
            .join(User, User.id == Inspector.user_id)
            .where(
                InspectionAssignment.organization_id == current_user.organization_id,
                InspectionAssignment.inspection_id.in_(inspection_ids),
                InspectionAssignment.status == AssignmentStatus.ACTIVE,
            )
        ).all()
        inspector_names = {inspection_id: full_name for inspection_id, full_name in assignment_rows}

    needle = search.strip().lower() if search else None
    inspector_needle = inspector.strip().lower() if inspector else None
    from_ts = _timestamp(date_from) if date_from else None
    to_ts = _timestamp(date_to) if date_to else None
    priority = {
        VerificationVerdict.REVIEW_REQUIRED: 0,
        VerificationVerdict.INCONCLUSIVE: 1,
        VerificationVerdict.FLAGGED: 2,
        VerificationVerdict.VERIFIED: 3,
    }

    items: list[ReviewQueueItem] = []
    for result in results:
        inspection_row = inspections.get(result.inspection_id)
        if inspection_row is None:
            continue
        if verdict is not None and result.verdict != verdict:
            continue

        result_ts = _timestamp(result.calculated_at or result.created_at)
        if from_ts is not None and result_ts < from_ts:
            continue
        if to_ts is not None and result_ts > to_ts:
            continue

        inspector_name = inspector_names.get(result.inspection_id)
        if inspector_needle and inspector_needle not in (inspector_name or "").lower():
            continue

        review = latest_review_for_result(db, result.id)
        if reviewed is True and review is None:
            continue
        if reviewed is False and review is not None:
            continue

        if needle:
            haystack = " ".join(
                value
                for value in [
                    inspection_row.title,
                    inspection_row.location_name,
                    inspection_row.location_address,
                    inspector_name,
                ]
                if value
            ).lower()
            if needle not in haystack:
                continue

        session = sessions.get(result.session_id)
        items.append(
            ReviewQueueItem(
                inspection_id=inspection_row.id,
                session_id=result.session_id,
                result_id=result.id,
                title=inspection_row.title,
                location_name=inspection_row.location_name,
                location_address=inspection_row.location_address,
                latitude=inspection_row.expected_latitude,
                longitude=inspection_row.expected_longitude,
                inspector_name=inspector_name,
                inspection_status=inspection_row.status,
                verdict=result.verdict,
                score=result.final_score,
                confidence=result.overall_confidence,
                engine_version=result.engine_version,
                calculated_at=result.calculated_at,
                capture_ended_at=session.capture_ended_at if session else None,
                latest_review=(
                    ReviewDecisionResponse(
                        id=review.id,
                        decision=review.decision,
                        reason=review.reason,
                        reviewer_user_id=review.reviewer_user_id,
                        created_at=review.created_at,
                    )
                    if review is not None
                    else None
                ),
            )
        )

    items.sort(
        key=lambda item: (
            priority.get(item.verdict, 9),
            -_timestamp(item.calculated_at),
        )
    )
    limited = items[:limit]
    return ReviewQueueResponse(items=limited, total=len(items))
