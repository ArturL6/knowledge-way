from pathlib import PurePosixPath
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select, func, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from redis import Redis
from rq import Queue
from app.config import settings
from app.git_auth import validate_clone_url
from app.db import get_db, verify_migration_ready
from app.models import Repository, Workspace, WorkspaceRepository, WorkspaceDependency, File, Symbol, SymbolEdge, CodeChunk, CodeCard, StructuralCard, IndexingJob, Conversation, Message
from app.search import search, search_with_capability

app=FastAPI(title='knowledge-way API',version='0.1.0')
app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origins.split(','),allow_methods=['*'],allow_headers=['*'])
@app.on_event('startup')
def startup(): verify_migration_ready()
class RepositoryIn(BaseModel):
 name:str=Field(min_length=1,max_length=255); clone_url:str=Field(min_length=8,max_length=2048); requested_revision:str|None=Field(default=None,pattern=r'^[0-9a-f]{40}$')
class RepositoryReindexIn(BaseModel):
 requested_revision:str|None=Field(default=None,pattern=r'^[0-9a-f]{40}$')
class WorkspaceIn(BaseModel):
 name:str=Field(min_length=1,max_length=255); description:str|None=Field(default=None,max_length=10000)
class WorkspaceUpdate(BaseModel):
 name:str|None=Field(default=None,min_length=1,max_length=255); description:str|None=Field(default=None,max_length=10000)
class WorkspaceDependencyIn(BaseModel):
 source_repository_id:str; target_repository_id:str; package_name:str|None=Field(default=None,max_length=512); import_path:str|None=Field(default=None,max_length=1024); reason:str|None=Field(default=None,max_length=10000); note:str|None=Field(default=None,max_length=10000)
class WorkspaceDependencyUpdate(BaseModel):
 package_name:str|None=Field(default=None,max_length=512); import_path:str|None=Field(default=None,max_length=1024); reason:str|None=Field(default=None,max_length=10000); note:str|None=Field(default=None,max_length=10000)
class ChatIn(BaseModel):
 question:str=Field(min_length=1,max_length=8000); repository_id:str|None=None; conversation_id:str|None=None
class ExplanationIn(BaseModel):
 question:str=Field(min_length=1,max_length=8000); repository_id:str
class DocumentationIn(BaseModel):
 repository_id:str; symbol_id:str
class CodeCardRunIn(BaseModel):
 limit:int|None=Field(default=25,ge=1,le=500)

def repo_out(r): return {'id':r.id,'name':r.name,'clone_url':r.clone_url,'requested_revision':r.requested_revision,'default_branch':r.default_branch,'indexed_branch':r.indexed_branch,'indexed_commit_sha':r.indexed_commit_sha,'latest_detected_commit_sha':r.latest_detected_commit_sha,'indexing_status':r.indexing_status,'indexing_progress':r.indexing_progress,'error_message':r.error_message,'last_indexed_at':r.last_indexed_at,'last_sync_at':r.last_sync_at,'created_at':r.created_at}
def workspace_out(w): return {'id':w.id,'name':w.name,'description':w.description,'created_at':w.created_at,'updated_at':w.updated_at}
def workspace_dependency_out(d): return {'id':d.id,'workspace_id':d.workspace_id,'source_repository_id':d.source_repository_id,'target_repository_id':d.target_repository_id,'package_name':d.package_name,'import_path':d.import_path,'reason':d.reason,'note':d.note,'created_at':d.created_at,'updated_at':d.updated_at}
def validate_dependency_membership(db,workspace_id,source_repository_id,target_repository_id):
 if source_repository_id==target_repository_id: raise HTTPException(422,'Source and target repositories must differ')
 members=set(db.scalars(select(WorkspaceRepository.repository_id).where(WorkspaceRepository.workspace_id==workspace_id)).all())
 if source_repository_id not in members or target_repository_id not in members: raise HTTPException(422,'Source and target repositories must both belong to this workspace')
def enqueue(repo_id,full=False):
 try: return Queue('indexing',connection=Redis.from_url(settings.redis_url),default_timeout=settings.index_job_timeout).enqueue('app.ingestion.index_repository',repo_id,full).id
 except Exception: return None
