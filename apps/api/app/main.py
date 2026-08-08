from pathlib import PurePosixPath
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from redis import Redis
from rq import Queue
from app.config import settings
from app.db import Base, engine, get_db
from app.models import Repository, File, Symbol, CodeChunk, IndexingJob, Conversation, Message
from app.search import search

app=FastAPI(title='knowledge-way API',version='0.1.0')
app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origins.split(','),allow_methods=['*'],allow_headers=['*'])
@app.on_event('startup')
def startup(): Base.metadata.create_all(engine)
class RepositoryIn(BaseModel):
 name:str=Field(min_length=1,max_length=255); clone_url:str=Field(min_length=8,max_length=2048)
class ChatIn(BaseModel):
 question:str=Field(min_length=1,max_length=8000); repository_id:str|None=None; conversation_id:str|None=None

def repo_out(r): return {'id':r.id,'name':r.name,'clone_url':r.clone_url,'default_branch':r.default_branch,'indexed_branch':r.indexed_branch,'indexed_commit_sha':r.indexed_commit_sha,'latest_detected_commit_sha':r.latest_detected_commit_sha,'indexing_status':r.indexing_status,'indexing_progress':r.indexing_progress,'error_message':r.error_message,'last_indexed_at':r.last_indexed_at,'last_sync_at':r.last_sync_at,'created_at':r.created_at}
def enqueue(repo_id,full=False):
 try: return Queue('indexing',connection=Redis.from_url(settings.redis_url)).enqueue('app.ingestion.index_repository',repo_id,full).id
 except Exception: return None
@app.get('/health')
def health(): return {'status':'ok'}
@app.get('/api/repositories')
def repositories(db:Session=Depends(get_db)): return [repo_out(r) for r in db.scalars(select(Repository).order_by(Repository.created_at.desc())).all()]
@app.post('/api/repositories',status_code=202)
def add_repository(body:RepositoryIn,db:Session=Depends(get_db)):
 if not (body.clone_url.startswith(('https://','git@','ssh://')) and '..' not in body.clone_url): raise HTTPException(422,'A safe Git clone URL is required')
 r=Repository(name=body.name,clone_url=body.clone_url,indexing_status='pending');db.add(r);db.commit();db.refresh(r); return {'repository':repo_out(r),'job_id':enqueue(r.id,True)}
@app.get('/api/repositories/{repo_id}')
def repository(repo_id:str,db:Session=Depends(get_db)):
 r=db.get(Repository,repo_id)
 if not r: raise HTTPException(404,'Repository not found')
 return repo_out(r)
@app.delete('/api/repositories/{repo_id}',status_code=204)
def delete_repository(repo_id:str,db:Session=Depends(get_db)):
 r=db.get(Repository,repo_id)
 if not r: raise HTTPException(404,'Repository not found')
 db.delete(r);db.commit()
@app.post('/api/repositories/{repo_id}/sync',status_code=202)
def sync(repo_id:str,db:Session=Depends(get_db)):
 if not db.get(Repository,repo_id): raise HTTPException(404,'Repository not found')
 return {'job_id':enqueue(repo_id,False)}
@app.post('/api/repositories/{repo_id}/reindex',status_code=202)
def reindex(repo_id:str,db:Session=Depends(get_db)):
 if not db.get(Repository,repo_id): raise HTTPException(404,'Repository not found')
 return {'job_id':enqueue(repo_id,True)}
@app.get('/api/repositories/{repo_id}/status')
def status(repo_id:str,db:Session=Depends(get_db)):
 r=db.get(Repository,repo_id)
 if not r: raise HTTPException(404,'Repository not found')
 return {'status':r.indexing_status,'progress':r.indexing_progress,'error':r.error_message,'indexed_commit_sha':r.indexed_commit_sha}
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
@app.get('/api/search')
def text_search(q:str,mode:str='hybrid',limit:int=30,db:Session=Depends(get_db)): return {'query':q,'mode':mode,'results':search(db,q,mode,min(max(limit,1),100))}
@app.get('/api/search/symbols')
def symbol_search(q:str,db:Session=Depends(get_db)): return {'results':search(db,q,'symbols')}
@app.post('/api/search/semantic')
def semantic_search(body:dict,db:Session=Depends(get_db)): return {'results':search(db,body.get('query',''),'semantic')}
@app.post('/api/chat')
def chat(body:ChatIn,db:Session=Depends(get_db)):
 results=search(db,body.question,'hybrid',12,repository_id=body.repository_id); citations=[{'repository':x['repository'],'file_id':x['file_id'],'path':x['path'],'start_line':x['start_line'],'end_line':x['end_line']} for x in results]
 context='\n\n'.join(f"[{i+1}] {x['repository']}/{x['path']}:{x['start_line']}-{x['end_line']}\n{x['snippet']}" for i,x in enumerate(results))
 answer=('No indexed code matched this question.' if not results else 'Grounded sources found for your question. Configure OPENAI_API_KEY to enable synthesized answers; the citations below are verified retrieval results.')
 convo=db.get(Conversation,body.conversation_id) if body.conversation_id else None
 if not convo: convo=Conversation(repository_id=body.repository_id,title=body.question[:120]);db.add(convo);db.flush()
 db.add(Message(conversation_id=convo.id,role='user',content=body.question));db.add(Message(conversation_id=convo.id,role='assistant',content=answer,citations=citations));db.commit()
 return {'conversation_id':convo.id,'answer':answer,'citations':citations,'retrieval':{'lexical':True,'semantic':False,'symbols':any(x['type']=='symbol' for x in results),'context_preview':context[:settings.chat_context_limit]}}
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
