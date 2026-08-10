"""Versioned, citation-safe Gemini summaries for indexed code symbols."""
import asyncio
import hashlib
import json
import logging
import time
from datetime import datetime
from typing import Annotated, Literal
from email.utils import parsedate_to_datetime

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import CodeCard, File, IndexingJob, Repository, Symbol, SymbolEdge
from app.providers import VertexEmbeddingProvider

PROMPT_VERSION = "code-card-v2-bounded"
MAX_RATE_LIMIT_RETRIES = 8
logger = logging.getLogger(__name__)


class CodeCardDetails(BaseModel):
    """The only provider response shape accepted for a persisted code card."""
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1, max_length=600)
    inputs: list[Annotated[str, Field(min_length=1, max_length=120)]] = Field(max_length=5)
    outputs: list[Annotated[str, Field(min_length=1, max_length=120)]] = Field(max_length=5)
    side_effects: list[Annotated[str, Field(min_length=1, max_length=120)]] = Field(max_length=5)
    dependencies: list[Annotated[str, Field(min_length=1, max_length=120)]] = Field(max_length=5)
    keywords: list[Annotated[str, Field(min_length=1, max_length=120)]] = Field(max_length=5)
    confidence: Literal["high", "medium", "low"]


def _generation_config():
    return {
        "temperature": 0,
        "maxOutputTokens": 512,
        "thinkingConfig": {"thinkingBudget": 0},
        "responseMimeType": "application/json",
        "responseSchema": {
            "type": "OBJECT",
            "properties": {
                "summary": {"type": "STRING"},
                "inputs": {"type": "ARRAY", "items": {"type": "STRING", "maxLength": 120}, "maxItems": 5},
                "outputs": {"type": "ARRAY", "items": {"type": "STRING", "maxLength": 120}, "maxItems": 5},
                "side_effects": {"type": "ARRAY", "items": {"type": "STRING", "maxLength": 120}, "maxItems": 5},
                "dependencies": {"type": "ARRAY", "items": {"type": "STRING", "maxLength": 120}, "maxItems": 5},
                "keywords": {"type": "ARRAY", "items": {"type": "STRING", "maxLength": 120}, "maxItems": 5},
                "confidence": {"type": "STRING", "enum": ["high", "medium", "low"]},
            },
            "required": ["summary", "inputs", "outputs", "side_effects", "dependencies", "keywords", "confidence"],
        },
    }


def _parse_details(raw_text: str) -> dict:
    try:
        return CodeCardDetails.model_validate_json(raw_text).model_dump()
    except (ValidationError, ValueError) as error:
        raise ValueError(f"invalid code card JSON: {error}") from error


def _access_token():
    return VertexEmbeddingProvider._refresh_credentials()


def _endpoint():
    location = settings.vertex_gemini_location
    host = "aiplatform.googleapis.com" if location == "global" else f"{location}-aiplatform.googleapis.com"
    return f"https://{host}/v1/projects/{settings.vertex_project_id}/locations/{location}/publishers/google/models/{settings.vertex_gemini_model}:generateContent"


def _prompt(repo, file, symbol, calls, imports):
    source = symbol.source_text[:settings.code_card_max_source_characters]
    return f'''Create one concise, factual code card. Use ONLY the supplied code and static metadata. Do not claim behavior that is not evidenced. Return strict JSON with exactly: summary (string, <= 50 words), inputs (array of strings), outputs (array of strings), side_effects (array of strings), dependencies (array of strings), keywords (array of strings), confidence (high|medium|low).

Keep the card compact: every array has at most 5 terse items, each item is at most 8 words. Do not enumerate every parameter, field, call, import, or implementation detail; select only the most important evidenced facts. Use [] when no evidence exists. Return JSON only, with no Markdown or prose outside the object.

Repository: {repo.name}
Path: {file.path}
Language: {symbol.language}
Symbol: {symbol.qualified_name}
Kind: {symbol.symbol_type}
Signature: {symbol.signature or ''}
Static calls: {', '.join(sorted(calls)) or 'none observed'}
Static imports: {', '.join(sorted(imports)) or 'none observed'}
Code:\n{source}'''


def _retry_delay(response: httpx.Response, attempt: int) -> float:
    """Return a bounded delay, honoring either form of Retry-After when possible."""
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return max(1.0, float(retry_after))
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(retry_after)
                return max(1.0, (retry_at - datetime.now(retry_at.tzinfo)).total_seconds())
            except (TypeError, ValueError):
                pass
    return min(60.0, 2.0 ** (attempt + 1))


async def _post_with_rate_limit_retries(token, payload):
    """Post a card request, retrying transient Vertex quota throttling only."""
    started = time.monotonic()
    for attempt in range(MAX_RATE_LIMIT_RETRIES):
        response = await _post(token, payload)
        if response.status_code != 429:
            logger.warning("code_card_request status=%s attempts=%s elapsed_s=%.3f", response.status_code, attempt + 1, time.monotonic() - started)
            return response
        if attempt == MAX_RATE_LIMIT_RETRIES - 1:
            logger.warning("code_card_request status=429 attempts=%s elapsed_s=%.3f exhausted=true", attempt + 1, time.monotonic() - started)
            response.raise_for_status()
        delay = _retry_delay(response, attempt)
        logger.warning("code_card_request status=429 attempt=%s retry_delay_s=%.3f elapsed_s=%.3f", attempt + 1, delay, time.monotonic() - started)
        await asyncio.sleep(delay)
    raise AssertionError("unreachable")


