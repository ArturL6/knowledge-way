# REVIEW-049 — Packet 0.4 external comparator local test drive

```yaml
verdict: blocked
packet: "0.4"
pr: 75
reviewed_head: "b7dd3e90aef9c1f9a28f7a474ee895879f4e839a"
reviewed_at: "2026-08-14T18:28:57+00:00"
criteria_checked:
  - "Exact PR head matches refreshed refs/pull/75/head: PASS"
  - "Packet branch excludes STATUS and RUNLOG governance writes: PASS"
  - "Packet verify (benchmarks/external-comparator-findings.md exists): PASS"
  - "Gold-task validation: PASS (25 provenance-backed tasks)"
  - "Full Python suite: PASS (95 tests)"
  - "Stage-R import boundary check: PASS (2 contracts kept; deliberate violation rejected)"
  - "Runner py_compile and git diff --check: PASS"
  - "Current-integration mergeability: PASS"
  - "All 12 PLAN Appendix A.7 classes actually exercised with replay-bound raw evidence: FAIL"
  - "HUMAN-DIRECTIVE-005 UID-before-trace and context/impact epistemic capture: FAIL"
  - "Findings agree with committed raw fixture: FAIL"
drift_findings:
  - "The runner does not resolve a symbol UID. It sends the bare string Route in every request field, including impact, despite the findings claiming Class:starlette/routing.py:Route was resolved and a UID-targeted impact was observed. Class 5 never calls trace at all; it reuses context and labels the absent target pair not-representable. This does not execute the PLAN A.7 trace question class or satisfy HD-005 section 4.6."
  - "The prose's impact evidence is not the committed raw observation. Findings report 27 upstream symbols with depth counts 3/11/13 and an exact epistemic field, while observation 06 reports 19 dependencies with depth counts 15/4 and only rendered lower-bound prose. The reproducible fixture therefore cannot substantiate the stated result."
  - "The runner hard-codes classifications before observing responses and exercises one shared Route anchor rather than any identified applicable gold-task cases. The packet narrative says gold tasks are applicable, but no task IDs, task questions, or task-oracle comparisons are run or captured. This falls short of the issued objective to evaluate applicable gold tasks and makes correct/partial labels non-reproducible judgments."
required_actions:
  - "Resolve and record exact symbol UIDs through eval-server before context/impact/trace calls. Select a concrete source/destination pair and execute the trace class with --from-uid/--to-uid-equivalent request fields; if the eval-server cannot represent trace, capture the actual attempted request/error rather than substituting context."
  - "Regenerate the raw fixture and findings from one bound run so impact count, depth counts, epistemic value, and boundary text agree. Preserve structured response fields (or the complete raw HTTP response) needed to verify exact versus lower-bound."
  - "Exercise a documented, representative subset of applicable committed gold tasks, record task IDs and oracle-based classification rationale, and make classification a reviewed output rather than a constant silently assigned before execution. Honest not-representable/environment-limited results remain acceptable."
  - "Re-run packet verify, validate_tasks, 95-test suite, import boundaries, py_compile, diff check, and current-integration merge simulation; then publish a new exact head for re-review."
scope_creep_risk: medium
```

## Independent execution

Reviewed detached exact head `b7dd3e90aef9c1f9a28f7a474ee895879f4e839a` after refreshing integration, main, and PR refs. `python3 benchmarks/validate_tasks.py` passed with 25 tasks; `uv run pytest -q` passed 95 tests; `governance/checks/stageR_import_boundary.sh` passed both live contracts and its deliberate-negative fixture; runner compilation, packet verify, patch hygiene, and current-integration merge simulation passed.

The block is evidence integrity and protocol coverage, not application-code quality. No merge is authorized for this SHA.