from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import select

from app.core.errors import SiteProofError
from app.models.receipt import EvidenceManifest, ReceiptLifecycleStatus, SigningKey, SigningKeyStatus
from app.models.trust import VerificationProcessingStatus, VerificationResult
from app.models.verification import EvidenceFile, EvidenceFileType, EvidenceUploadStatus
from app.services.fusion.service import analyze_session_fusion
from app.services.receipt_crypto import (
    Ed25519SigningKeyProvider,
    canonical_json_bytes,
    verify_ed25519_signature,
)
from app.services.receipt_manifest import seal_evidence_manifest, verify_manifest_evidence
from app.services.receipt_service import (
    deep_verify_receipt_evidence,
    issue_automated_receipt,
    receipt_signature_state,
    revoke_receipt,
)
from app.services.storage_service import get_storage_service
from app.services.verification.service import calculate_verification
from tests.test_phase6_fusion_service import _prepare_fusion_inputs


def _provider(key_id: str = "test-key-a") -> Ed25519SigningKeyProvider:
    return Ed25519SigningKeyProvider(
        key_id=key_id,
        private_key=Ed25519PrivateKey.generate(),
    )


def test_canonical_json_is_order_independent_and_utc_normalized():
    instant = datetime(2026, 8, 19, 14, 0, tzinfo=timezone.utc)
    a = {"b": 2, "a": {"score": 0.8900000001, "time": instant}}
    b = {"a": {"time": instant, "score": 0.89}, "b": 2}
    assert canonical_json_bytes(a) == canonical_json_bytes(b)
    assert b'"score":"0.890000"' in canonical_json_bytes(a)
    assert b'"time":"2026-08-19T14:00:00.000Z"' in canonical_json_bytes(a)


def test_ed25519_detects_score_verdict_signature_and_wrong_key_tampering():
    provider = _provider()
    public = provider.get_public_key()
    payload = canonical_json_bytes({"score": "93.00", "verdict": "VERIFIED"})
    signed = provider.sign(payload)
    assert verify_ed25519_signature(
        payload=payload,
        signature_base64=signed.signature_base64,
        public_key_base64=public.public_key_base64,
    )
    assert not verify_ed25519_signature(
        payload=canonical_json_bytes({"score": "99.00", "verdict": "VERIFIED"}),
        signature_base64=signed.signature_base64,
        public_key_base64=public.public_key_base64,
    )
    assert not verify_ed25519_signature(
        payload=canonical_json_bytes({"score": "93.00", "verdict": "FLAGGED"}),
        signature_base64=signed.signature_base64,
        public_key_base64=public.public_key_base64,
    )
    altered = (
        ("A" if signed.signature_base64[0] != "A" else "B")
        + signed.signature_base64[1:]
    )
    assert not verify_ed25519_signature(
        payload=payload,
        signature_base64=altered,
        public_key_base64=public.public_key_base64,
    )
    wrong = _provider("wrong").get_public_key()
    assert not verify_ed25519_signature(
        payload=payload,
        signature_base64=signed.signature_base64,
        public_key_base64=wrong.public_key_base64,
    )


