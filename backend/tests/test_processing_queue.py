import uuid
from datetime import timedelta

from sqlalchemy import select

from app.models.processing_job import VerificationProcessingJob
from app.services.processing_queue import (
    claim_processing_job,
    enqueue_processing_job,
    heartbeat_processing_job,
    mark_processing_job_failed,
    mark_processing_job_succeeded,
    utc_now,
)
from tests.phase3_helpers import (
    build_evidence,
    create_ready_inspection,
    create_session,
    finish_capture,
    login,
    seed_identities,
    start_capture,
    upload_all_evidence,
)


def _ready_session(client, db):
    identities = seed_identities(db)
    admin_headers = login(client, identities["admin"])
    inspector_headers = login(client, identities["inspector"])
    inspection_id = create_ready_inspection(
        client,
        admin_headers,
        inspector_headers,
        identities["profile"].id,
    )
    response = create_session(client, inspector_headers, inspection_id)
    assert response.status_code == 201, response.text
    return identities, admin_headers, inspector_headers, inspection_id, response.json()["sessionId"]


def test_queue_is_idempotent_leased_retryable_and_terminal(client, db):
    _, _, _, _, session_id = _ready_session(client, db)
    session_uuid = uuid.UUID(session_id)

    first = enqueue_processing_job(db, session_uuid, commit=True)
    duplicate = enqueue_processing_job(db, session_uuid, commit=True)
    assert duplicate.id == first.id

    claimed = claim_processing_job(db, lease_seconds=60)
    assert claimed is not None
    assert claimed.id == first.id
    assert claimed.status == "RUNNING"
    assert claimed.attempts == 1
    first_lease = claimed.lease_expires_at

    assert heartbeat_processing_job(db, claimed.id, lease_seconds=120) is True
    db.refresh(claimed)
    assert claimed.lease_expires_at > first_lease

    mark_processing_job_failed(db, claimed.id, RuntimeError("temporary processing failure"))
    db.refresh(claimed)
    assert claimed.status == "RETRY"
    assert claimed.next_attempt_at is not None
    assert "temporary processing failure" in claimed.last_error

    claimed.next_attempt_at = utc_now() - timedelta(seconds=1)
    db.commit()
    retried = claim_processing_job(db, lease_seconds=60)
    assert retried is not None
    assert retried.id == first.id
    assert retried.attempts == 2

    mark_processing_job_succeeded(db, retried.id)
    db.refresh(retried)
    assert retried.status == "COMPLETED"
    assert retried.lease_expires_at is None
    assert claim_processing_job(db) is None


def test_expired_worker_lease_is_reclaimed(client, db):
    _, _, _, _, session_id = _ready_session(client, db)
    job = enqueue_processing_job(db, uuid.UUID(session_id), commit=True)
    claimed = claim_processing_job(db, lease_seconds=30)
    assert claimed is not None
    assert claimed.id == job.id

    claimed.lease_expires_at = utc_now() - timedelta(seconds=1)
    db.commit()
    reclaimed = claim_processing_job(db, lease_seconds=30)
    assert reclaimed is not None
    assert reclaimed.id == job.id
    assert reclaimed.status == "RUNNING"
    assert reclaimed.attempts == 2


def test_evidence_completion_persists_durable_job(client, db):
    _, _, inspector_headers, _, session_id = _ready_session(client, db)
    assert start_capture(client, inspector_headers, session_id).status_code == 200
    assert finish_capture(client, inspector_headers, session_id).status_code == 200

    completed = upload_all_evidence(
        client,
        inspector_headers,
        session_id,
        build_evidence(session_id),
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "UPLOADED"

    job = db.scalar(
        select(VerificationProcessingJob).where(
            VerificationProcessingJob.session_id == uuid.UUID(session_id)
        )
    )
    assert job is not None
    assert job.status == "PENDING"
    assert job.pipeline_version == "verification-v2.0"

    # Retried completion is idempotent and does not create a second queue row.
    duplicate = upload_all_evidence(
        client,
        inspector_headers,
        session_id,
        build_evidence(session_id),
    )
    assert duplicate.status_code == 200, duplicate.text
    count = len(
        db.scalars(
            select(VerificationProcessingJob).where(
                VerificationProcessingJob.session_id == uuid.UUID(session_id)
            )
        ).all()
    )
    assert count == 1
