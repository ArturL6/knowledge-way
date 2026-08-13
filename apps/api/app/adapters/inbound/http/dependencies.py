"""HTTP adapter dependencies and response mapping helpers."""

from app.config import settings
from app.adapters.outbound.git_cli.git_auth import validate_clone_url
from app.adapters.outbound.postgres.db import SessionLocal, get_db, verify_migration_ready
from app.adapters.outbound.postgres.models import Repository, Workspace, WorkspaceRepository, WorkspaceDependency, File, Symbol, SymbolEdge, CodeChunk, CodeCard, StructuralCard, IndexingJob, Conversation, Message
from app.reconcile import reconcile_indexing_jobs
from app.search import search, search_with_capability
from app.adapters.outbound.llm_providers.providers import semantic_capability
from app.repository_cards import build_repository_card
from app.code_cards import code_card_model
from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from redis import Redis
from rq import Queue
from pathlib import PurePosixPath

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
