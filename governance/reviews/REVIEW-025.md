# REVIEW-025 — Packet 0.6 functional quickstart remediation

```yaml
verdict: blocked
packet: "0.6"
pr: 67
head_reviewed: f7b7e2080510b38917034f55d6da33898cfb7e65
base_reviewed: 8ce836493ffaeba0ddf9b8707a5681cae00a6be6
criteria_checked:
  - "Exact integration...HEAD diff: PASS — 9 files, +284/-2; git diff --check, bash syntax, and Node syntax clean; PR MERGEABLE"
  - "Branch/main hygiene: PASS — exact integration base and current origin/main 0954b41 are ancestors of HEAD; no tests are deleted"
  - "Keyless isolation and provider guard: PASS — none/false/none is enforced before Compose startup; Postgres and Redis remain internal; API and web use isolated loopback ports"
  - "Dynamic browser API routing: PASS — the web image is built against the reserved API port and isolated CORS permits the exact web origin"
  - "Working Compose product path: PASS for the single FastAPI repository — independent execution added it in the browser, indexed pinned commit f336ff8, searched, and opened source evidence"
  - "Binding fastapi-stack fixture: FAIL — the promoted quickstart indexes only fastapi/fastapi at f336ff8; the permanent selected workspace is FastAPI 0.115.0 at 40e33e49 plus Starlette 0.38.6 at 8d0cff82 and Pydantic v2.9.2 at 7cedbfb0, with the declared FastAPI-to-provider relationships"
  - "Full relevant LOCAL gauntlet: PASS — reviewer reran API/MCP pytest 95, import-linter 2 kept/0 broken, deliberate boundary rejection, evidence 12, sync-main, web unit 70, Next production build, existing Playwright 1, benchmark unittest 4, and the exact Compose functional smoke"
  - "Test-count ratchet: PASS — API/MCP 95, web 70, benchmark 4; no deleted tests"
  - "Provider/ADR-004 policy: PASS — no provider-default change; keyless mode makes no provider call and does not conflict with the binding Vertex production defaults, OpenRouter fallback, rerank none, or spend controls"
  - "Main policy, descopes, hosted CI: PASS — no main write, retrieval behavior change, hardening, Zoekt, SCIP, UI expansion, or hosted-CI requirement"
drift_findings:
  - "The remediation proves a useful single-repository path, but reinterprets the named fastapi-stack fixture as one unrelated FastAPI revision. That does not verify the owner-selected permanent three-repository workspace that this Stage-R promotion invariant is intended to make operable."
required_actions:
  - "Seed/index all three selected repositories at their immutable Packet 0.1 pins: FastAPI 0.115.0=40e33e49..., Starlette 0.38.6=8d0cff82..., and Pydantic v2.9.2=7cedbfb0...."
  - "Verify all three reach ready at the exact pins and that the quickstart workspace records FastAPI DEPENDS_ON Starlette and FastAPI DEPENDS_ON Pydantic, using the public product contracts available at this stage."
  - "Run the browser search/open-evidence smoke against the seeded selected workspace and commit the exact complete local-gauntlet output. If Packet 0.1 artifacts are needed as inputs, first integrate 0.1 and deliberately merge the updated integration branch into 0.6."
scope_creep_risk: low
```

The exact quickstart now works end to end for one repository, and the prior routing and functional-smoke blockers are fixed. Packet 0.6 remains **blocked** only on the concrete fixture-scope mismatch: Stage-R promotion must prove the permanent selected `fastapi-stack`, not a one-repository substitute.