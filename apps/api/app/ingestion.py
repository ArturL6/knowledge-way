import asyncio, hashlib, re, subprocess
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete, select

from app.config import settings
from app.git_auth import git_environment, redact_git_error
from app.db import SessionLocal
from app.models import CodeCard, CodeChunk, File, IndexingJob, Repository, Symbol, SymbolEdge
from app.structural_cards import refresh_structural_cards
from app.parser_facts import analyze_source
from app.providers import embedding_provider

EXT={'.py':'python','.js':'javascript','.jsx':'jsx','.ts':'typescript','.tsx':'tsx','.go':'go','.java':'java','.rs':'rust','.c':'c','.h':'c','.cpp':'cpp','.cs':'csharp','.rb':'ruby','.php':'php','.sh':'bash','.sql':'sql','.json':'json','.yaml':'yaml','.yml':'yaml','.toml':'toml','.md':'markdown'}
IGNORE={'.git','node_modules','vendor','dist','build','.next','coverage','target','.venv','venv','__pycache__'}
SECRET={'.env', '.env.local', 'credentials.json', 'secrets.yml'}
PARSER_LANGUAGES={'python', 'javascript', 'jsx', 'typescript', 'tsx'}
RESOLVED_CONFIDENCE=100
UNRESOLVED_CONFIDENCE=20


def run(*args,cwd=None,clone_url=None):
 env=git_environment(clone_url) if clone_url else None
 try:
  return subprocess.run(args,cwd=cwd,text=True,capture_output=True,check=True,env=env).stdout.strip()
 except subprocess.CalledProcessError as error:
  # stderr may contain HTTP diagnostics. Persist a deliberately redacted summary only.
  detail=redact_git_error(error.stderr or error.stdout or '')[:2000]
  raise RuntimeError(f'Git command failed (exit {error.returncode}): {detail or "no safe diagnostic available"}') from None
def language(p): return EXT.get(Path(p).suffix.lower())
def chunks(content,lang):
 lines=content.splitlines(); out=[]; pattern=r'^\s*(?:async\s+def|def|class)\s+([A-Za-z_]\w*)' if lang=='python' else r'^\s*(?:export\s+)?(?:async\s+)?(?:function|class|interface|const)\s+([A-Za-z_$]\w*)'
 starts=[(i+1,m.group(1)) for i,l in enumerate(lines) if (m:=re.match(pattern,l))]
 for n,(start,name) in enumerate(starts): out.append((name,start,(starts[n+1][0]-1 if n+1<len(starts) else len(lines)), '\n'.join(lines[start-1:(starts[n+1][0]-1 if n+1<len(starts) else len(lines))])))
 return out or [(None,1,len(lines),content)]


def _snapshot_code_cards(db, repo_id):
 """Keep valid derived cards while a deterministic reindex replaces symbol rows.

 Cards are keyed by stable source evidence (path, qualified name, source hash), not
 transient database symbol IDs.  This makes snapshot refreshes resumable without
 another billable Gemini request for unchanged code.
 """
 rows = db.execute(
  select(CodeCard, Symbol.qualified_name, File.path)
  .join(Symbol, CodeCard.symbol_id == Symbol.id)
  .join(File, Symbol.file_id == File.id)
  .where(CodeCard.repository_id == repo_id)
 ).all()
 return {
  (path, qualified_name, card.source_hash): {
   "model": card.model, "prompt_version": card.prompt_version, "status": card.status,
   "summary": card.summary, "details": card.details,
   "input_tokens": card.input_tokens, "output_tokens": card.output_tokens,
   "created_at": card.created_at,
  }
  for card, qualified_name, path in rows
 }


def _restore_code_cards(db, repo_id, sha, preserved_cards):
 """Attach preserved cards to the freshly parsed equivalent symbols."""
 if not preserved_cards:
  return 0
 restored = 0
 rows = db.execute(
  select(Symbol, File.path).join(File, Symbol.file_id == File.id)
  .where(Symbol.repository_id == repo_id)
 ).all()
 for symbol, path in rows:
  source_hash = hashlib.sha256(symbol.source_text.encode()).hexdigest()
  values = preserved_cards.get((path, symbol.qualified_name, source_hash))
  if values:
   db.add(CodeCard(repository_id=repo_id, symbol_id=symbol.id, source_hash=source_hash,
                   indexed_commit_sha=sha, **values))
   restored += 1
 return restored


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


