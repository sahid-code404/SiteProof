import json

import httpx
import pytest

from app.services.autonomous_ai_client import (
    MAX_PROVIDER_RESPONSE_BYTES,
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
