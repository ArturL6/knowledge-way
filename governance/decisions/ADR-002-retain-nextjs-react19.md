# ADR-002 — Retain Next.js + React 19 frontend

- **Status:** Accepted
- **Date:** 2026-08-12
- **Decision owner:** Knowledge-Way roadmap v2

## Context

The repository already contains a Next.js + React 19 application with dashboard, search, graph, files, and chat views. Rebuilding the frontend would not advance the roadmap's measured goals.

## Decision

Retain Next.js + React 19. Packet R.2 adds the Playwright smoke flow
(add repo → index → search → open evidence). Playwright is enforced by the binding
local test gauntlet on any change touching apps/web or a UI-facing contract; CI remains
optional advisory automation per ADR-003.

## Consequences

- No frontend framework replacement is in scope.
- Any UI-facing contract change requires the Playwright smoke flow in the packet gauntlet.
- A replacement proposal requires an ADR and a measurable justification.
