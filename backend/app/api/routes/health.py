from fastapi import APIRouter

from app.core.config import get_settings
from app.services.receipt_signing import signing_enabled, signing_service_ready

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str | bool]:
    settings = get_settings()
    autonomous_enabled = settings.autonomous_verification_enabled
    primary_model = settings.autonomous_vlm_model.strip()
    secondary_model = settings.autonomous_secondary_vlm_model.strip()
    contract_model = settings.autonomous_contract_model.strip()
    autonomous_provider_configured = bool(
        settings.autonomous_ai_base_url.strip() and primary_model and contract_model
    )
    autonomous_consensus_configured = bool(
        secondary_model and primary_model and secondary_model != primary_model
    )
    autonomous_ready = autonomous_provider_configured and autonomous_consensus_configured
    return {
        "status": "ok",
        "service": "siteproof-api",
        "receiptSigningEnabled": signing_enabled(),
        "signingServiceReady": signing_service_ready(),
        "autonomousVerificationEnabled": autonomous_enabled,
        "autonomousProviderConfigured": autonomous_provider_configured,
        "autonomousConsensusConfigured": autonomous_consensus_configured,
        "autonomousVerificationReady": (not autonomous_enabled) or autonomous_ready,
    }
