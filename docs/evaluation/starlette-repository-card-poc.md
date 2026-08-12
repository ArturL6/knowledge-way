# Starlette repository-card POC capture

**Captured:** 2026-08-11
**Repository:** `https://github.com/Kludex/starlette.git`
**Indexed commit:** `398e5a3430eb1ddd33e1d48d766efe41426e231f`

This is an API-level local evaluation of `GET /api/repositories/starlette-poc/repository-card` after indexing a shallow checkout into an ephemeral SQLite-backed test instance. The endpoint was called through FastAPI `TestClient`; indexing used the normal local parser/graph and structural-card pipeline. `EMBEDDING_PROVIDER` remained its default `none`, and Code Cards were disabled: no embedding or LLM provider was invoked.

## Captured bounded retrieval document

```text
Repository: Starlette
Indexed commit: 398e5a3430eb1ddd33e1d48d766efe41426e231f
Files: 129; Symbols: 1871; Ready code cards: 0
Languages: markdown (30), python (71), toml (2), unknown (18), yaml (8)
Modules:
- tests: 23 direct files, 4160 boundary edges
- .: 8 direct files, 4156 boundary edges
- starlette: 24 direct files, 3539 boundary edges
- tests/middleware: 11 direct files, 1125 boundary edges
- starlette/middleware: 12 direct files, 671 boundary edges
- benchmarks: 3 direct files, 151 boundary edges
- docs: 25 direct files, 0 boundary edges
- scripts: 7 direct files, 0 boundary edges
- docs/img: 2 direct files, 0 boundary edges
- docs/overrides/partials: 2 direct files, 0 boundary edges
- docs/css: 1 direct files, 0 boundary edges
- docs/overrides: 1 direct files, 0 boundary edges
```

The document was **796 characters** and returned the configured maximum of **12 modules**. Its facts reported 129 files and 1,871 symbols. This confirms the POC is bounded on a real repository without provider spend. It is a retrieval projection, not an authority: boundary-edge counts are persisted graph evidence, and no dependency, call-resolution, or cross-repository claim is inferred from the text.

## Review outcome

Review found that the initial POC could combine a current repository commit with old `StructuralCard` or `CodeCard` rows if stale rows remained in storage. The implementation now filters files, symbols, structural cards, and ready Code Cards to the repository's current `indexed_commit_sha`; the unit/API test injects stale same-repository evidence and proves it is absent. This keeps the advertised commit pin meaningful until the next phase persists versioned retrieval-document projections.
