from app.config import settings
import pytest
from app.providers import (OpenRouterEmbeddingProvider, VertexEmbeddingProvider,
                           clamp_embedding_input, embedding_provider, semantic_capability)
import asyncio
from app.search import _fuse


def test_semantic_provider_is_disabled_without_explicit_openrouter_key(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "none")
    monkeypatch.setattr(settings, "openrouter_api_key", None)
    assert embedding_provider() is None
    assert semantic_capability()["state"] == "disabled"


def test_openrouter_without_key_never_creates_provider(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "openrouter")
    monkeypatch.setattr(settings, "openrouter_api_key", None)
    assert embedding_provider() is None
    assert semantic_capability()["state"] == "unconfigured"


def test_vertex_provider_uses_explicit_project_configuration(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "vertex")
    monkeypatch.setattr(settings, "vertex_project_id", "ai-tinker-lab")
    monkeypatch.setattr(settings, "vertex_location", "us-central1")
    monkeypatch.setattr(settings, "vertex_embedding_model", "text-embedding-005")

    provider = embedding_provider()

    assert isinstance(provider, VertexEmbeddingProvider)
    assert provider.model == "vertex:text-embedding-005"
    assert semantic_capability() == {
        "state": "enabled",
        "enabled": True,
        "provider": "vertex",
        "model": "vertex:text-embedding-005",
        "reranking": {"enabled": False, "provider": "none", "model": None, "state": "disabled"},
    }


def test_vertex_without_project_never_creates_provider(monkeypatch):
    monkeypatch.setattr(settings, "embedding_provider", "vertex")
    monkeypatch.setattr(settings, "vertex_project_id", None)
    assert embedding_provider() is None
    assert semantic_capability()["state"] == "unconfigured"


def test_vertex_embedding_is_hard_blocked_without_enabled_audit_ledger(monkeypatch):
    monkeypatch.setattr(settings, "vertex_pilot_enabled", False)
    monkeypatch.setattr(settings, "vertex_pilot_ledger_id", None)
    provider = VertexEmbeddingProvider("project", "us-central1", "text-embedding-005", 2)
    with pytest.raises(RuntimeError, match="persistent pilot audit ledger"):
        asyncio.run(provider.embed_texts(["bounded document"]))


def test_vertex_does_not_retry_a_rate_limited_batch(monkeypatch):
    class FakeResponse:
        def __init__(self, status_code, body, headers=None):
            self.status_code = status_code
            self._body = body
            self.headers = headers or {}
        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError("rate limited")
        def json(self): return self._body

    class FakeClient:
        responses = [FakeResponse(429, {}, {"Retry-After": "0"})]
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs): return self.responses.pop(0)

    original_sleep = asyncio.sleep
    provider = VertexEmbeddingProvider("project", "us-central1", "text-embedding-005", 2)
    monkeypatch.setattr(settings, "vertex_pilot_enabled", True)
    monkeypatch.setattr(settings, "vertex_pilot_ledger_id", "ledger")
    monkeypatch.setattr("app.providers.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.providers.admit_vertex_embedding", lambda *args: type("Ledger", (), {"configuration": {"embedding_model": "text-embedding-005", "embedding_cost_usd_micros_per_document": 0}})())
    monkeypatch.setattr("app.providers.record_vertex_embedding_success", lambda *args, **kwargs: None)
    failed = []
    monkeypatch.setattr("app.providers.record_vertex_embedding_failure", lambda *args, **kwargs: failed.append(kwargs))
    monkeypatch.setattr(provider, "_access_token", lambda: original_sleep(0, result="token"))
    monkeypatch.setattr("app.providers.httpx.AsyncClient", lambda **kwargs: FakeClient())
    with pytest.raises(RuntimeError, match="rate limited"):
        asyncio.run(provider.embed_texts(["test"]))
    assert FakeClient.responses == []
    assert len(failed) == 1
    assert failed[0]["details"]["error_type"] == "RuntimeError"