MAX_GRAPH_NODES=100
def symbol_out(s): return {'id':s.id,'repository_id':s.repository_id,'file_id':s.file_id,'name':s.name,'qualified_name':s.qualified_name,'type':s.symbol_type,'language':s.language,'start_line':s.start_line,'end_line':s.end_line,'start_byte':s.start_byte,'end_byte':s.end_byte,'parent_symbol_id':s.parent_symbol_id,'signature':s.signature,'source_text':s.source_text}
def edge_out(e): return {'id':e.id,'source_symbol_id':e.source_symbol_id,'target_symbol_id':e.target_symbol_id,'target_name':e.target_name,'type':e.relationship_type,'confidence':e.confidence,'line':e.line_number,'source_file_id':e.source_file_id}
def edge_key(e): return (e.relationship_type,e.source_symbol_id or '',e.target_symbol_id or '',e.target_name,e.line_number,e.id)
def scoped_symbol(db,repo_id,symbol_id):
 s=next((x for x in db.scalars(select(Symbol).where(Symbol.repository_id==repo_id,Symbol.id==symbol_id)).all() if x.id==symbol_id and x.repository_id==repo_id),None)
 if not s: raise HTTPException(404,'Symbol not found')
 return s
def scoped_edges(db,repo_id): return sorted((e for e in db.scalars(select(SymbolEdge).where(SymbolEdge.repository_id==repo_id)).all() if e.repository_id==repo_id),key=edge_key)
def scoped_symbols(db,repo_id,ids): return {s.id:s for s in db.scalars(select(Symbol).where(Symbol.repository_id==repo_id,Symbol.id.in_(ids))).all() if s.repository_id==repo_id and s.id in ids}
def scoped_files(db,repo_id): return {f.id:f for f in db.scalars(select(File).where(File.repository_id==repo_id)).all() if f.repository_id==repo_id}
def citation(repo,file,item):
 line_count=max(len((file.content or '').splitlines()),1); start=max(1,min(item.start_line,line_count)); end=max(start,min(item.end_line,line_count))
 return {'repository_id':repo.id,'repository':repo.name,'indexed_commit_sha':getattr(item,'indexed_commit_sha',None) or file.indexed_commit_sha or repo.indexed_commit_sha,'file_id':file.id,'path':file.path,'start_line':start,'end_line':end,'symbol_id':getattr(item,'symbol_id',None) or getattr(item,'id',None)}
def result_citation(db,repo,result):
 file=db.get(File,result['file_id'])
 if file:
  item=type('Retrieved',(),{'start_line':result['start_line'],'end_line':result['end_line'],'symbol_id':result.get('symbol_id'),'indexed_commit_sha':result.get('indexed_commit_sha')})()
  return citation(repo,file,item)
 return {'repository_id':repo.id,'repository':repo.name,'indexed_commit_sha':result.get('indexed_commit_sha') or repo.indexed_commit_sha,'file_id':result['file_id'],'path':result['path'],'start_line':max(1,result['start_line']),'end_line':max(max(1,result['start_line']),result['end_line']),'symbol_id':result.get('symbol_id')}
@app.get('/health')
def health(): return {'status':'ok'}
@app.get('/api/workspaces')
def workspaces(db:Session=Depends(get_db)): return [workspace_out(w) for w in db.scalars(select(Workspace).order_by(Workspace.created_at.desc())).all()]
@app.post('/api/workspaces',status_code=201)
def add_workspace(body:WorkspaceIn,db:Session=Depends(get_db)):
 w=Workspace(name=body.name,description=body.description); db.add(w); db.commit(); db.refresh(w); return workspace_out(w)
@app.get('/api/workspaces/{workspace_id}')
def workspace(workspace_id:str,db:Session=Depends(get_db)):
 w=db.get(Workspace,workspace_id)
 if not w: raise HTTPException(404,'Workspace not found')
 return workspace_out(w)
@app.patch('/api/workspaces/{workspace_id}')
def update_workspace(workspace_id:str,body:WorkspaceUpdate,db:Session=Depends(get_db)):
 w=db.get(Workspace,workspace_id)
 if not w: raise HTTPException(404,'Workspace not found')
 for field,value in body.model_dump(exclude_unset=True).items(): setattr(w,field,value)
 db.commit(); db.refresh(w); return workspace_out(w)
