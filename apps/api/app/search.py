import asyncio
import math
import re
from dataclasses import dataclass
from sqlalchemy import select, or_
from app.config import settings
from app.models import Repository, File, Symbol, CodeChunk
from app.providers import embedding_provider, rerank_provider, semantic_capability

STOP_WORDS = {"a", "an", "and", "are", "defined", "do", "for", "how", "in", "is", "of", "the", "to", "what", "where", "which", "with"}

@dataclass
class Query:
    text: str
    repo: str | None = None
    language: str | None = None
    path: str | None = None


def parse_query(raw: str) -> Query:
    filters = dict(re.findall(r'(repo|lang|path):([^\s]+)', raw))
    text = re.sub(r'(repo|lang|path):[^\s]+', '', raw).strip().strip('"')
    return Query(text, filters.get('repo'), filters.get('lang'), filters.get('path'))


def query_terms(text: str) -> list[str]:
    return [term.lower() for term in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text) if term.lower() not in STOP_WORDS]


def result(kind, score, repo, file, item):
    return {'type': kind, 'score': float(score), 'repository': repo.name, 'repository_id': repo.id,
            'file_id': file.id, 'path': file.path, 'language': item.language,
            'start_line': item.start_line, 'end_line': item.end_line,
            'snippet': item.source_text[:1200], 'symbol': getattr(item, 'qualified_symbol_name', None) or getattr(item, 'qualified_name', None),
            'symbol_id': item.id if kind == 'symbol' else getattr(item, 'symbol_id', None),
            'result_id': item.id,
            'indexed_commit_sha': getattr(item, 'indexed_commit_sha', None) or getattr(file, 'indexed_commit_sha', None)}


def _key(item): return (item['type'], item['file_id'], item['start_line'], item['end_line'])
def _identity(item): return (item['type'], item['result_id'])
def _cosine(left, right):
    if len(left) != len(right): return None
    denominator = math.sqrt(sum(x*x for x in left)) * math.sqrt(sum(x*x for x in right))
    return sum(x*y for x, y in zip(left, right)) / denominator if denominator else None


def _fuse(result_sets, limit):
    """Deterministic reciprocal-rank fusion. Dedupes/merges on row identity
    (type, result_id) -- not location -- so distinct rows sharing a span stay
    separate while the same row found via multiple retrieval paths merges its
    scores. `_key` (location) remains the sort tie-breaker for determinism."""
    combined = {}
    for results in result_sets:
        for rank, item in enumerate(sorted(results, key=lambda x: (-x['score'], _key(x))), 1):
            identity = _identity(item)
            if identity not in combined: combined[identity] = dict(item, score=0.0)
            combined[identity]['score'] += 1.0 / (60 + rank)
    return sorted(combined.values(), key=lambda x: (-x['score'], _key(x)))[:limit]


