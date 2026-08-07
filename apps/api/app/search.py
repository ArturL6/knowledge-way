import re
from dataclasses import dataclass
from sqlalchemy import select, or_
from app.models import Repository, File, Symbol, CodeChunk
@dataclass
class Query: text:str; repo:str|None=None; language:str|None=None; path:str|None=None
def parse_query(raw:str)->Query:
    filters=dict(re.findall(r'(repo|lang|path):([^\s]+)',raw)); text=re.sub(r'(repo|lang|path):[^\s]+','',raw).strip().strip('"')
    return Query(text, filters.get('repo'), filters.get('lang'), filters.get('path'))
def search(db, raw:str, mode='hybrid', limit=30):
 q=parse_query(raw); repos={r.id:r for r in db.scalars(select(Repository)).all()}; candidates=[]
 if mode in ('hybrid','text','exact','semantic') and q.text:
  stmt=select(CodeChunk,File).join(File,CodeChunk.file_id==File.id).where(CodeChunk.source_text.ilike(f'%{q.text}%'))
  if q.language: stmt=stmt.where(CodeChunk.language==q.language)
  if q.path: stmt=stmt.where(File.path.ilike(f'%{q.path}%'))
  for c,f in db.execute(stmt.limit(limit*2)):
   r=repos.get(c.repository_id)
   if r and (not q.repo or q.repo.lower() in r.name.lower()): candidates.append({'type':'chunk','score':0.8,'repository':r.name,'repository_id':r.id,'file_id':f.id,'path':f.path,'language':c.language,'start_line':c.start_line,'end_line':c.end_line,'snippet':c.source_text[:1200],'symbol':c.qualified_symbol_name})
 if mode in ('hybrid','symbols') and q.text:
  stmt=select(Symbol,File).join(File,Symbol.file_id==File.id).where(or_(Symbol.name.ilike(f'%{q.text}%'),Symbol.qualified_name.ilike(f'%{q.text}%'))).limit(limit)
  for s,f in db.execute(stmt):
   r=repos.get(s.repository_id)
   if r and (not q.repo or q.repo.lower() in r.name.lower()): candidates.append({'type':'symbol','score':1.0 if s.name.lower()==q.text.lower() else .9,'repository':r.name,'repository_id':r.id,'file_id':f.id,'path':f.path,'language':s.language,'start_line':s.start_line,'end_line':s.end_line,'snippet':s.source_text[:1200],'symbol':s.qualified_name})
 seen=set(); unique=[]
 for item in sorted(candidates,key=lambda x:x['score'],reverse=True):
  key=(item['file_id'],item['start_line'])
  if key not in seen: seen.add(key); unique.append(item)
 return unique[:limit]
