from app.config import settings
from app.providers import embedding_provider, semantic_capability
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


def test_hybrid_fusion_is_deterministic():
    first = {"type": "chunk", "file_id": "a", "start_line": 1, "end_line": 2, "score": .2}
    second = {"type": "chunk", "file_id": "b", "start_line": 1, "end_line": 2, "score": .9}
    assert [item["file_id"] for item in _fuse([[first, second], [first]], 2)] == ["a", "b"]