@app.delete('/api/workspaces/{workspace_id}',status_code=204)
def delete_workspace(workspace_id:str,db:Session=Depends(get_db)):
 w=db.get(Workspace,workspace_id)
 if not w: raise HTTPException(404,'Workspace not found')
 db.execute(delete(WorkspaceDependency).where(WorkspaceDependency.workspace_id==workspace_id)); db.execute(delete(WorkspaceRepository).where(WorkspaceRepository.workspace_id==workspace_id)); db.delete(w); db.commit()
@app.get('/api/workspaces/{workspace_id}/dependencies')
def workspace_dependencies(workspace_id:str,db:Session=Depends(get_db)):
 if not db.get(Workspace,workspace_id): raise HTTPException(404,'Workspace not found')
 return [workspace_dependency_out(d) for d in db.scalars(select(WorkspaceDependency).where(WorkspaceDependency.workspace_id==workspace_id).order_by(WorkspaceDependency.created_at.desc())).all()]
@app.post('/api/workspaces/{workspace_id}/dependencies',status_code=201)
def add_workspace_dependency(workspace_id:str,body:WorkspaceDependencyIn,db:Session=Depends(get_db)):
 if not db.get(Workspace,workspace_id): raise HTTPException(404,'Workspace not found')
 validate_dependency_membership(db,workspace_id,body.source_repository_id,body.target_repository_id)
 dependency=WorkspaceDependency(workspace_id=workspace_id,**body.model_dump()); db.add(dependency)
 try: db.commit()
 except IntegrityError: db.rollback(); raise HTTPException(409,'Dependency declaration already exists')
 db.refresh(dependency); return workspace_dependency_out(dependency)
@app.patch('/api/workspaces/{workspace_id}/dependencies/{dependency_id}')
def update_workspace_dependency(workspace_id:str,dependency_id:str,body:WorkspaceDependencyUpdate,db:Session=Depends(get_db)):
 dependency=db.scalar(select(WorkspaceDependency).where(WorkspaceDependency.workspace_id==workspace_id,WorkspaceDependency.id==dependency_id))
 if not dependency: raise HTTPException(404,'Dependency not found')
 for field,value in body.model_dump(exclude_unset=True).items(): setattr(dependency,field,value)
 try: db.commit()
 except IntegrityError: db.rollback(); raise HTTPException(409,'Dependency declaration already exists')
 db.refresh(dependency); return workspace_dependency_out(dependency)
@app.delete('/api/workspaces/{workspace_id}/dependencies/{dependency_id}',status_code=204)
def delete_workspace_dependency(workspace_id:str,dependency_id:str,db:Session=Depends(get_db)):
 dependency=db.scalar(select(WorkspaceDependency).where(WorkspaceDependency.workspace_id==workspace_id,WorkspaceDependency.id==dependency_id))
 if not dependency: raise HTTPException(404,'Dependency not found')
 db.delete(dependency); db.commit()
@app.get('/api/workspaces/{workspace_id}/repositories')
def workspace_repositories(workspace_id:str,db:Session=Depends(get_db)):
 if not db.get(Workspace,workspace_id): raise HTTPException(404,'Workspace not found')
 statement=select(Repository).join(WorkspaceRepository,WorkspaceRepository.repository_id==Repository.id).where(WorkspaceRepository.workspace_id==workspace_id).order_by(Repository.created_at.desc())
 return [repo_out(r) for r in db.scalars(statement).all()]
@app.put('/api/workspaces/{workspace_id}/repositories/{repo_id}')
@app.post('/api/workspaces/{workspace_id}/repositories/{repo_id}')
def add_workspace_repository(workspace_id:str,repo_id:str,db:Session=Depends(get_db)):
 if not db.get(Workspace,workspace_id): raise HTTPException(404,'Workspace not found')
 if not db.get(Repository,repo_id): raise HTTPException(404,'Repository not found')
 membership=db.scalar(select(WorkspaceRepository).where(WorkspaceRepository.repository_id==repo_id))
 if membership:
  if membership.workspace_id==workspace_id: return {'workspace_id':workspace_id,'repository_id':repo_id}
  raise HTTPException(409,'Repository already belongs to another workspace')
 db.add(WorkspaceRepository(workspace_id=workspace_id,repository_id=repo_id))
 try: db.commit()
 except IntegrityError:
  db.rollback(); membership=db.scalar(select(WorkspaceRepository).where(WorkspaceRepository.repository_id==repo_id))
  if membership and membership.workspace_id==workspace_id: return {'workspace_id':workspace_id,'repository_id':repo_id}
  raise HTTPException(409,'Repository already belongs to another workspace')
 return {'workspace_id':workspace_id,'repository_id':repo_id}
