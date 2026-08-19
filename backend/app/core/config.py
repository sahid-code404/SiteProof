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

    challenge_count: int = 3
    challenge_timeout_seconds: int = 15
    challenge_baseline_ms: int = 500
    challenge_settling_ms: int = 350
    challenge_min_gyro_samples: int = 12
    challenge_max_sensor_samples: int = 5000
    challenge_window_start_tolerance_ms: int = 1000
    challenge_end_tolerance_ms: int = 500
    challenge_movement_threshold_rad_s: float = 0.18
    challenge_settle_threshold_rad_s: float = 0.10
    challenge_sensor_agreement_tolerance_degrees: float = 20.0
    challenge_sensor_conflict_degrees: float = 35.0
    challenge_pass_threshold: float = 0.75
    challenge_inconclusive_threshold: float = 0.50
    challenge_max_retries: int = 1
    challenge_failure_limit: int = 2
    rotation_min_target_degrees: float = 25.0
    rotation_max_target_degrees: float = 55.0
    tilt_min_target_degrees: float = 22.0
    tilt_max_target_degrees: float = 45.0
    # Android sensor coordinates in portrait: X points right, Y points toward the top.
    # These signs are explicit configuration so genuine device trials can tune semantics
    # without changing validation code. Defaults follow the current portrait convention.
    rotation_right_sign: float = -1.0
    tilt_down_sign: float = 1.0
    challenge_direction_weight: float = 0.30
    challenge_angle_weight: float = 0.30
    challenge_agreement_weight: float = 0.20
    challenge_timing_weight: float = 0.10
    challenge_smoothness_weight: float = 0.10

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

    @property
    def challenge_score_weights(self) -> dict[str, float]:
        weights = {
            "direction": self.challenge_direction_weight,
            "angle": self.challenge_angle_weight,
            "agreement": self.challenge_agreement_weight,
            "timing": self.challenge_timing_weight,
            "smoothness": self.challenge_smoothness_weight,
        }
        total = sum(weights.values())
        if total <= 0:
            return {name: 0.2 for name in weights}
        return {name: value / total for name, value in weights.items()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
