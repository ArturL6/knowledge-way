from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db import Base, get_db
from app.main import app
from app.models import CodeChunk, File, Repository, Symbol, Workspace, WorkspaceDependency, WorkspaceRepository, WorkspaceSnapshot, WorkspaceSnapshotRepository


def test_workspace_overview_only_exposes_declared_edges_and_repository_provenance():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all([
        Repository(id="api", name="API", clone_url="https://example.test/api.git", indexed_commit_sha="a" * 40, indexing_status="ready"),
        Repository(id="client", name="Client", clone_url="https://example.test/client.git", indexed_commit_sha="b" * 40, indexing_status="ready"),
        Repository(id="outside", name="Outside", clone_url="https://example.test/outside.git", indexed_commit_sha="c" * 40),
        Workspace(id="workspace", name="Demo"),
        WorkspaceRepository(workspace_id="workspace", repository_id="api"),
        WorkspaceRepository(workspace_id="workspace", repository_id="client"),
        WorkspaceSnapshot(id="snapshot", workspace_id="workspace", schema_version="workspace-snapshot-v1", manifest_hash="d" * 64),
        WorkspaceSnapshotRepository(snapshot_id="snapshot", repository_id="api", indexed_commit_sha="a" * 40),
        WorkspaceSnapshotRepository(snapshot_id="snapshot", repository_id="client", indexed_commit_sha="b" * 40),
    ])
    db.commit()
    db.add(File(id="file", repository_id="api", path="api.py", language="python", content="x", content_hash="h", size_bytes=1, indexed_commit_sha="a" * 40))
    db.commit()
    db.add_all([
        CodeChunk(id="embedded", repository_id="api", file_id="file", chunk_type="text", start_line=1, end_line=1, source_text="x", content_hash="h", indexed_commit_sha="a" * 40, embedding=[0.1]),
        CodeChunk(id="not-embedded", repository_id="api", file_id="file", chunk_type="text", start_line=1, end_line=1, source_text="y", content_hash="i", indexed_commit_sha="a" * 40),
        WorkspaceDependency(id="declared", workspace_id="workspace", source_repository_id="client", target_repository_id="api", package_name="api-client", reason="published contract"),
    ])
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    try:
        response = TestClient(app).get("/api/workspaces/workspace/overview?snapshot_id=snapshot")
        assert response.status_code == 200
        overview = response.json()
        assert [repo["id"] for repo in overview["repositories"]] == ["api", "client"]
        assert overview["repositories"][0]["vector_provenance"] == {"indexed_commit_sha": "a" * 40, "total_chunks": 2, "embedded_chunks": 1, "coverage_complete": False}
        assert overview["edges"] == [{
            "id": "declared", "workspace_id": "workspace", "source_repository_id": "client", "target_repository_id": "api", "package_name": "api-client", "import_path": None, "reason": "published contract", "note": None,
            "created_at": overview["edges"][0]["created_at"], "updated_at": overview["edges"][0]["updated_at"], "evidence_kind": "declared_workspace_dependency",
        }]
        assert overview["provenance"]["cross_repository_resolution"] == "not_performed"
        assert overview["provenance"]["edge_evidence"] == "declared_workspace_dependency_only"
        assert overview["snapshot"]["id"] == "snapshot"
        assert TestClient(app).get("/api/workspaces/workspace/overview").status_code == 422
        assert TestClient(app).get("/api/workspaces/missing/overview?snapshot_id=snapshot").status_code == 404
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_snapshot_relevant_repositories_ranks_only_current_pins_and_reports_stale_pins_unknown():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all([
        Repository(id="api", name="API", clone_url="https://example.test/api.git", indexed_commit_sha="a" * 40),
        Repository(id="stale", name="Stale", clone_url="https://example.test/stale.git", indexed_commit_sha="c" * 40),
        Workspace(id="workspace", name="Demo"),
    ])
    db.commit()
    db.add_all([
        WorkspaceSnapshot(id="snapshot", workspace_id="workspace", schema_version="workspace-snapshot-v1", manifest_hash="d" * 64),
        WorkspaceSnapshotRepository(snapshot_id="snapshot", repository_id="api", indexed_commit_sha="a" * 40),
        WorkspaceSnapshotRepository(snapshot_id="snapshot", repository_id="stale", indexed_commit_sha="b" * 40),
        WorkspaceDependency(id="declared", workspace_id="workspace", source_repository_id="api", target_repository_id="stale", reason="published contract"),
    ])
    db.commit()
    db.add(File(id="api-file", repository_id="api", path="api.py", language="python", content="change widget", content_hash="h", size_bytes=13, indexed_commit_sha="a" * 40))
    db.commit()
    db.add_all([
        CodeChunk(id="api-chunk", repository_id="api", file_id="api-file", chunk_type="text", language="python", start_line=1, end_line=1, source_text="change widget", content_hash="h", indexed_commit_sha="a" * 40),
        Symbol(id="api-symbol", repository_id="api", file_id="api-file", name="change_widget", qualified_name="change_widget", symbol_type="function", language="python", start_line=1, end_line=1, start_byte=0, end_byte=13, source_text="change widget"),
    ])
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    try:
        response = TestClient(app).get("/api/workspaces/workspace/snapshots/snapshot/relevant-repositories?q=change%20widget")
        assert response.status_code == 200
        body = response.json()
        assert [(item["repository_id"], item["indexed_commit_sha"]) for item in body["results"]] == [("api", "a" * 40)]
        assert body["results"][0]["evidence_kind"] == "lexical_or_parser_symbol"
        assert len(body["results"][0]["citations"]) == 2
        assert {citation["symbol_id"] for citation in body["results"][0]["citations"]} == {None, "api-symbol"}
        assert all(citation["indexed_commit_sha"] == "a" * 40 for citation in body["results"][0]["citations"])
        assert body["results"][0]["declared_dependencies"][0]["id"] == "declared"
        assert body["unknowns"] == [{"repository_id": "stale", "repository": "Stale", "indexed_commit_sha": "b" * 40, "evidence_kind": "unknown", "reason": "The snapshot commit is not the repository's currently indexed commit, so local evidence for this pin is unavailable."}]
        assert TestClient(app).get("/api/workspaces/workspace/snapshots/missing/relevant-repositories?q=x").status_code == 404
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()
