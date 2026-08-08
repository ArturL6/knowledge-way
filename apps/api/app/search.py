import asyncio
import math
import re
from dataclasses import dataclass
from sqlalchemy import select, or_
from app.models import Repository, File, Symbol, CodeChunk
from app.providers import embedding_provider, semantic_capability

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
    return {'type': kind, 'score': score, 'repository': repo.name, 'repository_id': repo.id,
            'file_id': file.id, 'path': file.path, 'language': item.language,
            'start_line': item.start_line, 'end_line': item.end_line,
            'snippet': item.source_text[:1200], 'symbol': getattr(item, 'qualified_symbol_name', None) or getattr(item, 'qualified_name', None)}


def _key(item): return (item['type'], item['file_id'], item['start_line'], item['end_line'])
def _cosine(left, right):
    if len(left) != len(right): return None
    denominator = math.sqrt(sum(x*x for x in left)) * math.sqrt(sum(x*x for x in right))
    return sum(x*y for x, y in zip(left, right)) / denominator if denominator else None


def _fuse(result_sets, limit):
    """Deterministic reciprocal-rank fusion, with stable identity tie-breaking."""
    combined = {}
    for results in result_sets:
        for rank, item in enumerate(sorted(results, key=lambda x: (-x['score'], _key(x))), 1):
            key = _key(item)
            if key not in combined: combined[key] = dict(item, score=0.0)
            combined[key]['score'] += 1.0 / (60 + rank)
    return sorted(combined.values(), key=lambda x: (-x['score'], _key(x)))[:limit]


def search_with_capability(db, raw: str, mode='hybrid', limit=30, repository_id: str | None = None):
    q, terms = parse_query(raw), query_terms(parse_query(raw).text)
    repos = {r.id: r for r in db.scalars(select(Repository)).all()}
    lexical, symbols, semantic = [], [], []
    def allowed(repo): return repo and (not repository_id or repo.id == repository_id) and (not q.repo or q.repo.lower() in repo.name.lower())
    def chunk_stmt():
        stmt = select(CodeChunk, File).join(File, CodeChunk.file_id == File.id)
        if q.language: stmt = stmt.where(CodeChunk.language == q.language)
        if q.path: stmt = stmt.where(File.path.ilike(f'%{q.path}%'))
        return stmt
    if mode in ('hybrid', 'text', 'exact') and q.text:
        for chunk, file in db.execute(chunk_stmt().where(CodeChunk.source_text.ilike(f'%{q.text}%')).limit(limit * 2)):
            repo = repos.get(chunk.repository_id)
            if allowed(repo): lexical.append(result('chunk', 1.0, repo, file, chunk))
    if not lexical and mode in ('hybrid', 'text') and terms:
        clauses = [CodeChunk.source_text.ilike(f'%{term}%') for term in terms]
        for chunk, file in db.execute(chunk_stmt().where(or_(*clauses)).limit(limit * 8)):
            repo = repos.get(chunk.repository_id)
            if allowed(repo): lexical.append(result('chunk', .45 + .35 * sum(t in chunk.source_text.lower() for t in terms) / len(terms), repo, file, chunk))
    if mode in ('hybrid', 'symbols') and terms:
        clauses = [Symbol.name.ilike(f'%{term}%') for term in terms] + [Symbol.qualified_name.ilike(f'%{term}%') for term in terms]
        for symbol, file in db.execute(select(Symbol, File).join(File, Symbol.file_id == File.id).where(or_(*clauses)).limit(limit * 3)):
            repo = repos.get(symbol.repository_id)
            if allowed(repo): symbols.append(result('symbol', 1.0 if symbol.name.lower() in terms or symbol.qualified_name.lower() in terms else .85, repo, file, symbol))
    capability = semantic_capability()
    provider = embedding_provider()
    if mode in ('hybrid', 'semantic') and q.text and provider is not None:
        try:
            query_vector = asyncio.run(provider.embed_texts([q.text]))[0]
            # Python cosine is portable to SQLite tests and pgvector production; only matching
            # model/dimension rows participate, avoiding invalid pgvector comparisons.
            for chunk, file in db.execute(chunk_stmt().where(CodeChunk.embedding_model == provider.model).where(CodeChunk.embedding.is_not(None))):
                repo = repos.get(chunk.repository_id)
                score = _cosine(query_vector, list(chunk.embedding))
                if allowed(repo) and score is not None: semantic.append(result('chunk', score, repo, file, chunk))
            semantic.sort(key=lambda x: (-x['score'], _key(x)))
            capability['indexed_candidates'] = len(semantic)
        except Exception:
            capability['state'] = 'degraded'
            capability['enabled'] = False
            capability['reason'] = 'embedding_request_failed'
    if mode == 'semantic': results = semantic[:limit]
    elif mode == 'symbols': results = _fuse([symbols], limit)
    elif mode in ('text', 'exact'): results = _fuse([lexical], limit)
    else: results = _fuse([lexical, symbols, semantic], limit)
    return results, capability


def search(db, raw: str, mode='hybrid', limit=30, repository_id: str | None = None):
    return search_with_capability(db, raw, mode, limit, repository_id)[0]
