from __future__ import annotations

import gzip
import json
import tempfile
from pathlib import Path
from typing import Any

from app.models.verification import EvidenceFile
from app.services.storage_service import StorageService


def read_evidence_bytes(storage: StorageService, evidence: EvidenceFile, *, max_bytes: int) -> bytes:
    local = storage.local_path(evidence.storage_key)
    if local is not None:
        if local.stat().st_size > max_bytes:
            raise ValueError("Evidence object exceeds allowed analysis size")
        return local.read_bytes()
    return storage.read_bytes(evidence.storage_key, max_bytes=max_bytes)


def maybe_gzip(payload: bytes) -> bytes:
    return gzip.decompress(payload) if payload[:2] == b"\x1f\x8b" else payload


def read_json_array(
    storage: StorageService,
    evidence: EvidenceFile,
    *,
    max_bytes: int,
) -> list[dict[str, Any]]:
    decoded = json.loads(maybe_gzip(read_evidence_bytes(storage, evidence, max_bytes=max_bytes)))
    if not isinstance(decoded, list):
        raise ValueError("Expected JSON array evidence")
    return [item for item in decoded if isinstance(item, dict)]


def read_json_object(
    storage: StorageService,
    evidence: EvidenceFile,
    *,
    max_bytes: int,
) -> dict[str, Any]:
    decoded = json.loads(maybe_gzip(read_evidence_bytes(storage, evidence, max_bytes=max_bytes)))
    if not isinstance(decoded, dict):
        raise ValueError("Expected JSON object evidence")
    return decoded


def read_ndjson(
    storage: StorageService,
    evidence: EvidenceFile,
    *,
    max_bytes: int,
) -> list[dict[str, Any]]:
    text = maybe_gzip(read_evidence_bytes(storage, evidence, max_bytes=max_bytes)).decode("utf-8")
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        if isinstance(value, dict):
            rows.append(value)
    return rows


def materialized_path(
    storage: StorageService,
    evidence: EvidenceFile,
) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    local = storage.local_path(evidence.storage_key)
    if local is not None:
        return local, None
    temp = tempfile.TemporaryDirectory(prefix="siteproof-advanced-")
    path = Path(temp.name) / (evidence.original_filename or "evidence.bin")
    storage.copy_to_file(evidence.storage_key, path)
    return path, temp
