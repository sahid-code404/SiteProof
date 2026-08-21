from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.inspection import Inspection
from app.models.trust import VerificationProcessingStatus, VerificationResult, VerificationVerdict
from app.models.user import User
from app.schemas.verification_result import (
    ReviewDecisionResponse,
    ReviewQueueItem,
    ReviewQueueResponse,
)
from app.services.verification.review import latest_review_for_result


def list_review_queue(
    db: Session,
    current_user: User,
    *,
    search: str | None = None,
    verdict: VerificationVerdict | None = None,
    reviewed: bool | None = None,
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

    needle = search.strip().lower() if search else None
    priority = {
        VerificationVerdict.REVIEW_REQUIRED: 0,
        VerificationVerdict.INCONCLUSIVE: 1,
        VerificationVerdict.FLAGGED: 2,
        VerificationVerdict.VERIFIED: 3,
    }

    items: list[ReviewQueueItem] = []
    for result in results:
        inspection = inspections.get(result.inspection_id)
        if inspection is None:
            continue
        if verdict is not None and result.verdict != verdict:
            continue

        review = latest_review_for_result(db, result.id)
        if reviewed is True and review is None:
            continue
        if reviewed is False and review is not None:
            continue

        if needle:
            haystack = " ".join(
                value
                for value in [inspection.title, inspection.location_name, inspection.location_address]
                if value
            ).lower()
            if needle not in haystack:
                continue

        items.append(
            ReviewQueueItem(
                inspection_id=inspection.id,
                session_id=result.session_id,
                result_id=result.id,
                title=inspection.title,
                location_name=inspection.location_name,
                location_address=inspection.location_address,
                latitude=inspection.expected_latitude,
                longitude=inspection.expected_longitude,
                inspection_status=inspection.status,
                verdict=result.verdict,
                score=result.final_score,
                confidence=result.overall_confidence,
                engine_version=result.engine_version,
                calculated_at=result.calculated_at,
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
            -(item.calculated_at.timestamp() if item.calculated_at else 0),
        )
    )
    limited = items[:limit]
    return ReviewQueueResponse(items=limited, total=len(items))
