from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SiteProof API"
    environment: str = "development"
    database_url: str = "sqlite:///./siteproof-dev.db"
    jwt_secret: str = "dev-only-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    cors_origins: str = "http://localhost:5173"

    verification_session_ttl_minutes: int = 15
    session_start_grace_seconds: int = 120
    capture_min_seconds: int = 8
    capture_max_seconds: int = 60
    location_freshness_seconds: int = 10
    preferred_location_accuracy_meters: float = 30.0

    storage_backend: str = "local"
    local_storage_path: str = "./siteproof-evidence"
    storage_endpoint_url: str | None = None
    storage_access_key: str | None = None
    storage_secret_key: str | None = None
    storage_bucket: str = "siteproof-evidence"
    storage_region: str = "us-east-1"

    max_video_bytes: int = 100 * 1024 * 1024
    max_sensor_bytes: int = 10 * 1024 * 1024
    max_location_bytes: int = 2 * 1024 * 1024
    max_metadata_bytes: int = 1 * 1024 * 1024
    max_manifest_bytes: int = 1 * 1024 * 1024
    max_thumbnail_bytes: int = 5 * 1024 * 1024

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
