from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.verification import EvidenceFile, EvidenceFileType, EvidenceUploadStatus

ALGORITHM_VERSION = "evidence-reuse-v1"


def analyze_exact_evidence_reuse(
    db: Session,
    *,
    organization_id,
    session_id,
) -> dict[str, Any]:
    current = list(
        db.scalars(
            select(EvidenceFile).where(
                EvidenceFile.organization_id == organization_id,
                EvidenceFile.session_id == session_id,
                EvidenceFile.upload_status == EvidenceUploadStatus.UPLOADED,
                EvidenceFile.hash_verified.is_(True),
                EvidenceFile.file_type.in_([EvidenceFileType.VIDEO, EvidenceFileType.SENSOR_DATA]),
            )
        ).all()
    )
    by_type = {record.file_type: record for record in current}
    matches: dict[str, list[str]] = {}

    for file_type in (EvidenceFileType.VIDEO, EvidenceFileType.SENSOR_DATA):
        record = by_type.get(file_type)
        if record is None:
            continue
        session_ids = list(
            db.scalars(
                select(EvidenceFile.session_id)
                .where(
                    EvidenceFile.organization_id == organization_id,
                    EvidenceFile.session_id != session_id,
                    EvidenceFile.file_type == file_type,
                    EvidenceFile.sha256 == record.sha256,
                    EvidenceFile.upload_status == EvidenceUploadStatus.UPLOADED,
                    EvidenceFile.hash_verified.is_(True),
                )
                .distinct()
            ).all()
        )
        if session_ids:
            matches[file_type.value] = [str(value) for value in session_ids]

    video_reuse = bool(matches.get(EvidenceFileType.VIDEO.value))
    sensor_reuse = bool(matches.get(EvidenceFileType.SENSOR_DATA.value))
    score = 0.0
    codes: list[str] = []
    reasons: list[str] = []

    if video_reuse and sensor_reuse:
        score = 1.0
        codes.append("EXACT_EVIDENCE_REUSE")
        reasons.append("The same verified video and sensor byte hashes appeared in another session.")
    elif video_reuse:
        score = 0.82
        codes.append("EXACT_VIDEO_REUSE")
        reasons.append("The same verified video byte hash appeared in another session.")
    elif sensor_reuse:
        score = 0.68
        codes.append("EXACT_SENSOR_REUSE")
        reasons.append("The same verified sensor byte hash appeared in another session.")
    else:
        reasons.append("No exact video or sensor evidence hash reuse was found in other sessions.")

    return {
        "score": score,
        "reason_codes": codes,
        "reasons": reasons,
        "metrics": {
            "matchesByType": matches,
            "exactPackageReuse": video_reuse and sensor_reuse,
            "videoReuse": video_reuse,
            "sensorReuse": sensor_reuse,
        },
        "algorithm_version": ALGORITHM_VERSION,
    }
