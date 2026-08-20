# REVIEW-062 — Packet K.1 query digestion and BM25 re-scoring

```yaml
verdict: needs_changes
packet: "K.1"
pr: 84
reviewed_head_sha: "eca7b9815da32a2652db4088c2b2c03efd68aeb6"
reviewed_integration_head: "e9196a9f06b6cf35af8be2bd832073fc8494b47e"
semantic_guard: awaiting_owner
criteria_checked:
  - "Exact-head identity: PASS (refreshed packet ref and GitHub PR headRefOid both eca7b9815da32a2652db4088c2b2c03efd68aeb6)"
  - "Strict K.1 scope and packet hygiene: PASS (three retrieval/test files only; no STATUS/RUNLOG, K.2/K.3, or comparator material)"
  - "Focused/full tests: PASS (independent exact-head run: 116 passed; focused search coverage included)"
  - "Hexagonal boundaries: PASS (import-linter: 2 contracts kept, 0 broken)"
  - "Current integration compatibility: PASS (no-conflict --no-commit merge simulation with e9196a9)"
  - "BM25 ranking behavior: FAIL (candidates remain in ts_rank_cd order; computed BM25 scores are attached but the lexical list is never sorted by those scores before text-mode RRF or hybrid fusion, so BM25 does not re-rank results)"
  - "Exact-head K.0 inheritance: FAIL (packet head predates landed K.0; merge current integration into the packet branch with a merge commit, never rebase, before producing binding evidence)"
  - "Keyless scorecard gate: FAIL (no exact-head keyless scorecard or demonstrated text hit@5/text p95 delta; PR body explicitly contains only local tests)"
  - "Semantic scorecard: AWAITING_OWNER (authorized ADC path is absent; no fallback provider may be used)"
  - "Disk audit: PASS (/ has 11G available; no prune threshold crossed)"
drift_findings:
  - "BM25 scores currently have no ranking effect because retrieval consumes lexical list order, which remains the SQL ts_rank_cd order."
required_actions:
  - "Sort the bounded lexical candidate list deterministically by descending BM25 score (stable evidence-key tie-break) before text-mode RRF and hybrid fusion; add an integration-level regression test proving that BM25 changes result order rather than only score fields."
  - "Merge refreshed origin/integration/roadmap-v2 into packet/K.1-query-digestion-bm25 with a normal merge commit; do not rebase or force-push. Preserve all landed K.0 keyless defaults, caller semantic settings, ADC fail-fast/read-only mount, and disposable browser preparation."
  - "Run and commit an exact-new-head hermetic keyless scorecard with pinned served-manifest verification and teardown. Demonstrate materially improved text hit@5 toward >=0.40 and improved text p95, and preserve the dual-scorecard gates."
  - "Keep semantic_guard=awaiting_owner while /home/hermes/.gcloud-kw/application_default_credentials.json is absent; never use a fallback provider. Mandatory follow-up: the first post-ADC semantic-enabled scorecard must confirm hybrid >=0.68 or reopen drift."
  - "Remediate only with new commits on the packet branch; do not start K.2 or K.3 and do not edit STATUS/RUNLOG there."
scope_creep_risk: low
```

## Independent execution

The review used a detached disposable worktree at exact PR head
`eca7b9815da32a2652db4088c2b2c03efd68aeb6`. The full Python suite passed with
116 tests and import-linter kept both contracts. A no-commit merge simulation
against freshly fetched integration head `e9196a9f06b6cf35af8be2bd832073fc8494b47e`
completed without conflicts.

The implementation computes BM25 values for the bounded Postgres candidate
window, but appends candidates in the original `ts_rank_cd DESC` SQL order.
Single-mode text retrieval then runs RRF over that list order, and hybrid fusion
does the same. Because neither path sorts by the new BM25 score, the advertised
BM25 re-scoring does not actually alter rank. Unit tests cover the formula but do
not catch this retrieval-level defect.

The branch also predates K.0 and has no exact-head keyless scorecard. ADC remains
absent at the sole authorized path, so semantic regression is correctly
`awaiting_owner`; this does not excuse the keyless gate. Any new packet head
requires a fresh independent review.