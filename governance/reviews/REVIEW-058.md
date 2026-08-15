# REVIEW-058 — Packet 1.5 weighted RRF fusion

```yaml
verdict: on_track
packet: "1.5"
pr: 81
reviewed_head: "5917b04b9623f0f32c3b880405af453264c46685"
reviewed_integration_head: "7944f2e"
reviewed_at: "2026-08-15T15:55:00+00:00"
criteria_checked:
  - "Exact PR head 5917b04; mergeable; diff = pure fusion module + config + search wiring + tests + one scorecard json; no STATUS/RUNLOG; no gitnexus: PASS"
  - "pytest re-executed at head: PASS (113, +10 vs 103)"
  - "lint-imports: PASS (2 kept, 0 broken; new app/domain/retrieval.py is pure — no adapter/framework imports)"
  - "Weighted RRF correctness: semantic=1.0 > lexical(0.5)+symbol(0.4)=0.9, so two weak modes cannot outvote one strong mode; single-mode order unchanged (constant scaling); dedupe/tie-break preserved; unit tests on constructed rankings prove the dilution fix: PASS"
  - "Embedded scorecard (reviewer-run, full fastapi-stack, 19,147 chunks): hybrid hit@5 = 0.68 >= semantic 0.64 — the hybrid>=every-mode property HOLDS and reverses the prior 0.56<0.60 regression: PASS"
drift_findings: []
required_actions: []
observations:
  - "Stage-1 exit criterion 'hybrid >= every single mode' is now MET; hybrid hit@5 0.68 far exceeds the ADR-007 0.44 target and the GitNexus 0.44 reference. Remaining Stage-1 gaps: p95 hybrid <=1s (currently ~3.5s) and exact/quoted hit@1>=0.9."
  - "Asymmetry (honestly flagged by implementer): a gold row found ONLY by lexical/symbol can be outranked by a lone semantic hit — inherent to trusting semantic more. Empirically harmless on the gold set (hybrid 0.68 is the best mode)."
  - "Recurring pre-existing bug reconfirmed: docker-compose worker command `python -m app.worker` is a dead shim (real entrypoint app.adapters.outbound.rq_jobs.worker). File separately."
  - "Embedding-reuse cache confirmed working (reindex to pinned SHA made no extra Vertex calls); spend stayed within the approved ~$0.46-0.79."
scope_creep_risk: low
```

## Independent execution
Re-ran at head 5917b04: pytest 113 passed, lint-imports 2/0. Confirmed cc84891..5917b04 adds only the scorecard JSON (code identical to the already-reviewed fusion module). Reviewer-run embedded scorecard on the full pinned corpus confirms hybrid hit@5 0.68 >= semantic 0.64. Per HD-004 this authorizes merge of PR #81.
