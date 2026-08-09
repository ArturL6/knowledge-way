from types import SimpleNamespace
from fastapi.testclient import TestClient
from app.db import get_db
from app.main import app
from app.models import Repository, File, Symbol, SymbolEdge

class Result:
 def __init__(self, values): self.values=values
 def all(self): return self.values

class Db:
 def __init__(self):
  self.repo=SimpleNamespace(id='repo',name='demo',indexed_commit_sha='commit')
  self.files={'file':SimpleNamespace(id='file',repository_id='repo',path='demo.py',content='one\ntwo\nthree',indexed_commit_sha='commit')}
  self.symbols=[SimpleNamespace(id='root',repository_id='repo',file_id='file',name='root',qualified_name='demo.root',symbol_type='function',language='python',start_line=1,end_line=9,start_byte=0,end_byte=1,parent_symbol_id=None,signature='root()',source_text='def root(): pass'),SimpleNamespace(id='caller',repository_id='repo',file_id='file',name='caller',qualified_name='demo.caller',symbol_type='function',language='python',start_line=2,end_line=2,start_byte=0,end_byte=1,parent_symbol_id=None,signature=None,source_text='root()')]
  self.edges=[SimpleNamespace(id='edge',repository_id='repo',source_symbol_id='caller',target_symbol_id='root',target_name='demo.root',relationship_type='calls',source_file_id='file',line_number=2,confidence=100)]
 def get(self, model, value):
  if model is Repository: return self.repo if value=='repo' else None
  if model is File: return self.files.get(value)
 def scalars(self, statement):
  entity=statement.column_descriptions[0]['entity']
  return Result(self.symbols if entity is Symbol else self.edges if entity is SymbolEdge else [])

def client(monkeypatch, results=None):
 db=Db(); app.dependency_overrides[get_db]=lambda:db
 monkeypatch.setattr('app.main.search_with_capability',lambda *args,**kwargs:(results or [],{'enabled':False}))
 return TestClient(app)
def teardown_function(): app.dependency_overrides.clear()

def test_explanation_is_scoped_read_only_and_has_valid_citations(monkeypatch):
 results=[{'repository':'demo','repository_id':'repo','file_id':'file','path':'demo.py','start_line':1,'end_line':9,'symbol_id':'root','indexed_commit_sha':'commit','symbol':'demo.root'}]
 response=client(monkeypatch,results).post('/api/explanations',json={'question':'root','repository_id':'repo'})
 assert response.status_code==200
 body=response.json(); assert body['grounded'] is True and body['answer_mode']=='retrieval_only'
 assert body['citations'][0] == {'repository_id':'repo','repository':'demo','indexed_commit_sha':'commit','file_id':'file','path':'demo.py','start_line':1,'end_line':3,'symbol_id':'root'}
 assert client(monkeypatch).post('/api/explanations',json={'question':'x','repository_id':'missing'}).status_code==404

def test_explanation_no_results_and_documentation_are_deterministic(monkeypatch):
 api=client(monkeypatch)
 empty=api.post('/api/explanations',json={'question':'nothing','repository_id':'repo'}).json()
 assert empty['grounded'] is False and empty['citations']==[] and 'evidences' in empty['answer']
 doc=api.post('/api/documentation/generate',json={'repository_id':'repo','symbol_id':'root'})
 assert doc.status_code==200
 assert '# demo.root' in doc.json()['markdown'] and '`demo.caller`' in doc.json()['markdown']
 assert doc.json()['scope']=={'repository_id':'repo','indexed_commit_sha':'commit'}
 assert api.post('/api/documentation/generate',json={'repository_id':'repo','symbol_id':'missing'}).status_code==404