@app.delete('/api/workspaces/{workspace_id}/repositories/{repo_id}',status_code=204)
def remove_workspace_repository(workspace_id:str,repo_id:str,db:Session=Depends(get_db)):
 if not db.get(Workspace,workspace_id): raise HTTPException(404,'Workspace not found')
 membership=db.scalar(select(WorkspaceRepository).where(WorkspaceRepository.workspace_id==workspace_id,WorkspaceRepository.repository_id==repo_id))
 if not membership: raise HTTPException(404,'Repository is not a member of this workspace')
 db.execute(delete(WorkspaceDependency).where(WorkspaceDependency.workspace_id==workspace_id,(WorkspaceDependency.source_repository_id==repo_id)|(WorkspaceDependency.target_repository_id==repo_id))); db.delete(membership); db.commit()
@app.get('/api/repositories')
def repositories(db:Session=Depends(get_db)): return [repo_out(r) for r in db.scalars(select(Repository).order_by(Repository.created_at.desc())).all()]
@app.post('/api/repositories',status_code=202)
def add_repository(body:RepositoryIn,db:Session=Depends(get_db)):
 try: body.clone_url=validate_clone_url(body.clone_url)
 except ValueError as error: raise HTTPException(422,str(error))
 r=Repository(name=body.name,clone_url=body.clone_url,requested_revision=body.requested_revision,indexing_status='pending');db.add(r);db.commit();db.refresh(r); return {'repository':repo_out(r),'job_id':enqueue(r.id,True)}
@app.get('/api/repositories/{repo_id}')
def repository(repo_id:str,db:Session=Depends(get_db)):
 r=db.get(Repository,repo_id)
 if not r: raise HTTPException(404,'Repository not found')
 return repo_out(r)
@app.delete('/api/repositories/{repo_id}',status_code=204)
def delete_repository(repo_id:str,db:Session=Depends(get_db)):
 r=db.get(Repository,repo_id)
 if not r: raise HTTPException(404,'Repository not found')
 db.execute(delete(WorkspaceDependency).where((WorkspaceDependency.source_repository_id==repo_id)|(WorkspaceDependency.target_repository_id==repo_id))); db.execute(delete(WorkspaceRepository).where(WorkspaceRepository.repository_id==repo_id)); db.delete(r);db.commit()
@app.post('/api/repositories/{repo_id}/sync',status_code=202)
def sync(repo_id:str,db:Session=Depends(get_db)):
 if not db.get(Repository,repo_id): raise HTTPException(404,'Repository not found')
 return {'job_id':enqueue(repo_id,False)}
@app.post('/api/repositories/{repo_id}/reindex',status_code=202)
def reindex(repo_id:str,body:RepositoryReindexIn|None=None,db:Session=Depends(get_db)):
 repo=db.get(Repository,repo_id)
 if not repo: raise HTTPException(404,'Repository not found')
 if body and 'requested_revision' in body.model_fields_set: repo.requested_revision=body.requested_revision; db.commit()
 return {'job_id':enqueue(repo_id,True)}
@app.get('/api/repositories/{repo_id}/status')
def status(repo_id:str,db:Session=Depends(get_db)):
 r=db.get(Repository,repo_id)
 if not r: raise HTTPException(404,'Repository not found')
 return {'status':r.indexing_status,'progress':r.indexing_progress,'error':r.error_message,'indexed_commit_sha':r.indexed_commit_sha}
@app.post('/api/repositories/{repo_id}/code-cards',status_code=202)
def generate_code_cards(repo_id:str,body:CodeCardRunIn,db:Session=Depends(get_db)):
 if not db.get(Repository,repo_id): raise HTTPException(404,'Repository not found')
 if not settings.code_cards_enabled: raise HTTPException(409,'Code cards are disabled')
 try: job_id=Queue('indexing',connection=Redis.from_url(settings.redis_url),default_timeout=settings.index_job_timeout).enqueue('app.code_cards.generate_code_cards',repo_id,body.limit).id
 except Exception: raise HTTPException(503,'Could not enqueue code-card generation')
 return {'job_id':job_id,'model':settings.vertex_gemini_model,'limit':body.limit}
