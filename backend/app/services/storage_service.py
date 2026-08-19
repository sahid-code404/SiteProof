import shutil
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath

from app.core.config import get_settings


@dataclass(frozen=True)
class StorageStat:
    size_bytes: int


class StorageService:
    def put_file(self, source: Path, key: str, content_type: str) -> StorageStat:
        raise NotImplementedError

    def stat(self, key: str) -> StorageStat:
        raise NotImplementedError

    def read_bytes(self, key: str, *, max_bytes: int) -> bytes:
        raise NotImplementedError

    def local_path(self, key: str) -> Path | None:
        return None

    def presigned_download_url(self, key: str, *, expires_seconds: int = 300) -> str | None:
        return None


def _validated_key(key: str) -> PurePosixPath:
    path = PurePosixPath(key)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("Invalid storage key")
    return path


class LocalObjectStorage(StorageService):
    def __init__(self, root: str):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        relative = _validated_key(key)
        target = (self.root / Path(*relative.parts)).resolve()
        if self.root not in target.parents and target != self.root:
            raise ValueError("Invalid storage key")
        return target

    def put_file(self, source: Path, key: str, content_type: str) -> StorageStat:
        del content_type
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as input_file, target.open("wb") as output_file:
            shutil.copyfileobj(input_file, output_file, length=1024 * 1024)
        return StorageStat(size_bytes=target.stat().st_size)

    def stat(self, key: str) -> StorageStat:
        target = self._path(key)
        return StorageStat(size_bytes=target.stat().st_size)

    def read_bytes(self, key: str, *, max_bytes: int) -> bytes:
        target = self._path(key)
        if target.stat().st_size > max_bytes:
            raise ValueError("Object exceeds allowed read size")
        return target.read_bytes()

    def local_path(self, key: str) -> Path | None:
        target = self._path(key)
        return target if target.exists() else None


class S3ObjectStorage(StorageService):
    def __init__(self) -> None:
        settings = get_settings()
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - dependency is installed in production image.
            raise RuntimeError("boto3 is required for S3-compatible storage") from exc
        self.bucket = settings.storage_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.storage_endpoint_url or None,
            aws_access_key_id=settings.storage_access_key or None,
            aws_secret_access_key=settings.storage_secret_key or None,
            region_name=settings.storage_region,
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            self.client.create_bucket(Bucket=self.bucket)

    def put_file(self, source: Path, key: str, content_type: str) -> StorageStat:
        _validated_key(key)
        self.client.upload_file(
            str(source),
            self.bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )
        return self.stat(key)

    def stat(self, key: str) -> StorageStat:
        _validated_key(key)
        response = self.client.head_object(Bucket=self.bucket, Key=key)
        return StorageStat(size_bytes=int(response["ContentLength"]))

    def read_bytes(self, key: str, *, max_bytes: int) -> bytes:
        metadata = self.stat(key)
        if metadata.size_bytes > max_bytes:
            raise ValueError("Object exceeds allowed read size")
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read(max_bytes + 1)

    def presigned_download_url(self, key: str, *, expires_seconds: int = 300) -> str | None:
        _validated_key(key)
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_seconds,
        )


@lru_cache
def get_storage_service() -> StorageService:
    settings = get_settings()
    if settings.storage_backend.lower() == "s3":
        return S3ObjectStorage()
    return LocalObjectStorage(settings.local_storage_path)