def search_with_capability(db, raw: str, mode='hybrid', limit=30, repository_id: str | None = None,
                           repository_ids: set[str] | None = None, rerank: bool = False):
    q, terms = parse_query(raw), query_terms(parse_query(raw).text)
    repos = {r.id: r for r in db.scalars(select(Repository)).all()}
    lexical, symbols, semantic = [], [], []
    exact_lexical_match = False
    # The allowed IDs are resolved server-side and pushed into every retrieval statement
    # before LIMIT. `repository_ids` is the workspace boundary; repository_id only narrows it.
    if repository_ids is not None and repository_id is not None and repository_id not in repository_ids:
        raise ValueError('Repository is not a member of this workspace')
    allowed_ids = {rid for rid, r in repos.items()
                   if (repository_ids is None or rid in repository_ids)
                   and (not repository_id or rid == repository_id)
                   and (not q.repo or q.repo.lower() in r.name.lower())}
    def chunk_stmt():
        stmt = (select(CodeChunk, File).join(File, CodeChunk.file_id == File.id)
                 .where(CodeChunk.repository_id.in_(allowed_ids))
                 .order_by(File.path, CodeChunk.start_line, CodeChunk.id))
        if q.language: stmt = stmt.where(CodeChunk.language == q.language)
        if q.path: stmt = stmt.where(File.path.ilike(f'%{q.path}%'))
        return stmt
    if mode in ('hybrid', 'text', 'exact') and q.text:
        for chunk, file in db.execute(chunk_stmt().where(CodeChunk.source_text.ilike(f'%{q.text}%')).limit(limit * 2)):
            lexical.append(result('chunk', 1.0, repos[chunk.repository_id], file, chunk))
        exact_lexical_match = bool(lexical)
    if not lexical and mode in ('hybrid', 'text') and terms:
        clauses = [CodeChunk.source_text.ilike(f'%{term}%') for term in terms]
        for chunk, file in db.execute(chunk_stmt().where(or_(*clauses)).limit(limit * 8)):
            lexical.append(result('chunk', .45 + .35 * sum(t in chunk.source_text.lower() for t in terms) / len(terms), repos[chunk.repository_id], file, chunk))
    if mode in ('hybrid', 'symbols') and terms:
        clauses = [Symbol.name.ilike(f'%{term}%') for term in terms] + [Symbol.qualified_name.ilike(f'%{term}%') for term in terms]
        symbol_stmt = (select(Symbol, File).join(File, Symbol.file_id == File.id)
                        .where(Symbol.repository_id.in_(allowed_ids)).where(or_(*clauses))
                        .order_by(File.path, Symbol.start_line, Symbol.id).limit(limit * 3))
        for symbol, file in db.execute(symbol_stmt):
            symbols.append(result('symbol', 1.0 if symbol.name.lower() in terms or symbol.qualified_name.lower() in terms else .85, repos[symbol.repository_id], file, symbol))
    capability = semantic_capability()
    provider = embedding_provider()
    # Exact lexical source hits are already precise evidence. In hybrid mode, avoid a billable
    # embedding round-trip for that fast path; broad token matches still receive semantic recall.
    if mode in ('hybrid', 'semantic') and q.text and provider is not None and (mode == 'semantic' or not exact_lexical_match):
        try:
            query_vector = asyncio.run(provider.embed_texts([q.text]))[0]
            # Python cosine is portable to SQLite tests and pgvector production; only matching
            # model/dimension rows participate, avoiding invalid pgvector comparisons. No LIMIT
            # here (it scans all embedded chunks), but the repository scope in chunk_stmt()
            # still applies -- this query must not read rows outside allowed_ids either.
            for chunk, file in db.execute(chunk_stmt().where(CodeChunk.embedding_model == provider.model).where(CodeChunk.embedding.is_not(None))):
                score = _cosine(query_vector, list(chunk.embedding))
                if score is not None: semantic.append(result('chunk', score, repos[chunk.repository_id], file, chunk))
            semantic.sort(key=lambda x: (-x['score'], _key(x)))
            capability['indexed_candidates'] = len(semantic)
        except Exception:
            capability['state'] = 'degraded'
            capability['enabled'] = False
            capability['reason'] = 'embedding_request_failed'
    if mode == 'semantic': results = semantic[:limit]
    elif mode == 'symbols': results = _fuse([symbols], limit)
    elif mode in ('text', 'exact'): results = _fuse([lexical], limit)
    else:
        candidate_limit = max(limit, min(settings.rerank_candidate_limit, 100)) if rerank else limit
        results = _fuse([lexical, symbols, semantic], candidate_limit)
    reranker = rerank_provider() if rerank and mode == 'hybrid' else None
    capability['reranking']['requested'] = rerank
    capability['reranking']['applied'] = False
    if rerank and reranker is not None and results:
        try:
            documents = [f"{item.get('symbol') or ''}\n{item['path']}\n{item['snippet']}" for item in results]
            scores = asyncio.run(reranker.rerank(q.text, documents))
            if len(scores) != len(results): raise RuntimeError('reranker returned incomplete scores')
            results = [item for _, item in sorted(zip(scores, results), key=lambda x: (-x[0], _key(x[1])))]
            capability['reranking']['applied'] = True
        except Exception:
            capability['reranking']['state'] = 'degraded'
            capability['reranking']['reason'] = 'rerank_request_failed'
    return results[:limit], capability


def search(db, raw: str, mode='hybrid', limit=30, repository_id: str | None = None,
           repository_ids: set[str] | None = None):
    return search_with_capability(db, raw, mode, limit, repository_id, repository_ids)[0]
