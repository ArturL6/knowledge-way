import re
from dataclasses import dataclass
from sqlalchemy import select, or_
from app.models import Repository, File, Symbol, CodeChunk

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
    """Extract code-like terms from a natural-language question for lexical fallback."""
    return [term.lower() for term in re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text) if term.lower() not in STOP_WORDS]


def result(kind, score, repo, file, item):
    return {
        'type': kind, 'score': score, 'repository': repo.name, 'repository_id': repo.id,
        'file_id': file.id, 'path': file.path, 'language': item.language,
        'start_line': item.start_line, 'end_line': item.end_line,
        'snippet': item.source_text[:1200], 'symbol': getattr(item, 'qualified_symbol_name', None) or item.qualified_name,
    }


def search(db, raw: str, mode='hybrid', limit=30, repository_id: str | None = None):
    q = parse_query(raw)
    repos = {r.id: r for r in db.scalars(select(Repository)).all()}
    candidates = []
    terms = query_terms(q.text)

    def allowed(repo):
        return repo and (not repository_id or repo.id == repository_id) and (not q.repo or q.repo.lower() in repo.name.lower())

    if mode in ('hybrid', 'text', 'exact', 'semantic') and q.text:
        stmt = select(CodeChunk, File).join(File, CodeChunk.file_id == File.id).where(CodeChunk.source_text.ilike(f'%{q.text}%'))
        if q.language: stmt = stmt.where(CodeChunk.language == q.language)
        if q.path: stmt = stmt.where(File.path.ilike(f'%{q.path}%'))
        for chunk, file in db.execute(stmt.limit(limit * 2)):
            repo = repos.get(chunk.repository_id)
            if allowed(repo): candidates.append(result('chunk', 1.0, repo, file, chunk))

    # Natural-language questions seldom occur verbatim in source. When exact text has
    # no match, retrieve chunks containing one or more code-like query terms instead.
    if not candidates and mode in ('hybrid', 'text', 'semantic') and terms:
        clauses = [CodeChunk.source_text.ilike(f'%{term}%') for term in terms]
        stmt = select(CodeChunk, File).join(File, CodeChunk.file_id == File.id).where(or_(*clauses))
        if q.language: stmt = stmt.where(CodeChunk.language == q.language)
        if q.path: stmt = stmt.where(File.path.ilike(f'%{q.path}%'))
        for chunk, file in db.execute(stmt.limit(limit * 8)):
            repo = repos.get(chunk.repository_id)
            if not allowed(repo): continue
            matches = sum(term in chunk.source_text.lower() for term in terms)
            candidates.append(result('chunk', 0.45 + 0.35 * matches / len(terms), repo, file, chunk))

    if mode in ('hybrid', 'symbols') and terms:
        clauses = [Symbol.name.ilike(f'%{term}%') for term in terms] + [Symbol.qualified_name.ilike(f'%{term}%') for term in terms]
        stmt = select(Symbol, File).join(File, Symbol.file_id == File.id).where(or_(*clauses)).limit(limit * 3)
        for symbol, file in db.execute(stmt):
            repo = repos.get(symbol.repository_id)
            if not allowed(repo): continue
            exact = symbol.name.lower() in terms or symbol.qualified_name.lower() in terms
            candidates.append(result('symbol', 1.0 if exact else .85, repo, file, symbol))

    seen, unique = set(), []
    for item in sorted(candidates, key=lambda x: x['score'], reverse=True):
        key = (item['file_id'], item['start_line'])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique[:limit]
