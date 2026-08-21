from __future__ import annotations

import base64
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


def utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc)
    milliseconds = value.microsecond // 1000
    return value.replace(microsecond=milliseconds * 1000).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


def fixed_decimal(value: float | Decimal, places: int) -> str:
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        raise ValueError("Non-finite numbers cannot be signed")
    quantum = Decimal(1).scaleb(-places)
    return format(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP), f".{places}f")


def _normalize(value: Any) -> Any:
    if isinstance(value, datetime):
        return utc_iso(value)
    if isinstance(value, Decimal):
        return fixed_decimal(value, 6)
    if isinstance(value, float):
        return fixed_decimal(value, 6)
    if isinstance(value, dict):
        return {str(key): _normalize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalize(item) for item in value]
    return value


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        _normalize(value),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class SignatureResult:
    algorithm: str
    key_id: str
    signature_base64: str
    payload_sha256: str


@dataclass(frozen=True)
class PublicKeyInfo:
    key_id: str
    algorithm: str
    public_key_base64: str


class SigningKeyProvider:
    def sign(self, payload: bytes) -> SignatureResult:
        raise NotImplementedError

    def get_public_key(self) -> PublicKeyInfo:
        raise NotImplementedError


class Ed25519SigningKeyProvider(SigningKeyProvider):
    def __init__(self, *, key_id: str, private_key: Ed25519PrivateKey) -> None:
        self._key = private_key
        self._key_id = key_id

    @classmethod
    def from_pem_file(cls, *, key_id: str, path: str | Path) -> "Ed25519SigningKeyProvider":
        pem = Path(path).read_bytes()
        key = serialization.load_pem_private_key(pem, password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise ValueError("Configured signing key is not an Ed25519 private key")
        return cls(key_id=key_id, private_key=key)

    def sign(self, payload: bytes) -> SignatureResult:
        signature = self._key.sign(payload)
        return SignatureResult(
            algorithm="Ed25519",
            key_id=self._key_id,
            signature_base64=base64.b64encode(signature).decode("ascii"),
            payload_sha256=sha256_hex(payload),
        )

    def get_public_key(self) -> PublicKeyInfo:
        raw = self._key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        return PublicKeyInfo(
            key_id=self._key_id,
            algorithm="Ed25519",
            public_key_base64=base64.b64encode(raw).decode("ascii"),
        )


def verify_ed25519_signature(
    *, payload: bytes, signature_base64: str, public_key_base64: str
) -> bool:
    try:
        signature = base64.b64decode(signature_base64, validate=True)
        public_key = base64.b64decode(public_key_base64, validate=True)
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, payload)
        return True
    except (ValueError, InvalidSignature):
        return False
