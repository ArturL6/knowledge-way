import subprocess
from pathlib import Path
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from app import ingestion
from app.db import Base
from app.models import Repository, StructuralCard

def git(root,*args):
 return subprocess.run(['git',*args],cwd=root,text=True,capture_output=True,check=True).stdout.strip()

def test_git_commit_changes_incrementally_refresh_graph_derived_cards(monkeypatch,tmp_path):
 engine=create_engine('sqlite://'); Base.metadata.create_all(engine); sessions=sessionmaker(bind=engine,expire_on_commit=False)
 monkeypatch.setattr(ingestion,'SessionLocal',sessions); monkeypatch.setattr(ingestion.settings,'repository_storage_path',str(tmp_path))
 # This test covers structural cards, not embeddings. Without this, a developer's real
 # repo-root .env (config.py searches upward for it) can set EMBEDDING_PROVIDER=openrouter
 # with a real API key, making index_repository() issue a live, billed embedding request.
 monkeypatch.setattr(ingestion,'embedding_provider',lambda:None)
 repo=Repository(name='labeled-multi-language-fixture',clone_url='unused')
 with sessions() as db: db.add(repo); db.commit()
 root=tmp_path/repo.id; root.mkdir(); git(root,'init'); git(root,'config','user.email','fixture@example.test'); git(root,'config','user.name','Fixture')
 def write(path,text):
  p=root/path; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text)
 write(Path('apps/api/__init__.py'),'')
 write(Path('apps/api/users.py'),'def find_user(user_id):\n    return user_id\n')
 write(Path('apps/web/page.ts'),'export function profile() { return "user" }\n')
 write(Path('shared/auth.php'),'<?php function token() { return "v1"; }\n')
 git(root,'add','.'); git(root,'commit','-m','fixture v1'); sha1=git(root,'rev-parse','HEAD')
 def fake_run(*args,**kwargs):
  if args[1:3]==('rev-parse','HEAD'): return git(root,'rev-parse','HEAD')
  if args[1:3]==('branch','--show-current'): return 'main'
  return ''
 monkeypatch.setattr(ingestion,'run',fake_run)
 ingestion.index_repository(repo.id,full=True)
 with sessions() as db:
  v1={(c.kind,c.path):(c.id,c.content_fingerprint,c.indexed_commit_sha) for c in db.scalars(select(StructuralCard).where(StructuralCard.repository_id==repo.id)).all()}
  assert ('package','apps/api') in v1 and ('directory','shared') in v1
  assert all(value[2]==sha1 for value in v1.values())
 write(Path('apps/api/users.py'),'def find_user(user_id):\n    return user_id\n\ndef delete_user(user_id):\n    return None\n')
 (root/'shared/auth.php').unlink(); write(Path('docs/contract.md'),'profile uses apps/api/users.py\n')
 git(root,'add','-A'); git(root,'commit','-m','change api remove php'); sha2=git(root,'rev-parse','HEAD')
 ingestion.index_repository(repo.id,full=False)
 with sessions() as db:
  cards={(c.kind,c.path):c for c in db.scalars(select(StructuralCard).where(StructuralCard.repository_id==repo.id)).all()}
  assert ('directory','shared') not in cards
  assert ('directory','docs') in cards
  assert cards[('directory','apps/api')].content_fingerprint != v1[('directory','apps/api')][1]
  assert cards[('directory','apps/web')].content_fingerprint == v1[('directory','apps/web')][1]
  assert all(c.indexed_commit_sha==sha2 for c in cards.values())
