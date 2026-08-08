# KW-003 — Tree-sitter facts and explainable code graph

**Priority:** P0  
**Depends on:** KW-001, KW-002

## Goal
Replace declaration regexes with parser facts and turn `SymbolEdge` into a reliable, navigable PostgreSQL graph.

## Scope
- Parser interface: declarations, scopes, imports, references, diagnostics; start with Python and TypeScript/TSX.
- Persist stable symbol keys, qualified names, parent symbols, accurate byte/line ranges, signatures, parser version.
- Persist `CONTAINS`, `IMPORTS`, `CALLS`, `INHERITS`, and `IMPLEMENTS` only where evidence exists.
- Persist unresolved/ambiguous references instead of inventing targets.
- Resolution taxonomy: `EXACT_SCOPE` 1.00, `EXACT_IMPORT` .95, `UNIQUE_QUALIFIED` .90, `UNIQUE_LOCAL_NAME` .80, `TYPE_INFERRED` .65, `AMBIGUOUS`, `UNRESOLVED`.
- Add outgoing/incoming/file-source adjacency indexes and edge source-range provenance.

## Acceptance criteria
- Fixtures cover nested symbols, aliases, direct/qualified calls, duplicate target names, TypeScript exports, Unicode offsets, and syntax-error diagnostics.
- Edge results include source citation, target or unresolved target name, confidence, resolution kind, parser version, and commit SHA.
- Duplicate names never silently resolve to an arbitrary symbol.
- Reindexing the same commit is idempotent and does not duplicate active graph facts.
