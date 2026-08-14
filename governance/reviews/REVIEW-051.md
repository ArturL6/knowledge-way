# REVIEW-051 — Packet 0.4 external comparator exact-head re-review

```yaml
verdict: blocked
packet: "0.4"
pr: 77
reviewed_head: "bc2f840eed25dae0b94a7ccf0061b999ba38d9e7"
reviewed_integration_head: "bbbfe25c86c16ba6bb2bc9224017d7687de1e707"
reviewed_at: "2026-08-14T20:29:19+00:00"
criteria_checked:
  - "Exact GitHub PR head equals refreshed refs/pull/77/head: PASS"
  - "HD-006 staleness remediation: PASS (current integration merged normally at 76bfde4 and followed by remediation commit bc2f840; no rebase or force push)"
  - "Packet diff is limited to three benchmark artifacts and excludes STATUS/RUNLOG: PASS"
  - "Packet verify and 25-task validation: PASS"
  - "Runner py_compile and git diff --check: PASS"
  - "Full Python suite: PASS (95 tests)"
  - "Stage-R import boundary check: PASS (2 live contracts kept; deliberate violation rejected)"
  - "Findings claims match committed raw evidence for UID-targeted impact and epistemic fields: FAIL"
drift_findings:
  - "benchmarks/external-comparator-findings.md claims that UID-targeted upstream impact reports 27 symbols, depth counts 3/11/13, a dynamic-dispatch boundary, and epistemic lower-bound, allegedly verbatim in the fixture. The committed observation 06 instead has HTTP 200 with raw_response `Error: Target 'undefined' not found` and contains none of those fields. The runner's request uses `uid`; the captured endpoint did not accept it as a target. This repeats the evidence/prose contradiction blocked in REVIEW-049 and cannot authorize merge."
required_actions:
  - "Correct the eval-server impact invocation so the committed raw observation actually exercises the resolved Route target and captures the returned epistemic, boundary, symbol-count, and depth fields; determine the v1.6.9 payload contract from public CLI/help or observed interface behavior without copying source."
  - "Regenerate the fixture and findings together. Every quantitative and epistemic statement must be directly supported by the committed raw response; if impact remains unavailable, classify it honestly as not-representable or environment-limited and remove unsupported numbers."
  - "Because the packet head will change, refresh integration again. If stale, remediate only by normal merge of current integration plus a subsequent commit under HD-006 §1; never rebase or force-push. Re-run all checks and request exact-head re-review."
scope_creep_risk: low
```

## Independent execution

Immediately before judgment, refs were explicitly refreshed to integration
`bbbfe25c86c16ba6bb2bc9224017d7687de1e707`, main
`d72137f4cfbf3beaf1ae392710b7da489ed1972f`, and PR #77
`bc2f840eed25dae0b94a7ccf0061b999ba38d9e7`. On a detached exact-head
worktree, current-integration ancestry and the required merge-plus-follow-up
history passed. The diff contains only the three packet benchmark artifacts;
packet verify, 25-task validation, runner compilation, diff hygiene, all 95
Python tests, and both import contracts with the deliberate-negative fixture
passed.

No merge is authorized for this SHA. The blocker is evidence integrity: the
committed fixture records a failed impact target while the narrative presents
successful lower-bound impact metrics as if they were in that fixture.
