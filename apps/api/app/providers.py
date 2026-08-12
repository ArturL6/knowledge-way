import asyncio
import hashlib
import json
import math
from typing import Protocol

import httpx

from app.config import settings
from app.db import SessionLocal
from app.pilot_audit import (admit_vertex_embedding, record_vertex_embedding_failure,
                             record_vertex_embedding_success)


# Floor for the halving retry below, so a genuinely un-embeddable input raises instead of looping.
MIN_EMBEDDING_INPUT_CHARACTERS = 500


class EmbeddingProvider(Protocol):
    model: str

    async def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


class ChatProvider(Protocol):
    async def answer(self, question: str, context: str) -> str: ...


class RerankProvider(Protocol):
    model: str

    async def rerank(self, query: str, documents: list[str]) -> list[float]: ...


class CohereRerankProvider:
    """Cohere v2 rerank adapter; only called for user-enabled, bounded candidate sets."""
    def __init__(self, api_key: str, model: str):
        self.api_key, self.model = api_key, model

    async def rerank(self, query: str, documents: list[str]) -> list[float]:
        if not documents:
            return []
        payload = {"model": self.model, "query": query, "documents": documents, "top_n": len(documents)}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post("https://api.cohere.com/v2/rerank", headers={"Authorization": f"Bearer {self.api_key}"}, json=payload)
        response.raise_for_status()
        scores = [0.0] * len(documents)
        for item in response.json().get("results", []):
            index, score = item.get("index"), item.get("relevance_score")
            if isinstance(index, int) and 0 <= index < len(scores) and isinstance(score, (int, float)):
                scores[index] = float(score)
        return scores


class OpenRouterEmbeddingProvider:
    """OpenAI-compatible OpenRouter embeddings adapter."""

    def __init__(self, api_key: str, model: str, base_url: str):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        from openai import AsyncOpenAI, BadRequestError

        client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        clamped = [clamp_embedding_input(text) for text in texts]
        try:
            response = await client.embeddings.create(model=self.model, input=clamped)
        except BadRequestError:
            # An oversized member used to fail the whole batch and abort the entire index run.
            if len(texts) > 1:
                # Isolate the offender rather than guess which one it was. Ordering is preserved.
                midpoint = len(texts) // 2
                return await self.embed_texts(texts[:midpoint]) + await self.embed_texts(texts[midpoint:])
            # A lone input the provider still rejects: the character budget is only a proxy for a
            # token limit, and the true ratio varies with how densely the source tokenizes. Halve
            # and retry so the limit is discovered instead of assumed. Bounded by the text length.
            shortened = clamped[0][: len(clamped[0]) // 2]
            if len(shortened) < MIN_EMBEDDING_INPUT_CHARACTERS:
                raise
            return await self.embed_texts([shortened])
        embeddings = [list(item.embedding) for item in response.data]
        return _validate_embeddings(embeddings, len(texts))


def clamp_embedding_input(text: str) -> str:
    """Bound one embedding input to the provider's per-input token ceiling.

    ponytail: characters, not tokens, so no tokenizer dependency and no per-model table. The
    default is deliberately conservative for source code, which tokenizes far worse than prose.
    A clamped chunk loses its tail from the vector while `source_text` keeps the full body, so
    citations stay complete and only recall on the tail suffers. Swap in a real tokenizer if
    that recall loss ever shows up in evaluation.
    """
    budget = settings.embedding_max_input_characters
    if budget <= 0 or len(text) <= budget:
        return text
    return text[:budget]


class VertexEmbeddingProvider:
    """Vertex AI text embeddings using Application Default Credentials (ADC)."""

    def __init__(self, project_id: str, location: str, model: str, output_dimensions: int):
        self.project_id = project_id
        self.location = location
        self.vertex_model = model
        self.model = f"vertex:{model}"
        self.output_dimensions = output_dimensions
        self.endpoint = (
            f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}"
            f"/locations/{location}/publishers/google/models/{model}:predict"
        )

    async def _access_token(self) -> str:
        return await asyncio.to_thread(self._refresh_credentials)

    @staticmethod
    def _refresh_credentials() -> str:
        import google.auth
        from google.auth.transport.requests import Request

        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        credentials.refresh(Request())
        if not credentials.token:
            raise RuntimeError("Google ADC did not return an access token")
        return credentials.token

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if not settings.vertex_pilot_enabled or not settings.vertex_pilot_ledger_id:
            raise RuntimeError("Vertex embedding blocked: an enabled persistent pilot audit ledger is required")
        # Validate the persisted budget and price provenance before refreshing ADC or opening a
        # network connection. Configuration alone can never authorize a paid call.
        db = SessionLocal()
        try:
            ledger = admit_vertex_embedding(db, settings.vertex_pilot_ledger_id, len(texts))
            if ledger.configuration["embedding_model"] != self.vertex_model:
                raise RuntimeError("Vertex embedding blocked: configured model differs from pilot audit ledger")
            token = await self._access_token()
            payload = {
                "instances": [{"content": text} for text in texts],
                "parameters": {"outputDimensionality": self.output_dimensions},
            }
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    # The bounded pilot deliberately makes one provider request per admitted batch.
                    # Retrying or recursively splitting after a provider-side failure would create
                    # unledgered extra paid-call attempts and violate the pilot contract.
                    response = await client.post(
                        self.endpoint,
                        headers={"Authorization": f"Bearer {token}"},
                        json=payload,
                    )
                if response.status_code == 400:
                    raise RuntimeError(
                        f"Vertex rejected embedding input (inputs={len(texts)}, "
                        f"characters={sum(len(text) for text in texts)}): {response.text}"
                    )
                response.raise_for_status()
                try:
                    embeddings = [prediction["embeddings"]["values"] for prediction in response.json()["predictions"]]
                except (KeyError, TypeError) as exc:
                    raise RuntimeError("Vertex AI returned an invalid embedding response") from exc
                embeddings = _validate_embeddings(embeddings, len(texts))
            except Exception as exc:
                record_vertex_embedding_failure(
                    db, ledger, model=self.vertex_model, texts=texts,
                    details={"error_type": type(exc).__name__, "message": str(exc)[:500],
                             "output_dimensions": self.output_dimensions},
                )
                raise
            usage = response.json().get("metadata", {}).get("usageMetadata", {})
            input_tokens = usage.get("promptTokenCount")
            if not isinstance(input_tokens, int):
                input_tokens = None
            record_vertex_embedding_success(
                db, ledger, model=self.vertex_model, texts=texts, input_tokens=input_tokens,
                cost_usd_micros=ledger.configuration["embedding_cost_usd_micros_per_document"] * len(texts),
                details={"output_dimensions": self.output_dimensions},
            )
            return embeddings
        finally:
            db.close()


