from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.core.config import get_settings

MAX_PROVIDER_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_PROVIDER_REQUEST_BYTES = 32 * 1024 * 1024
MAX_PROVIDER_IMAGE_COUNT = 24
MAX_PROVIDER_ATTEMPTS = 3
RETRYABLE_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})
SENSITIVE_PROVIDER_KEYS = frozenset(
    {
        "latitude",
        "longitude",
        "expectedlatitude",
        "expectedlongitude",
        "allowedradiusmeters",
        "locationaddress",
    }
)


@dataclass(frozen=True)
class AIJsonResponse:
    payload: dict[str, Any]
    raw_hash: str
    model: str


class AutonomousAIError(RuntimeError):
    pass


def _extract_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise AutonomousAIError("Model response did not contain a JSON object")
        try:
            value = json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise AutonomousAIError("Model response contained invalid JSON") from exc
    if not isinstance(value, dict):
        raise AutonomousAIError("Model response JSON must be an object")
    return value


def _message_text(response: dict[str, Any]) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AutonomousAIError("Provider response did not contain chat-completion content") from exc
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        if parts:
            return "\n".join(parts)
    raise AutonomousAIError("Provider returned unsupported message content")


def _validate_response_size(response: httpx.Response) -> None:
    declared = response.headers.get("content-length")
    if declared:
        try:
            if int(declared) > MAX_PROVIDER_RESPONSE_BYTES:
                raise AutonomousAIError("Autonomous AI provider response exceeded the safety limit")
        except ValueError:
            pass
    if len(response.content) > MAX_PROVIDER_RESPONSE_BYTES:
        raise AutonomousAIError("Autonomous AI provider response exceeded the safety limit")


def _retry_delay_seconds(attempt: int) -> float:
    # Deterministic and intentionally short: queue-level retries remain the outer reliability layer.
    return 0.25 * (2 ** max(0, attempt - 1))


def _should_retry_status(status_code: int) -> bool:
    return status_code in RETRYABLE_STATUS_CODES


def _redact_sensitive_provider_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _redact_sensitive_provider_fields(item)
            for key, item in value.items()
            if str(key).replace("_", "").lower() not in SENSITIVE_PROVIDER_KEYS
        }
    if isinstance(value, list):
        return [_redact_sensitive_provider_fields(item) for item in value]
    return value


def _minimize_provider_user_text(user_text: str) -> str:
    """Remove dedicated precise-location fields before any text leaves SiteProof.

    Natural-language admin text is preserved exactly because it can itself define the inspection
    task. Structured latitude/longitude, radius and full address fields are unnecessary for visual
    semantic analysis and remain handled by SiteProof's deterministic location checks instead.
    """
    try:
        parsed = json.loads(user_text)
    except json.JSONDecodeError:
        return user_text
    minimized = _redact_sensitive_provider_fields(parsed)
    return json.dumps(minimized, ensure_ascii=False, separators=(",", ":"))


