from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.processing_job import VerificationProcessingJob

PIPELINE_VERSION = "verification-v2.0"
DEFAULT_MAX_ATTEMPTS = 5
DEFAULT_LEASE_SECONDS = 300
MAX_ERROR_LENGTH = 4000


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def enqueue_processing_job(
    db: Session,
    session_id: uuid.UUID,
    *,
    pipeline_version: str = PIPELINE_VERSION,
    commit: bool = False,
) -> VerificationProcessingJob:
    """Create one durable job per session/pipeline without duplicating work."""
    existing = db.scalar(
        select(VerificationProcessingJob).where(
            VerificationProcessingJob.session_id == session_id,
            VerificationProcessingJob.pipeline_version == pipeline_version,
        )
    )
    if existing is not None:
        # A terminal success is immutable. A manually repaired failed job can be re-queued only
        # when it still has retry budget; normal transient failures are already RETRY jobs.
        if existing.status == "FAILED" and existing.attempts < existing.max_attempts:
            existing.status = "RETRY"
            existing.next_attempt_at = utc_now()
            existing.lease_expires_at = None
            existing.last_error = None
        if commit:
            db.commit()
        else:
            db.flush()
        return existing

    job = VerificationProcessingJob(
        session_id=session_id,
        pipeline_version=pipeline_version,
        status="PENDING",
        attempts=0,
        max_attempts=DEFAULT_MAX_ATTEMPTS,
        next_attempt_at=utc_now(),
    )
    db.add(job)
    if commit:
        db.commit()
        db.refresh(job)
    else:
        db.flush()
    return job


def _recover_expired_leases(db: Session, now: datetime) -> None:
    # Lock expired rows before changing them so two PostgreSQL workers cannot both recover the
    # same dead lease. SKIP LOCKED also keeps a healthy worker claim from blocking the queue.
    expired = list(
        db.scalars(
            select(VerificationProcessingJob)
            .where(
                VerificationProcessingJob.status == "RUNNING",
                VerificationProcessingJob.lease_expires_at.is_not(None),
                VerificationProcessingJob.lease_expires_at <= now,
            )
            .with_for_update(skip_locked=True)
        ).all()
    )
    for job in expired:
        if job.attempts >= job.max_attempts:
            job.status = "FAILED"
            job.next_attempt_at = None
        else:
            job.status = "RETRY"
            job.next_attempt_at = now
        job.lease_expires_at = None
        if not job.last_error:
            job.last_error = "Worker lease expired before processing completed."


def claim_processing_job(
    db: Session,
    *,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> VerificationProcessingJob | None:
    """Atomically lease the next runnable job.

    PostgreSQL uses SKIP LOCKED so multiple workers can safely claim different jobs. SQLite
    ignores the row-lock clause in unit tests, where workers run serially.
    """
    now = utc_now()
    _recover_expired_leases(db, now)
    # SessionLocal has autoflush disabled. Persist recovered RUNNING -> RETRY transitions inside
    # this transaction so the same claim call can immediately lease the recovered job.
    db.flush()
    job = db.scalar(
        select(VerificationProcessingJob)
        .where(
            VerificationProcessingJob.status.in_(["PENDING", "RETRY"]),
            VerificationProcessingJob.attempts < VerificationProcessingJob.max_attempts,
            or_(
                VerificationProcessingJob.next_attempt_at.is_(None),
                VerificationProcessingJob.next_attempt_at <= now,
            ),
        )
        .order_by(VerificationProcessingJob.created_at, VerificationProcessingJob.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        db.commit()  # persist any expired-lease recovery performed above
        return None

    job.status = "RUNNING"
    job.attempts += 1
    job.next_attempt_at = None
    job.lease_expires_at = now + timedelta(seconds=max(30, lease_seconds))
    job.last_error = None
    db.commit()
    db.refresh(job)
    return job


def _active_attempt(
    db: Session,
    job_id: uuid.UUID,
    attempt: int,
) -> VerificationProcessingJob | None:
    job = db.get(VerificationProcessingJob, job_id)
    if job is None or job.status != "RUNNING" or job.attempts != attempt:
        return None
    return job


def heartbeat_processing_job(
    db: Session,
    job_id: uuid.UUID,
    attempt: int,
    *,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> bool:
    # `attempt` is a fencing token. A stale worker from an expired lease cannot extend a newer
    # worker's lease or later mark its replacement attempt complete.
    job = _active_attempt(db, job_id, attempt)
    if job is None:
        return False
    job.lease_expires_at = utc_now() + timedelta(seconds=max(30, lease_seconds))
    db.commit()
    return True


def mark_processing_job_succeeded(db: Session, job_id: uuid.UUID, attempt: int) -> bool:
    job = _active_attempt(db, job_id, attempt)
    if job is None:
        return False
    job.status = "COMPLETED"
    job.next_attempt_at = None
    job.lease_expires_at = None
    job.last_error = None
    db.commit()
    return True


def mark_processing_job_failed(
    db: Session,
    job_id: uuid.UUID,
    attempt: int,
    error: BaseException,
) -> bool:
    job = _active_attempt(db, job_id, attempt)
    if job is None:
        return False
    job.last_error = (str(error) or error.__class__.__name__)[:MAX_ERROR_LENGTH]
    job.lease_expires_at = None
    if job.attempts >= job.max_attempts:
        job.status = "FAILED"
        job.next_attempt_at = None
    else:
        # 5, 10, 20, 40, ... seconds, capped so a transient service outage recovers promptly.
        delay_seconds = min(300, 5 * (2 ** max(0, job.attempts - 1)))
        job.status = "RETRY"
        job.next_attempt_at = utc_now() + timedelta(seconds=delay_seconds)
    db.commit()
    return True
