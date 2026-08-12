from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import Repository, Workspace, WorkspaceRepository, WorkspaceSnapshot, WorkspaceSnapshotRepository


def test_workspace_snapshot_is_membership_validated_commit_pinned_and_immutable():
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    for table in (Repository.__table__,Workspace.__table__,WorkspaceRepository.__table__,WorkspaceSnapshot.__table__,WorkspaceSnapshotRepository.__table__): table.create(engine)
    db=sessionmaker(bind=engine)()
    db.add_all([Repository(id='one',name='one',clone_url='https://example.test/one.git',indexed_commit_sha='a'*40),Repository(id='two',name='two',clone_url='https://example.test/two.git',indexed_commit_sha='b'*40)])
    db.commit(); app.dependency_overrides[get_db]=lambda:db
    try:
        api=TestClient(app); workspace_id=api.post('/api/workspaces',json={'name':'Pinned'}).json()['id']
        api.put(f'/api/workspaces/{workspace_id}/repositories/one'); api.put(f'/api/workspaces/{workspace_id}/repositories/two')
        assert api.post(f'/api/workspaces/{workspace_id}/snapshots',json={'repository_pins':[{'repository_id':'one','indexed_commit_sha':'a'*40}]}).status_code==422
        assert api.post(f'/api/workspaces/{workspace_id}/snapshots',json={'repository_pins':[{'repository_id':'one','indexed_commit_sha':'c'*40},{'repository_id':'two','indexed_commit_sha':'b'*40}]}).status_code==422
        payload={'repository_pins':[{'repository_id':'two','indexed_commit_sha':'b'*40},{'repository_id':'one','indexed_commit_sha':'a'*40}]}
        created=api.post(f'/api/workspaces/{workspace_id}/snapshots',json=payload)
        assert created.status_code==201; snapshot=created.json()
        assert snapshot['repository_pins']==[{'repository_id':'one','indexed_commit_sha':'a'*40},{'repository_id':'two','indexed_commit_sha':'b'*40}]
        assert len(snapshot['manifest_hash'])==64
        assert api.delete('/api/repositories/one').status_code==409
        assert api.delete(f'/api/workspaces/{workspace_id}').status_code==409
        assert api.post(f'/api/workspaces/{workspace_id}/snapshots',json=payload).json()['id']==snapshot['id']
        db.get(Repository,'one').indexed_commit_sha='d'*40; db.commit()
        fetched=api.get(f"/api/workspaces/{workspace_id}/snapshots/{snapshot['id']}")
        assert fetched.status_code==200 and fetched.json()['repository_pins']==snapshot['repository_pins']
        assert len(api.get(f'/api/workspaces/{workspace_id}/snapshots').json())==1
    finally:
        app.dependency_overrides.clear(); db.close(); engine.dispose()