def _validate_embeddings(embeddings: list[list[float]], expected_count: int) -> list[list[float]]:
    if len(embeddings) != expected_count or not all(embeddings):
        raise RuntimeError("embedding provider returned an incomplete embedding batch")
    dimensions = len(embeddings[0])
    if any(len(vector) != dimensions for vector in embeddings):
        raise RuntimeError("embedding provider returned inconsistent vector dimensions")
    return embeddings


def embedding_provider() -> EmbeddingProvider | None:
    """Return an enabled provider, never attempting a request while disabled/unconfigured."""
    provider = settings.embedding_provider.lower()
    if provider == "openrouter" and settings.openrouter_api_key:
        return OpenRouterEmbeddingProvider(
            settings.openrouter_api_key,
            settings.openrouter_embedding_model,
            settings.openrouter_base_url,
        )
    # Vertex is a paid pilot provider.  Do not advertise it as a usable semantic
    # capability (or let indexing enter its path) until the explicit ledger gate
    # is enabled; credentials and a project alone are deliberately insufficient.
    if (provider == "vertex" and settings.vertex_project_id and
            settings.vertex_pilot_enabled and settings.vertex_pilot_ledger_id):
        return VertexEmbeddingProvider(
            settings.vertex_project_id,
            settings.vertex_location,
            settings.vertex_embedding_model,
            settings.vertex_embedding_dimensions,
        )
    return None


def rerank_provider() -> RerankProvider | None:
    provider = settings.rerank_provider.lower()
    if provider == "cohere" and settings.cohere_api_key and settings.rerank_model:
        return CohereRerankProvider(settings.cohere_api_key, settings.rerank_model)
    return None


def rerank_capability() -> dict[str, object]:
    provider = settings.rerank_provider.lower()
    active = rerank_provider()
    return {"enabled": active is not None, "provider": provider, "model": active.model if active else settings.rerank_model,
            "state": "enabled" if active else ("disabled" if provider == "none" else "unconfigured")}


def semantic_capability() -> dict[str, object]:
    provider = settings.embedding_provider.lower()
    enabled = embedding_provider() is not None
    if enabled:
        state = "enabled"
    elif provider == "none":
        state = "disabled"
    elif provider == "vertex" and settings.vertex_project_id:
        state = "pilot_guarded"
    elif provider in {"openrouter", "vertex"}:
        state = "unconfigured"
    else:
        state = "unsupported_provider"
    active_provider = embedding_provider()
    return {
        "state": state,
        "enabled": enabled,
        "provider": provider,
        "model": active_provider.model if active_provider else None,
        "reranking": rerank_capability(),
    }


def deterministic_embedding(text: str, dimensions: int = 16) -> list[float]:
    """Test-only deterministic vector helper; never used by production indexing."""
    values = [0.0] * dimensions
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode()).digest()
        values[digest[0] % dimensions] += 1 if digest[1] % 2 else -1
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]
