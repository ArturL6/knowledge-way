# Knowledge-Way — Plan (single handover document)

**Status:** Execution plan v2 — self-contained. This is the only document the implementer and reviewer need.
**Precedence:** This document governs. Appendix A condenses the background spec; on any conflict, the plan sections win. The plan is changed only via ADR + reviewer verdict, never by momentum.
**Bootstrap:** Commit this file as `governance/PLAN.md` on a new branch `integration/roadmap-v2` created from `main`. Packet R.1 creates the remaining governance files and cron jobs; work proceeds packet by packet from there.

**Basis:** Existing codebase `ArturL6/knowledge-way` — adopted, not rewritten. Assessment: ~2,150 lines app Python, 80 passing tests, correct core concepts already present (workspaces, commit pinning, edge confidence, unresolved call targets, versioned extractors/prompts, hash-gated embeddings, deterministic commit-pinned repository-card POC validated on Starlette). Verdict: solid basis; restructure and harden rather than restart.

**Roles:** **Implementer** = Hermes (with the configured Codex tier), working in scheduled autonomous runs. **Reviewer** = Sol high, gating every packet and stage against this plan. The reviewer never writes code.

---

## How to read this document

- Work proceeds as a **walking skeleton**: the system already runs end-to-end; every stage must leave it running end-to-end with strictly better, *measured* capability.
- Work is decomposed into **work packets** (`R.1`, `1.3`, …). A packet is the unit a scheduled implementer run picks up: small enough for one session, with a machine-checkable `verify` command.
- **Exit criteria are binding** and, wherever possible, executable (`governance/checks/`). A stage is done when criteria pass, not when code exists.
- **The benchmark is the referee.** Hybrid search quality is currently not solid; it becomes measurable first (Stage 0) and is then fixed against those measurements (Stage 1). No retrieval change merges without a scorecard delta.

## The goal, restated (what "solid" means)

> Given a natural-language development task, the system returns the correct repositories, files, symbols, and relationships with exact evidence — reliably enough that a coding agent needs materially fewer exploratory tool calls than with grep alone.

Solidity is therefore defined as: **hit@5 on gold tasks, false-edge rate, and latency** — not subjective demo feel. (Background: Appendix A.1–A.2.)

## Known weaknesses of the current retrieval (diagnosed, fixed in Stage 1)

