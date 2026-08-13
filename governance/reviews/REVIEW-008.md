---
verdict: drift
packet: "R.4"
reviewed_head_sha: "869eabdd133479081e1b6033e0e9e6d56970fd27"
criteria_checked:
  - "Explicit STATUS handoff is pr_open and matching PR #61 is open from packet/R.4-hexagon-adapters into integration/roadmap-v2: PASS"
  - "Fetched exact GitHub PR head and diff; PR head, remote packet head, and checked-out reviewed SHA equal 869eabdd133479081e1b6033e0e9e6d56970fd27: PASS"
  - "Packet-to-integration PR direction and ancestry: PASS; fetched origin/integration/roadmap-v2 is an ancestor of the packet head"
  - "One-packet-per-branch/PR and integration handoff hygiene: FAIL; GitHub's base remains 2d6993ac and does not contain the recorded R.3 integration merge, so PR #61 includes R.3 packaging/governance changes and prior review artifacts in addition to R.4"
  - "Committed IMPLEMENTATION-R.4 evidence for exact reviewed SHA: FAIL; the evidence records commands and results but names neither reviewed head 869eabdd133479081e1b6033e0e9e6d56970fd27 nor a tested implementation SHA with an accounted-for evidence-only commit"
  - "Exact STATUS verify command pytest -q: PASS independently; 70 tests passed with 209 warnings"
  - "FastAPI endpoint regression tests: PASS independently; readonly, graph, workspaces, and repository-card suites returned 7 passed with 39 warnings"
  - "Python compilation, compatibility identity check, port declaration test, and PR diff whitespace check: PASS"
  - "Eight required application Protocols exist without framework/adapter imports: PASS"
  - "Required in-memory fake for every port and use-case tests without Docker: FAIL; no in-memory fakes were added, and test_ports.py checks only that eight runtime-checkable Protocol declarations exist"
  - "Outbound moves and compatibility: PASS in inspected R.4 implementation; PostgreSQL, tree-sitter, provider, Git CLI, and RQ modules are under specified adapters, with legacy compatibility shims preserving object identity where checked"
  - "Static ruff, import-linter, and type-check commands: NOT AVAILABLE; no tools/configuration exist yet, with boundary enforcement assigned to R.6"
  - "Playwright: NOT APPLICABLE; apps/web and UI-facing contracts are untouched by R.4"
  - "Retrieval scorecard: NOT APPLICABLE; R.4 does not change retrieval behavior"
  - "PLAN scope, no weakened criteria, no unjustified infrastructure, standing evidence/snapshot rules, and no PLAN change: PASS except for the branch/evidence/fake-test findings above"
drift_findings:
  - "PR #61 is not an isolated R.4 packet against its actual GitHub base. origin/integration/roadmap-v2 is still 2d6993ac, while STATUS records R.3 merged at 08f025b and the packet was created from unpublished local integration commit fc2371a. Consequently the exact PR diff includes R.3's pyproject/uv/Docker/governance work and prior reviews, violating one packet per branch/PR and making the base state inconsistent with STATUS."
  - "IMPLEMENTATION-R.4.md is not SHA-bound. It does not identify 869eabdd133479081e1b6033e0e9e6d56970fd27 or any tested implementation SHA, so the required evidence cannot be proven to cover the exact reviewed head."
  - "PLAN.md requires every port to have an in-memory fake and use-case tests to run without Docker. R.4 defines eight Protocols but supplies no fakes; its sole new test verifies declaration count/runtime-checkability rather than usable fake-backed boundaries."
required_actions:
  - "Publish the already reviewed R.3 integration merge to integration/roadmap-v2, then merge that actual remote integration base into the R.4 packet branch (or otherwise update it without force-pushing) so GitHub PR #61's diff contains only R.4 work."
  - "Provide an in-memory fake for each of RepoStore, SourceControl, LexicalSearch, VectorSearch, CodeParser, LLM, Embeddings, and JobQueue, and exercise them through application/use-case contract tests that require no Docker."
  - "After remediation, rerun pytest -q, applicable endpoint tests, compilation/static checks, and git diff --check; commit IMPLEMENTATION-R.4 evidence naming the exact tested implementation SHA and explicitly account for any later evidence/status-only commit before returning STATUS to pr_open."
scope_creep_risk: medium
---

# REVIEW-008 — R.4 hexagonal adapters

## Verdict

`drift` — promotion of PR #61 is blocked at reviewed head `869eabdd133479081e1b6033e0e9e6d56970fd27`.

## Independent review record

The reviewer fetched the exact open PR head and GitHub-base diff, inspected the adapter moves, ports, compatibility shims, tests, governance evidence, and branch graph, and independently reran the packet verifier and applicable endpoint regressions. The implementation is behavior-preserving under the available suite: `pytest -q` returned 70 passing tests, selected FastAPI endpoint tests returned 7 passing tests, compilation and whitespace checks passed, and compatibility identities were preserved.

Promotion is nevertheless blocked. The actual remote integration base has not received the STATUS-recorded R.3 merge, causing PR #61 to include prior-packet content; implementation evidence is not bound to the reviewed SHA; and the mandatory in-memory fakes for the eight ports are absent. Playwright and a retrieval scorecard are not applicable. This is the first R.4 drift verdict and no consecutive same-topic drift exists, so no drift flag or global implementation pause is triggered.