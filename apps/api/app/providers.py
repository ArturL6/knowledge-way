import hashlib
import math
from typing import Protocol

from app.config import settings


class EmbeddingProvider(Protocol):
    model: str

    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class ChatProvider(Protocol):
    async def answer(self, question: str, context: str) -> str: ...


class OpenRouterEmbeddingProvider:
    """OpenAI-compatible OpenRouter embeddings adapter.

    It is instantiated only after both the explicit provider setting and API key are set.
    """

    def __init__(self, api_key: str, model: str, base_url: str):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        response = await client.embeddings.create(model=self.model, input=texts)
        embeddings = [list(item.embedding) for item in response.data]
        if len(embeddings) != len(texts) or not all(embeddings):
            raise RuntimeError("embedding provider returned an incomplete embedding batch")
        dimensions = len(embeddings[0])
        if any(len(vector) != dimensions for vector in embeddings):
            raise RuntimeError("embedding provider returned inconsistent vector dimensions")
        return embeddings


def embedding_provider() -> EmbeddingProvider | None:
    """Return an enabled provider, never attempting a request while disabled/unconfigured."""
    if settings.embedding_provider.lower() == "openrouter" and settings.openrouter_api_key:
        return OpenRouterEmbeddingProvider(
            settings.openrouter_api_key,
            settings.openrouter_embedding_model,
            settings.openrouter_base_url,
        )
    return None


def semantic_capability() -> dict[str, object]:
    provider = settings.embedding_provider.lower()
    enabled = provider == "openrouter" and bool(settings.openrouter_api_key)
    if enabled:
        state = "enabled"
    elif provider == "none":
        state = "disabled"
    elif provider == "openrouter":
        state = "unconfigured"
    else:
        state = "unsupported_provider"
    return {
        "state": state,
        "enabled": enabled,
        "provider": provider,
        "model": settings.openrouter_embedding_model if provider == "openrouter" else None,
        "reranking": {"enabled": False, "provider": settings.rerank_provider, "model": settings.rerank_model},
    }


def deterministic_embedding(text: str, dimensions: int = 16) -> list[float]:
    """Test-only deterministic vector helper; never used by production indexing."""
    values = [0.0] * dimensions
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode()).digest()
        values[digest[0] % dimensions] += 1 if digest[1] % 2 else -1
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]
