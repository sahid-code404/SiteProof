from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import SiteProofError
from app.models.receipt import EvidenceManifest
from app.models.verification import EvidenceFile, EvidenceFileType, EvidenceUploadStatus, VerificationSession
from app.services.audit_service import record_audit
from app.services.receipt_crypto import canonical_json_bytes, sha256_hex, utc_iso
from app.services.storage_service import StorageService, get_storage_service

SEALED_MANIFEST_SCHEMA_VERSION = "1.0"
SEALED_EVIDENCE_TYPES = {
    EvidenceFileType.VIDEO,
    EvidenceFileType.SENSOR_DATA,
    EvidenceFileType.LOCATION_DATA,
    EvidenceFileType.SESSION_METADATA,
    EvidenceFileType.MANIFEST,
}


@dataclass(frozen=True)
class HashCheck:
    evidence_file_id: uuid.UUID
    file_type: str
    state: str
    expected_sha256: str
    observed_sha256: str | None
    expected_size_bytes: int
    observed_size_bytes: int | None


@dataclass(frozen=True)
class EvidenceIntegrityResult:
    state: str
    checks: list[HashCheck]


def stream_sha256(storage: StorageService, key: str) -> tuple[str, int]:
    hasher = hashlib.sha256()
    total = 0
    for chunk in storage.iter_bytes(key, chunk_size=1024 * 1024):
        if not chunk:
            continue
        total += len(chunk)
        hasher.update(chunk)
    return hasher.hexdigest(), total


def _session_records(db: Session, session: VerificationSession) -> list[EvidenceFile]:
    records = list(
        db.scalars(
            select(EvidenceFile).where(
                EvidenceFile.session_id == session.id,
                EvidenceFile.organization_id == session.organization_id,
            )
        ).all()
    )
    selected = [record for record in records if record.file_type in SEALED_EVIDENCE_TYPES]
    selected.sort(key=lambda record: (record.file_type.value, str(record.id)))
    missing = SEALED_EVIDENCE_TYPES - {record.file_type for record in selected}
    if missing:
        raise SiteProofError(
            409,
            "EVIDENCE_INCOMPLETE",
            "Required evidence is missing and cannot be sealed.",
            {"types": sorted(item.value for item in missing)},
        )
    return selected


def verify_current_evidence(
    db: Session,
    session: VerificationSession,
    *,
    storage: StorageService | None = None,
) -> EvidenceIntegrityResult:
    object_storage = storage or get_storage_service()
    checks: list[HashCheck] = []
    for record in _session_records(db, session):
        if record.upload_status != EvidenceUploadStatus.UPLOADED or not record.hash_verified:
            checks.append(
                HashCheck(
                    evidence_file_id=record.id,
                    file_type=record.file_type.value,
                    state="ERROR",
                    expected_sha256=record.sha256,
                    observed_sha256=None,
                    expected_size_bytes=record.size_bytes,
                    observed_size_bytes=None,
                )
            )
            continue
        try:
            observed_sha256, observed_size = stream_sha256(object_storage, record.storage_key)
            state = (
                "MATCH"
                if observed_sha256 == record.sha256 and observed_size == record.size_bytes
                else "MISMATCH"
            )
        except FileNotFoundError:
            observed_sha256, observed_size, state = None, None, "MISSING"
        except Exception:
            observed_sha256, observed_size, state = None, None, "ERROR"
        checks.append(
            HashCheck(
                evidence_file_id=record.id,
                file_type=record.file_type.value,
                state=state,
                expected_sha256=record.sha256,
                observed_sha256=observed_sha256,
                expected_size_bytes=record.size_bytes,
                observed_size_bytes=observed_size,
            )
        )
    states = {check.state for check in checks}
    state = "MATCH"
    if "MISSING" in states:
        state = "MISSING"
    elif "MISMATCH" in states:
        state = "MISMATCH"
    elif "ERROR" in states:
        state = "ERROR"
    return EvidenceIntegrityResult(state=state, checks=checks)


