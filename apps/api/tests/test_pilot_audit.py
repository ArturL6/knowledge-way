import pytest

from app.pilot_audit import (REQUIRED_CAPS, admit_vertex_embedding,
                             record_vertex_embedding_failure, record_vertex_embedding_success)


class _DB:
    def __init__(self, ledger): self.ledger = ledger
    def get(self, model, identifier): return self.ledger if identifier == "ledger" else None


def _ledger(**overrides):
    values = {
        "provider": "vertex", "status": "active",
        "price_source": {"url": "https://cloud.google.com/vertex-ai/pricing", "version": "2026-08-12"},
        "caps": REQUIRED_CAPS.copy(),
        "configuration": {"embedding_model": "text-embedding-005", "embedding_cost_usd_micros_per_document": 100},
        "actual": {"embedding_documents": 10, "cost_usd_micros": 0},
    }
    values.update(overrides)
    return type("Ledger", (), values)()


def test_admission_requires_active_priced_unchanged_ledger():
    assert admit_vertex_embedding(_DB(_ledger()), "ledger", 1).provider == "vertex"
    with pytest.raises(RuntimeError, match="price source"):
        admit_vertex_embedding(_DB(_ledger(price_source={})), "ledger", 1)
    with pytest.raises(RuntimeError, match="hard caps"):
        admit_vertex_embedding(_DB(_ledger(caps={})), "ledger", 1)


def test_admission_blocks_document_and_cost_cap_before_provider_call():
    with pytest.raises(RuntimeError, match="document cap"):
        admit_vertex_embedding(_DB(_ledger(actual={"embedding_documents": 150, "cost_usd_micros": 0})), "ledger", 1)
    with pytest.raises(RuntimeError, match="USD 5"):
        admit_vertex_embedding(_DB(_ledger(actual={"embedding_documents": 0, "cost_usd_micros": 5_000_000})), "ledger", 1)
    with pytest.raises(RuntimeError, match="USD 5"):
        admit_vertex_embedding(_DB(_ledger(configuration={"embedding_model": "text-embedding-005", "embedding_cost_usd_micros_per_document": 5_000_000}, actual={"embedding_documents": 10, "cost_usd_micros": 0})), "ledger", 1)


class _EventDB(_DB):
    def __init__(self, ledger):
        super().__init__(ledger)
        self.added, self.commits = [], 0
    def add(self, row): self.added.append(row)
    def commit(self): self.commits += 1


def test_successful_embedding_is_evented_and_atomically_accounted():
    ledger = _ledger()
    ledger.id = "ledger"
    db = _EventDB(ledger)
    event = record_vertex_embedding_success(
        db, ledger, model="text-embedding-005", texts=["one", "two"],
        input_tokens=3, cost_usd_micros=200, details={"output_dimensions": 768},
    )
    assert db.commits == 1
    assert db.added == [event]
    assert ledger.actual == {"embedding_documents": 12, "cost_usd_micros": 200}
    assert event.operation == "embedding"
    assert event.input_tokens == 3
    assert event.cost_usd_micros == 200
    assert event.input_hash


def test_admission_requires_deterministic_price_accounting():
    with pytest.raises(RuntimeError, match="price accounting"):
        admit_vertex_embedding(_DB(_ledger(configuration={"embedding_model": "text-embedding-005"})), "ledger", 1)


def test_failed_provider_call_is_evented_without_inventing_usage():
    ledger = _ledger()
    ledger.id = "ledger"
    db = _EventDB(ledger)
    event = record_vertex_embedding_failure(
        db, ledger, model="text-embedding-005", texts=["one"],
        details={"error_type": "RuntimeError", "message": "rejected"},
    )
    assert db.commits == 1
    assert event.status == "failed"
    assert event.cost_usd_micros == 0
    assert event.input_tokens is None
    assert ledger.actual == {"embedding_documents": 10, "cost_usd_micros": 0}
