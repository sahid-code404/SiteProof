from fastapi import APIRouter

from app.core.config import get_settings
from app.services.receipt_signing import signing_enabled, signing_service_ready

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str | bool]:
    settings = get_settings()
    autonomous_enabled = settings.autonomous_verification_enabled
    autonomous_provider_configured = bool(
        settings.autonomous_ai_base_url.strip() and settings.autonomous_vlm_model.strip()
    )
    return {
        "status": "ok",
        "service": "siteproof-api",
        "receiptSigningEnabled": signing_enabled(),
        "signingServiceReady": signing_service_ready(),
        "autonomousVerificationEnabled": autonomous_enabled,
        "autonomousProviderConfigured": autonomous_provider_configured,
        "autonomousVerificationReady": (not autonomous_enabled) or autonomous_provider_configured,
    }
