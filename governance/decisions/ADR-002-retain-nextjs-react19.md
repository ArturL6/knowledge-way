# ADR-002 — Retain Next.js + React 19 frontend

- **Status:** Accepted
- **Date:** 2026-08-12
- **Decision owner:** Knowledge-Way roadmap v2

## Context

The repository already contains a Next.js + React 19 application with dashboard, search, graph, files, and chat views. Rebuilding the frontend would not advance the roadmap's measured goals.

## Decision

Retain Next.js + React 19. Stage R adds the Playwright smoke flow and CI enforcement; later stages evolve the existing UI only when the API contracts and benchmarks justify it.

## Consequences

- No frontend framework replacement is in scope.
- Any UI-facing contract change requires the Playwright smoke flow in the packet gauntlet.
- A replacement proposal requires an ADR and a measurable justification.
