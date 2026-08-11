"""Versioned, provider-neutral retrieval-document projections over canonical facts."""
import hashlib
import json
from sqlalchemy import select
from app.models import File, Repository, RetrievalDocument, StructuralCard, WorkspaceDependency

SCHEMA_VERSION = "retrieval-document-v1"
KINDS = {"repository", "module", "contract"}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _persist(db, *, kind, subject_id, parent_id, repository_id, indexed_commit_sha, source, provenance, content):
    source_fingerprint = fingerprint(source)
    provenance_fingerprint = fingerprint(provenance)
    content_hash = hashlib.sha256(content.encode()).hexdigest()
    existing = db.scalar(select(RetrievalDocument).where(
        RetrievalDocument.kind == kind, RetrievalDocument.subject_id == subject_id,
        RetrievalDocument.parent_id == parent_id, RetrievalDocument.repository_id == repository_id,
        RetrievalDocument.indexed_commit_sha == indexed_commit_sha,
        RetrievalDocument.source_fingerprint == source_fingerprint,
        RetrievalDocument.provenance_fingerprint == provenance_fingerprint,
        RetrievalDocument.content_hash == content_hash,
    ))
    if existing:
        return existing
    row = RetrievalDocument(kind=kind, subject_id=subject_id, parent_id=parent_id,
        repository_id=repository_id, indexed_commit_sha=indexed_commit_sha,
        source_fingerprint=source_fingerprint, provenance_fingerprint=provenance_fingerprint,
        content_hash=content_hash, schema_version=SCHEMA_VERSION, content=content)
    db.add(row)
    return row


def rebuild_repository_documents(db, repo: Repository):
    """Persist deterministic projections pinned to the repository's indexed snapshot."""
    commit = repo.indexed_commit_sha
    if not commit:
        return []
    files = db.scalars(select(File).where(File.repository_id == repo.id, File.indexed_commit_sha == commit)).all()
    rows = [_persist(db, kind="repository", subject_id=repo.id, parent_id=None,
        repository_id=repo.id, indexed_commit_sha=commit,
        source={"files": sorted((f.path, f.content_hash) for f in files)},
        provenance={"repository_id": repo.id, "indexed_commit_sha": commit},
        content="\n".join([f"Repository: {repo.name}", f"Indexed commit: {commit}", f"Files: {len(files)}"]))]
    cards = db.scalars(select(StructuralCard).where(
        StructuralCard.repository_id == repo.id, StructuralCard.indexed_commit_sha == commit,
        StructuralCard.kind.in_(("package", "directory")))).all()
    for card in sorted(cards, key=lambda c: (c.path, c.kind)):
        facts = card.facts or {}
        rows.append(_persist(db, kind="module", subject_id=f"{card.kind}:{card.path}", parent_id=repo.id,
            repository_id=repo.id, indexed_commit_sha=commit,
            source={"structural_card": card.content_fingerprint},
            provenance={"structural_card": card.provenance_fingerprint, "indexed_commit_sha": commit},
            content="\n".join([f"Module: {card.path or '.'}", f"Repository: {repo.name}", f"Indexed commit: {commit}",
                f"Kind: {card.kind}", f"Facts: {json.dumps(facts, sort_keys=True, separators=(',', ':'))}"])))
    dependencies = db.scalars(select(WorkspaceDependency).where(WorkspaceDependency.source_repository_id == repo.id)).all()
    for dependency in sorted(dependencies, key=lambda d: d.id):
        rows.append(_persist(db, kind="contract", subject_id=dependency.id, parent_id=repo.id,
            repository_id=repo.id, indexed_commit_sha=commit,
            source={"dependency": [dependency.workspace_id, dependency.source_repository_id, dependency.target_repository_id, dependency.package_name, dependency.import_path, dependency.reason, dependency.note]},
            provenance={"evidence": "declared-workspace-dependency", "workspace_id": dependency.workspace_id, "indexed_commit_sha": commit},
            content="\n".join(["Declared repository dependency (not import/call resolution)", f"Source repository: {repo.name}",
                f"Indexed commit: {commit}", f"Target repository id: {dependency.target_repository_id}",
                f"Package: {dependency.package_name or ''}", f"Import path: {dependency.import_path or ''}", f"Reason: {dependency.reason or ''}"])))
    db.flush()
    return rows


def document_out(row, preview=False):
    result = {key: getattr(row, key) for key in ("id", "kind", "subject_id", "parent_id", "repository_id", "indexed_commit_sha", "source_fingerprint", "provenance_fingerprint", "content_hash", "schema_version", "created_at")}
    if preview:
        result["content"] = row.content
    return result
