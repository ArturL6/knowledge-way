# KW-002 — Secure repository admission, authorization, and secret policy

**Priority:** P0  
**Depends on:** KW-001

## Problem
Current APIs are unauthenticated; clone URLs and full source can be exposed, and Git clone/fetch accepts user-controlled remotes. Filename-only secret exclusions are insufficient before external embeddings or chat.

## Scope
- Add principal, tenant/workspace, repository membership, and centralized authorization checks.
- Scope every repository/file/search/job/conversation query in SQL; no UI-only filtering.
- Replace prefix clone-URL validation with parsed scheme/host/port/path policy; reject URL credentials, local/file remotes, loopback/private networks, and unsafe SSH variants.
- Store credential references only; redact remote URLs/errors/logging.
- Add content secret scanning/redaction before persistence, embedding, search, file reads, MCP output, and LLM context.

## Acceptance criteria
- Cross-tenant reads, searches, deletion, sync/reindex, chat, file reads, and MCP calls fail without existence leakage.
- Tests cover URL bypasses, embedded tokens, private-IP SSRF attempts, keys/JWTs/connection strings, and false-positive fixtures.
- API responses never expose local checkout paths, raw credentials, or secret values.
- A documented local single-user mode uses the same authorization code path.
