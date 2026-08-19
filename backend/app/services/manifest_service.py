import gzip
import io
import json
from collections import Counter
from typing import Any

from pydantic import ValidationError

from app.core.errors import SiteProofError
from app.models.verification import EvidenceFile, EvidenceFileType, VerificationSession
from app.schemas.session import EvidenceManifestDocument
from app.services.storage_service import StorageService


def _decompress_if_needed(data: bytes, *, max_decompressed_bytes: int) -> bytes:
    if not data.startswith(b"\x1f\x8b"):
        if len(data) > max_decompressed_bytes:
            raise SiteProofError(422, "EVIDENCE_INVALID", "Evidence package is too large to validate.")
        return data
    with gzip.GzipFile(fileobj=io.BytesIO(data), mode="rb") as zipped:
        result = zipped.read(max_decompressed_bytes + 1)
    if len(result) > max_decompressed_bytes:
        raise SiteProofError(422, "EVIDENCE_INVALID", "Compressed evidence expands beyond the limit.")
    return result


def parse_manifest(data: bytes) -> EvidenceManifestDocument:
    try:
        return EvidenceManifestDocument.model_validate_json(data)
    except (ValidationError, ValueError) as exc:
        raise SiteProofError(422, "MANIFEST_INVALID", "Evidence manifest is not valid JSON.") from exc


def validate_manifest_against_records(
    document: EvidenceManifestDocument,
    verification_session: VerificationSession,
    records: dict[EvidenceFileType, EvidenceFile],
) -> None:
    if document.session_id != verification_session.id:
        raise SiteProofError(422, "MANIFEST_SESSION_MISMATCH", "Manifest session ID does not match.")

    entry_types = [entry.type for entry in document.files]
    if len(entry_types) != len(set(entry_types)):
        raise SiteProofError(422, "MANIFEST_DUPLICATE_FILE", "Manifest contains duplicate file types.")

    required = {
        EvidenceFileType.VIDEO,
        EvidenceFileType.SENSOR_DATA,
        EvidenceFileType.LOCATION_DATA,
        EvidenceFileType.SESSION_METADATA,
    }
    if not required.issubset(set(entry_types)):
        raise SiteProofError(422, "MANIFEST_INCOMPLETE", "Manifest is missing required evidence.")

    for entry in document.files:
        if entry.type == EvidenceFileType.MANIFEST:
            raise SiteProofError(422, "MANIFEST_INVALID", "Manifest must not recursively list itself.")
        record = records.get(entry.type)
        if record is None:
            raise SiteProofError(422, "MANIFEST_UNKNOWN_FILE", "Manifest references unknown evidence.")
        if entry.name != record.original_filename:
            raise SiteProofError(422, "MANIFEST_FILENAME_MISMATCH", "Manifest filename does not match.")
        if entry.size_bytes != record.size_bytes:
            raise SiteProofError(422, "MANIFEST_SIZE_MISMATCH", "Manifest file size does not match.")
        if entry.sha256.lower() != record.sha256:
            raise SiteProofError(422, "MANIFEST_HASH_MISMATCH", "Manifest file hash does not match.")


