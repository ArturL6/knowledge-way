"""Versioned, citation-safe Gemini summaries for indexed code symbols."""
import asyncio
import hashlib
import json
from datetime import datetime

import httpx
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import CodeCard, File, IndexingJob, Repository, Symbol, SymbolEdge
from app.providers import VertexEmbeddingProvider

PROMPT_VERSION = "code-card-v1"


def _access_token():
    return VertexEmbeddingProvider._refresh_credentials()


def _endpoint():
    location = settings.vertex_gemini_location
    host = "aiplatform.googleapis.com" if location == "global" else f"{location}-aiplatform.googleapis.com"
    return f"https://{host}/v1/projects/{settings.vertex_project_id}/locations/{location}/publishers/google/models/{settings.vertex_gemini_model}:generateContent"


def _prompt(repo, file, symbol, calls, imports):
    source = symbol.source_text[:settings.code_card_max_source_characters]
    return f'''Create one concise, factual code card. Use ONLY the supplied code and static metadata. Do not claim behavior that is not evidenced. Return strict JSON with exactly: summary (string, <= 50 words), inputs (array of strings), outputs (array of strings), side_effects (array of strings), dependencies (array of strings), keywords (array of strings), confidence (high|medium|low).

Repository: {repo.name}
Path: {file.path}
Language: {symbol.language}
Symbol: {symbol.qualified_name}
Kind: {symbol.symbol_type}
Signature: {symbol.signature or ''}
Static calls: {', '.join(sorted(calls)) or 'none observed'}
Static imports: {', '.join(sorted(imports)) or 'none observed'}
Code:\n{source}'''


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
        completed = 0
        for symbol in targets:
            file = db.get(File, symbol.file_id)
            calls = [e.target_name for e in edges if e.source_symbol_id == symbol.id and e.relationship_type == "call"]
            imports = [e.target_name for e in edges if e.source_file_id == symbol.file_id and e.relationship_type == "import"]
            token = _access_token()
            payload = {"contents": [{"role":"user", "parts":[{"text":_prompt(repo, file, symbol, calls, imports)}]}], "generationConfig": {"temperature":0, "maxOutputTokens":384, "thinkingConfig":{"thinkingBudget":0}, "responseMimeType":"application/json"}}
            response = asyncio.run(_post(token, payload)); response.raise_for_status()
            body = response.json()
            try:
                details = json.loads(body["candidates"][0]["content"]["parts"][0]["text"])
                summary = details["summary"].strip()
            except (KeyError, IndexError, TypeError, json.JSONDecodeError):
                # A malformed model response is not evidence; skip that symbol and retain the deterministic index.
                continue
            if not summary:
                continue
            usage = body.get("usageMetadata", {})
            values = dict(repository_id=repo_id, source_hash=hashlib.sha256(symbol.source_text.encode()).hexdigest(), indexed_commit_sha=repo.indexed_commit_sha or "", model=settings.vertex_gemini_model, prompt_version=PROMPT_VERSION, status="ready", summary=summary, details=details, input_tokens=usage.get("promptTokenCount"), output_tokens=usage.get("candidatesTokenCount"))
            card = cards.get(symbol.id)
            if card:
                for key, value in values.items(): setattr(card, key, value)
            else:
                card = CodeCard(symbol_id=symbol.id, **values); db.add(card); cards[symbol.id] = card
            completed += 1; job.progress = {"phase":"generating", "total":len(targets), "completed":completed}; db.commit()
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