@app.get('/api/repositories/{repo_id}/symbols/{symbol_id}/code-card')
def code_card(repo_id:str,symbol_id:str,db:Session=Depends(get_db)):
 scoped_symbol(db,repo_id,symbol_id)
 card=db.scalar(select(CodeCard).where(CodeCard.repository_id==repo_id,CodeCard.symbol_id==symbol_id))
 if not card: raise HTTPException(404,'No Code Card for this symbol')
 return {'symbol_id':card.symbol_id,'summary':card.summary,'details':card.details,'model':card.model,'prompt_version':card.prompt_version,'indexed_commit_sha':card.indexed_commit_sha,'input_tokens':card.input_tokens,'output_tokens':card.output_tokens}
@app.get('/api/repositories/{repo_id}/structural-cards')
def structural_cards(repo_id:str,path:str='',kind:str|None=None,limit:int=Query(50,ge=1,le=100),db:Session=Depends(get_db)):
 if not db.get(Repository,repo_id): raise HTTPException(404,'Repository not found')
 if kind and kind not in {'directory','package'}: raise HTTPException(422,'Invalid structural card kind')
 query=select(StructuralCard).where(StructuralCard.repository_id==repo_id)
 if kind: query=query.where(StructuralCard.kind==kind)
 cards=sorted(db.scalars(query).all(),key=lambda c:(c.path.count('/'),c.path,c.kind))
 prefix=path.strip('/')
 cards=[c for c in cards if c.path==prefix or (not prefix and c.path.count('/')==0) or (prefix and c.path.startswith(prefix+'/') and c.path[len(prefix)+1:].count('/')==0)]
 return {'repository_id':repo_id,'path':prefix,'cards':[{'kind':c.kind,'path':c.path,'facts':c.facts,'indexed_commit_sha':c.indexed_commit_sha,'content_fingerprint':c.content_fingerprint,'provenance_fingerprint':c.provenance_fingerprint,'schema_version':c.schema_version} for c in cards[:limit]],'truncated':len(cards)>limit}
@app.get('/api/repositories/{repo_id}/structural-cards/{kind}')
def structural_card(repo_id:str,kind:str,path:str='',db:Session=Depends(get_db)):
 card=db.scalar(select(StructuralCard).where(StructuralCard.repository_id==repo_id,StructuralCard.kind==kind,StructuralCard.path==path.strip('/')))
 if not card: raise HTTPException(404,'Structural card not found')
 return {'repository_id':repo_id,'kind':card.kind,'path':card.path,'facts':card.facts,'indexed_commit_sha':card.indexed_commit_sha,'content_fingerprint':card.content_fingerprint,'provenance_fingerprint':card.provenance_fingerprint,'schema_version':card.schema_version}
@app.get('/api/repositories/{repo_id}/tree')
def tree(repo_id:str,path:str='',db:Session=Depends(get_db)):
 if not db.get(Repository,repo_id): raise HTTPException(404,'Repository not found')
 prefix=path.strip('/')+'/' if path else ''
 files=db.scalars(select(File).where(File.repository_id==repo_id,File.path.like(prefix+'%'))).all(); children={}
 for f in files:
  rest=f.path[len(prefix):]; first=rest.split('/')[0]
  children[first]={'name':first,'type':'file' if '/' not in rest else 'directory','path':prefix+first,**({'file_id':f.id} if '/' not in rest else {})}
 return sorted(children.values(),key=lambda x:(x['type']!='directory',x['name']))
@app.get('/api/files/{file_id}')
def file(file_id:str,db:Session=Depends(get_db)):
 f=db.get(File,file_id)
 if not f: raise HTTPException(404,'File not found')
 return {'id':f.id,'repository_id':f.repository_id,'path':f.path,'language':f.language,'content':f.content,'indexed_commit_sha':f.indexed_commit_sha}
@app.get('/api/files/{file_id}/symbols')
def symbols(file_id:str,db:Session=Depends(get_db)): return [{'id':s.id,'name':s.name,'qualified_name':s.qualified_name,'type':s.symbol_type,'start_line':s.start_line,'end_line':s.end_line} for s in db.scalars(select(Symbol).where(Symbol.file_id==file_id)).all()]
@app.get('/api/repositories/{repo_id}/symbols/{symbol_id}')
def symbol_detail(repo_id:str,symbol_id:str,db:Session=Depends(get_db)):
 if not db.get(Repository,repo_id): raise HTTPException(404,'Repository not found')
 return symbol_out(scoped_symbol(db,repo_id,symbol_id))
