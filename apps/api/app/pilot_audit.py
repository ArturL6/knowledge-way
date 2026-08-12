"""Hard local admission guard for the bounded Vertex pilot.

This deliberately runs before ADC is refreshed or a provider request is made.  The ledger is
created by an operator/migration workflow; this module never creates an implicit ledger.
"""
from sqlalchemy.orm import Session

from app.models import ProviderAuditLedger

REQUIRED_CAPS = {
    "cost_usd_micros": 5_000_000,
    "embedding_documents": 150,
    "llm_calls": 30,
    "llm_input_tokens": 100_000,
    "llm_output_tokens": 15_000,
}


def admit_vertex_embedding(db: Session, ledger_id: str, document_count: int) -> ProviderAuditLedger:
    """Return an active, priced ledger only when this bounded request fits its hard caps.

    A missing or malformed price source is a blocker: callers must not substitute estimated
    pricing for an unaccountable paid request.
    """
    ledger = db.get(ProviderAuditLedger, ledger_id)
    if ledger is None or ledger.provider != "vertex" or ledger.status != "active":
        raise RuntimeError("Vertex embedding blocked: active persistent pilot audit ledger not found")
    if not isinstance(ledger.price_source, dict) or not ledger.price_source.get("url") or not ledger.price_source.get("version"):
        raise RuntimeError("Vertex embedding blocked: deterministic provider price source/version is required")
    if not isinstance(ledger.caps, dict) or any(ledger.caps.get(key) != value for key, value in REQUIRED_CAPS.items()):
        raise RuntimeError("Vertex embedding blocked: pilot ledger hard caps are missing or changed")
    if not isinstance(ledger.configuration, dict) or not ledger.configuration.get("embedding_model"):
        raise RuntimeError("Vertex embedding blocked: ledger must record the exact embedding model")
    actual = ledger.actual if isinstance(ledger.actual, dict) else {}
    used = actual.get("embedding_documents", 0)
    cost = actual.get("cost_usd_micros", 0)
    if not isinstance(used, int) or not isinstance(cost, int) or used < 0 or cost < 0:
        raise RuntimeError("Vertex embedding blocked: ledger actuals are invalid")
    if document_count <= 0 or used + document_count > REQUIRED_CAPS["embedding_documents"]:
        raise RuntimeError("Vertex embedding blocked: embedding document cap would be exceeded")
    if cost >= REQUIRED_CAPS["cost_usd_micros"]:
        raise RuntimeError("Vertex embedding blocked: USD 5 cost cap reached")
    return ledger
