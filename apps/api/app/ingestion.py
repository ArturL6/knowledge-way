import hashlib, re, subprocess
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete, select

from app.config import settings
from app.db import SessionLocal
from app.models import CodeChunk, File, IndexingJob, Repository, Symbol, SymbolEdge
from app.parser_facts import analyze_source

EXT={'.py':'python','.js':'javascript','.jsx':'jsx','.ts':'typescript','.tsx':'tsx','.go':'go','.java':'java','.rs':'rust','.c':'c','.h':'c','.cpp':'cpp','.cs':'csharp','.rb':'ruby','.php':'php','.sh':'bash','.sql':'sql','.json':'json','.yaml':'yaml','.yml':'yaml','.toml':'toml','.md':'markdown'}
IGNORE={'.git','node_modules','vendor','dist','build','.next','coverage','target','.venv','venv','__pycache__'}
SECRET={'.env', '.env.local', 'credentials.json', 'secrets.yml'}
PARSER_LANGUAGES={'python', 'javascript', 'jsx', 'typescript', 'tsx'}
RESOLVED_CONFIDENCE=100
UNRESOLVED_CONFIDENCE=20


def run(*args,cwd=None): return subprocess.run(args,cwd=cwd,text=True,capture_output=True,check=True).stdout.strip()
def language(p): return EXT.get(Path(p).suffix.lower())
def chunks(content,lang):
 lines=content.splitlines(); out=[]; pattern=r'^\s*(?:async\s+def|def|class)\s+([A-Za-z_]\w*)' if lang=='python' else r'^\s*(?:export\s+)?(?:async\s+)?(?:function|class|interface|const)\s+([A-Za-z_$]\w*)'
 starts=[(i+1,m.group(1)) for i,l in enumerate(lines) if (m:=re.match(pattern,l))]
 for n,(start,name) in enumerate(starts): out.append((name,start,(starts[n+1][0]-1 if n+1<len(starts) else len(lines)), '\n'.join(lines[start-1:(starts[n+1][0]-1 if n+1<len(starts) else len(lines))])))
 return out or [(None,1,len(lines),content)]


def _parser_symbols_and_chunks(db, repo_id, file, content, lang, sha):
 """Persist parser declarations and return parser reference evidence for one file."""
 facts = analyze_source(content, lang)
 symbols_by_qualified = {}
 raw = content.encode('utf-8')
 for declaration in facts.declarations:
  source_text = raw[declaration.range.start_byte:declaration.range.end_byte].decode('utf-8')
  symbol = Symbol(
   repository_id=repo_id, file_id=file.id, name=declaration.name,
   qualified_name=declaration.qualified_name, symbol_type=declaration.kind,
   language=lang, start_line=declaration.range.start_line,
   end_line=declaration.range.end_line, start_byte=declaration.range.start_byte,
   end_byte=declaration.range.end_byte, source_text=source_text,
   signature=declaration.signature,
  )
  db.add(symbol); db.flush()
  symbols_by_qualified[declaration.qualified_name] = symbol
  if declaration.parent_qualified_name:
   symbol.parent_symbol_id = symbols_by_qualified[declaration.parent_qualified_name].id
  db.add(CodeChunk(
   repository_id=repo_id, file_id=file.id, symbol_id=symbol.id, language=lang,
   chunk_type=declaration.kind, symbol_name=declaration.name,
   qualified_symbol_name=declaration.qualified_name,
   start_line=declaration.range.start_line, end_line=declaration.range.end_line,
   source_text=source_text, content_hash=hashlib.sha256(source_text.encode()).hexdigest(),
   indexed_commit_sha=sha,
  ))
 return facts, symbols_by_qualified


def _legacy_symbols_and_chunks(db, repo_id, file, content, lang, sha):
 for name,start,end,text in chunks(content,lang):
  sym=None
  if name:
   sym=Symbol(repository_id=repo_id,file_id=file.id,name=name,qualified_name=name,symbol_type='declaration',language=lang,start_line=start,end_line=end,start_byte=0,end_byte=len(text),source_text=text,signature=text.splitlines()[0]); db.add(sym);db.flush()
  db.add(CodeChunk(repository_id=repo_id,file_id=file.id,symbol_id=sym.id if sym else None,language=lang,chunk_type='function' if name else 'text',symbol_name=name,qualified_symbol_name=name,start_line=start,end_line=end,source_text=text,content_hash=hashlib.sha256(text.encode()).hexdigest(),indexed_commit_sha=sha))


