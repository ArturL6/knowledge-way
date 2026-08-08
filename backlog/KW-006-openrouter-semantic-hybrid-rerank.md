# KW-006 — Optional OpenRouter semantic indexing, hybrid retrieval, and reranking

**Priority:** P1  
**Depends on:** KW-001, KW-002, KW-004

## Decision
Initial provider/model: OpenRouter with `openai/text-embedding-3-small`. Feature remains disabled unless explicitly configured.

## Scope
- Provider adapter with OpenRouter base URL, key handling, timeouts, retry/backoff, bounded batches, model/version provenance.
- Embed changed/unembedded chunks only; reuse same normalized content hash + provider/model/version.
- Fixed vector dimensionality and pgvector ANN migration/index.
- Semantic candidates scoped in SQL to authorized repository/workspace IDs.
- Fuse lexical, symbol, vector, and later graph candidates using reciprocal-rank fusion; deterministic tie breaking.
- Optional separate reranker after candidate fusion; report modalities and degraded state truthfully.

## Acceptance criteria
- Missing provider credential leaves lexical/symbol retrieval functional and says semantic is unavailable rather than falsely enabled.
- Deterministic-vector tests prove semantic rank, model-version invalidation, repository isolation, retry/failure behavior, and fusion ordering.
- Live provider smoke test is opt-in and never logs keys or code content.
- Reembedding workflow is explicit when model/dimension changes.
