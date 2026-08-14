from app.config import Settings, settings
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


def test_owner_selected_provider_defaults_are_vertex():
    fields = Settings.model_fields
    assert fields["embedding_provider"].default == "vertex"
    assert fields["vertex_embedding_model"].default == "text-embedding-005"
    assert fields["vertex_embedding_dimensions"].default == 768
    assert fields["code_card_provider"].default == "vertex"
    assert fields["vertex_gemini_model"].default == "gemini-3.5-flash-lite"
    assert fields["rerank_provider"].default == "none"


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


def test_vertex_retries_a_rate_limited_batch(monkeypatch):
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
        responses = [
            FakeResponse(429, {}, {"Retry-After": "0"}),
            FakeResponse(200, {"predictions": [{"embeddings": {"values": [0.1, 0.2]}}]}),
        ]
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs): return self.responses.pop(0)

    delays = []
    original_sleep = asyncio.sleep
    provider = VertexEmbeddingProvider("project", "us-central1", "text-embedding-005", 2)
    monkeypatch.setattr(provider, "_access_token", lambda: original_sleep(0, result="token"))
    monkeypatch.setattr("app.providers.httpx.AsyncClient", lambda **kwargs: FakeClient())
    monkeypatch.setattr("app.providers.asyncio.sleep", lambda seconds: delays.append(seconds) or original_sleep(0))

    assert asyncio.run(provider.embed_texts(["test"])) == [[0.1, 0.2]]
    assert delays == [1.0]


def test_vertex_splits_a_payload_vertex_rejects(monkeypatch):
    class FakeResponse:
        def __init__(self, status_code, body):
            self.status_code, self._body, self.headers = status_code, body, {}
        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError("bad request")
        def json(self): return self._body

    class FakeClient:
        calls = []
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, *args, **kwargs):
            texts = [item["content"] for item in kwargs["json"]["instances"]]
            self.calls.append(texts)
            if len(texts) == 2:
                return FakeResponse(400, {})
            return FakeResponse(200, {"predictions": [{"embeddings": {"values": [float(len(text))]}} for text in texts]})

    provider = VertexEmbeddingProvider("project", "us-central1", "text-embedding-005", 1)
    original_sleep = asyncio.sleep
    monkeypatch.setattr(provider, "_access_token", lambda: original_sleep(0, result="token"))
    fake = FakeClient()
    monkeypatch.setattr("app.providers.httpx.AsyncClient", lambda **kwargs: fake)

    assert asyncio.run(provider.embed_texts(["first", "second"])) == [[5.0], [6.0]]
    assert fake.calls == [["first", "second"], ["first"], ["second"]]


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