def _persist_edges(db, repo_id, parser_files):
 """Resolve only a unique declaration name inside this repository."""
 all_symbols = db.scalars(select(Symbol).where(Symbol.repository_id == repo_id)).all()
 candidates = {}
 for symbol in all_symbols:
  candidates.setdefault(symbol.name, []).append(symbol)

 def edge(source_file, source_symbol, target_name, relationship_type, line):
  matches = candidates.get(target_name, [])
  target = matches[0] if len(matches) == 1 else None
  db.add(SymbolEdge(
   repository_id=repo_id, source_symbol_id=source_symbol.id if source_symbol else None,
   target_symbol_id=target.id if target else None, target_name=target_name,
   relationship_type=relationship_type, source_file_id=source_file.id,
   line_number=line, confidence=RESOLVED_CONFIDENCE if target else UNRESOLVED_CONFIDENCE,
  ))

 for file, facts, symbols_by_qualified in parser_files:
  for reference in facts.references:
   edge(file, symbols_by_qualified.get(reference.scope_qualified_name), reference.target_name,
        'call', reference.range.start_line)
  for imported in facts.imports:
   # The imported declaration is the useful target for from-imports; bare imports
   # retain their local/module spelling as unresolved evidence when no declaration exists.
   target_name = imported.imported_name or imported.local_name or imported.module
   if target_name:
    edge(file, None, target_name, 'import', imported.range.start_line)


def index_repository(repo_id, full=False):
 db=SessionLocal(); repo=db.get(Repository,repo_id); job=IndexingJob(repository_id=repo_id,kind='full' if full else 'sync',status='running',started_at=datetime.utcnow(),progress={'phase':'cloning'}); db.add(job); db.commit()
 try:
  root=Path(settings.repository_storage_path)/repo_id; root.parent.mkdir(parents=True,exist_ok=True)
  if not root.exists(): run('git','clone','--depth','1',repo.clone_url,str(root))
  else: run('git','fetch','--depth','1','origin',cwd=root); run('git','reset','--hard','origin/HEAD',cwd=root)
  sha=run('git','rev-parse','HEAD',cwd=root); repo.local_path=str(root); repo.latest_detected_commit_sha=sha; repo.indexing_status='indexing'; repo.indexing_progress={'phase':'scanning'}; db.commit()
  paths=[]
  for p in root.rglob('*'):
   if not p.is_file() or any(x in IGNORE for x in p.parts) or p.name in SECRET or p.suffix.lower() in {'.pem','.key'} or p.stat().st_size>settings.max_file_size: continue
   try: raw=p.read_text(errors='strict')
   except (UnicodeDecodeError,OSError): continue
   paths.append((p.relative_to(root).as_posix(),raw,p.stat().st_size,language(str(p))))
  if full:
   # A full index is a graph snapshot. Never leave references to replaced symbols.
   db.execute(delete(SymbolEdge).where(SymbolEdge.repository_id == repo_id))
  existing={f.path:f for f in db.scalars(select(File).where(File.repository_id==repo_id)).all()}
  parser_files=[]
  for path,content,size,lang in paths:
   digest=hashlib.sha256(content.encode()).hexdigest(); f=existing.pop(path,None)
   if f and f.content_hash==digest and not full: continue
   if f: db.execute(delete(Symbol).where(Symbol.file_id==f.id)); db.execute(delete(CodeChunk).where(CodeChunk.file_id==f.id)); f.content=content;f.content_hash=digest;f.size_bytes=size;f.language=lang;f.indexed_commit_sha=sha
   else: f=File(repository_id=repo_id,path=path,content=content,content_hash=digest,size_bytes=size,language=lang,indexed_commit_sha=sha);db.add(f);db.flush()
   if full and lang in PARSER_LANGUAGES:
    facts, symbols = _parser_symbols_and_chunks(db, repo_id, f, content, lang, sha)
    parser_files.append((f, facts, symbols))
   else:
    _legacy_symbols_and_chunks(db, repo_id, f, content, lang, sha)
  for f in existing.values(): db.delete(f)
  if full:
   db.flush()
   _persist_edges(db, repo_id, parser_files)
  repo.indexed_commit_sha=sha;repo.indexed_branch=run('git','branch','--show-current',cwd=root);repo.indexing_status='ready';repo.indexing_progress={'phase':'finalizing','files':len(paths)};repo.last_indexed_at=datetime.utcnow();repo.last_sync_at=datetime.utcnow();job.status='ready';job.progress=repo.indexing_progress;job.finished_at=datetime.utcnow();db.commit()
 except Exception as e:
  repo.indexing_status='failed';repo.error_message=str(e);job.status='failed';job.error_message=str(e);job.finished_at=datetime.utcnow();db.commit();raise
 finally: db.close()