def _embedding_document(repo, chunk, file, symbol, card, edges):
 """Evidence-first retrieval document; AI cards are optional, never a substitute for code."""
 calls=sorted({e.target_name for e in edges if symbol and e.source_symbol_id==symbol.id and e.relationship_type=='call'})[:20]
 imports=sorted({e.target_name for e in edges if e.source_file_id==file.id and e.relationship_type=='import'})[:20]
 header=[f'Repository: {repo.name}',f'Path: {file.path}',f'Language: {chunk.language or "unknown"}',f'Kind: {chunk.chunk_type}']
 if symbol: header += [f'Symbol: {symbol.qualified_name}',f'Signature: {symbol.signature or symbol.name}']
 if card: header += [f'AI code-card summary (commit {card.indexed_commit_sha}): {card.summary}',f'Keywords: {", ".join(card.details.get("keywords", []))}']
 if calls: header.append(f'Static calls: {", ".join(calls)}')
 if imports: header.append(f'Static imports: {", ".join(imports)}')
 return '\n'.join(header)+'\n\nSource code:\n'+chunk.source_text


def _embed_full_index_chunks(db, repo_id, reusable_embeddings):
 """Persist embeddings for contextual retrieval documents, with code as primary evidence."""
 provider = embedding_provider()
 if provider is None: return
 repo=db.get(Repository,repo_id); files={f.id:f for f in db.scalars(select(File).where(File.repository_id==repo_id)).all()}; symbols={s.id:s for s in db.scalars(select(Symbol).where(Symbol.repository_id==repo_id)).all()}; cards={c.symbol_id:c for c in db.scalars(select(CodeCard).where(CodeCard.repository_id==repo_id)).all()}; edges=db.scalars(select(SymbolEdge).where(SymbolEdge.repository_id==repo_id)).all(); missing=[]
 for chunk in db.scalars(select(CodeChunk).where(CodeChunk.repository_id == repo_id)).all():
  if not chunk.source_text.strip(): db.delete(chunk); continue
  text=_embedding_document(repo,chunk,files[chunk.file_id],symbols.get(chunk.symbol_id),cards.get(chunk.symbol_id),edges); key=hashlib.sha256(text.encode()).hexdigest()
  cached=reusable_embeddings.get((key,provider.model))
  if cached is not None: chunk.embedding,chunk.embedding_model,chunk.embedding_input_hash=cached,provider.model,key
  else: missing.append((chunk,text,key))
 for offset in range(0,len(missing),settings.embedding_batch_size):
  batch=missing[offset:offset+settings.embedding_batch_size]; vectors=asyncio.run(provider.embed_texts([text for _,text,_ in batch]))
  if len(vectors)!=len(batch): raise RuntimeError('embedding provider returned an incomplete embedding batch')
  for (chunk,_,document_key),vector in zip(batch,vectors): chunk.embedding,chunk.embedding_model,chunk.embedding_input_hash=vector,provider.model,document_key


def reembed_repository(repo_id):
 """Refresh only vectors after Code Cards change; no clone or graph rebuild."""
 db=SessionLocal()
 try:
  repo=db.get(Repository,repo_id)
  if not repo: raise RuntimeError('Repository not found')
  _embed_full_index_chunks(db,repo_id,{})
  db.commit()
 finally: db.close()


