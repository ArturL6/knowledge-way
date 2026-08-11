from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db import Base, get_db
from app.main import app
from app.models import CodeCard, File, Repository, StructuralCard, Symbol


def _session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_repository_card_is_bounded_commit_scoped_and_uses_only_persisted_evidence():
    db = _session()
    repo = Repository(id="repo", name="demo", clone_url="https://example.test/demo.git", indexed_commit_sha="a" * 40)
    other = Repository(id="other", name="other", clone_url="https://example.test/other.git", indexed_commit_sha="b" * 40)
    db.add_all([repo, other])
    db.commit()
    db.add_all([
        File(id="f", repository_id="repo", path="pkg/service.py", language="python", content="def run(): pass", content_hash="file-hash", size_bytes=15, indexed_commit_sha="a" * 40),
        File(id="foreign-file", repository_id="other", path="leak.py", language="python", content="x", content_hash="foreign-hash", size_bytes=1, indexed_commit_sha="b" * 40),
    ])
    db.commit()
    db.add_all([
        Symbol(id="s", repository_id="repo", file_id="f", name="run", qualified_name="pkg.service.run", symbol_type="function", language="python", start_line=1, end_line=1, start_byte=0, end_byte=15, source_text="def run(): pass"),
        Symbol(id="foreign-symbol", repository_id="other", file_id="foreign-file", name="leak", qualified_name="leak", symbol_type="function", language="python", start_line=1, end_line=1, start_byte=0, end_byte=1, source_text="x"),
    ])
    db.commit()
    db.add_all([
        CodeCard(id="card", repository_id="repo", symbol_id="s", source_hash="symbol-hash", indexed_commit_sha="a" * 40, model="test", prompt_version="v1", status="ready", summary="Runs the service flow.", details={"keywords": ["service", "flow"]}),
        CodeCard(id="foreign-card", repository_id="other", symbol_id="foreign-symbol", source_hash="foreign-symbol-hash", indexed_commit_sha="b" * 40, model="test", prompt_version="v1", status="ready", summary="Must not leak.", details={"keywords": ["foreign"]}),
        StructuralCard(id="module", repository_id="repo", kind="package", path="pkg", facts={"direct_files": [{"path": "pkg/service.py"}], "languages": {"python": 1}, "boundary_edges": [{"count": 2}]}, content_fingerprint="content", provenance_fingerprint="provenance", indexed_commit_sha="a" * 40, schema_version="v1"),
    ])
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    try:
        response = TestClient(app).get("/api/repositories/repo/repository-card")
        assert response.status_code == 200
        card = response.json()
        assert card["indexed_commit_sha"] == "a" * 40
        assert card["facts"]["file_count"] == 1
        assert card["facts"]["symbol_count"] == 1
        assert card["facts"]["ready_code_card_count"] == 1
        assert card["facts"]["modules"] == [{"path": "pkg", "kind": "package", "direct_file_count": 1, "languages": {"python": 1}, "boundary_edge_count": 2, "indexed_commit_sha": "a" * 40, "provenance_fingerprint": "provenance"}]
        assert card["facts"]["code_card_excerpts"][0]["qualified_name"] == "pkg.service.run"
        assert "Must not leak" not in card["retrieval_document"]
        assert "Repository: demo" in card["retrieval_document"]
        assert "preview-only" in card["limitations"][-1]
        assert TestClient(app).get("/api/repositories/missing/repository-card").status_code == 404
    finally:
        app.dependency_overrides.clear()
        db.close()
