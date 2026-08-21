from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.inspection import Inspection, InspectionStatus
from app.models.receipt import SignedReceipt
from app.models.trust import VerificationProcessingStatus, VerificationResult, VerificationVerdict
from app.models.user import User
from app.schemas.inspection import DashboardSummary, DashboardVerificationItem
from app.services.inspection_service import dashboard_summary as operational_dashboard_summary


_ACTIVE_VERIFICATION_STATES = {
    VerificationProcessingStatus.PENDING,
    VerificationProcessingStatus.WAITING_FOR_SIGNALS,
    VerificationProcessingStatus.CALCULATING,
}


def _latest_results(db: Session, current_user: User) -> dict[object, VerificationResult]:
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
    return latest


def dashboard_summary(db: Session, current_user: User) -> DashboardSummary:
    """Return Phase 11 dashboard data from the latest result per inspection.

    Historical verification results and superseded receipts remain queryable, but they do
    not inflate current dashboard verdict counts.
    """

    base = operational_dashboard_summary(db, current_user)
    latest = _latest_results(db, current_user)
    current_results = list(latest.values())
    completed = [
        row
        for row in current_results
        if row.processing_status == VerificationProcessingStatus.COMPLETED and row.verdict is not None
    ]

    verified = sum(row.verdict == VerificationVerdict.VERIFIED for row in completed)
    review_required = sum(row.verdict == VerificationVerdict.REVIEW_REQUIRED for row in completed)
    flagged = sum(row.verdict == VerificationVerdict.FLAGGED for row in completed)
    inconclusive = sum(row.verdict == VerificationVerdict.INCONCLUSIVE for row in completed)
    processing = sum(row.processing_status in _ACTIVE_VERIFICATION_STATES for row in current_results)

    processing_inspection_ids = set(
        db.scalars(
            select(Inspection.id).where(
                Inspection.organization_id == current_user.organization_id,
                Inspection.status == InspectionStatus.PROCESSING,
            )
        ).all()
    )
    processing += sum(inspection_id not in latest for inspection_id in processing_inspection_ids)

    latest_completed = completed[:6]
    inspection_ids = [row.inspection_id for row in latest_completed]
    inspections = (
        {
            row.id: row
            for row in db.scalars(select(Inspection).where(Inspection.id.in_(inspection_ids))).all()
        }
        if inspection_ids
        else {}
    )

    result_ids = [row.id for row in latest_completed]
    receipts_by_result: dict[object, SignedReceipt] = {}
    if result_ids:
        receipts = db.scalars(
            select(SignedReceipt)
            .where(SignedReceipt.verification_result_id.in_(result_ids))
            .order_by(SignedReceipt.issued_at.desc())
        ).all()
        for receipt in receipts:
            receipts_by_result.setdefault(receipt.verification_result_id, receipt)

    latest_items: list[DashboardVerificationItem] = []
    for result in latest_completed:
        inspection = inspections.get(result.inspection_id)
        if inspection is None:
            continue
        receipt = receipts_by_result.get(result.id)
        latest_items.append(
            DashboardVerificationItem(
                inspection_id=inspection.id,
                title=inspection.title,
                location_name=inspection.location_name,
                inspection_status=inspection.status,
                verification_status=result.processing_status,
                verdict=result.verdict,
                score=result.final_score,
                confidence=result.overall_confidence,
                engine_version=result.engine_version,
                calculated_at=result.calculated_at,
                receipt_number=receipt.receipt_number if receipt else None,
                receipt_status=receipt.lifecycle_status.value if receipt else None,
            )
        )

    completed_count = len(completed)
    return base.model_copy(
        update={
            "verified": verified,
            "review_required": review_required,
            "flagged": flagged,
            "inconclusive": inconclusive,
            "verification_processing": processing,
            "verification_completed": completed_count,
            "verification_rate": round((verified / completed_count) * 100, 1) if completed_count else 0.0,
            "latest_verifications": latest_items,
        }
    )