def index_repository(repo_id, full=False):
 db=SessionLocal(); repo=db.get(Repository,repo_id); job=IndexingJob(repository_id=repo_id,kind='full' if full else 'sync',status='running',started_at=datetime.utcnow(),progress={'phase':'cloning'}); db.add(job); db.commit()
 try:
  root=Path(settings.repository_storage_path)/repo_id; root.parent.mkdir(parents=True,exist_ok=True)
  if not root.exists(): run('git','clone','--depth','1',repo.clone_url,str(root),clone_url=repo.clone_url)
  if repo.requested_revision:
   run('git','fetch','--depth','1','origin',repo.requested_revision,cwd=root,clone_url=repo.clone_url)
   run('git','checkout','--detach',repo.requested_revision,cwd=root)
  else:
   run('git','fetch','--depth','1','origin',cwd=root,clone_url=repo.clone_url); run('git','reset','--hard','origin/HEAD',cwd=root)
  sha=run('git','rev-parse','HEAD',cwd=root)
  if repo.requested_revision and sha != repo.requested_revision: raise RuntimeError('requested revision did not resolve to the indexed commit')
  repo.local_path=str(root); repo.latest_detected_commit_sha=sha; repo.indexing_status='indexing'; repo.indexing_progress={'phase':'scanning'}; db.commit()
  paths=[]
  for p in root.rglob('*'):
   if not p.is_file() or any(x in IGNORE for x in p.parts) or p.name in SECRET or p.suffix.lower() in {'.pem','.key'} or p.stat().st_size>settings.max_file_size: continue
   try: raw=p.read_text(errors='strict')
   except (UnicodeDecodeError,OSError): continue
   paths.append((p.relative_to(root).as_posix(),raw,p.stat().st_size,language(str(p))))
  # Preserve valid card payloads before replacing transient symbol IDs below.
  preserved_cards = _snapshot_code_cards(db, repo_id)
  # Make deletion explicit so SQLite tests and PostgreSQL have identical semantics.
  db.execute(delete(CodeCard).where(CodeCard.repository_id == repo_id))
  db.execute(delete(SymbolEdge).where(SymbolEdge.repository_id == repo_id))
  reusable_embeddings = {}
  # Keyed on the hash of the embedded document, not of raw source: a chunk whose code is unchanged
  # but whose code card or resolved calls moved must be re-embedded, not served a stale vector.
  if embedding_provider() is not None:
   for chunk in db.scalars(select(CodeChunk).where(CodeChunk.repository_id==repo_id).where(CodeChunk.embedding.is_not(None))).all():
    if chunk.embedding_model and chunk.embedding_input_hash:
     reusable_embeddings[(chunk.embedding_input_hash, chunk.embedding_model)] = list(chunk.embedding)
  existing={f.path:f for f in db.scalars(select(File).where(File.repository_id==repo_id)).all()}
  parser_files=[]
  for path,content,size,lang in paths:
   digest=hashlib.sha256(content.encode()).hexdigest(); f=existing.pop(path,None)
   if f and f.content_hash==digest: f.indexed_commit_sha=sha
   if f: db.execute(delete(Symbol).where(Symbol.file_id==f.id)); db.execute(delete(CodeChunk).where(CodeChunk.file_id==f.id)); f.content=content;f.content_hash=digest;f.size_bytes=size;f.language=lang;f.indexed_commit_sha=sha
   else: f=File(repository_id=repo_id,path=path,content=content,content_hash=digest,size_bytes=size,language=lang,indexed_commit_sha=sha);db.add(f);db.flush()
   if lang in PARSER_LANGUAGES:
    facts, symbols = _parser_symbols_and_chunks(db, repo_id, f, content, lang, sha)
    parser_files.append((f, facts, symbols))
   else:
    _legacy_symbols_and_chunks(db, repo_id, f, content, lang, sha)
  for f in existing.values(): db.delete(f)
  db.flush()
  _persist_edges(db, repo_id, parser_files)
  _restore_code_cards(db, repo_id, sha, preserved_cards)
  db.flush()
  refresh_structural_cards(db, repo_id, sha)
  _embed_full_index_chunks(db, repo_id, reusable_embeddings)
  repo.indexed_commit_sha=sha;repo.indexed_branch=run('git','branch','--show-current',cwd=root) or None;repo.indexing_status='ready';repo.error_message=None;repo.indexing_progress={'phase':'finalizing','files':len(paths)};repo.last_indexed_at=datetime.utcnow();repo.last_sync_at=datetime.utcnow();job.status='ready';job.progress=repo.indexing_progress;job.finished_at=datetime.utcnow();db.commit()
 except Exception as e:
  # The try block is part-way through a destructive rewrite: the old symbols, chunks and edges
  # are already deleted and the replacements are incomplete. Committing the failure bookkeeping
  # on this session would flush that half-written state and publish a corrupt index, so discard
  # it first and record the failure on a clean transaction.
  db.rollback()
  repo.indexing_status='failed';repo.error_message=str(e);job.status='failed';job.error_message=str(e);job.finished_at=datetime.utcnow();db.commit();raise
 finally: db.close()
