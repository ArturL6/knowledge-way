"""Hard local admission guard for the bounded Vertex pilot.

This deliberately runs before ADC is refreshed or a provider request is made.  The ledger is
created by an operator/migration workflow; this module never creates an implicit ledger.
"""
import hashlib
import json

from sqlalchemy.orm import Session

from app.models import ProviderAuditEvent, ProviderAuditLedger

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
    unit_cost = ledger.configuration.get("embedding_cost_usd_micros_per_document")
    if not isinstance(unit_cost, int) or unit_cost < 0:
        raise RuntimeError("Vertex embedding blocked: deterministic per-document price accounting is required")
    actual = ledger.actual if isinstance(ledger.actual, dict) else {}
    used = actual.get("embedding_documents", 0)
    cost = actual.get("cost_usd_micros", 0)
    if not isinstance(used, int) or not isinstance(cost, int) or used < 0 or cost < 0:
        raise RuntimeError("Vertex embedding blocked: ledger actuals are invalid")
    if document_count <= 0 or used + document_count > REQUIRED_CAPS["embedding_documents"]:
        raise RuntimeError("Vertex embedding blocked: embedding document cap would be exceeded")
    projected_cost = unit_cost * document_count
    if cost >= REQUIRED_CAPS["cost_usd_micros"] or cost + projected_cost >= REQUIRED_CAPS["cost_usd_micros"]:
        raise RuntimeError("Vertex embedding blocked: USD 5 cost cap would be reached or exceeded")
    return ledger


def record_vertex_embedding_success(db: Session, ledger: ProviderAuditLedger, *, model: str,
                                    texts: list[str], input_tokens: int | None,
                                    cost_usd_micros: int, details: dict | None = None) -> ProviderAuditEvent:
    """Atomically account for a successful paid embedding response before it is returned.

    Vertex embedding responses do not reliably include token/cost usage. The pilot therefore
    refuses to persist a response unless the caller has deterministically accounted for its cost.
    """
    if cost_usd_micros < 0 or input_tokens is not None and input_tokens < 0:
        raise RuntimeError("Vertex embedding blocked: provider usage accounting is invalid")
    actual = dict(ledger.actual or {})
    used_documents = actual.get("embedding_documents", 0)
    used_cost = actual.get("cost_usd_micros", 0)
    if not isinstance(used_documents, int) or not isinstance(used_cost, int):
        raise RuntimeError("Vertex embedding blocked: ledger actuals are invalid")
    if used_documents + len(texts) > REQUIRED_CAPS["embedding_documents"] or used_cost + cost_usd_micros > REQUIRED_CAPS["cost_usd_micros"]:
        raise RuntimeError("Vertex embedding blocked: actual usage would exceed a hard cap")
    actual["embedding_documents"] = used_documents + len(texts)
    actual["cost_usd_micros"] = used_cost + cost_usd_micros
    event = ProviderAuditEvent(
        ledger_id=ledger.id, operation="embedding", model=model,
        model_version=ledger.configuration.get("embedding_model_version"),
        input_hash=hashlib.sha256(json.dumps(texts, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest(),
        input_tokens=input_tokens, output_tokens=0, cost_usd_micros=cost_usd_micros,
        status="succeeded", details=details or {},
    )
    ledger.actual = actual
    db.add(event)
    db.commit()
    return event


def record_vertex_embedding_failure(db: Session, ledger: ProviderAuditLedger, *, model: str,
                                    texts: list[str], details: dict) -> ProviderAuditEvent:
    """Persist one auditable zero-cost event for a failed Vertex request.

    The pilot makes no retries, but a rejected or unavailable request is still a provider call
    and must be visible in the persistent ledger. Vertex does not return billable usage for
    failed requests, so the event records a deterministic zero cost rather than guessing.
    """
    event = ProviderAuditEvent(
        ledger_id=ledger.id, operation="embedding", model=model,
        model_version=ledger.configuration.get("embedding_model_version"),
        input_hash=hashlib.sha256(json.dumps(texts, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest(),
        input_tokens=None, output_tokens=0, cost_usd_micros=0, status="failed", details=details,
    )
    db.add(event)
    db.commit()
    return event
