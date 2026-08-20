# HUMAN-DIRECTIVE-011 — Unblock the benchmark path: K.0, credentials, disk hygiene

**From:** Project owner · **Date:** 2026-08-20
**To:** kw-navigator, kw-implementer, kw-benchmark
**Authority:** Owner directive; ratify as the next ADR via the normal flow. Highest directive number wins. HD-009/HD-010 remain fully in force; this directive only clears the blockers the benchmark job correctly reported (five blocked runs on 2026-08-20) so the K-sprint's scorecard gates can function.

---

## 1. Micro-packet K.0 — semantic-capable quickstart provisioning (insert BEFORE K.1's scorecard gate)

The benchmark job found a real defect: `scripts/quickstart_smoke.sh` hard-codes `EMBEDDING_PROVIDER=none`, so a semantic-enabled stack can never be provisioned even with valid credentials; additionally, disposable worktrees lack Playwright dependencies, failing the browser smoke.

**Scope (small, surgical):**
1. `scripts/quickstart_smoke.sh` honors caller-provided environment: `EMBEDDING_PROVIDER`, `VERTEX_PROJECT_ID`, `CODE_CARDS_ENABLED`, `RERANK_PROVIDER`, and the ADC volume mount. **When nothing is set, keyless (`EMBEDDING_PROVIDER=none`) remains the default** — the owner's keyless quickstart experience is unchanged.
2. When `EMBEDDING_PROVIDER=vertex` is requested, the script verifies the ADC file exists at the expected path before starting the stack and fails fast with a clear message if not.
3. Disposable worktrees install web/Playwright dependencies before the browser smoke (e.g., `npm ci` + `npx playwright install --with-deps chromium` in the worktree, or an equivalently cached mechanism).
4. No product retrieval code changes in this packet.

**Exit criteria:** on one and the same integration head, the benchmark job produces BOTH a keyless scorecard and a semantic-enabled scorecard hermetically (own stack, pinned corpora manifest verified, teardown); keyless default behavior unchanged (existing quickstart tests pass).

**Sequencing:** K.0 → then K.1's exit is measured against both scorecards per HD-010 §3. If K.1 implementation work is already in progress, it may continue in parallel, but its PR cannot pass review before K.0 has landed and both scorecards exist.

## 2. Credentials — owner action recorded (agents: verify, don't wait blindly)

The owner is provisioning Vertex ADC at exactly:

```text
/home/hermes/.gcloud-kw/application_default_credentials.json   (chmod 600)
```

for project `ai-tinker-lab` (embedding model `text-embedding-005` @ 768, per ADR-004/005). Agent behavior:

1. **Benchmark job:** keep the current correct behavior — check the path each tick; the first tick after the file appears (and K.0 is merged) runs the binding semantic-enabled scorecard. Continue producing keyless scorecards in the meantime so K-packet keyless targets are measurable immediately.
2. **Navigator:** while ADC is absent, semantic-regression checks are `awaiting_owner` — reviews may still approve K-packets on keyless evidence PLUS a mandatory follow-up condition recorded in the review: "semantic-enabled regression check to be confirmed by the first post-ADC scorecard; regression = reopen as drift." This keeps the sprint moving without weakening the ≥0.68 guard.
3. Never work around missing credentials with the fallback provider (corpus-consistency rule stands).

## 3. Disk hygiene (standing rule; the job machine hit 474 MB free today)

Hermetic runs build Docker images every cycle; unbounded build cache will recur.

1. **Benchmark job:** before each provisioning attempt, check free space; if < 5 GB, run `docker builder prune -af` (build cache only) and log the reclaimed amount; if still < 5 GB, block with a clear `disk` reason instead of attempting the build.
2. **Every job's teardown:** remove its disposable images/volumes as already practiced; additionally prune dangling images older than 24h.
3. **Navigator's daily audit:** include `df -h /` output; below 10 GB free two audits in a row → drift flag for the owner (machine needs bigger disk or an external prune cron).
4. Never prune volumes belonging to a running stack; never use `docker system prune --volumes` in automation (data-destructive breadth) — build-cache and dangling-image pruning only.

## 4. Processing

**Implementer, first tick:** commit this file to `governance/directives/HUMAN-DIRECTIVE-011.md`; ratifying ADR; insert K.0 into STATUS ahead of the K.1 scorecard gate.
**Navigator, next tick:** verify the ADR; issue `next_instruction: K.0` (or approve the parallel arrangement per §1 if K.1 is mid-flight); apply the §2.2 review convention; add §3 checks to the daily audit.
**Benchmark job:** adopt §2.1 and §3.1 behavior immediately (they refine, not contradict, the existing contract).

**Success state:** K.0 merged; ADC present; the same head carries both a keyless and a semantic-enabled scorecard; K.1 reviewed against real numbers; disk never again the reason a scorecard didn't happen.
