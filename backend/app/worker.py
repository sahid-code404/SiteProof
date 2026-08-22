from __future__ import annotations

import logging
import os
import signal
import threading

import app.models  # noqa: F401
from app.db.session import SessionLocal
from app.services.processing_pipeline import run_verification_pipeline
from app.services.processing_queue import (
    DEFAULT_LEASE_SECONDS,
    claim_processing_job,
    heartbeat_processing_job,
    mark_processing_job_failed,
    mark_processing_job_succeeded,
)

logger = logging.getLogger("siteproof.worker")
_STOP = threading.Event()


def _handle_stop(*_) -> None:
    _STOP.set()


def _heartbeat(job_id, attempt: int, stop_event: threading.Event, interval_seconds: float) -> None:
    while not stop_event.wait(interval_seconds):
        try:
            with SessionLocal() as db:
                if not heartbeat_processing_job(db, job_id, attempt):
                    return
        except Exception:
            logger.exception("failed to extend processing lease for job %s", job_id)


def process_one() -> bool:
    with SessionLocal() as db:
        job = claim_processing_job(db)
    if job is None:
        return False

    claimed_attempt = job.attempts
    heartbeat_stop = threading.Event()
    heartbeat_thread = threading.Thread(
        target=_heartbeat,
        args=(
            job.id,
            claimed_attempt,
            heartbeat_stop,
            max(10.0, DEFAULT_LEASE_SECONDS / 3),
        ),
        daemon=True,
        name=f"processing-heartbeat-{job.id}",
    )
    heartbeat_thread.start()
    try:
        logger.info(
            "processing session=%s job=%s attempt=%s/%s",
            job.session_id,
            job.id,
            claimed_attempt,
            job.max_attempts,
        )
        run_verification_pipeline(job.session_id)
    except Exception as error:
        logger.exception("verification processing failed for session %s", job.session_id)
        with SessionLocal() as db:
            mark_processing_job_failed(db, job.id, claimed_attempt, error)
    else:
        with SessionLocal() as db:
            accepted = mark_processing_job_succeeded(db, job.id, claimed_attempt)
        if accepted:
            logger.info("verification processing completed for session %s", job.session_id)
        else:
            logger.warning(
                "processing completion ignored because lease was superseded for session %s",
                job.session_id,
            )
    finally:
        heartbeat_stop.set()
        heartbeat_thread.join(timeout=2.0)
    return True


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    poll_seconds = max(0.25, float(os.getenv("SITEPROOF_WORKER_POLL_SECONDS", "1.0")))
    logger.info("SiteProof verification worker started")
    while not _STOP.is_set():
        try:
            worked = process_one()
        except Exception:
            logger.exception("worker loop failed before a job could be processed")
            worked = False
        if not worked:
            _STOP.wait(poll_seconds)
    logger.info("SiteProof verification worker stopped")


if __name__ == "__main__":
    main()
