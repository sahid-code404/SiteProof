from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.services.receipt_crypto import Ed25519SigningKeyProvider, SigningKeyProvider


def signing_enabled() -> bool:
    return get_settings().receipt_signing_enabled


@lru_cache
def get_signing_key_provider() -> SigningKeyProvider:
    settings = get_settings()
    if not settings.receipt_signing_enabled:
        raise RuntimeError("Receipt signing is disabled")
    return Ed25519SigningKeyProvider.from_pem_file(
        key_id=settings.receipt_signing_key_id,
        path=settings.receipt_signing_private_key_path,
    )


def signing_service_ready() -> bool:
    if not signing_enabled():
        return False
    try:
        get_signing_key_provider().get_public_key()
        return True
    except (OSError, ValueError, RuntimeError):
        return False


def validate_production_signing_configuration() -> None:
    settings = get_settings()
    if settings.environment.lower() != "production" or not settings.receipt_signing_enabled:
        return
    path = Path(settings.receipt_signing_private_key_path)
    if not path.is_file():
        raise RuntimeError(
            "Production receipt signing is enabled but the configured private key is unavailable"
        )
    get_signing_key_provider().get_public_key()
