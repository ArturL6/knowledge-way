import asyncio
from types import SimpleNamespace

import pytest

from app import code_cards


class FakeResponse:
    def __init__(self, status_code, headers=None):
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_code_cards_retry_vertex_rate_limit_and_honor_retry_after(monkeypatch):
    responses = [FakeResponse(429, {"Retry-After": "2"}), FakeResponse(200)]
    delays = []
    original_sleep = asyncio.sleep

    async def fake_post(token, payload):
        return responses.pop(0)

    monkeypatch.setattr(code_cards, "_post", fake_post)
    monkeypatch.setattr(
        code_cards.asyncio,
        "sleep",
        lambda seconds: delays.append(seconds) or original_sleep(0),
    )

    assert asyncio.run(code_cards._post_with_rate_limit_retries("token", {})).status_code == 200
    assert delays == [2.0]


def test_code_cards_rate_limit_stops_after_bounded_retries(monkeypatch):
    calls = 0
    original_sleep = asyncio.sleep

    async def fake_post(token, payload):
        nonlocal calls
        calls += 1
        return FakeResponse(429)

    monkeypatch.setattr(code_cards, "_post", fake_post)
    monkeypatch.setattr(code_cards.asyncio, "sleep", lambda seconds: original_sleep(0))

    try:
        asyncio.run(code_cards._post_with_rate_limit_retries("token", {}))
    except RuntimeError as error:
        assert str(error) == "HTTP 429"
    else:
        raise AssertionError("expected final 429 to be raised")
    assert calls == code_cards.MAX_RATE_LIMIT_RETRIES


def test_code_card_batch_limits_in_flight_requests(monkeypatch):
    active = 0
    peak = 0

    async def fake_post_with_retries(token, payload):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return FakeResponse(200)

    monkeypatch.setattr(code_cards, "_post_with_rate_limit_retries", fake_post_with_retries)
    responses = asyncio.run(code_cards._post_batch("token", [{"id": i} for i in range(8)], 3))
    assert len(responses) == 8
    assert peak == 3


def test_code_card_prompt_bounds_lists_and_requests_json_only():
    prompt = code_cards._prompt(
        SimpleNamespace(name="repo"),
        SimpleNamespace(path="x.py"),
        SimpleNamespace(source_text="def f(): pass", language="python", qualified_name="f", symbol_type="function", signature="()"),
        ["one"],
        ["two"],
    )
    assert "every array has at most 5 terse items" in prompt
    assert "Return JSON only" in prompt


def test_code_card_generation_contract_uses_native_json_schema_and_safe_output_budget():
    config = code_cards._generation_config()
    # 512 caused a real provider response to end before the closing JSON delimiter.
    # The contract allows structured fields whose valid compact serialization exceeds it.
    assert config["maxOutputTokens"] == 1024
    assert config["responseMimeType"] == "application/json"
    assert config["responseSchema"]["type"] == "OBJECT"
    assert set(config["responseSchema"]["required"]) == {
        "summary", "inputs", "outputs", "side_effects", "dependencies", "keywords", "confidence"
    }


def test_code_card_details_rejects_truncated_or_overlong_model_output():
    assert code_cards._parse_details('{"summary":"ok","inputs":[],"outputs":[],"side_effects":[],"dependencies":[],"keywords":[],"confidence":"high"}')["summary"] == "ok"
    try:
        code_cards._parse_details('{"summary":"truncated"')
    except ValueError:
        pass
    else:
        raise AssertionError("truncated output must not be accepted")


def test_code_card_details_accepts_compact_long_identifier_fact():
    item = "Emits PydanticJsonSchema warning when merging json_schema_extra types"
    details = code_cards._parse_details(
        '{"summary":"ok","inputs":[],"outputs":[],"side_effects":['
        '"Emits PydanticJsonSchema warning when merging json_schema_extra types"'
        '],"dependencies":[],"keywords":[],"confidence":"high"}'
    )
    assert details["side_effects"] == [item]


def test_openrouter_payload_disables_reasoning_and_requests_a_strict_schema(monkeypatch):
    monkeypatch.setattr(code_cards.settings, "code_card_provider", "openrouter")
    monkeypatch.setattr(code_cards.settings, "openrouter_card_model", "vendor/model")
    payload = code_cards._build_payload("the prompt")

    # A reasoning model spends max_tokens deliberating and returns content=None, which is how a
    # 25-symbol run produced zero cards twice before this was set.
    assert payload["reasoning"] == {"enabled": False}
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert payload["model"] == "vendor/model"
    assert [m["content"] for m in payload["messages"]] == ["the prompt"]


def test_openrouter_retry_payload_states_what_was_rejected(monkeypatch):
    monkeypatch.setattr(code_cards.settings, "code_card_provider", "openrouter")
    payload = code_cards._build_payload("the prompt", "summary: field required")

    assert len(payload["messages"]) == 2
    assert "summary: field required" in payload["messages"][1]["content"]


def test_null_content_becomes_a_validation_failure_not_an_attribute_error(monkeypatch):
    monkeypatch.setattr(code_cards.settings, "code_card_provider", "openrouter")
    body = {"choices": [{"message": {"content": None}}], "usage": {"prompt_tokens": 7}}

    text, input_tokens, output_tokens = code_cards._extract_card(body)

    assert text == ""
    assert (input_tokens, output_tokens) == (7, None)
    with pytest.raises(ValueError):
        code_cards._parse_details(text)