def neighbors(repo_id,symbol_id,direction,db):
 if not db.get(Repository,repo_id): raise HTTPException(404,'Repository not found')
 scoped_symbol(db,repo_id,symbol_id)
 edges=[e for e in scoped_edges(db,repo_id) if (e.target_symbol_id==symbol_id if direction=='callers' else e.source_symbol_id==symbol_id) and (e.source_symbol_id if direction=='callers' else e.target_symbol_id)]
 ids={e.source_symbol_id if direction=='callers' else e.target_symbol_id for e in edges}; related=scoped_symbols(db,repo_id,ids)
 result=[]
 for e in edges:
  related_id=e.source_symbol_id if direction=='callers' else e.target_symbol_id
  if related_id in related: result.append({'symbol':symbol_out(related[related_id]),'edge':edge_out(e)})
 return sorted(result,key=lambda x:(x['symbol']['qualified_name'],x['symbol']['id'],x['edge']['type'],x['edge']['line'],x['edge']['id']))
@app.get('/api/repositories/{repo_id}/symbols/{symbol_id}/callers')
def callers(repo_id:str,symbol_id:str,db:Session=Depends(get_db)): return {'symbol_id':symbol_id,'callers':neighbors(repo_id,symbol_id,'callers',db)}
@app.get('/api/repositories/{repo_id}/symbols/{symbol_id}/callees')
def callees(repo_id:str,symbol_id:str,db:Session=Depends(get_db)): return {'symbol_id':symbol_id,'callees':neighbors(repo_id,symbol_id,'callees',db)}
@app.get('/api/repositories/{repo_id}/symbols/{symbol_id}/subgraph')
def subgraph(repo_id:str,symbol_id:str,depth:int=Query(1,ge=1,le=2),max_nodes:int=Query(MAX_GRAPH_NODES,ge=1,le=MAX_GRAPH_NODES),db:Session=Depends(get_db)):
 if not db.get(Repository,repo_id): raise HTTPException(404,'Repository not found')
 scoped_symbol(db,repo_id,symbol_id)
 edges=[e for e in scoped_edges(db,repo_id) if e.source_symbol_id and e.target_symbol_id]
 available=scoped_symbols(db,repo_id,{x for e in edges for x in (e.source_symbol_id,e.target_symbol_id)}|{symbol_id})
 selected={symbol_id}; frontier={symbol_id}; truncated=False
 for _ in range(depth):
  candidates=[]
  for e in edges:
   if e.source_symbol_id in frontier and e.target_symbol_id in available: candidates.append(e.target_symbol_id)
   if e.target_symbol_id in frontier and e.source_symbol_id in available: candidates.append(e.source_symbol_id)
  next_frontier=[]
  for node_id in sorted(set(candidates),key=lambda i:(available[i].qualified_name,i)):
   if node_id not in selected:
    if len(selected)>=max_nodes: truncated=True; break
    selected.add(node_id); next_frontier.append(node_id)
  frontier=set(next_frontier)
  if not frontier: break
 graph_edges=[e for e in edges if e.source_symbol_id in selected and e.target_symbol_id in selected]
 return {'root_symbol_id':symbol_id,'depth':depth,'max_nodes':max_nodes,'truncated':truncated,'nodes':[symbol_out(available[i]) for i in sorted(selected,key=lambda i:(available[i].qualified_name,i))],'edges':[edge_out(e) for e in graph_edges]}
