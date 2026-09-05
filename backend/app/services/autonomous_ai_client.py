from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings


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


class AutonomousAIClient:
    """Minimal OpenAI-compatible JSON client.

    SiteProof intentionally depends on an interface rather than a specific vendor. Any provider
    exposing an OpenAI-compatible ``/chat/completions`` endpoint can be used, including a private
    on-prem model server. Evidence is sent only when autonomous verification is explicitly enabled.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.autonomous_ai_base_url.rstrip("/")
        self.api_key = settings.autonomous_ai_api_key.strip()
        self.timeout = settings.autonomous_ai_timeout_seconds

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

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

        content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
        for image in image_data_urls or []:
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
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        endpoint = f"{self.base_url}/chat/completions"
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=False) as client:
                response = client.post(endpoint, headers=headers, json=payload)
                if response.status_code in {400, 404, 422}:
                    # Some OpenAI-compatible providers do not implement response_format.
                    payload.pop("response_format", None)
                    response = client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()
                body = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AutonomousAIError(f"Autonomous AI provider request failed: {type(exc).__name__}") from exc

        text = _message_text(body)
        parsed = _extract_json(text)
        return AIJsonResponse(
            payload=parsed,
            raw_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            model=model,
        )
