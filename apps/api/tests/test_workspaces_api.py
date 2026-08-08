from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import Repository, Workspace, WorkspaceRepository, WorkspaceDependency


def test_workspace_crud_and_exclusive_idempotent_membership():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Repository.__table__.create(engine)
    Workspace.__table__.create(engine)
    WorkspaceRepository.__table__.create(engine)
    WorkspaceDependency.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add_all([
        Repository(id="repo-1", name="one", clone_url="https://example.test/one.git"),
        Repository(id="repo-2", name="two", clone_url="https://example.test/two.git"),
    ])
    db.commit()
    app.dependency_overrides[get_db] = lambda: db
    try:
        api = TestClient(app)
        first = api.post("/api/workspaces", json={"name": "First", "description": "initial"})
        second = api.post("/api/workspaces", json={"name": "Second"})
        assert first.status_code == second.status_code == 201
        first_id, second_id = first.json()["id"], second.json()["id"]
        assert api.patch(f"/api/workspaces/{first_id}", json={"name": "Renamed"}).json()["name"] == "Renamed"

        added = api.put(f"/api/workspaces/{first_id}/repositories/repo-1")
        again = api.put(f"/api/workspaces/{first_id}/repositories/repo-1")
        conflict = api.put(f"/api/workspaces/{second_id}/repositories/repo-1")
        assert added.status_code == again.status_code == 200
        assert conflict.status_code == 409
        assert [repo["id"] for repo in api.get(f"/api/workspaces/{first_id}/repositories").json()] == ["repo-1"]

        assert api.delete(f"/api/workspaces/{first_id}/repositories/repo-1").status_code == 204
        assert api.get(f"/api/workspaces/{first_id}/repositories").json() == []
        api.put(f"/api/workspaces/{first_id}/repositories/repo-1")
        api.put(f"/api/workspaces/{first_id}/repositories/repo-2")
        declared = api.post(f"/api/workspaces/{first_id}/dependencies", json={
            "source_repository_id": "repo-1", "target_repository_id": "repo-2",
            "package_name": "shared-client", "import_path": "@shared/client",
            "reason": "uses the shared API client", "note": "declared metadata only",
        })
        assert declared.status_code == 201
        dependency_id = declared.json()["id"]
        assert api.get(f"/api/workspaces/{first_id}/dependencies").json()[0]["import_path"] == "@shared/client"
        updated = api.patch(f"/api/workspaces/{first_id}/dependencies/{dependency_id}", json={"note": "updated"})
        assert updated.status_code == 200
        assert updated.json()["note"] == "updated"
        assert api.post(f"/api/workspaces/{first_id}/dependencies", json={"source_repository_id": "repo-1", "target_repository_id": "repo-1"}).status_code == 422
        assert api.post(f"/api/workspaces/{first_id}/dependencies", json={"source_repository_id": "repo-1", "target_repository_id": "missing"}).status_code == 422
        assert api.delete(f"/api/workspaces/{first_id}/dependencies/{dependency_id}").status_code == 204
        assert api.delete(f"/api/workspaces/{first_id}").status_code == 204
        assert db.query(WorkspaceRepository).count() == 0
        assert db.query(WorkspaceDependency).count() == 0
        assert api.get(f"/api/workspaces/{first_id}").status_code == 404
    finally:
        app.dependency_overrides.clear()
        db.close()
        engine.dispose()