def validate_sensor_package(
    data: bytes,
    verification_session: VerificationSession,
) -> None:
    raw = _decompress_if_needed(data, max_decompressed_bytes=40 * 1024 * 1024)
    counts: Counter[str] = Counter()
    previous_by_type: dict[str, int] = {}
    try:
        text = raw.decode("utf-8")
        for line in text.splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            relative = int(item["relativeTimestampNs"])
            sensor_type = str(item["type"])
            if relative < 0 or relative < previous_by_type.get(sensor_type, -1):
                raise ValueError("timestamps are not monotonic per sensor")
            previous_by_type[sensor_type] = relative
            if sensor_type not in {"ACCELEROMETER", "GYROSCOPE", "ROTATION_VECTOR", "MAGNETOMETER"}:
                raise ValueError("unknown sensor type")
            values = item["values"]
            if not isinstance(values, list) or len(values) < 3:
                raise ValueError("sensor values missing")
            counts[sensor_type] += 1
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise SiteProofError(422, "SENSOR_PACKAGE_INVALID", "Sensor package is not structurally valid.") from exc

    if not counts:
        raise SiteProofError(422, "SENSOR_PACKAGE_INVALID", "Sensor package contains no samples.")

    summary = verification_session.sensor_summary or {}
    expected = {
        "ACCELEROMETER": int(summary.get("accelerometer_samples", 0)),
        "GYROSCOPE": int(summary.get("gyroscope_samples", 0)),
        "ROTATION_VECTOR": int(summary.get("rotation_vector_samples", 0)),
        "MAGNETOMETER": int(summary.get("magnetometer_samples", 0)),
    }
    for sensor_type, expected_count in expected.items():
        if counts[sensor_type] != expected_count:
            raise SiteProofError(
                422,
                "SENSOR_COUNT_MISMATCH",
                f"{sensor_type} sample count does not match capture summary.",
            )


def validate_location_package(
    data: bytes,
    verification_session: VerificationSession,
) -> None:
    raw = _decompress_if_needed(data, max_decompressed_bytes=10 * 1024 * 1024)
    try:
        items: list[dict[str, Any]] = json.loads(raw.decode("utf-8"))
        if not isinstance(items, list) or not items:
            raise ValueError("location list missing")
        previous_time = -1
        for item in items:
            relative = int(item["relativeTimestampNs"])
            latitude = float(item["latitude"])
            longitude = float(item["longitude"])
            accuracy = float(item["accuracyMeters"])
            if relative < 0 or relative < previous_time:
                raise ValueError("timestamps are not monotonic")
            if not -90 <= latitude <= 90 or not -180 <= longitude <= 180 or accuracy < 0:
                raise ValueError("invalid location values")
            previous_time = relative
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise SiteProofError(
            422, "LOCATION_PACKAGE_INVALID", "Location package is not structurally valid."
        ) from exc

    expected = int((verification_session.location_summary or {}).get("location_samples", 0))
    if len(items) != expected:
        raise SiteProofError(
            422, "LOCATION_COUNT_MISMATCH", "Location sample count does not match capture summary."
        )


def validate_session_metadata(data: bytes, verification_session: VerificationSession) -> None:
    try:
        metadata = json.loads(data.decode("utf-8"))
        if str(metadata["sessionId"]) != str(verification_session.id):
            raise ValueError("wrong session")
        capture = metadata["capture"]
        duration = int(capture["durationMs"])
        if duration != int(verification_session.capture_duration_ms or 0):
            raise ValueError("wrong duration")
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise SiteProofError(
            422, "SESSION_METADATA_INVALID", "Session metadata does not match this capture."
        ) from exc


def validate_uploaded_evidence(
    storage: StorageService,
    verification_session: VerificationSession,
    records: dict[EvidenceFileType, EvidenceFile],
) -> EvidenceManifestDocument:
    manifest_record = records[EvidenceFileType.MANIFEST]
    manifest_data = storage.read_bytes(manifest_record.storage_key, max_bytes=1024 * 1024)
    document = parse_manifest(manifest_data)
    validate_manifest_against_records(document, verification_session, records)

    sensor = records[EvidenceFileType.SENSOR_DATA]
    sensor_data = storage.read_bytes(sensor.storage_key, max_bytes=10 * 1024 * 1024)
    validate_sensor_package(sensor_data, verification_session)

    locations = records[EvidenceFileType.LOCATION_DATA]
    location_data = storage.read_bytes(locations.storage_key, max_bytes=2 * 1024 * 1024)
    validate_location_package(location_data, verification_session)

    metadata = records[EvidenceFileType.SESSION_METADATA]
    metadata_data = storage.read_bytes(metadata.storage_key, max_bytes=1024 * 1024)
    validate_session_metadata(metadata_data, verification_session)
    return document
