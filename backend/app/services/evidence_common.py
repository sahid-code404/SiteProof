import uuid

from app.core.config import get_settings
from app.core.errors import SiteProofError
from app.models.verification import EvidenceFile, EvidenceFileType, EvidenceUploadStatus
from app.schemas.session import EvidenceFileRequest, EvidenceFileResponse

REQUIRED_EVIDENCE = {
    EvidenceFileType.VIDEO,
    EvidenceFileType.SENSOR_DATA,
    EvidenceFileType.LOCATION_DATA,
    EvidenceFileType.SESSION_METADATA,
    EvidenceFileType.MANIFEST,
}
MIME_TYPES = {
    EvidenceFileType.VIDEO: {"video/mp4"},
    EvidenceFileType.SENSOR_DATA: {"application/octet-stream", "application/gzip"},
    EvidenceFileType.LOCATION_DATA: {"application/json", "application/gzip"},
    EvidenceFileType.SESSION_METADATA: {"application/json"},
    EvidenceFileType.MANIFEST: {"application/json"},
    EvidenceFileType.THUMBNAIL: {"image/jpeg"},
}
EXTENSIONS = {
    EvidenceFileType.VIDEO: ".mp4",
    EvidenceFileType.SENSOR_DATA: ".dat",
    EvidenceFileType.LOCATION_DATA: ".json",
    EvidenceFileType.SESSION_METADATA: ".json",
    EvidenceFileType.MANIFEST: ".json",
    EvidenceFileType.THUMBNAIL: ".jpg",
}


def size_limit(file_type: EvidenceFileType) -> int:
    settings = get_settings()
    return {
        EvidenceFileType.VIDEO: settings.max_video_bytes,
        EvidenceFileType.SENSOR_DATA: settings.max_sensor_bytes,
        EvidenceFileType.LOCATION_DATA: settings.max_location_bytes,
        EvidenceFileType.SESSION_METADATA: settings.max_metadata_bytes,
        EvidenceFileType.MANIFEST: settings.max_manifest_bytes,
        EvidenceFileType.THUMBNAIL: settings.max_thumbnail_bytes,
    }[file_type]


def validate_file_descriptor(item: EvidenceFileRequest) -> None:
    if item.mime_type.lower() not in MIME_TYPES[item.type]:
        raise SiteProofError(
            422, "UNSUPPORTED_MIME_TYPE", f"{item.type.value} does not accept MIME type {item.mime_type}."
        )
    if item.size_bytes > size_limit(item.type):
        raise SiteProofError(
            413, "EVIDENCE_FILE_TOO_LARGE", f"{item.type.value} exceeds the configured file size limit."
        )


def storage_key(
    organization_id: uuid.UUID,
    inspection_id: uuid.UUID,
    session_id: uuid.UUID,
    file_type: EvidenceFileType,
) -> str:
    object_id = uuid.uuid4()
    return (
        f"organizations/{organization_id}/inspections/{inspection_id}/sessions/{session_id}/"
        f"{file_type.value.lower()}/{object_id}{EXTENSIONS[file_type]}"
    )


def evidence_response(record: EvidenceFile) -> EvidenceFileResponse:
    return EvidenceFileResponse(
        id=record.id,
        type=record.file_type,
        filename=record.original_filename,
        mime_type=record.mime_type,
        size_bytes=record.size_bytes,
        sha256=record.sha256,
        upload_status=record.upload_status,
        hash_verified=record.hash_verified,
        uploaded_at=record.uploaded_at,
        download_path=(
            f"sessions/{record.session_id}/evidence/{record.id}/content"
            if record.upload_status == EvidenceUploadStatus.UPLOADED
            else None
        ),
    )
