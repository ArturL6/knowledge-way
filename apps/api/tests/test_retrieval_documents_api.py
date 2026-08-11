from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.db import Base, get_db
from app.main import app
from app.models import File, Repository, StructuralCard

def test_persisted_retrieval_documents_are_versioned_and_previewable():
 engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool); Base.metadata.create_all(engine); db=sessionmaker(bind=engine)()
 repo=Repository(id='repo',name='Demo',clone_url='https://example.test/demo.git',indexed_commit_sha='a'*40)
 db.add(repo); db.commit()
 db.add_all([File(id='file',repository_id='repo',path='pkg/a.py',language='python',content='x',content_hash='f'*64,size_bytes=1,indexed_commit_sha='a'*40),StructuralCard(id='card',repository_id='repo',kind='package',path='pkg',facts={'direct_files':[{'path':'pkg/a.py'}]},content_fingerprint='c'*64,provenance_fingerprint='p'*64,indexed_commit_sha='a'*40,schema_version='v1')]); db.commit(); app.dependency_overrides[get_db]=lambda:db
 try:
  api=TestClient(app); created=api.post('/api/repositories/repo/retrieval-documents/rebuild'); assert created.status_code==201
  documents=created.json()['documents']; assert {d['kind'] for d in documents}=={'repository','module'}
  assert all(len(d['content_hash'])==64 and len(d['source_fingerprint'])==64 for d in documents)
  assert api.post('/api/repositories/repo/retrieval-documents/rebuild').json()['documents'][0]['id']==documents[0]['id']
  listed=api.get('/api/repositories/repo/retrieval-documents?kind=module').json()['documents']; assert len(listed)==1
  preview=api.get(f"/api/repositories/repo/retrieval-documents/{listed[0]['id']}/preview"); assert preview.status_code==200 and 'Module: pkg' in preview.json()['content']
  assert api.get('/api/repositories/repo/retrieval-documents?kind=nope').status_code==422
 finally: app.dependency_overrides.clear(); db.close(); engine.dispose()
