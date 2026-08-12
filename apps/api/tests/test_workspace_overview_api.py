from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db import Base, get_db
from app.main import app
from app.models import CodeChunk, File, Repository, Workspace, WorkspaceDependency, WorkspaceRepository


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
        response = TestClient(app).get("/api/workspaces/workspace/overview")
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
        assert TestClient(app).get("/api/workspaces/missing/overview").status_code == 404
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()
