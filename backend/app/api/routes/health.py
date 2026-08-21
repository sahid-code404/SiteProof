from fastapi import APIRouter

from app.services.receipt_signing import signing_enabled, signing_service_ready

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "service": "siteproof-api",
        "receiptSigningEnabled": signing_enabled(),
        "signingServiceReady": signing_service_ready(),
    }
