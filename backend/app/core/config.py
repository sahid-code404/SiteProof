from functools import lru_cache

from pydantic import field_validator
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
    challenge_timeout_seconds: int = 18
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
    challenge_max_retries: int = 3
    challenge_failure_limit: int = 2
    rotation_min_target_degrees: float = 25.0
    rotation_max_target_degrees: float = 55.0
    tilt_min_target_degrees: float = 22.0
    tilt_max_target_degrees: float = 45.0
    rotation_right_sign: float = -1.0
    tilt_down_sign: float = 1.0
    challenge_direction_weight: float = 0.30
    challenge_angle_weight: float = 0.30
    challenge_agreement_weight: float = 0.20
    challenge_timing_weight: float = 0.10
    challenge_smoothness_weight: float = 0.10

    # Phase 5 accepted visual-motion analysis.
    vision_analysis_version: str = "vision-v1.4"
    vision_analysis_fps: float = 12.0
    vision_max_width: int = 960
    vision_pre_challenge_padding_ms: int = 200
    vision_post_challenge_padding_ms: int = 200
    vision_min_features: int = 40
    vision_max_features: int = 600
    vision_grid_rows: int = 4
    vision_grid_cols: int = 4
    vision_lk_window_size: int = 21
    vision_forward_backward_max_error_px: float = 1.5
    vision_ransac_threshold_px: float = 3.0
    vision_min_inlier_ratio: float = 0.45
    vision_scene_cut_hist_distance: float = 0.60
    vision_duplicate_mean_absdiff: float = 1.5
    vision_motion_threshold_px: float = 1.5
    vision_timeline_tolerance_ms: int = 300
    vision_video_duration_tolerance_ms: int = 1500
    vision_max_invalid_frame_ratio: float = 0.20
    vision_assumed_horizontal_fov_degrees: float = 65.0
    vision_max_duration_seconds: int = 90
    vision_max_frame_count: int = 5000
    vision_max_resolution_pixels: int = 3840 * 2160
    vision_max_processing_seconds: float = 20.0
    vision_feature_weight: float = 0.20
    vision_inlier_weight: float = 0.30
    vision_consistency_weight: float = 0.25
    vision_coverage_weight: float = 0.15
    vision_continuity_weight: float = 0.10

    # Phase 6 deterministic visual-inertial consistency.
    fusion_analysis_version: str = "fusion-v1.0"
    fusion_resample_hz: float = 20.0
    fusion_max_alignment_lag_ms: int = 500
    fusion_strong_angle_error_deg: float = 8.0
    fusion_max_angle_error_deg: float = 25.0
    fusion_relative_angle_error_full_penalty: float = 0.60
    fusion_timing_excellent_ms: int = 150
    fusion_timing_good_ms: int = 350
    fusion_timing_weak_ms: int = 700
    fusion_pass_threshold: float = 0.80
    fusion_partial_threshold: float = 0.60
    fusion_min_sensor_confidence: float = 0.50
    fusion_min_visual_confidence: float = 0.50
    fusion_strong_contradiction_confidence: float = 0.80
    fusion_motion_floor_deg: float = 5.0
    fusion_large_motion_deg: float = 25.0
    fusion_min_scene_continuity_score: float = 0.55
    fusion_scene_freeze_warning_ms: int = 1500
    fusion_duration_mismatch_score: float = 0.35
    fusion_max_sensor_uncompressed_bytes: int = 50 * 1024 * 1024
    fusion_max_processing_seconds: float = 5.0
    fusion_direction_weight: float = 0.25
    fusion_magnitude_weight: float = 0.25
    fusion_timing_weight: float = 0.20
    fusion_correlation_weight: float = 0.20
    fusion_duration_weight: float = 0.10

    storage_backend: str = "local"
    local_storage_path: str = "./siteproof-evidence"
    storage_endpoint_url: str | None = None
    storage_access_key: str | None = None
    storage_secret_key: str | None = None
    storage_bucket: str = "siteproof-evidence"
    storage_region: str = "us-east-1"

    # 75-second FHD evidence can legitimately exceed the old 100 MiB ceiling on some devices.
    # Keep a bounded 256 MiB server limit; Android additionally rejects unusually large files
    # before upload and checks free storage before capture begins.
    max_video_bytes: int = 256 * 1024 * 1024
    max_sensor_bytes: int = 10 * 1024 * 1024
    max_location_bytes: int = 2 * 1024 * 1024
    max_metadata_bytes: int = 1 * 1024 * 1024
    max_manifest_bytes: int = 1 * 1024 * 1024
    max_thumbnail_bytes: int = 5 * 1024 * 1024

    # Phase 8 server-side cryptographic receipts. Only an external key path is configured;
    # private key bytes are never stored in settings, Git, or PostgreSQL.
    receipt_signing_enabled: bool = False
    receipt_signing_key_id: str = "siteproof-signing-dev-01"
    receipt_signing_private_key_path: str = "/run/siteproof-secrets/siteproof-signing-private.pem"
    public_receipt_details: str = "MINIMAL"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("challenge_max_retries", mode="after")
    @classmethod
    def enforce_minimum_challenge_retries(cls, value: int) -> int:
        return max(3, value)

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

    @property
    def vision_confidence_weights(self) -> dict[str, float]:
        weights = {
            "feature": self.vision_feature_weight,
            "inlier": self.vision_inlier_weight,
            "consistency": self.vision_consistency_weight,
            "coverage": self.vision_coverage_weight,
            "continuity": self.vision_continuity_weight,
        }
        total = sum(weights.values())
        if total <= 0:
            return {name: 0.2 for name in weights}
        return {name: value / total for name, value in weights.items()}

    @property
    def fusion_score_weights(self) -> dict[str, float]:
        weights = {
            "direction": self.fusion_direction_weight,
            "magnitude": self.fusion_magnitude_weight,
            "timing": self.fusion_timing_weight,
            "correlation": self.fusion_correlation_weight,
            "duration": self.fusion_duration_weight,
        }
        total = sum(weights.values())
        if total <= 0:
            return {
                "direction": 0.25,
                "magnitude": 0.25,
                "timing": 0.20,
                "correlation": 0.20,
                "duration": 0.10,
            }
        return {name: value / total for name, value in weights.items()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
