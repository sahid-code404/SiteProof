import json

import httpx
import pytest

import app.services.autonomous_ai_client as ai_module
from app.services.autonomous_ai_client import (
    MAX_PROVIDER_RESPONSE_BYTES,
    AutonomousAIClient,
    AutonomousAIError,
    _extract_json,
    _message_text,
    _retry_delay_seconds,
    _should_retry_status,
    _validate_response_size,
)


def test_extract_json_accepts_plain_and_fenced_objects():
    assert _extract_json('{"ok": true}') == {"ok": True}
    assert _extract_json('```json\n{"ok": true}\n```') == {"ok": True}


def test_extract_json_rejects_non_object_payload():
    with pytest.raises(AutonomousAIError, match="must be an object"):
        _extract_json('[1, 2, 3]')


def test_message_text_supports_openai_multimodal_text_parts():
    body = {
        "choices": [
            {
                "message": {
                    "content": [
                        {"type": "text", "text": "{\"part\":"},
                        {"type": "text", "text": "true}"},
                    ]
                }
            }
        ]
    }
    assert json.loads(_message_text(body)) == {"part": True}


def test_provider_response_size_is_bounded_by_declared_length():
    response = httpx.Response(
        200,
        headers={"content-length": str(MAX_PROVIDER_RESPONSE_BYTES + 1)},
        content=b"{}",
    )
    with pytest.raises(AutonomousAIError, match="safety limit"):
        _validate_response_size(response)


def test_provider_response_size_is_bounded_by_actual_body():
    response = httpx.Response(200, content=b"x" * (MAX_PROVIDER_RESPONSE_BYTES + 1))
    with pytest.raises(AutonomousAIError, match="safety limit"):
        _validate_response_size(response)


def test_retry_policy_is_limited_to_transient_status_codes():
    assert _should_retry_status(429) is True
    assert _should_retry_status(503) is True
    assert _should_retry_status(401) is False
    assert _should_retry_status(404) is False
    assert _retry_delay_seconds(1) == pytest.approx(0.25)
    assert _retry_delay_seconds(2) == pytest.approx(0.50)


class _FakeHttpClient:
    def __init__(self, responses: list[httpx.Response]):
        self.responses = list(responses)
        self.payloads: list[dict] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, endpoint: str, *, headers: dict, json: dict):
        del headers
        self.payloads.append(json)
        response = self.responses.pop(0)
        response.request = httpx.Request("POST", endpoint)
        return response


def _provider_success(content: str = '{"ok": true}') -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": content}}]},
    )


def _configured_client() -> AutonomousAIClient:
    client = AutonomousAIClient()
    client.base_url = "https://provider.example"
    client.api_key = ""
    client.timeout = 1.0
    return client


def test_complete_json_retries_transient_provider_failure(monkeypatch):
    fake = _FakeHttpClient([httpx.Response(503, json={"error": "busy"}), _provider_success()])
    monkeypatch.setattr(ai_module.httpx, "Client", lambda **_: fake)
    monkeypatch.setattr(ai_module.time, "sleep", lambda _: None)

    result = _configured_client().complete_json(
        model="vlm-test",
        system_prompt="system",
        user_text="user",
    )

    assert result.payload == {"ok": True}
    assert len(fake.payloads) == 2
    assert all("response_format" in payload for payload in fake.payloads)


def test_complete_json_falls_back_when_provider_rejects_response_format(monkeypatch):
    fake = _FakeHttpClient([httpx.Response(400, json={"error": "unsupported"}), _provider_success()])
    monkeypatch.setattr(ai_module.httpx, "Client", lambda **_: fake)

    result = _configured_client().complete_json(
        model="vlm-test",
        system_prompt="system",
        user_text="user",
    )

    assert result.payload == {"ok": True}
    assert "response_format" in fake.payloads[0]
    assert "response_format" not in fake.payloads[1]
