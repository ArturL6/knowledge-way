# REVIEW-015 — Packet R.7a main synchronization

```yaml
verdict: blocked
packet: "R.7a"
pr: 65
head: b766a6bdc6fac7ab15ee65eb8a9877c133b26519
criteria_checked:
  - "Exact integration...HEAD diff inspected: PASS (48 files, +2076/-174; diff-check clean)"
  - "Deliberate origin/main integration: PASS (origin/main is an ancestor; merge 2823ded has integration and main parents)"
  - "Deleted-but-unmigrated test audit: PASS (no test deletion in the packet diff; candidate has 21 tracked API/web test files)"
  - "Test-count ratchet: PASS (reviewer collected 84 API tests; 84 API, 10 MCP, and 70 web unit tests passed)"
  - "Import boundaries and Stage-R evidence: PASS (2 contracts kept; 12 evidence tests passed; deliberate boundary violation rejected)"
  - "fastapi-stack fixture, quickstart stage-exit invariant, main policy, and descopes: PASS"
  - "HUMAN-DIRECTIVE-001 provider decision: FAIL (ADR-004 and runtime defaults select Vertex, while the binding directive requires OpenRouter embeddings/cards)"
  - "CI evidence: FAIL (both API and MCP jobs fail before collection because the merged workflow installs deleted requirements.txt files)"
drift_findings:
  - "ADR-004 lines 26-30 reverses HUMAN-DIRECTIVE-001 section 2 instead of ratifying it: the directive requires EMBEDDING_PROVIDER=openrouter with openai/text-embedding-3-small and CODE_CARD_PROVIDER=openrouter; the candidate defaults both capabilities to Vertex. This is a binding substantive mismatch, not paperwork."
  - "The newly merged .github/workflows/ci.yml invokes apps/api/requirements.txt and apps/mcp/requirements.txt, but those files do not exist after the uv migration. GitHub runs 31735229420 and 31735224875 therefore have red API/MCP jobs without running tests. CI remains advisory, but a knowingly non-executable merged workflow is concrete broken evidence and must not be integrated as-is."
required_actions:
  - "Make ADR-004 and the runtime/.env defaults conform to HUMAN-DIRECTIVE-001 section 2: OpenRouter text-embedding-3-small (1536 dimensions), OpenRouter cards using the existing configured card model, rerank none, and the USD 50/USD 40 controls. If the owner intends Vertex instead, obtain a new explicit directive/ADR before changing this binding decision."
  - "Update the CI workflow to install and run the current uv projects rather than nonexistent requirements.txt files, then attach a green API/MCP/web run (or remove the broken advisory workflow if that is the deliberately documented choice)."
  - "Re-run the full R.7a gauntlet on the corrected head, including web build and Playwright because UI contracts are in the exact diff. Quickstart remains a Stage-R promotion gate owned by packet 0.6 and does not independently block this packet."
scope_creep_risk: medium
```