def test_vertex_does_not_split_a_payload_vertex_rejects(monkeypatch):
    class FakeResponse:
        def __init__(self, status_code, body):
            self.status_code, self._body, self.headers = status_code, body, {}
        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError("bad request")
        def json(self): return self._body
        @property
        def text(self): return "invalid payload"

    class FakeClient:
        calls = []
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs):
            texts = [item["content"] for item in kwargs["json"]["instances"]]
            self.calls.append(texts)
            return FakeResponse(400, {})

    provider = VertexEmbeddingProvider("project", "us-central1", "text-embedding-005", 1)
    monkeypatch.setattr(settings, "vertex_pilot_enabled", True)
    monkeypatch.setattr(settings, "vertex_pilot_ledger_id", "ledger")
    monkeypatch.setattr("app.providers.SessionLocal", lambda: type("DB", (), {"close": lambda self: None})())
    monkeypatch.setattr("app.providers.admit_vertex_embedding", lambda *args: type("Ledger", (), {"configuration": {"embedding_model": "text-embedding-005", "embedding_cost_usd_micros_per_document": 0}})())
    monkeypatch.setattr("app.providers.record_vertex_embedding_success", lambda *args, **kwargs: None)
    failed = []
    monkeypatch.setattr("app.providers.record_vertex_embedding_failure", lambda *args, **kwargs: failed.append(kwargs))
    original_sleep = asyncio.sleep
    monkeypatch.setattr(provider, "_access_token", lambda: original_sleep(0, result="token"))
    fake = FakeClient()
    monkeypatch.setattr("app.providers.httpx.AsyncClient", lambda **kwargs: fake)

    with pytest.raises(RuntimeError, match="Vertex rejected embedding input"):
        asyncio.run(provider.embed_texts(["first", "second"]))
    assert fake.calls == [["first", "second"]]
    assert len(failed) == 1
    assert failed[0]["details"]["error_type"] == "RuntimeError"


def test_hybrid_fusion_is_deterministic():
    first = {"type": "chunk", "result_id": "a", "file_id": "a", "start_line": 1, "end_line": 2, "score": .2}
    second = {"type": "chunk", "result_id": "b", "file_id": "b", "start_line": 1, "end_line": 2, "score": .9}
    assert [item["file_id"] for item in _fuse([[first, second], [first]], 2)] == ["a", "b"]


class _FakeOpenRouter:
    """Rejects any input longer than `ceiling` characters, the way the real endpoint rejects any
    input over its token limit. Records every batch so ordering can be asserted."""

    def __init__(self, ceiling):
        self.ceiling, self.batches = ceiling, []
        self.embeddings = self

    def __call__(self, **kwargs):
        return self

    async def create(self, model, input):
        from openai import BadRequestError

        self.batches.append(list(input))
        if any(len(text) > self.ceiling for text in input):
            raise BadRequestError.__new__(BadRequestError)
        return type("R", (), {"data": [type("E", (), {"embedding": [float(len(t))]})() for t in input]})()


def test_openrouter_clamps_each_input_to_the_configured_budget(monkeypatch):
    monkeypatch.setattr(settings, "embedding_max_input_characters", 10)
    assert clamp_embedding_input("x" * 25) == "x" * 10
    assert clamp_embedding_input("short") == "short"
    # A budget of zero disables clamping rather than truncating everything to nothing.
    monkeypatch.setattr(settings, "embedding_max_input_characters", 0)
    assert clamp_embedding_input("x" * 25) == "x" * 25


def test_openrouter_isolates_one_oversized_input_instead_of_failing_the_batch(monkeypatch):
    monkeypatch.setattr(settings, "embedding_max_input_characters", 0)
    # Sizes are above the 500-character halving floor, so this exercises the real path.
    fake = _FakeOpenRouter(ceiling=1000)
    monkeypatch.setattr("openai.AsyncOpenAI", fake)
    provider = OpenRouterEmbeddingProvider("key", "model", "https://example.invalid")
    oversized = "x" * 4000

    result = asyncio.run(provider.embed_texts(["aa", oversized, "bbb"]))

    # Halved 4000 -> 2000 -> 1000, and the innocents come back in their original positions.
    assert result == [[2.0], [1000.0], [3.0]]
    assert fake.batches[0] == ["aa", oversized, "bbb"]  # whole batch attempted first
    assert ["aa"] in fake.batches and ["bbb"] in fake.batches


def test_openrouter_raises_rather_than_looping_on_an_unembeddable_input(monkeypatch):
    monkeypatch.setattr(settings, "embedding_max_input_characters", 0)
    fake = _FakeOpenRouter(ceiling=0)  # rejects everything, so halving can never succeed
    monkeypatch.setattr("openai.AsyncOpenAI", fake)
    provider = OpenRouterEmbeddingProvider("key", "model", "https://example.invalid")

    with pytest.raises(Exception):
        asyncio.run(provider.embed_texts(["x" * 4000]))
    # Bounded by the 500-character floor: 4000 -> 2000 -> 1000 -> 500 -> stop.
    assert len(fake.batches) <= 5
