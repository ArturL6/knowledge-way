import pytest

from app.pilot_audit import REQUIRED_CAPS, admit_vertex_embedding


class _DB:
    def __init__(self, ledger): self.ledger = ledger
    def get(self, model, identifier): return self.ledger if identifier == "ledger" else None


def _ledger(**overrides):
    values = {
        "provider": "vertex", "status": "active",
        "price_source": {"url": "https://cloud.google.com/vertex-ai/pricing", "version": "2026-08-12"},
        "caps": REQUIRED_CAPS.copy(),
        "configuration": {"embedding_model": "text-embedding-005"},
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
