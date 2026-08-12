import hashlib
from typing import cast

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import (Base, ProviderAuditLedger, Repository, Workspace, WorkspaceSnapshot,
                        WorkspaceSnapshotRepository)
from app.pilot_audit import (REQUIRED_CAPS, admit_vertex_embedding,
                             record_vertex_embedding_failure, record_vertex_embedding_success)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


class _DB:
    def __init__(self, ledger): self.ledger = ledger
    def get(self, model, identifier): return self.ledger if identifier == "ledger" else None
    def scalars(self, statement):
        return type("Scalars", (), {"all": lambda _: ["repository-a", "repository-b"]})()


def _ledger(**overrides):
    values = {
        "provider": "vertex", "status": "active", "workspace_snapshot_id": "immutable-snapshot",
        "price_source": {"url": "https://cloud.google.com/vertex-ai/pricing", "version": "2026-08-12"},
        "caps": REQUIRED_CAPS.copy(),
        "configuration": {"embedding_model": "text-embedding-005", "embedding_cost_usd_micros_per_document": 100,
                          "repository_ids": ["repository-a", "repository-b"],
                          "intended_embedding_documents": 2, "projected_max_embedding_documents": 150,
                          "embedding_document_input_hashes": [_hash("one"), _hash("two")]},
        "actual": {"embedding_documents": 0, "cost_usd_micros": 0},
    }
    values.update(overrides)
    return type("Ledger", (), values)()


def test_admission_requires_active_priced_unchanged_ledger():
    assert admit_vertex_embedding(_DB(_ledger()), "ledger", ["one"]).provider == "vertex"
    with pytest.raises(RuntimeError, match="price source"):
        admit_vertex_embedding(_DB(_ledger(price_source={})), "ledger", ["one"])
    with pytest.raises(RuntimeError, match="hard caps"):
        admit_vertex_embedding(_DB(_ledger(caps={})), "ledger", ["one"])


def test_admission_blocks_unplanned_duplicate_and_cap_exceeding_inputs():
    for texts, message in ((["unknown"], "planned"), (["one", "one"], "unique")):
        with pytest.raises(RuntimeError, match=message):
            admit_vertex_embedding(_DB(_ledger()), "ledger", texts)
    with pytest.raises(RuntimeError, match="document cap"):
        admit_vertex_embedding(_DB(_ledger(actual={"embedding_documents": 150, "cost_usd_micros": 0})), "ledger", ["one"])
    with pytest.raises(RuntimeError, match="USD 5"):
        admit_vertex_embedding(_DB(_ledger(actual={"embedding_documents": 0, "cost_usd_micros": 5_000_000})), "ledger", ["one"])


class _EventDB(_DB):
    def __init__(self, ledger): super().__init__(ledger); self.added, self.commits = [], 0
    def add(self, row): self.added.append(row)
    def commit(self): self.commits += 1


def test_success_is_evented_accounted_and_prevents_reuse():
    ledger = _ledger(); ledger.id = "ledger"; db = _EventDB(ledger)
    event = record_vertex_embedding_success(db, ledger, model="text-embedding-005", texts=["one", "two"],
                                             input_tokens=3, cost_usd_micros=200)
    assert db.commits == 1 and db.added == [event]
    assert ledger.actual == {"embedding_documents": 2, "cost_usd_micros": 200,
                             "embedding_document_input_hashes": [_hash("one"), _hash("two")]}
    with pytest.raises(RuntimeError, match="previously embedded"):
        admit_vertex_embedding(_DB(ledger), "ledger", ["one"])


def test_success_cannot_understate_price_change_model_or_record_unplanned_input():
    ledger = _ledger()
    for model, texts, cost in (("text-embedding-005", ["one", "two"], 199), ("another", ["one", "two"], 200),
                               ("text-embedding-005", ["unknown"], 100)):
        with pytest.raises(RuntimeError, match="match the ledger model|planned ledger hashes"):
            record_vertex_embedding_success(_EventDB(ledger), cast(ProviderAuditLedger, ledger), model=model,
                                            texts=texts, input_tokens=2, cost_usd_micros=cost)


@pytest.mark.parametrize("overrides", [
    {"workspace_snapshot_id": None},
    {"configuration": {"embedding_model": "text-embedding-005", "embedding_cost_usd_micros_per_document": 100,
                       "repository_ids": [], "intended_embedding_documents": 1, "projected_max_embedding_documents": 1,
                       "embedding_document_input_hashes": [_hash("one")]}},
    {"configuration": {"embedding_model": "text-embedding-005", "embedding_cost_usd_micros_per_document": 100,
                       "repository_ids": ["a"], "intended_embedding_documents": 1, "projected_max_embedding_documents": 1}},
])
def test_admission_requires_snapshot_repository_scope_and_planned_hashes(overrides):
    with pytest.raises(RuntimeError, match="snapshot|one or two|input hash"):
        admit_vertex_embedding(_DB(_ledger(**overrides)), "ledger", ["one"])


def test_admission_rejects_repositories_not_in_pinned_snapshot():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine); db = sessionmaker(bind=engine)()
    db.add(Workspace(id="workspace", name="Workspace")); db.add(Repository(id="repository-a", name="A", clone_url="https://example.test/a.git")); db.commit()
    db.add(WorkspaceSnapshot(id="immutable-snapshot", workspace_id="workspace", manifest_hash="a" * 64, schema_version="workspace-snapshot-v1")); db.commit()
    db.add(WorkspaceSnapshotRepository(snapshot_id="immutable-snapshot", repository_id="repository-a", indexed_commit_sha="a" * 40)); db.commit()
    ledger = _ledger(); guarded_db = type("DB", (), {"get": lambda *_: ledger, "scalars": db.scalars})()
    with pytest.raises(RuntimeError, match="real members"):
        admit_vertex_embedding(guarded_db, "ledger", ["one"])


def test_failure_is_evented_without_inventing_usage():
    ledger = _ledger(); ledger.id = "ledger"; db = _EventDB(ledger)
    event = record_vertex_embedding_failure(db, ledger, model="text-embedding-005", texts=["one"], details={"error_type": "RuntimeError"})
    assert db.commits == 1 and event.status == "failed" and event.cost_usd_micros == 0
    assert ledger.actual == {"embedding_documents": 0, "cost_usd_micros": 0}
