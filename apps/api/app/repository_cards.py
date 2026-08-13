"""Bounded repository-level retrieval projection over persisted facts and Code Cards.

This POC deliberately does not use an LLM or create a second source of truth.  It makes a
commit-pinned Repository Card plus a compact retrieval document that can later be embedded
with the existing provider pipeline.
"""
from collections import Counter
from sqlalchemy import func, select
from app.adapters.outbound.postgres.models import CodeCard, File, Repository, StructuralCard, Symbol

SCHEMA_VERSION = "repository-card-poc-v1"
MAX_MODULES = 12
MAX_CODE_CARD_EXCERPTS = 12
MAX_KEYWORDS = 20


def _module_rows(db, repo_id, indexed_commit_sha):
    cards = db.scalars(
        select(StructuralCard).where(
            StructuralCard.repository_id == repo_id,
            StructuralCard.indexed_commit_sha == indexed_commit_sha,
            StructuralCard.kind.in_(("package", "directory")),
        )
    ).all()
    # Prefer package cards; each path is represented once, with a deterministic fallback.
    by_path = {}
    for card in sorted(cards, key=lambda c: (c.path.count("/"), c.path, c.kind != "package")):
        by_path.setdefault(card.path, card)
    rows = []
    for path, card in by_path.items():
        facts = card.facts or {}
        boundary = facts.get("boundary_edges", [])
        rows.append({
            "path": path,
            "kind": card.kind,
            "direct_file_count": len(facts.get("direct_files", [])),
            "languages": facts.get("languages", {}),
            "boundary_edge_count": sum(item.get("count", 0) for item in boundary),
            "indexed_commit_sha": card.indexed_commit_sha,
            "provenance_fingerprint": card.provenance_fingerprint,
        })
    return sorted(rows, key=lambda r: (-r["boundary_edge_count"], -r["direct_file_count"], r["path"]))[:MAX_MODULES]


def build_repository_card(db, repo: Repository):
    # The repository's indexed commit is the snapshot boundary. Never blend stale
    # projection rows into a card that claims current snapshot provenance.
    snapshot = repo.indexed_commit_sha
    files = db.scalars(
        select(File).where(File.repository_id == repo.id, File.indexed_commit_sha == snapshot)
    ).all()
    files_by_id = {file.id: file for file in files}
    symbols = db.scalars(
        select(Symbol).join(File, File.id == Symbol.file_id).where(
            Symbol.repository_id == repo.id,
            File.repository_id == repo.id,
            File.indexed_commit_sha == snapshot,
        )
    ).all()
    ready_card_count = db.scalar(
        select(func.count(CodeCard.id)).where(
            CodeCard.repository_id == repo.id,
            CodeCard.status == "ready",
            CodeCard.indexed_commit_sha == snapshot,
        )
    ) or 0
    cards = db.execute(
        select(CodeCard, Symbol)
        .join(Symbol, Symbol.id == CodeCard.symbol_id)
        .join(File, File.id == Symbol.file_id)
        .where(
            CodeCard.repository_id == repo.id,
            CodeCard.status == "ready",
            CodeCard.indexed_commit_sha == snapshot,
            Symbol.repository_id == repo.id,
            File.repository_id == repo.id,
            File.indexed_commit_sha == snapshot,
        )
        .order_by(Symbol.qualified_name, Symbol.id)
        .limit(MAX_CODE_CARD_EXCERPTS)
    ).all()
    languages = dict(sorted(Counter(f.language or "unknown" for f in files).items()))
    symbol_types = dict(sorted(Counter(s.symbol_type for s in symbols).items()))
    keywords = []
    excerpts = []
    for card, symbol in cards:
        for keyword in card.details.get("keywords", []):
            if keyword not in keywords and len(keywords) < MAX_KEYWORDS:
                keywords.append(keyword)
        file = files_by_id.get(symbol.file_id)
        excerpts.append({
            "symbol_id": symbol.id,
            "qualified_name": symbol.qualified_name,
            "path": file.path if file else None,
            "summary": card.summary,
            "indexed_commit_sha": card.indexed_commit_sha,
        })
    modules = _module_rows(db, repo.id, snapshot)
    facts = {
        "file_count": len(files),
        "symbol_count": len(symbols),
        "ready_code_card_count": ready_card_count,
        "languages": languages,
        "symbol_types": symbol_types,
        "modules": modules,
        "code_card_excerpts": excerpts,
        "keywords": keywords,
    }
    retrieval_lines = [
        f"Repository: {repo.name}",
        f"Indexed commit: {repo.indexed_commit_sha or 'unknown'}",
        f"Files: {len(files)}; Symbols: {len(symbols)}; Ready code cards: {ready_card_count}",
        "Languages: " + ", ".join(f"{name} ({count})" for name, count in languages.items()),
    ]
    if modules:
        retrieval_lines.append("Modules:")
        retrieval_lines.extend(
            f"- {module['path'] or '.'}: {module['direct_file_count']} direct files, "
            f"{module['boundary_edge_count']} boundary edges"
            for module in modules
        )
    if keywords:
        retrieval_lines.append("Code-card keywords: " + ", ".join(keywords))
    if excerpts:
        retrieval_lines.append("Representative code-card evidence:")
        retrieval_lines.extend(
            f"- {excerpt['qualified_name']} ({excerpt['path']}): {excerpt['summary']}"
            for excerpt in excerpts
        )
    return {
        "repository_id": repo.id,
        "repository": repo.name,
        "indexed_commit_sha": repo.indexed_commit_sha,
        "schema_version": SCHEMA_VERSION,
        "facts": facts,
        "retrieval_document": "\n".join(retrieval_lines),
        "limitations": [
            "Deterministic POC: this card is derived from indexed local facts and ready Code Cards.",
            "It has no LLM-generated repository prose and no cross-repository resolution.",
            "The retrieval document is preview-only; it is not persisted or embedded by this POC.",
        ],
    }
