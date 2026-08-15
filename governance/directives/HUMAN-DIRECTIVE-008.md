# HUMAN-DIRECTIVE-008 — Pull a minimal product UI forward, in parallel with retrieval

**From:** Project owner
**To:** all Knowledge-Way scheduler roles
**Authority:** Owner scope decision. Carves a bounded exception to the rule-12 "UI expansion descoped until after Stage 4" constraint. All other binding rules (hexagon boundary, evidence, no-force-push, merge gate, scorecard-on-retrieval-change, budget, GitNexus isolation) remain in force.

The current web UI is too bare to use: there is no way to create a workspace or add repos to it, and the code-graph page can only show a single symbol's subgraph and only lists repos that were already `ready` at page load. The owner directs building a minimal but usable product UI **now**, in parallel with the retrieval track (Vertex/semantic packet 1.3 continues).

Scope of the authorized UI work (one packet, `apps/web` + read-only API additions only if needed):

1. **Usable code graph.** Repo picker that auto-refreshes the ready-repo list (no stale empty dropdown); ability to select a repo and browse its graph (repo/module overview, not only a single symbol's subgraph); click a node to expand neighbors.
2. **Workspace management UI.** A Workspaces view to create/delete workspaces, add/remove repositories, and pick an active workspace that scopes search and graph. Backed by the existing `/api/workspaces*` endpoints.
3. **Add-repo UX polish.** On the Dashboard, live indexing progress and auto-refresh while a repo indexes, so readiness is visible without a manual reload.

Constraints: reuse existing `/api/*` endpoints where possible (add only read-only endpoints if strictly necessary, behind the same hexagon boundary — no SQL/framework leakage into domain/application); Playwright E2E is mandatory for the web changes; keyless; GitNexus remains inspiration only (no code, no dependency). This is product UI, not GitNexus integration.

This directive does not change the Stage-1 retrieval exit criteria or the ADR-007 target; it runs alongside them.