@app.get('/api/repositories/{repo_id}/graph')
def repository_graph(repo_id:str,max_nodes:int=Query(MAX_GRAPH_NODES,ge=10,le=MAX_GRAPH_NODES),db:Session=Depends(get_db)):
 """Return a bounded repository overview with structural and code relationship nodes."""
 repo=db.get(Repository,repo_id)
 if not repo: raise HTTPException(404,'Repository not found')
 files=scoped_files(db,repo_id); edges=[e for e in scoped_edges(db,repo_id) if e.source_symbol_id and e.target_symbol_id]
 symbols={s.id:s for s in db.scalars(select(Symbol).where(Symbol.repository_id==repo_id)).all() if s.repository_id==repo_id and s.file_id in files}
 degree={symbol_id:0 for symbol_id in symbols}
 for edge in edges:
  if edge.source_symbol_id in degree: degree[edge.source_symbol_id]+=1
  if edge.target_symbol_id in degree: degree[edge.target_symbol_id]+=1
 selected=[]; selected_files=set(); directories=set(); budget=max_nodes-1
 for symbol in sorted(symbols.values(),key=lambda s:(-degree[s.id],s.qualified_name,s.id)):
  file=files[symbol.file_id]; ancestors=[]; parent=PurePosixPath(file.path).parent
  while str(parent) not in ('', '.'):
   ancestors.append(str(parent)); parent=parent.parent
  added=1+(0 if file.id in selected_files else 1)+sum(directory not in directories for directory in ancestors)
  if len(selected)+len(selected_files)+len(directories)+added>budget: continue
  selected.append(symbol.id); selected_files.add(file.id); directories.update(ancestors)
 graph_nodes=[{'id':f'repository:{repo.id}','name':getattr(repo,'name',repo.id),'kind':'repository'}]
 graph_nodes += [{'id':f'directory:{directory}','name':directory,'kind':'directory'} for directory in sorted(directories)]
 graph_nodes += [{'id':f'file:{file.id}','name':file.path,'path':file.path,'kind':'file'} for file_id,file in sorted(files.items(),key=lambda item:item[1].path) if file_id in selected_files]
 graph_nodes += [dict(symbol_out(symbols[symbol_id]),kind=symbols[symbol_id].symbol_type) for symbol_id in selected]
 graph_edges=[]
 for directory in directories:
  parent=str(PurePosixPath(directory).parent)
  graph_edges.append({'source':f'directory:{parent}' if parent not in ('', '.') else f'repository:{repo.id}','target':f'directory:{directory}','relationship':'contains','confidence':1})
 for file_id in selected_files:
  file=files[file_id]; parent=str(PurePosixPath(file.path).parent)
  graph_edges.append({'source':f'directory:{parent}' if parent not in ('', '.') else f'repository:{repo.id}','target':f'file:{file.id}','relationship':'contains','confidence':1})
 for symbol_id in selected:
  graph_edges.append({'source':f'file:{symbols[symbol_id].file_id}','target':symbol_id,'relationship':'defines','confidence':1})
 graph_edges += [edge_out(edge) for edge in edges if edge.source_symbol_id in selected and edge.target_symbol_id in selected]
 return {'repository_id':repo.id,'max_nodes':max_nodes,'truncated':len(selected)<len(symbols),'nodes':graph_nodes,'edges':graph_edges}
@app.get('/api/search')
def text_search(q:str,mode:str='hybrid',limit:int=30,repository_id:str|None=None,rerank:bool=False,db:Session=Depends(get_db)):
 if repository_id and not db.get(Repository,repository_id): raise HTTPException(404,'Repository not found')
 results, semantic = search_with_capability(db,q,mode,min(max(limit,1),100),repository_id=repository_id,rerank=rerank)
 return {'query':q,'mode':mode,'results':results,'semantic':semantic}
@app.get('/api/search/symbols')
def symbol_search(q:str,db:Session=Depends(get_db)): return {'results':search(db,q,'symbols')}
@app.post('/api/search/semantic')
def semantic_search(body:dict,db:Session=Depends(get_db)):
 results, semantic = search_with_capability(db,body.get('query',''),'semantic')
 return {'results':results,'semantic':semantic}
@app.post('/api/explanations')
def explanation(body:ExplanationIn,db:Session=Depends(get_db)):
 repo=db.get(Repository,body.repository_id)
 if not repo: raise HTTPException(404,'Repository not found')
 results,_=search_with_capability(db,body.question,'hybrid',8,repository_id=repo.id); citations=[result_citation(db,repo,x) for x in results]
 answer='No indexed code in this repository evidences an answer to this question.' if not results else 'Retrieved evidence: '+'; '.join(f"{x['path']}:{x['start_line']}-{x['end_line']}"+(f" ({x['symbol']})" if x.get('symbol') else '') for x in results[:3])+'.'
 return {'answer':answer,'citations':citations,'scope':{'repository_id':repo.id,'indexed_commit_sha':repo.indexed_commit_sha},'grounded':bool(results),'answer_mode':'retrieval_only'}
