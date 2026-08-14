# REVIEW-024 — Packet 0.6 local quickstart v1

```yaml
verdict: blocked
packet: "0.6"
pr: 67
head_reviewed: f2aabf9661af14efe79be1cec4b67fb54d903f31
base_reviewed: 8ce836493ffaeba0ddf9b8707a5681cae00a6be6
criteria_checked:
  - "Exact integration...HEAD diff: PASS — 7 files, +160/-2; git diff --check and shell syntax clean; PR CLEAN/MERGEABLE"
  - "Branch/main hygiene: PASS — exact integration base and current origin/main 0954b41 are ancestors of HEAD"
  - "Keyless provider guard: PASS — none/false/none is enforced before Compose startup; no provider spend is recorded"
  - "Stack startup probes: PASS per exact artifact evidence — API docs and web root returned HTTP 200"
  - "Binding fastapi-stack seed/index/search flow: FAIL — the script only starts Compose and probes two roots; it never seeds/indexes the selected FastAPI/Starlette/Pydantic workspace, waits for indexing, searches it, or opens evidence"
  - "Clean-machine Playwright smoke: FAIL — the recorded Playwright run is the pre-existing suite outside the quickstart and does not exercise the promoted Compose artifact's add-repo -> index -> search -> open-evidence flow"
  - "Ephemeral browser API routing: FAIL — web is built with NEXT_PUBLIC_API_URL=http://127.0.0.1:8000/api while quickstart publishes API on an unrelated ephemeral port, so browser-side repository/search operations target the wrong port even though the web root probe passes"
  - "Full relevant LOCAL gauntlet evidence: PARTIAL — API/MCP/web counts, import boundary, build, and basic Compose probes are recorded, but the packet's binding functional quickstart gauntlet is absent"
  - "Test-count ratchet/deleted tests: PASS — no tests deleted; recorded API+MCP total 95 and web unit 70"
  - "Provider/ADR-004, main policy, descopes, hosted CI: PASS — no conflicting provider/default, main, scope, or hosted-CI change"
drift_findings:
  - "The quickstart proves container roots, not the required working keyless product path. This is a concrete promotion-invariant and local-evidence failure."
required_actions:
  - "Make the isolated Compose web artifact use the dynamically published API endpoint (or use a stable isolated loopback mapping that cannot conflict) so browser-side API calls work."
  - "Extend scripts/quickstart_smoke.sh to seed and index the pinned fastapi-stack fixture, wait for successful indexing, execute a deterministic search, and verify returned/openable evidence without credentials or provider calls."
  - "Run Playwright against that exact quickstart stack for add/seed repo -> index -> search -> open evidence, and commit exact output from the complete local gauntlet."
scope_creep_risk: low
```

Packet 0.6 is **blocked** at the reviewed implementation head. Startup is useful progress and the keyless guard is sound, but HTTP 200 on `/docs` and `/` is not the binding quickstart invariant. The promoted artifact must demonstrate the working seed/index/search/evidence path and its browser must actually reach the isolated API.