def seal_evidence_manifest(
    db: Session,
    session: VerificationSession,
    *,
    actor_user_id: uuid.UUID,
    storage: StorageService | None = None,
) -> EvidenceManifest:
    existing = db.scalar(
        select(EvidenceManifest).where(
            EvidenceManifest.session_id == session.id,
            EvidenceManifest.schema_version == SEALED_MANIFEST_SCHEMA_VERSION,
        )
    )
    if existing is not None:
        integrity = verify_manifest_evidence(db, existing, storage=storage)
        if integrity.state != "MATCH":
            raise SiteProofError(
                409,
                "SEALED_EVIDENCE_CHANGED",
                "Current evidence does not match the already sealed manifest.",
            )
        return existing

    integrity = verify_current_evidence(db, session, storage=storage)
    if integrity.state != "MATCH":
        raise SiteProofError(
            409,
            "EVIDENCE_INTEGRITY_FAILURE",
            "Stored evidence failed independent SHA-256 verification.",
            {"state": integrity.state},
        )

    records_by_id = {record.id: record for record in _session_records(db, session)}
    entries = []
    for check in integrity.checks:
        record = records_by_id[check.evidence_file_id]
        entries.append(
            {
                "evidenceFileId": str(record.id),
                "type": record.file_type.value,
                "sizeBytes": record.size_bytes,
                "sha256": record.sha256,
            }
        )
    entries.sort(key=lambda item: (item["type"], item["evidenceFileId"]))
    payload = {
        "schemaVersion": SEALED_MANIFEST_SCHEMA_VERSION,
        "organizationId": str(session.organization_id),
        "inspectionId": str(session.inspection_id),
        "sessionId": str(session.id),
        "capture": {
            "startedAt": utc_iso(session.capture_started_at or session.created_at),
            "endedAt": utc_iso(session.capture_ended_at or session.uploaded_at or datetime.now(timezone.utc)),
            "durationMs": int(session.capture_duration_ms or 0),
        },
        "evidenceFiles": entries,
    }
    canonical = canonical_json_bytes(payload)
    sealed_at = datetime.now(timezone.utc)
    manifest = EvidenceManifest(
        organization_id=session.organization_id,
        inspection_id=session.inspection_id,
        session_id=session.id,
        schema_version=SEALED_MANIFEST_SCHEMA_VERSION,
        canonical_payload=canonical.decode("utf-8"),
        sha256=sha256_hex(canonical),
        evidence_file_count=len(entries),
        total_size_bytes=sum(item["sizeBytes"] for item in entries),
        sealed_at=sealed_at,
    )
    db.add(manifest)
    db.flush()
    record_audit(
        db,
        organization_id=session.organization_id,
        actor_user_id=actor_user_id,
        entity_type="EVIDENCE_MANIFEST",
        entity_id=manifest.id,
        action="EVIDENCE_MANIFEST_SEALED",
        metadata={
            "schemaVersion": manifest.schema_version,
            "sha256": manifest.sha256,
            "fileCount": manifest.evidence_file_count,
        },
    )
    return manifest


def verify_manifest_evidence(
    db: Session,
    manifest: EvidenceManifest,
    *,
    storage: StorageService | None = None,
) -> EvidenceIntegrityResult:
    session = db.get(VerificationSession, manifest.session_id)
    if session is None or session.organization_id != manifest.organization_id:
        return EvidenceIntegrityResult(state="ERROR", checks=[])
    try:
        payload = json.loads(manifest.canonical_payload)
    except json.JSONDecodeError:
        return EvidenceIntegrityResult(state="ERROR", checks=[])
    if sha256_hex(manifest.canonical_payload.encode("utf-8")) != manifest.sha256:
        return EvidenceIntegrityResult(state="MISMATCH", checks=[])

    object_storage = storage or get_storage_service()
    records = {
        record.id: record
        for record in db.scalars(
            select(EvidenceFile).where(EvidenceFile.session_id == manifest.session_id)
        ).all()
    }
    checks: list[HashCheck] = []
    for item in payload.get("evidenceFiles", []):
        try:
            evidence_id = uuid.UUID(item["evidenceFileId"])
            expected_sha = str(item["sha256"])
            expected_size = int(item["sizeBytes"])
            file_type = str(item["type"])
        except (KeyError, TypeError, ValueError):
            return EvidenceIntegrityResult(state="ERROR", checks=checks)
        record = records.get(evidence_id)
        if record is None or record.organization_id != manifest.organization_id or record.file_type.value != file_type:
            checks.append(HashCheck(evidence_id, file_type, "MISSING", expected_sha, None, expected_size, None))
            continue
        try:
            observed_sha, observed_size = stream_sha256(object_storage, record.storage_key)
            state = "MATCH" if observed_sha == expected_sha and observed_size == expected_size else "MISMATCH"
        except FileNotFoundError:
            observed_sha, observed_size, state = None, None, "MISSING"
        except Exception:
            observed_sha, observed_size, state = None, None, "ERROR"
        checks.append(
            HashCheck(evidence_id, file_type, state, expected_sha, observed_sha, expected_size, observed_size)
        )
    states = {check.state for check in checks}
    if "MISSING" in states:
        state = "MISSING"
    elif "MISMATCH" in states:
        state = "MISMATCH"
    elif "ERROR" in states:
        state = "ERROR"
    else:
        state = "MATCH"
    return EvidenceIntegrityResult(state=state, checks=checks)