@app.post('/api/documentation/generate')
def documentation(body:DocumentationIn,db:Session=Depends(get_db)):
 repo=db.get(Repository,body.repository_id)
 if not repo: raise HTTPException(404,'Repository not found')
 symbol=scoped_symbol(db,repo.id,body.symbol_id); file=db.get(File,symbol.file_id)
 if not file: raise HTTPException(404,'File not found')
 edges=scoped_edges(db,repo.id); callers=[e for e in edges if e.target_symbol_id==symbol.id and e.source_symbol_id]; callees=[e for e in edges if e.source_symbol_id==symbol.id and e.target_symbol_id]
 related=scoped_symbols(db,repo.id,{e.source_symbol_id for e in callers}|{e.target_symbol_id for e in callees}); citations=[citation(repo,file,symbol)]
 for related_symbol in sorted(related.values(),key=lambda s:(s.qualified_name,s.id)):
  related_file=db.get(File,related_symbol.file_id)
  if related_file: citations.append(citation(repo,related_file,related_symbol))
 caller_names=[related[e.source_symbol_id].qualified_name for e in callers if e.source_symbol_id in related]; callee_names=[related[e.target_symbol_id].qualified_name for e in callees if e.target_symbol_id in related]
 markdown=f"# {symbol.qualified_name}\n\n**Type:** {symbol.symbol_type}\n\n**Location:** `{file.path}:{symbol.start_line}-{symbol.end_line}`\n\n## Overview\n\n{symbol.signature or symbol.name}\n\n## Direct callers\n\n"+('\n'.join(f'- `{name}`' for name in sorted(caller_names)) if caller_names else 'No indexed direct callers.')+"\n\n## Direct callees\n\n"+('\n'.join(f'- `{name}`' for name in sorted(callee_names)) if callee_names else 'No indexed direct callees.')
 return {'markdown':markdown,'citations':citations,'scope':{'repository_id':repo.id,'indexed_commit_sha':repo.indexed_commit_sha}}
@app.post('/api/chat')
def chat(body:ChatIn,db:Session=Depends(get_db)):
 results, semantic = search_with_capability(db,body.question,'hybrid',12,repository_id=body.repository_id); citations=[{'repository':x['repository'],'file_id':x['file_id'],'path':x['path'],'start_line':x['start_line'],'end_line':x['end_line']} for x in results]
 context='\n\n'.join(f"[{i+1}] {x['repository']}/{x['path']}:{x['start_line']}-{x['end_line']}\n{x['snippet']}" for i,x in enumerate(results))
 answer=('No indexed code matched this question.' if not results else 'Grounded sources found for your question. Configure OPENAI_API_KEY to enable synthesized answers; the citations below are verified retrieval results.')
 convo=db.get(Conversation,body.conversation_id) if body.conversation_id else None
 if not convo: convo=Conversation(repository_id=body.repository_id,title=body.question[:120]);db.add(convo);db.flush()
 db.add(Message(conversation_id=convo.id,role='user',content=body.question));db.add(Message(conversation_id=convo.id,role='assistant',content=answer,citations=citations));db.commit()
 return {'conversation_id':convo.id,'answer':answer,'citations':citations,'retrieval':{'lexical':True,'semantic':semantic,'symbols':any(x['type']=='symbol' for x in results),'context_preview':context[:settings.chat_context_limit]}}
@app.get('/api/jobs/{job_id}')
def job(job_id:str,db:Session=Depends(get_db)):
 j=db.get(IndexingJob,job_id)
 if not j: raise HTTPException(404,'Job not found')
 return {'id':j.id,'status':j.status,'kind':j.kind,'progress':j.progress,'error_message':j.error_message}
@app.get('/api/conversations')
def conversations(db:Session=Depends(get_db)): return [{'id':c.id,'title':c.title,'created_at':c.created_at} for c in db.scalars(select(Conversation).order_by(Conversation.created_at.desc())).all()]
@app.get('/api/conversations/{conversation_id}')
def conversation(conversation_id:str,db:Session=Depends(get_db)):
 if not db.get(Conversation,conversation_id): raise HTTPException(404,'Conversation not found')
 return [{'id':m.id,'role':m.role,'content':m.content,'citations':m.citations,'created_at':m.created_at} for m in db.scalars(select(Message).where(Message.conversation_id==conversation_id).order_by(Message.created_at)).all()]
