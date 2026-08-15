# Vertex AI readiness

Per ADR-006 / HUMAN-DIRECTIVE-005 §3.2: Vertex is "configured" only after
`VERTEX_PROJECT_ID` + ADC pass a subset probe (≤10 chunks) using
`text-embedding-005`, returning 768-dim vectors. Record outcome + approximate
cost here before any full-corpus embedding.

## Probe — 2026-08-15

- **Project:** `ai-tinker-lab` (owner-provided)
- **ADC:** present at `~/.gcloud-kw/application_default_credentials.json`
  (no-sudo config dir; `~/.config/gcloud` is root-owned from a prior Docker
  mount). Quota project set to `ai-tinker-lab`.
- **Endpoint:** `us-central1-aiplatform.googleapis.com … /models/text-embedding-005:predict`
- **Request:** 5 short code-like texts, `parameters.outputDimensionality = 768`
  (mirrors `VertexEmbeddingProvider.embed_texts`).
- **Result:** HTTP 200 in ~2.0s; **5 vectors, all 768 dimensions**. `PROBE_OK`.
- **Input size:** 205 characters total.
- **Approximate cost:** negligible — well under $0.0001 (text-embedding-005 is
  billed per ~1k input tokens; ~50 tokens here).

**Status: Vertex is configured and verified.** Semantic embedding work (packet
1.3 ANN, 1.4 structure-aware units) may proceed under the standing controls:
small-subset-first (≤200 files / ≤500 chunks) with committed samples + a
full-run cost extrapolation BEFORE any full-corpus embed; USD 50/month product
cap, pause at USD 40 (current product spend ≈ $0). Corpus embeddings use exactly
one provider+model: Vertex `text-embedding-005` @768 (ADR-004/005).