def _validate_provider_base_url(base_url: str) -> None:
    parsed = urlsplit(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise AutonomousAIError("Autonomous AI provider URL must be an HTTP(S) endpoint")
    if parsed.username or parsed.password:
        raise AutonomousAIError("Autonomous AI provider URL must not contain embedded credentials")
    if parsed.query or parsed.fragment:
        raise AutonomousAIError("Autonomous AI provider URL must not contain a query or fragment")


def _normalized_provider_endpoint(base_url: str) -> tuple[str, str, int | None, str] | None:
    value = base_url.strip().rstrip("/")
    if not value:
        return None
    try:
        _validate_provider_base_url(value)
        parsed = urlsplit(value)
        port = parsed.port
    except (AutonomousAIError, ValueError):
        return None
    if port is None:
        port = 443 if parsed.scheme.lower() == "https" else 80
    path = parsed.path.rstrip("/")
    return parsed.scheme.lower(), (parsed.hostname or "").lower(), port, path


def provider_endpoints_independent(primary_base_url: str, secondary_base_url: str) -> bool:
    primary = _normalized_provider_endpoint(primary_base_url)
    secondary = _normalized_provider_endpoint(secondary_base_url)
    return bool(primary and secondary and primary != secondary)


def _validate_provider_request(user_text: str, image_data_urls: list[str]) -> None:
    if len(image_data_urls) > MAX_PROVIDER_IMAGE_COUNT:
        raise AutonomousAIError("Autonomous AI request contained too many evidence frames")
    total_bytes = len(user_text.encode("utf-8"))
    for image in image_data_urls:
        if not image.startswith("data:image/jpeg;base64,"):
            raise AutonomousAIError("Autonomous AI evidence images must be inline JPEG data URLs")
        total_bytes += len(image.encode("ascii"))
        if total_bytes > MAX_PROVIDER_REQUEST_BYTES:
            raise AutonomousAIError("Autonomous AI request exceeded the evidence payload safety limit")


class AutonomousAIClient:
    """Minimal hardened OpenAI-compatible JSON client with provider diversity support.

    The contract compiler and primary VLM use the primary endpoint. A distinctly named secondary
    VLM can be routed to a separate secondary endpoint so one provider outage, policy defect or
    correlated model behavior cannot masquerade as independent semantic consensus.

    Redirects are disabled so an upstream endpoint cannot silently redirect evidence or bearer
    credentials to another host. Provider response bodies and request payloads are bounded,
    transient failures get only a few short retries, provider response text is never copied into
    raised errors, and structured precise-location fields are stripped before provider egress.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.autonomous_ai_base_url.rstrip("/")
        self.api_key = settings.autonomous_ai_api_key.strip()
        self.secondary_base_url = settings.autonomous_secondary_ai_base_url.rstrip("/")
        self.secondary_api_key = settings.autonomous_secondary_ai_api_key.strip()
        self.primary_model = settings.autonomous_vlm_model.strip()
        self.secondary_model = settings.autonomous_secondary_vlm_model.strip()
        self.contract_model = settings.autonomous_contract_model.strip()
        self.timeout = settings.autonomous_ai_timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    @property
    def independent_secondary_configured(self) -> bool:
        return bool(
            self.secondary_model
            and self.secondary_model != self.primary_model
            and self.secondary_model != self.contract_model
            and provider_endpoints_independent(self.base_url, self.secondary_base_url)
        )

    def _provider_for_model(self, model: str) -> tuple[str, str]:
        selected = model.strip()
        if selected and selected == self.secondary_model and selected != self.contract_model:
            if not self.secondary_base_url:
                raise AutonomousAIError("Secondary autonomous AI provider is not configured")
            return self.secondary_base_url, self.secondary_api_key
        return self.base_url, self.api_key

    def _request(
        self,
        client: httpx.Client,
        endpoint: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(1, MAX_PROVIDER_ATTEMPTS + 1):
            try:
                response = client.post(endpoint, headers=headers, json=payload)
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt == MAX_PROVIDER_ATTEMPTS:
                    break
                time.sleep(_retry_delay_seconds(attempt))
                continue

            if _should_retry_status(response.status_code) and attempt < MAX_PROVIDER_ATTEMPTS:
                time.sleep(_retry_delay_seconds(attempt))
                continue
            return response

        raise AutonomousAIError(
            f"Autonomous AI provider request failed: {type(last_error).__name__ if last_error else 'transport error'}"
        ) from last_error

    def complete_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_text: str,
        image_data_urls: list[str] | None = None,
    ) -> AIJsonResponse:
        if not self.configured:
            raise AutonomousAIError("Autonomous AI provider is not configured")
        if not model.strip():
            raise AutonomousAIError("Autonomous AI model is not configured")

        provider_base_url, provider_api_key = self._provider_for_model(model)
        _validate_provider_base_url(provider_base_url)
        minimized_user_text = _minimize_provider_user_text(user_text)
        images = list(image_data_urls or [])
        _validate_provider_request(minimized_user_text, images)
        content: list[dict[str, Any]] = [{"type": "text", "text": minimized_user_text}]
        for image in images:
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": image, "detail": "high"},
                }
            )

        payload: dict[str, Any] = {
            "model": model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            "response_format": {"type": "json_object"},
        }
        headers = {"Content-Type": "application/json"}
        if provider_api_key:
            headers["Authorization"] = f"Bearer {provider_api_key}"

        endpoint = f"{provider_base_url}/chat/completions"
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=False) as client:
                response = self._request(client, endpoint, headers, payload)
                if response.status_code in {400, 422}:
                    # Some OpenAI-compatible providers do not implement response_format.
                    fallback_payload = dict(payload)
                    fallback_payload.pop("response_format", None)
                    response = self._request(client, endpoint, headers, fallback_payload)
                _validate_response_size(response)
                response.raise_for_status()
                body = response.json()
        except AutonomousAIError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise AutonomousAIError(f"Autonomous AI provider request failed: {type(exc).__name__}") from exc

        if not isinstance(body, dict):
            raise AutonomousAIError("Provider response JSON must be an object")
        text = _message_text(body)
        parsed = _extract_json(text)
        return AIJsonResponse(
            payload=parsed,
            raw_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            model=model,
        )