async def _post_batch(token, payloads, concurrency: int):
    """Send a bounded batch concurrently while preserving input/output ordering."""
    semaphore = asyncio.Semaphore(concurrency)

    async def post_one(payload):
        async with semaphore:
            request_started = time.monotonic()
            response = await _post_with_rate_limit_retries(token, payload)
            return response, time.monotonic() - request_started

    return await asyncio.gather(*(post_one(payload) for payload in payloads))


def generate_code_cards(repo_id: str, limit: int | None = None):
    if not settings.code_cards_enabled or not settings.vertex_project_id:
        raise RuntimeError("Code cards are disabled or Vertex is unconfigured")
    db = SessionLocal()
    job = IndexingJob(repository_id=repo_id, kind="code_cards", status="running", started_at=datetime.utcnow(), progress={"phase": "selecting"})
    db.add(job); db.commit()
    try:
        repo = db.get(Repository, repo_id)
        if not repo:
            raise RuntimeError("Repository not found")
        symbols = db.scalars(select(Symbol).where(Symbol.repository_id == repo_id).order_by(Symbol.qualified_name)).all()
        cards = {c.symbol_id: c for c in db.scalars(select(CodeCard).where(CodeCard.repository_id == repo_id)).all()}
        targets = [s for s in symbols if cards.get(s.id) is None or cards[s.id].source_hash != hashlib.sha256(s.source_text.encode()).hexdigest()]
        if limit is not None:
            targets = targets[:limit]
        job.progress = {"phase": "generating", "total": len(targets), "completed": 0}; db.commit()
        edges = db.scalars(select(SymbolEdge).where(SymbolEdge.repository_id == repo_id)).all()
        # ADC tokens are valid for the job duration; refreshing per symbol is needless latency.
        token = _access_token()
        completed = 0
        concurrency = settings.code_card_request_concurrency
        if concurrency < 1:
            raise RuntimeError("code_card_request_concurrency must be at least 1")
        for batch_start in range(0, len(targets), concurrency):
            prepared = []
            for symbol in targets[batch_start:batch_start + concurrency]:
                card_started = time.monotonic()
                file = db.get(File, symbol.file_id)
                calls = [e.target_name for e in edges if e.source_symbol_id == symbol.id and e.relationship_type == "call"]
                imports = [e.target_name for e in edges if e.source_file_id == symbol.file_id and e.relationship_type == "import"]
                payload = {"contents": [{"role":"user", "parts":[{"text":_prompt(repo, file, symbol, calls, imports)}]}], "generationConfig": _generation_config()}
                prepared.append((symbol, card_started, time.monotonic() - card_started, payload))
            responses = asyncio.run(_post_batch(token, [item[3] for item in prepared], concurrency))
            for (symbol, card_started, context_elapsed, _), (response, provider_elapsed) in zip(prepared, responses):
                response.raise_for_status()
                parse_started = time.monotonic()
                body = response.json()
                raw_text = ""
                try:
                    raw_text = body["candidates"][0]["content"]["parts"][0]["text"]
                    details = _parse_details(raw_text)
                    summary = details["summary"].strip()
                    parse_elapsed = time.monotonic() - parse_started
                except (KeyError, IndexError, TypeError, ValueError) as error:
                    # Valid cards from earlier batches are durable; this symbol is retried on resume.
                    preview = " ".join(raw_text.split())[:240]
                    logger.error("code_card_result outcome=invalid symbol=%s elapsed_s=%.3f error=%s response_preview=%r", symbol.qualified_name, time.monotonic() - card_started, type(error).__name__, preview)
                    raise RuntimeError(f"invalid code-card JSON for {symbol.qualified_name}; resumable retry required") from error
                if not summary:
                    logger.error("code_card_result outcome=empty_summary symbol=%s elapsed_s=%.3f", symbol.qualified_name, time.monotonic() - card_started)
                    raise RuntimeError(f"empty code-card summary for {symbol.qualified_name}; resumable retry required")
                usage = body.get("usageMetadata", {})
                values = dict(repository_id=repo_id, source_hash=hashlib.sha256(symbol.source_text.encode()).hexdigest(), indexed_commit_sha=repo.indexed_commit_sha or "", model=settings.vertex_gemini_model, prompt_version=PROMPT_VERSION, status="ready", summary=summary, details=details, input_tokens=usage.get("promptTokenCount"), output_tokens=usage.get("candidatesTokenCount"))
                card = cards.get(symbol.id)
                if card:
                    for key, value in values.items(): setattr(card, key, value)
                else:
                    card = CodeCard(symbol_id=symbol.id, **values); db.add(card); cards[symbol.id] = card
                completed += 1; job.progress = {"phase":"generating", "total":len(targets), "completed":completed}
                persist_started = time.monotonic(); db.commit(); persist_elapsed = time.monotonic() - persist_started
                logger.warning("code_card_result outcome=persisted symbol=%s context_s=%.3f provider_s=%.3f parse_s=%.3f persist_s=%.3f total_s=%.3f", symbol.qualified_name, context_elapsed, provider_elapsed, parse_elapsed, persist_elapsed, time.monotonic() - card_started)
        # Refresh vectors only after cards are committed; the vector document keeps original code plus card context.
        db.commit()
        from app.ingestion import reembed_repository
        reembed_repository(repo_id)
        job.status="ready"; job.finished_at=datetime.utcnow(); db.commit()
        return {"total": len(targets), "completed": completed, "model": settings.vertex_gemini_model}
    except Exception as exc:
        job.status="failed"; job.error_message=str(exc); job.finished_at=datetime.utcnow(); db.commit(); raise
    finally:
        db.close()


async def _post(token, payload):
    async with httpx.AsyncClient(timeout=60.0) as client:
        return await client.post(_endpoint(), headers={"Authorization": f"Bearer {token}"}, json=payload)