def _store_uploaded_evidence(
    data,
    db,
    tmp_path,
    *,
    file_type: EvidenceFileType,
    filename: str,
    mime_type: str,
    payload: bytes,
) -> EvidenceFile:
    session = data["session"]
    path = tmp_path / filename
    path.write_bytes(payload)
    storage_key = f"{session.organization_id}/{session.id}/phase8/{filename}"
    data["storage"].put_file(path, storage_key, mime_type)
    record = EvidenceFile(
        organization_id=session.organization_id,
        inspection_id=session.inspection_id,
        session_id=session.id,
        file_type=file_type,
        storage_key=storage_key,
        original_filename=filename,
        mime_type=mime_type,
        size_bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        upload_status=EvidenceUploadStatus.UPLOADED,
        hash_verified=True,
        uploaded_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.flush()
    return record


def _complete_sealable_evidence(data, db, tmp_path) -> None:
    session = data["session"]
    existing = {
        record.file_type: record
        for record in db.scalars(
            select(EvidenceFile).where(EvidenceFile.session_id == session.id)
        ).all()
    }
    assert EvidenceFileType.SENSOR_DATA in existing

    video = _store_uploaded_evidence(
        data,
        db,
        tmp_path,
        file_type=EvidenceFileType.VIDEO,
        filename="capture.mp4",
        mime_type="video/mp4",
        payload=b"siteproof-phase8-test-video-evidence\x00\x01\x02",
    )
    locations_payload = json.dumps(
        [
            {
                "relativeTimestampNs": 0,
                "latitude": 22.5726,
                "longitude": 88.3639,
                "accuracyMeters": 5.0,
            }
        ],
        separators=(",", ":"),
    ).encode("utf-8")
    locations = _store_uploaded_evidence(
        data,
        db,
        tmp_path,
        file_type=EvidenceFileType.LOCATION_DATA,
        filename="locations.json",
        mime_type="application/json",
        payload=locations_payload,
    )
    metadata_payload = json.dumps(
        {
            "sessionId": str(session.id),
            "capture": {"durationMs": int(session.capture_duration_ms or 0)},
        },
        separators=(",", ":"),
    ).encode("utf-8")
    metadata = _store_uploaded_evidence(
        data,
        db,
        tmp_path,
        file_type=EvidenceFileType.SESSION_METADATA,
        filename="session-metadata.json",
        mime_type="application/json",
        payload=metadata_payload,
    )

    manifest_entries = [existing[EvidenceFileType.SENSOR_DATA], video, locations, metadata]
    manifest_payload = json.dumps(
        {
            "sessionId": str(session.id),
            "files": [
                {
                    "type": record.file_type.value,
                    "name": record.original_filename,
                    "sizeBytes": record.size_bytes,
                    "sha256": record.sha256,
                }
                for record in manifest_entries
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    _store_uploaded_evidence(
        data,
        db,
        tmp_path,
        file_type=EvidenceFileType.MANIFEST,
        filename="manifest.json",
        mime_type="application/json",
        payload=manifest_payload,
    )
    db.commit()


def _use_application_storage(data, db) -> None:
    session = data["session"]
    sensor = db.scalar(
        select(EvidenceFile).where(
            EvidenceFile.session_id == session.id,
            EvidenceFile.file_type == EvidenceFileType.SENSOR_DATA,
        )
    )
    assert sensor is not None
    sensor_path = data["storage"].local_path(sensor.storage_key)
    assert sensor_path is not None
    storage = get_storage_service()
    storage.put_file(sensor_path, sensor.storage_key, sensor.mime_type)
    data["storage"] = storage


def _issued_fixture(client, db, tmp_path):
    data = _prepare_fusion_inputs(client, db, tmp_path)
    session = data["session"]
    _use_application_storage(data, db)
    _complete_sealable_evidence(data, db, tmp_path)
    analyze_session_fusion(db, session.id, storage=data["storage"])
    result = calculate_verification(
        db,
        session.id,
        actor_user_id=data["identities"]["admin"].id,
    )
    receipt = issue_automated_receipt(
        db,
        result.id,
        provider=_provider(),
        storage=data["storage"],
        actor_user_id=data["identities"]["admin"].id,
    )
    return data, result, receipt


def test_incomplete_evidence_is_not_sealed(client, db, tmp_path):
    data = _prepare_fusion_inputs(client, db, tmp_path)
    session = data["session"]
    with pytest.raises(SiteProofError) as exc_info:
        seal_evidence_manifest(
            db,
            session,
            actor_user_id=data["identities"]["admin"].id,
            storage=data["storage"],
        )
    assert exc_info.value.code == "EVIDENCE_INCOMPLETE"
    assert set(exc_info.value.details["types"]) == {
        "VIDEO",
        "LOCATION_DATA",
        "SESSION_METADATA",
        "MANIFEST",
    }


def test_receipt_end_to_end_is_idempotent_and_manifest_is_deterministic(
    client,
    db,
    tmp_path,
):
    data, result, receipt = _issued_fixture(client, db, tmp_path)
    again = issue_automated_receipt(
        db,
        result.id,
        provider=_provider("unused-second-provider"),
        storage=data["storage"],
        actor_user_id=data["identities"]["admin"].id,
    )
    assert again.id == receipt.id
    assert receipt_signature_state(db, receipt) == ("VALID", True)
    payload = json.loads(receipt.canonical_payload)
    assert payload["manifestSha256"] == receipt.manifest_sha256
    assert payload["verification"]["score"] == f"{result.final_score:.2f}"
    assert payload["verification"]["verdict"] == result.verdict.value
    assert len(payload["verification"]["signals"]) == 7
    assert [item["type"] for item in payload["verification"]["signals"]] == sorted(
        item["type"] for item in payload["verification"]["signals"]
    )
    manifest = db.get(EvidenceManifest, receipt.manifest_id)
    manifest_payload = json.loads(manifest.canonical_payload)
    order = [
        (item["type"], item["evidenceFileId"])
        for item in manifest_payload["evidenceFiles"]
    ]
    assert order == sorted(order)
    integrity = verify_manifest_evidence(db, manifest, storage=data["storage"])
    assert integrity.state == "MATCH"
    assert all(check.state == "MATCH" for check in integrity.checks)


def test_one_byte_evidence_mutation_is_detected(client, db, tmp_path):
    data, _, receipt = _issued_fixture(client, db, tmp_path)
    video = db.scalar(
        select(EvidenceFile).where(
            EvidenceFile.session_id == receipt.session_id,
            EvidenceFile.file_type == EvidenceFileType.VIDEO,
        )
    )
    path = data["storage"].local_path(video.storage_key)
    content = bytearray(path.read_bytes())
    assert content
    content[0] ^= 0x01
    path.write_bytes(content)
    state, checks = deep_verify_receipt_evidence(
        db,
        receipt,
        storage=data["storage"],
        actor_user_id=data["identities"]["admin"].id,
    )
    assert state == "MISMATCH"
    video_check = next(check for check in checks if check.file_type == "VIDEO")
    assert video_check.state == "MISMATCH"
    assert video_check.observed_sha256 != video_check.expected_sha256


def test_retired_key_still_verifies_and_compromised_key_is_warned(
    client,
    db,
    tmp_path,
):
    _, _, receipt = _issued_fixture(client, db, tmp_path)
    key = db.scalar(select(SigningKey).where(SigningKey.key_id == receipt.signing_key_id))
    key.status = SigningKeyStatus.RETIRED
    db.commit()
    assert receipt_signature_state(db, receipt) == ("VALID", True)
    key.status = SigningKeyStatus.COMPROMISED
    db.commit()
    assert receipt_signature_state(db, receipt) == ("COMPROMISED_KEY", True)


def test_key_rotation_and_new_result_supersede_old_receipt(client, db, tmp_path):
    data, result, old_receipt = _issued_fixture(client, db, tmp_path)
    second = VerificationResult(
        id=uuid.uuid4(),
        organization_id=result.organization_id,
        inspection_id=result.inspection_id,
        session_id=result.session_id,
        policy_id=result.policy_id,
        policy_name=result.policy_name,
        policy_version=result.policy_version,
        engine_version="verification-engine-v1.1-test",
        processing_status=VerificationProcessingStatus.COMPLETED,
        raw_score=result.raw_score,
        final_score=result.final_score,
        verdict=result.verdict,
        overall_confidence=result.overall_confidence,
        hard_rule_triggered=result.hard_rule_triggered,
        hard_rule_codes_json=result.hard_rule_codes_json,
        summary=result.summary,
        summary_reasons_json=result.summary_reasons_json,
        warnings_json=result.warnings_json,
        limitations_json=result.limitations_json,
        diagnostics_json=result.diagnostics_json,
        calculated_at=datetime.now(timezone.utc),
    )
    db.add(second)
    db.commit()
    new_receipt = issue_automated_receipt(
        db,
        second.id,
        provider=_provider("test-key-b"),
        storage=data["storage"],
        actor_user_id=data["identities"]["admin"].id,
    )
    db.refresh(old_receipt)
    old_key = db.scalar(
        select(SigningKey).where(SigningKey.key_id == old_receipt.signing_key_id)
    )
    new_key = db.scalar(
        select(SigningKey).where(SigningKey.key_id == new_receipt.signing_key_id)
    )
    assert old_key.status == SigningKeyStatus.RETIRED
    assert new_key.status == SigningKeyStatus.ACTIVE
    assert old_receipt.lifecycle_status == ReceiptLifecycleStatus.SUPERSEDED
    assert old_receipt.superseded_by_id == new_receipt.id
    assert receipt_signature_state(db, old_receipt) == ("VALID", True)


def test_issued_receipt_payload_fields_are_immutable(client, db, tmp_path):
    _, _, receipt = _issued_fixture(client, db, tmp_path)
    receipt.score += 1
    with pytest.raises(ValueError, match="immutable"):
        db.commit()
    db.rollback()


def test_unknown_key_is_reported_without_accepting_signature(client, db, tmp_path):
    _, _, receipt = _issued_fixture(client, db, tmp_path)
    key = db.scalar(select(SigningKey).where(SigningKey.key_id == receipt.signing_key_id))
    db.delete(key)
    db.commit()
    assert receipt_signature_state(db, receipt) == ("UNKNOWN_KEY", False)


def test_revoked_receipt_keeps_valid_signature(client, db, tmp_path):
    data, _, receipt = _issued_fixture(client, db, tmp_path)
    revoke_receipt(
        db,
        receipt,
        actor_user_id=data["identities"]["admin"].id,
        reason="Controlled test revocation",
    )
    assert receipt.lifecycle_status == ReceiptLifecycleStatus.REVOKED
    assert receipt_signature_state(db, receipt) == ("VALID", True)


def test_receipt_api_is_scoped_and_public_verification_is_minimal(
    client,
    db,
    tmp_path,
):
    data, _, receipt = _issued_fixture(client, db, tmp_path)
    detail = client.get(
        f"/api/v1/receipts/{receipt.id}",
        headers=data["reviewer_headers"],
    )
    assert detail.status_code == 200, detail.text
    assert detail.json()["signatureValid"] is True
    assert detail.json()["canonicalPayload"]["sessionId"] == str(receipt.session_id)
    denied = client.get(
        f"/api/v1/receipts/{receipt.id}",
        headers=data["other_admin_headers"],
    )
    assert denied.status_code == 404
    public = client.post(
        "/api/v1/receipts/verify",
        json={"receiptId": receipt.lookup_token},
    )
    assert public.status_code == 200, public.text
    body = public.json()
    assert body["signatureValid"] is True
    assert body["receiptStatus"] == "ISSUED"
    assert body["verdict"] is None
    assert body["score"] is None
    evidence = client.post(
        f"/api/v1/receipts/{receipt.id}/verify-evidence",
        headers=data["reviewer_headers"],
    )
    assert evidence.status_code == 200, evidence.text
    assert evidence.json()["state"] == "MATCH"
