# HUMAN-DIRECTIVE-010 — Keyless retrieval sprint; defer the rest as tracked work

**From:** Project owner · **Date:** 2026-08-20
**To:** kw-navigator, kw-implementer, kw-benchmark
**Authority:** Owner directive; ratify as the next ADR. Highest directive number wins. HD-009 stays in force except where re-sequenced here. Goal and all standing rules (HD-009 §4) unchanged.

---

## 1. Decision and rationale

The external keyless comparison (ADR-007: comparator 0.44 hit@5 keyless vs our 0.24–0.32 keyless) shows our **non-semantic retrieval is the weakest layer** and the highest-leverage work: stronger keyless recall feeds weighted RRF and lifts hybrid beyond 0.68, and it makes the **keyless quickstart** — the owner's local-testing path — genuinely good without any API keys. This sprint is therefore not a detour: it re-scopes already-queued packets (1.2, 1.2b, parts of 1.4/1.7) into a focused sequence. Everything displaced is **deferred, not dropped** (§4).

**Sprint targets (binding):**
- **Keyless** file hit@5 ≥ **0.44** (parity with the comparator's keyless class), stretch 0.50.
- **Semantic-enabled hybrid** never regresses below **0.68** (regression guard on every packet).
- **Hybrid p95 ≤ 1s** (the outstanding Stage-1 latency criterion — solved inside this sprint, since the slow ILIKE symbol pass is exactly what K.2 replaces).

## 2. Clean-room rule (extends HD-007; mandatory)

Every retrieval mechanism in this sprint is standard public information-retrieval literature; the comparator only provided behavioral evidence that these levers matter. **Each implementing PR/ADR must cite its public source** (e.g., BM25 → Robertson & Zaragoza 2009 "The Probabilistic Relevance Framework"; RRF → Cormack, Clarke & Buettcher 2009; IDF → Spärck Jones 1972). Implementation proceeds from those sources and the agent's own design — never from comparator code, which no agent may read, fetch, or reference. Reviewer verifies the citation exists and product paths remain comparator-free.

## 3. The sprint — three packets, in order

**K.1 — Query digestion + BM25 re-scoring + lexical latency.**
Index side: per-workspace document-frequency statistics (small `term_df` table or `ts_stat`-derived, refreshed on reindex). Query side: deterministic digester — strip markdown fences/checklists/URLs/HTML-comment boilerplate, tokenize identifiers (camelCase/snake_case/dotted), drop stopwords, keep the top ~12 corpus-rarest terms. Retrieval: keep the GIN tsvector index for candidate generation, re-score top-N candidates with true BM25 (k1≈1.2, b≈0.75) as a pure function in `domain/retrieval.py`. Exit: keyless text-mode hit@5 materially up (expect ≥0.32→~0.40), text-mode p95 down, hybrid ≥0.68 held, unit tests on digester + BM25 math.

**K.2 — Name-first compact retrieval units (absorbs old 1.2 + 1.2b).**
Index symbols, files, modules, and existing cards as first-class lexical documents (qualified names identifier-tokenized + docstrings/card text) — a dense entity index replacing the ILIKE symbol pass entirely. Two-stage retrieval: digested terms → entity index (high precision) → member chunks of top entities. Includes the exact/quoted path: quoted strings and identifier-shaped queries route to indexed exact/prefix + pg_trgm. Exit: **hybrid p95 ≤ 1s**; exact/identifier hit@1 ≥ 0.9 (on the identifier-query task subset per HD-009 §5.3); keyless hit@5 ≥ 0.40; hybrid ≥ 0.68 held.

**K.3 — Graph expansion into fusion (keyless part of old 1.7/2.4).**
For top candidates, add a distance-damped 1-hop neighbor list as an extra RRF input: same-file symbols, callers/callees (existing edges), co-imported files, and the convention-paired **test file** (import + naming heuristics — gold sets include tests, so this directly serves the oracle). Exit: **keyless hit@5 ≥ 0.44**; hybrid ≥ 0.68 held (expect it to rise); expansion behind a flag with with/without scorecards committed; revert if neutral.

**Benchmark job during the sprint:** run BOTH scorecards on every integration change — keyless (co-binding for K-packet exits) and semantic-enabled (binding regression guard). Label both clearly.

## 4. Deferral mechanism — the rest stays tracked, not dropped

STATUS.md remains the single work queue. Displaced packets get `state: deferred` with a one-line reason and their position in the resume order; **GitHub issues may mirror them for owner visibility, but issues are never a second work source — agents take work only from STATUS.** Deferred now, resume order after the sprint:

1. **1.4** — card embeddings + local-ONNX-model experiment (ADR-010 tolerance gate unchanged; note K.2's entity/card lexical index does half of 1.4's prep).
2. **1.6** — query planner (K.1's digester + K.2's routing cover most of it; re-scope on resume).
3. **1.8** — rerank evaluation.
4. **0.5** — benchmark-cron formality doc.
5. **1.0x** — worker-shim fix + close PR #55: NOT deferred; still the first housekeeping packet before K.1 (it's an hour of work and unblocks clean ephemeral stacks).

## 5. After the sprint

With K.1–K.3 landed, re-check **all Stage-1 exit criteria** (hybrid ≥ targets and ≥ every mode: expected; p95 ≤ 1s: K.2; exact hit@1 ≥ 0.9: K.2) → stage-exit review → **promotion to main** → resume the deferred queue (§4 order) → Stage 2. Owner is needed only at: ADR-010 local-model sign-off (when 1.4 resumes), Stage-1 exit acknowledgment, Stage-4 go/no-go.

## 6. Processing

**Implementer, first tick:** commit this file to `governance/directives/HUMAN-DIRECTIVE-010.md`; ratifying ADR (include the §2 citation rule); update STATUS: insert K.1–K.3 after 1.0x, mark 1.4/1.6/1.8/0.5 `deferred` with reasons + resume order; optionally open mirror issues labeled `deferred/post-sprint`.
**Navigator, next tick:** verify ADR matches; issue `next_instruction: 1.0x`, then K.1 → K.2 → K.3 in strict order, each with hermetic dual scorecards and exact-head review per the standing gate.

**Success state:** keyless hit@5 ≥ 0.44 and hybrid > 0.68 with p95 ≤ 1s, achieved from cited public literature with zero comparator contact — then Stage-1 promotion and the deferred queue resumes.