1. Lexical search is `ILIKE '%term%'` over chunks — no FTS/trigram indexes, no identifier tokenization (camelCase/snake_case), no real ranking, sequential scans.
2. Semantic search embeds the query, then **scans every embedded chunk and computes cosine in Python** — O(n) per query; pgvector's ANN index is never used in the query path.
3. Fusion combines raw scores from incomparable scales (ILIKE heuristics vs cosine vs constants) instead of rank-based fusion.
4. Embedding targets are raw chunks only — no structure-aware units (cards/modules/symbols).
5. Hybrid mode always runs everything; no query planning (main's exact-hit fast path is a start, not a plan).
6. No gold-task evaluation loop, so none of the above is currently measurable.

## Global technology decisions

| Concern | Decision | Note |
|---|---|---|
| Codebase | **knowledge-way**, integration branch `integration/roadmap-v2` | Created from `main`; merge `feat/hierarchical-retrieval-poc` into it in Stage R |
| Backend | Python 3.12+, **FastAPI**, SQLAlchemy 2, Alembic | Already in place |
| Architecture | **Hexagonal (ports & adapters)** — retrofitted in Stage R | Import-linter enforces the boundary in the local gauntlet |
| Database | PostgreSQL + **pgvector** | Already in place; ANN actually used from Stage 1 |
| Jobs | **Keep Redis + RQ** | ADR-001: working and tested; a Postgres-queue reversal is not justified |
| Frontend | **Keep Next.js + React 19** | ADR-002: exists with search/graph/files/chat views |
| E2E testing | **Playwright** on `apps/web` | Added in R.2; mandatory on any web/UI change |
| Package manager | Migrate `requirements.txt` → **uv** | Stage R packet |
| Parsing | tree-sitter (already integrated via `parser_facts.py`, versioned) | Extend languages per benchmark need |
| Lexical index | Postgres FTS + pg_trgm first; **Zoekt only if Stage 4 benchmark demands** | Behind a `LexicalSearch` port either way |
| Precise symbols | SCIP — Stage 5, benchmark-gated | Behind the `CodeParser` port |
| LLM / embeddings | Existing `providers.py` abstraction | Becomes the `llm` port |
| Agent protocol | Existing `apps/mcp` | Tool set grows in Stage 4 |

## Target hexagonal layout (Stage R restructure map)

Domain + application layers must not import FastAPI, SQLAlchemy, tree-sitter, redis, or any LLM SDK. Existing modules map as follows:

```text
apps/api/src/ski/
├── domain/                    ← extract pure logic from repository_cards.py,
│   │                            structural_cards.py, graph shaping in main.py
│   ├── model.py               ← plain dataclasses mirroring today's SQLAlchemy models
│   ├── retrieval.py           ← fusion, ranking, planning rules (pure functions)
│   └── graph.py               ← traversal/honesty logic (pure)
├── application/
│   ├── ports/                 ← Protocols: RepoStore, SourceControl, LexicalSearch,
│   │                            VectorSearch, CodeParser, LLM, Embeddings, JobQueue
│   └── use_cases/             ← search, ingestion, reconcile, repository_cards
│                                orchestration, code_cards flow
├── adapters/
│   ├── inbound/http/          ← routers extracted from main.py (427 lines → thin routers)
│   ├── inbound/mcp/           ← apps/mcp calls use cases via HTTP as today
│   └── outbound/
│       ├── postgres/          ← models.py, db.py, FTS/pgvector queries
│       ├── git_cli/           ← git_auth.py, git_askpass.py, clone/sync from ingestion.py
│       ├── treesitter/        ← parser_facts.py
│       ├── rq_jobs/           ← worker.py
│       └── llm_providers/     ← providers.py
└── config.py                  ← composition root (wires adapters to ports)
```

**Hexagonal test rule:** every port gets an in-memory fake; use-case tests run without Docker (today's SQLite-portable tests already do this — preserve that property). Adapter tests run against docker-compose.

---

## Branching model & test gauntlet (incremental, always-green)

**`main` is the fresh start and the permanent base.** All work flows toward it in small, verified increments:

```text
main                          # stable truth; only receives stage-complete promotions
└── integration/roadmap-v2    # created FROM main; kept ALWAYS up to date with main
    └── packet/<id>-<slug>    # one packet per branch, branched from integration
```

Rules:

1. **Integration branches from main** (Stage R.2); `feat/hierarchical-retrieval-poc` is merged *into* integration there, then the old feature branches are frozen — no further work lands on them.
2. **Integration stays current:** if anything lands on main, the next scheduled run merges main → integration before starting a packet. Divergence from main is drift.
3. **Packet branches start fresh from integration** (merge integration in first if stale) and must pass the full **test gauntlet** before merging back:
   - static checks: ruff (lint + format), import-linter (hexagon boundary), type check;
   - unit tests (fast, no Docker — the SQLite-portable suite);
   - **API endpoint tests** (FastAPI TestClient integration tests for every touched or added endpoint);
   - **e2e with Playwright — mandatory whenever `apps/web` or a UI-facing contract is touched**, skipped otherwise (smoke flow: add repo → index → search → open evidence);
   - the packet's own `verify` command from STATUS.md;
   - scorecard run for retrieval-touching packets (standing rule 10).
4. **Merge direction is always packet → integration**, on green gauntlet + reviewer verdict. Integration therefore only ever gets better, one verified packet at a time.
5. **Stage completion promotes integration → main:** when a stage's exit criteria pass and the reviewer issues the stage-exit verdict, integration merges into main. Main is thus a sequence of proven, stage-sized improvements.
6. CI is optional advisory automation. The binding merge gate is recorded local-gauntlet evidence plus a reviewer verdict.

## Governance & autonomous operation (Hermes cron setup)

Three hardening principles are binding:

1. **Artifacts, never summaries.** Reviews consume the actual diff, test output, and scorecards — not the implementer's narrative.
2. **Local gauntlet enforces, reviewer judges.** Import-linter, pytest, and `governance/checks/*.sh` are run and their output is committed or attached to the PR; drift cannot merge even if a review is missed.
3. **One packet per branch/PR**, merged only on recorded green local gauntlet + reviewer verdict.

### Repository artifacts (committed in `governance/`)

```text
governance/
├── PLAN.md              # this file — single source of truth
├── STATUS.md            # machine-readable packet board (format below)
├── decisions/           # ADR-NNN-*.md (ADR-001 RQ, ADR-002 Next.js created in Stage R)
├── reviews/             # REVIEW-NNN.md — reviewer verdicts, append-only
└── checks/              # executable exit criteria (bash/pytest), run locally and recorded with the PR
```

### STATUS.md packet board format (what cron jobs read and write)

```yaml
stage: 1
packets:
  - id: "1.3"
    title: "Replace Python-cosine scan with pgvector ANN query"
    state: todo | in_progress | pr_open | review_blocked | done
    branch: packet/1.3-pgvector-ann
    verify: "governance/checks/stage1_ann.sh"
    blocked_by: ["1.1"]
last_review: REVIEW-014
drift_flags: []
```

### Scheduled jobs (set up as Hermes cron jobs in packet R.1)

| Job | Schedule | Prompt contract |
|---|---|---|
| `implementer-run` | nightly (or every N hours) | Read PLAN.md + STATUS.md. **First: merge main → integration if main moved; merge integration → current packet branch if stale.** Pick the lowest-numbered `todo` packet with no unmet `blocked_by`. Set `in_progress`. Implement on `packet/<id>-<slug>` branched from integration. Run the **full test gauntlet** (static checks, unit, API endpoint tests, Playwright if web/UI touched, packet `verify`, scorecard if retrieval touched). Open PR **into integration** containing: diff, gauntlet + verify output, STATUS.md update to `pr_open`. **Never** start a packet from a future stage. **Never** merge. |
| `reviewer-run` | every morning | For each `pr_open` packet: fetch diff + recorded local gauntlet output + verify output. Check against PLAN.md packet definition and standing rules. Write `governance/reviews/REVIEW-NNN.md` with the verdict contract below. Verdict `on_track` → approve merge. `drift` → set `review_blocked` with required actions. |
| `drift-audit` | weekly | Diff the integration branch against PLAN.md stage scope. Check: hexagon boundary intact, no unplanned dependencies, scorecard trend not regressing, STATUS.md matches reality, integration current with main. Output: audit review + updated `drift_flags`. |
| `benchmark-run` | weekly (from Stage 0 on) | Run the gold-task harness against integration; commit scorecard to `benchmarks/results/`; flag any regression as a drift finding. |

### Reviewer verdict contract (every review, no exceptions)

```yaml
verdict: on_track | drift | blocked
packet: "1.3"
criteria_checked: ["ANN query uses vector index: PASS (EXPLAIN shows index scan)", ...]
drift_findings: ["Added elasticsearch dependency; PLAN mandates Postgres FTS. Revert or ADR."]
required_actions: [...]
scope_creep_risk: low | medium | high
```

**Drift rule:** two consecutive `drift` verdicts on the same topic → all cron jobs pause (`drift_flags` non-empty blocks `implementer-run`), and the human decides: PLAN changes via ADR, or the work reverts. The plan is never silently outvoted by momentum.

**Reviewer's standing questions:** (1) Does this packet exist in the current stage? (2) Is any exit criterion being reinterpreted to pass easier? (3) Standing rules intact? (4) New infra justified by a measurement? (5) Hexagon boundary intact? (6) Did the scorecard move the right way?

---

# Stage R — Adopt & restructure (≈ 1 week)

**Goal:** One healthy integration branch based on main, hexagonal structure, governance live, cron jobs running. No feature work.

### Packets

- **R.1 — Governance bootstrap.** Create `governance/` (PLAN=this file, STATUS, ADR-001 RQ, ADR-002 Next.js, empty reviews/, checks/). Configure the four cron jobs per the table above. Verify: cron jobs execute a dry run end-to-end (implementer picks a dummy packet, reviewer reviews it).
- **R.2 — Branch consolidation, main as base.** Create `integration/roadmap-v2` **from `main`** (main is the fresh start). Merge `feat/hierarchical-retrieval-poc` into it (4 files, +249 lines — resolve trivially). Freeze all other feature branches — no further work lands on them. Verify: full test suite green (≥ 80 tests); `git merge-base` confirms integration descends from current main.
- **R.3 — uv migration.** `pyproject.toml` + lockfile replaces `requirements.txt`; the local gauntlet installs via uv. Verify: clean-checkout local run green.
- **R.4 — Hexagon: extract ports + move adapters.** Create the layout above; move `models.py/db.py`→postgres adapter, `parser_facts.py`→treesitter adapter, `providers.py`→llm adapter, `git_*`→git adapter, `worker.py`→rq adapter; define the eight port Protocols. Behavior-preserving; tests untouched and green.
- **R.5 — Hexagon: split main.py.** Routers → `adapters/inbound/http/`; logic → use cases; pure fusion/ranking/graph shaping → `domain/`. Verify: `main.py` gone or < 50 lines of app factory; tests green.
- **R.6 — Boundary enforcement.** import-linter contract (domain/application import nothing from adapters or frameworks) wired into the local gauntlet. Verify: the local check fails on a deliberate violation fixture, passes on HEAD.
- **R.7 — Evidence table.** New `evidence(id, repository_id, indexed_commit_sha, path, start_line, end_line, extractor, extractor_version, content_hash)`; `symbol_edges` gains `evidence_id`; backfill from existing `source_file_id`+`line_number`; DB constraint/test: **no edge without evidence** (standing rule 1).

### Exit criteria
- [ ] `governance/checks/stageR.sh` passes: tests green, import-linter green, evidence constraint enforced, uv-only install works, Playwright smoke green.
- [ ] All four cron jobs have completed at least one real cycle (one packet implemented, reviewed, merged autonomously).

### Non-goals
No retrieval changes, no new features, no new endpoints.

---

# Stage 0 — Measurement first (≈ 1 week, partially parallel with R)

**Goal:** Make retrieval quality measurable before improving it, and learn from GitNexus. Extends the existing `benchmarks/` folder (task/corpora/result schemas already exist — build on them).

### Packets

- **0.1 — Workspace selection** *(human decision)*. Choose 2–5 real interacting repositories (≥ 1 API relationship, ≥ 1 shared package/schema). Document in `benchmarks/corpora.json`. These are permanent.
- **0.2 — Gold tasks.** 20–40 historical tasks from those repos' history/issues in `benchmarks/tasks/` (YAML: description + gold repositories/files/symbols/tests/cross-repo impacts + source commit). Extend the existing `tasks.json` format if compatible.
- **0.3 — Retrieval scorecard harness.** `benchmarks/run_retrieval.py`: for each gold task, query `/api/search` (each mode + hybrid); score **hit@1/hit@5 for files and symbols, MRR, p50/p95 latency**. Output committed scorecard. Verify: harness runs against the current (weak) search and produces the baseline scorecard — the number Stage 1 must beat.
- **0.4 — GitNexus test drive.** Run GitNexus (github.com/abhigyanpatwari/GitNexus) on the same workspace; execute the 12 question classes in Appendix A.7; record correct/partial/incorrect/not-representable + latency; write `benchmarks/gitnexus-findings.md`. License: PolyForm Noncommercial — study concepts, never copy code.
- **0.5 — Wire `benchmark-run` cron** to 0.3's harness with regression flagging.

### Exit criteria
- [ ] Baseline scorecard committed (current search, real workspace, gold tasks).
- [ ] GitNexus findings documented with representation-gap vs accuracy-gap classification.

---

# Stage 1 — Retrieval solidity (≈ 2–3 weeks) — the search rewrite

**Goal:** Fix all six diagnosed weaknesses. Every packet lands with a scorecard delta; the stage ends when hybrid search is measurably solid.

### Packets

- **1.1 — Postgres FTS for lexical.** `tsvector` column on chunks with a code-aware tokenizer: split identifiers (camelCase, snake_case, dotted paths) into searchable terms at index time; GIN index; `ts_rank`-based scoring replaces the ILIKE-percentage heuristic. Keep an exact-substring path (pg_trgm GIN index) for quoted queries, config strings, and error messages. Both behind the `LexicalSearch` port. Verify: EXPLAIN shows index scans; scorecard: lexical hit@5 ≥ baseline, p95 latency down on the real workspace.
- **1.2 — Symbol search hardening.** Exact and prefix match on `qualified_name` via proper indexes; identifier-aware matching (`PaymentService.capture`, `capture`); exact symbol hit always outranks fuzzy hits.
- **1.3 — pgvector ANN queries.** Replace the Python cosine full scan with a real `ORDER BY embedding <=> :q LIMIT k` query using an HNSW index, filtered by model + workspace scope. Keep the Python path only as the SQLite test fallback behind the `VectorSearch` port. Verify: EXPLAIN shows index usage; semantic query latency independent of corpus size.
- **1.4 — Structure-aware embedding units.** Embed, in addition to chunks: symbol cards (existing `code_cards`), structural/module cards, and the deterministic repository cards from the hierarchical-retrieval POC. Hash-gated regeneration (mechanism exists — extend it). This is **hierarchical retrieval** made real: repo card → module card → symbol → chunk, coarse-to-fine.
- **1.5 — Rank fusion (RRF).** Replace mixed-scale score fusion with reciprocal-rank fusion across lexical/symbol/semantic candidate lists; keep the exact-hit fast path (main's #54) as a planner rule, not a special case. Pure function in `domain/retrieval.py` with unit tests on constructed rankings.
- **1.6 — Query planner v1.** Deterministic rules route: quoted/regex-like → lexical-exact; identifier-shaped → symbol-first; otherwise semantic+lexical in parallel; "who calls / references / impact" reserved for Stage 2/4 handlers. Ambiguous → optional cheap LLM classification via the `llm` port (routes retrieval, never answers). No LLM in the inner loop.
- **1.7 — Hierarchical retrieval flow.** For concept queries: retrieve top repo/module cards first, then constrain symbol/chunk retrieval to those scopes, then fuse. Measure with and without the hierarchical constraint.
- **1.8 — Rerank (existing hook) evaluation.** Keep the rerank provider path; measure its scorecard delta; disable by default if it doesn't pay for its latency.

### Exit criteria (all measured on the Stage 0 harness, committed scorecards)
- [ ] Hybrid hit@5 (files) improves ≥ 30% relative over the Stage 0 baseline, and hybrid ≥ every single mode alone.
- [ ] Exact identifier and quoted-string queries: hit@1 ≥ 0.9.
- [ ] p95 hybrid latency ≤ 1s on the real workspace; semantic latency flat in corpus size.
- [ ] Zero framework/SQL imports in `domain/retrieval.py` (import-linter).

### Non-goals
No Zoekt, no Elasticsearch, no learned ranker, no new node types.

---

# Stage 2 — Graph & evidence hardening (≈ 1–2 weeks)

**Goal:** Reliable who-calls / references / definition answers with honest completeness. Builds on existing `SymbolEdge` + graph-honesty tests.

### Packets

- **2.1 — Completeness surfaced end-to-end.** Edges/queries report `completeness: exact | lower_bound` with causes (unresolved dynamic dispatch, unindexed dependency). The nullable `target_symbol_id` + `target_name` design already stores unresolved calls — expose them honestly in API + MCP responses. (Concept: Appendix A.4.)
- **2.2 — Resolution improvements.** Same-file → same-repo qualified-name resolution pass (tree-sitter heuristic), confidence scaled by match quality; measured by a resolution-rate metric on the real workspace.
- **2.3 — Callers/references/definition API + MCP tools** (`references`, `callers`, `neighbors`) with evidence rows on every claim.
- **2.4 — Graph expansion in retrieval.** 1-hop neighbor expansion of top candidates feeds RRF fusion (planner-gated). Scorecard delta required; revert if neutral.

### Exit criteria
- [ ] "Who calls X?" correct on fixture + real workspace with evidence lines; unresolved calls visible as lower-bound, never dropped.
- [ ] No edge without evidence — constraint holds for new extractors too.

---

# Stage 3 — Cross-repository extraction & workspace cards (≈ 2 weeks)

**Goal:** `workspace_dependencies` stops being manually declared and becomes extracted, evidence-backed knowledge; the workspace reads as one application. This is the GitNexus-groups capability we are testing against.

### Packets

- **3.1 — Package-dependency extractor.** Parse `pyproject.toml`/`package.json` across workspace repos; provider/consumer match ⇒ `DEPENDS_ON` edge (confidence 0.95, evidence = manifest lines). Manual declarations remain possible but are marked `source: declared` vs `source: extracted`.
- **3.2 — HTTP-contract extractor.** Route definitions (FastAPI decorators, Express/Next handlers) → `APIEndpoint` facts + `PROVIDES_API`; outgoing HTTP calls with literal/near-literal paths → `CONSUMES_API` on match, confidence by match quality, **evidence on both sides**. Unmatched candidates stored, flagged, never invented.
- **3.3 — Workspace card.** Deterministic projection (POC pattern) over repos + cross-repo edges: what this application is, its repos, their connections. Embedded as the top hierarchy level for 1.7 retrieval.
- **3.4 — LLM narrative layer on cards (optional, measured).** Existing `code_cards` LLM pipeline extended to repo/workspace summaries — clearly separated from deterministic facts, snapshot-pinned, hash-gated. Secrets redacted before any prompt.
- **3.5 — False-edge audit check.** `governance/checks/stage3_edges.sh`: dump all cross-repo edges with evidence for human/reviewer spot-verification; false-edge rate recorded in the scorecard.

### Exit criteria
- [ ] Real workspace shows correct extracted `DEPENDS_ON` and ≥ 1 correct `CONSUMES_API` edge; audited false-edge count = 0.
- [ ] Workspace overview endpoint/UI answers "what are these repos and how do they connect?" from extracted data only.

---

# Stage 4 — Agent interface, impact, and the ablation benchmark (≈ 2 weeks)

**Goal:** The index proves its value to a real coding agent, with impact analysis as a first-class primitive.

### Packets

- **4.1 — Impact traversal.** Reverse traversal over calls/imports/references, crossing repos via Stage 3 edges; collects affected symbols/files/repos/endpoints/tests; ranked by confidence × distance; completeness marked. `impact` endpoint + MCP tool.
- **4.2 — Diff impact.** POST a unified diff → changed symbols → impact set (what agents call before editing).
- **4.3 — MCP tool set completion:** `search_code`, `search_semantic`, `find_symbol`, `references`, `repo_card`, `workspace_overview`, `neighbors`, `impact` — each with output contracts an agent can rely on (evidence + snapshot identity always present).
- **4.4 — Ablation benchmark.** Drive a real coding agent over the gold tasks in configurations: **A** grep-only; **B** A + lexical/symbol tools; **C** B + semantic/cards; **D** C + graph/impact; **E** GitNexus (Stage 0 setup). Metrics: tool calls, tokens, files opened, time-to-first-correct-file, cross-repo impacts found, false leads.
- **4.5 — Go/no-go writeup.** `benchmarks/results.md`: per capability, measurable gain / neutral / harmful. **Gates Stage 5+.**

### Exit criteria
- [ ] Impact finds the known cross-repo consumer for ≥ 1 gold task.
- [ ] Ablation results committed for A–E on ≥ 15 tasks; written verdict per capability.

---

# Stage 5 — Freshness & precision (benchmark-gated, ≈ 2–4 weeks)

Only build what Stage 4 justified.

- **5.1 — Incremental indexing hardening.** Extend the existing unchanged-file skip into full diff-driven reindex (changed files → affected symbols/edges/cards only); index-lag metric (HEAD sha vs indexed sha) exposed; polling → webhook trigger.
- **5.2 — Zoekt** behind the `LexicalSearch` port — only if scorecards showed Postgres FTS limits (latency or exact-search quality at workspace scale). Side-by-side comparison recorded.
- **5.3 — SCIP (TypeScript and/or Python)** behind the `CodeParser` port — only if heuristic resolution errors measurably hurt agent tasks. SCIP edges land at confidence 0.99 / completeness exact; tree-sitter remains fallback.
- **5.4 — Ops:** structured logging, per-stage timing, API auth token, workspace isolation test.

### Exit criteria
- [ ] One-file commit reindexes in seconds; index lag observable.
- [ ] Scorecards did not regress; adopted precision upgrades show their promised delta.

---

# Stage 6 — UI evolution (≈ 1–2 weeks, parallelizable)

The Next.js app exists (dashboard, search, graph, files, chat). Evolve, don't rebuild:

- **6.1** Workspace overview view (repos + purposes + extracted connections).
- **6.2** Evidence-first result rendering: every claim shows evidence lines, confidence/completeness, snapshot sha.
- **6.3** Impact view: symbol or pasted diff → ranked impact set.
- **6.4** Hierarchical drill-down: workspace card → repo card → module → symbol → source lines.

### Exit criteria
- [ ] A new engineer can answer "what does this workspace do and how are the repos connected?" from the UI alone, with every claim evidenced. (Playwright covers the flows.)

---

# Stage 7+ — Extensions (each benchmark-gated, rough order)

1. **Agent worktree overlays** — base snapshot + uncommitted diff; highest agent value.
2. **More cross-repo extractors** — shared schemas, message topics, DB tables.
3. **Process/flow cards** — entrypoint → steps → contracts → tests.
4. **Infra topology** — Kubernetes, Terraform, Compose.
5. **Runtime evidence** — OpenTelemetry `OBSERVED_CALLS` vs `STATIC_CALLS`.
6. **Learned ranking / intent classifier** — only once query telemetry exists.

---

## Standing rules (apply to every packet)

1. **No edge without evidence.** Ever. (DB-enforced since R.7.)
2. **Deterministic before LLM.** LLM-inferred structure is always marked inferred; deterministic facts and LLM narrative never blend into one field.
3. **Confidence ≠ completeness.** Report both.
4. **Idempotent, versioned extractors** (parser/prompt/schema versions — pattern exists; keep it universal).
5. **Every answer carries snapshot identity** (`indexed_commit_sha`), and projections never blend rows across snapshots (POC-branch lesson — preserved as a test).
6. **False cross-repo edges are the worst failure mode** — tracked in every scorecard.
7. **New infrastructure requires a measurement**, not an architecture diagram.
8. **GitNexus: study concepts, never copy code** (PolyForm Noncommercial).
9. **Secrets never enter cards, embeddings, or prompts.**
10. **Every retrieval change ships with a scorecard delta**; regressions block merge.
11. **Hexagonal boundary enforced by the local gauntlet** (import-linter), not discipline.
12. **No packet merges without a recorded green local gauntlet + a reviewer verdict**; two consecutive drift verdicts on one topic pause all cron jobs until the human decides.
13. **Branch hygiene:** main is the base; integration is always current with main; packets always branch from and merge into integration; integration promotes to main only at stage exit. Frozen legacy branches never receive new work.

---

# Appendix A — Condensed background spec (reference, non-binding)

The full spec (`software-knowledge-index-project-spec-2.md`) is optional background; this appendix carries everything the reviewer needs to judge intent.

## A.1 Product goal

A **versioned, evidence-backed software knowledge index** that continuously understands multiple repositories as one application and exposes exact, semantic, structural, and impact-aware context to humans and coding agents. It must answer exact questions (*where is `PaymentService.capture()` defined?*), structural (*who calls it?*), semantic (*where do we implement retry behavior?*), architectural (*how does checkout depend on billing?*), and impact questions (*what breaks if this contract changes?*) — drilling from Application → Repository → Module → File → Symbol → exact source lines.

## A.2 Core hypothesis

Most coding-agent inefficiency comes from **context localization and application reconstruction**, not from writing code. A maintained application model should let agents make correct changes with substantially fewer exploratory tool calls, fewer tokens, and fewer wrong assumptions. Success is measured as developer/agent effectiveness on real historical tasks — never as demo quality.

## A.3 Key design principle: no universal retriever

Different representations answer different questions; preserve them instead of collapsing everything into embeddings:

| Representation | Best at |
|---|---|
| Lexical search | Exact strings, identifiers, regex, config |
| Symbol index | Definitions, references, implementations |
| Tree-sitter / AST | Structural understanding |
| Dependency graph | Relationships and impact |
| Vector search | Semantic similarity, concepts |
| Cards | Compressed high-level meaning |
| Git | History and change |
| Contracts / manifests | Cross-repository relationships |
| Runtime telemetry (future) | Actual production behavior |
| LLM | Interpretation and synthesis — never silent authority |

## A.4 Evidence, confidence, completeness

Every relationship records evidence (extractor, repo, commit, file, lines) and a confidence reflecting its source hierarchy: compiler/SCIP > contracts/manifests > tree-sitter structure > heuristics > LLM inference. LLM-created edges are always explicitly marked inferred. **Confidence** ("we are certain these seven callers exist") is distinct from **completeness** ("there may be callers we could not resolve" → `lower_bound`, with causes). Answers must communicate both; unresolved information is surfaced, never silently dropped.

## A.5 Deliberately small ontology

Nodes: Workspace, Repository, Module/Package, File, Symbol (fn/class/method), APIEndpoint, later Service/Topic/Table/Test/Deployment. Edges: CONTAINS, IMPORTS, CALLS, REFERENCES, DEPENDS_ON, PROVIDES_API, CONSUMES_API, TESTS — grown only when a relationship demonstrably improves navigation, impact analysis, or agent context. Cross-repo relationship sources, deterministic first: package manifests, OpenAPI/route definitions and generated clients, shared schemas (protobuf/JSON-schema), message topics, infra manifests, shared DB tables, CI artifacts, shared config keys.

## A.6 GitNexus positioning

GitNexus (repo: abhigyanpatwari/GitNexus) already implements much repository-level intelligence: tree-sitter parsing with language-aware resolution, knowledge graph, BM25 + embeddings + RRF, process discovery, impact traversal, MCP, and repository groups with a Contract Registry for cross-repo links. It validates our hybrid-retrieval assumptions and is the benchmark baseline (config E). Our differentiation lives **above** that layer: a unified multi-repo application graph, persistent versioned cards, a stronger evidence/completeness model, freshness, agent overlays, and eventually runtime evidence. **License: PolyForm Noncommercial 1.0.0 — behaviors and public architecture may be studied and benchmarked; source code must never be copied or mechanically rewritten.**

## A.7 GitNexus evaluation question classes (used in packet 0.4)

1. Where is feature X implemented? 2. What does symbol X do? 3. Who calls X? 4. What does X call? 5. Trace X to Y. 6. What changes if X changes? 7. Which repository consumes endpoint X? 8. Which tests should run after changing X? 9. Where does this value originate? 10. Does equivalent functionality already exist? 11. How does this user action flow across repositories? 12. What architecture knowledge is missing from the index?

## A.8 Evaluation metrics vocabulary

Navigation efficiency (time to first correct file/symbol, files opened, searches, tool calls); model efficiency (input/output tokens, context size); task quality (success, tests passing, wrong files edited, missed cross-repo dependencies); architecture quality (cross-repo impacts detected, correct tests identified); redundancy (duplicate implementation created vs existing one discovered).

## A.9 Security & data governance

The system indexes sensitive private code. Requirements: workspace isolation, repository authorization, encrypted secrets, no cross-workspace retrieval, auditable access, configurable external-LLM use, eventual self-hosted inference. Derived artifacts (cards, embeddings, graph metadata) are sensitive source-derived data; repository credentials must never appear in cards, embeddings, or prompts.

## A.10 Long-term direction (context for prioritization, not scope)

Architecture drift detection, auto-generated architecture docs, change planning, cross-agent coordination on overlapping edits, dead-code/dead-API detection with runtime evidence, migration planning, ownership intelligence. Final target: an agent starts a task with "understand this change" and receives an evidence-backed context package (repos, architecture, existing implementations, exact symbols and ranges, contracts, tests, impacts, history) — spending its reasoning budget on designing and implementing the change instead of reconstructing the system.
