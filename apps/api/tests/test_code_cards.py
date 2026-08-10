import asyncio
from types import SimpleNamespace

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
