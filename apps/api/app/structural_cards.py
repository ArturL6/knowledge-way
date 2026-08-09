"""Deterministic, evidence-only views over an indexed repository graph."""
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import PurePosixPath
from sqlalchemy import delete, select
from app.models import File, StructuralCard, Symbol, SymbolEdge

SCHEMA_VERSION="structural-card-v1"
MAX_BOUNDARY_EVIDENCE=20

def canonical(value): return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True)
def fingerprint(value): return hashlib.sha256(canonical(value).encode()).hexdigest()
def ancestors(path):
 parent=PurePosixPath(path).parent; out={""}
 while str(parent) not in ("", "."): out.add(str(parent)); parent=parent.parent
 return out

def refresh_structural_cards(db,repo_id,sha):
 files=sorted(db.scalars(select(File).where(File.repository_id==repo_id)).all(),key=lambda f:f.path)
 symbols=db.scalars(select(Symbol).where(Symbol.repository_id==repo_id)).all()
 edges=db.scalars(select(SymbolEdge).where(SymbolEdge.repository_id==repo_id)).all()
 by_file=defaultdict(list); by_id={f.id:f for f in files}; symbol_file_by_id={}
 for symbol in symbols:
  by_file[symbol.file_id].append(symbol)
  symbol_file_by_id[symbol.id]=symbol.file_id
 paths={p for file in files for p in ancestors(file.path)}
 package_paths={str(PurePosixPath(f.path).parent) if str(PurePosixPath(f.path).parent)!="." else "" for f in files if PurePosixPath(f.path).name in {"__init__.py","package.json"}}
 inputs=[]
 for kind,path in [("directory",p) for p in paths]+[("package",p) for p in package_paths]:
  direct=[f for f in files if str(PurePosixPath(f.path).parent).replace(".","")==path]
  child_paths=sorted({str(PurePosixPath(f.path).relative_to(path)).split("/")[0] for f in files if path and f.path.startswith(path+"/") and "/" in str(PurePosixPath(f.path).relative_to(path))} if path else {f.path.split("/")[0] for f in files if "/" in f.path})
  direct_symbols=[s for f in direct for s in by_file[f.id]]
  owned={f.id for f in files if f.path==path or (not path or f.path.startswith(path+"/"))}
  boundary=[]
  for edge in edges:
   source_inside=edge.source_file_id in owned; target_file=by_id.get(symbol_file_by_id.get(edge.target_symbol_id)); target_inside=bool(target_file and target_file.id in owned)
   if source_inside != target_inside:
    boundary.append((edge.relationship_type,"resolved" if edge.target_symbol_id else "unresolved",edge.target_name,edge.confidence))
  aggregates=[]
  for (relationship,resolution), group in __import__('itertools').groupby(sorted(boundary),key=lambda x:x[:2]):
   rows=list(group); aggregates.append({"relationship":relationship,"resolution":resolution,"count":len(rows),"targets":sorted({x[2] for x in rows})[:MAX_BOUNDARY_EVIDENCE]})
  facts={"direct_files":[{"path":f.path,"language":f.language,"content_hash":f.content_hash} for f in direct],"languages":dict(sorted(Counter(f.language or "unknown" for f in direct).items())),"symbol_types":dict(sorted(Counter(s.symbol_type for s in direct_symbols).items())),"child_paths":child_paths,"boundary_edges":aggregates}
  inputs.append((kind,path,facts))
 existing={(c.kind,c.path):c for c in db.scalars(select(StructuralCard).where(StructuralCard.repository_id==repo_id)).all()}; wanted=set()
 for kind,path,facts in inputs:
  wanted.add((kind,path)); content=fingerprint(facts); provenance=fingerprint({"schema_version":SCHEMA_VERSION,"files":[x["content_hash"] for x in facts["direct_files"]],"facts":facts})
  card=existing.get((kind,path))
  if not card: db.add(StructuralCard(repository_id=repo_id,kind=kind,path=path,facts=facts,content_fingerprint=content,provenance_fingerprint=provenance,indexed_commit_sha=sha,schema_version=SCHEMA_VERSION))
  else: card.facts=facts;card.content_fingerprint=content;card.provenance_fingerprint=provenance;card.indexed_commit_sha=sha;card.schema_version=SCHEMA_VERSION
 for key,card in existing.items():
  if key not in wanted: db.delete(card)
