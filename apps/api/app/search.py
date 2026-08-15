import asyncio
import math
import re
from dataclasses import dataclass
from sqlalchemy import select, or_, func, literal_column, delete, text as sql_text
from app.config import settings
from app.adapters.outbound.postgres.models import Repository, File, Symbol, CodeChunk, TermDocumentFrequency
from app.adapters.outbound.llm_providers.providers import embedding_provider, rerank_provider, semantic_capability
from app.domain.retrieval import fuse_rankings

STOP_WORDS = {"a", "an", "and", "are", "defined", "do", "for", "how", "in", "is", "of", "the", "to", "what", "where", "which", "with"}

# ADR-008: OR-ing every exploded query term (a real query can be a whole issue body, 150-300
# terms) matches a huge fraction of the corpus and makes ts_rank_cd sort it all -- measured p95
# ~3x the baseline. Digesting down to the N rarest (most discriminating) terms first keeps
# recall (common words add candidates, not signal) while bounding candidate-set size. N lives in
# settings.rare_term_limit (env RARE_TERM_LIMIT), not a module constant, so it can be tuned with
# an API restart instead of a rebuild.

# Must exactly mirror the generated-column expression in migration 20260815_0011_chunk_fts.py
# (camelCase boundary split, then `._/` treated as separators) so query tokens and indexed
# tokens agree. Case doesn't need to match here: to_tsquery/to_tsvector('simple', ...) lowercase.
_CAMEL_BOUNDARY = re.compile(r'([a-z0-9])([A-Z])')
_IDENTIFIER_SEPARATORS = re.compile(r'[._/]+')


def split_identifier_tokens(text_value: str) -> str:
    return _IDENTIFIER_SEPARATORS.sub(' ', _CAMEL_BOUNDARY.sub(r'\1 \2', text_value))


def select_discriminating_terms(terms, document_frequency, limit=25):
    """Pure term-selection (ADR-008): pick up to `limit` rarest-first terms by corpus document
    frequency. Deterministic tie-break: lower df, then longer term, then lexicographic.

    Terms absent from `document_frequency` are dropped whenever at least one known term
    exists -- an unseen lexeme can't match any indexed row, so keeping it wastes a slot
    without adding candidates. If NONE are known (e.g. an empty/stale df map), degrade to a
    still-deterministic length/lexicographic ordering over all terms rather than returning
    nothing."""
    seen, unique = set(), []
    for term in terms:
        if term not in seen: seen.add(term); unique.append(term)
    known = [t for t in unique if t in document_frequency]
    pool = known if known else unique
    return sorted(pool, key=lambda t: (document_frequency.get(t, 0), -len(t), t))[:limit]


def refresh_term_document_frequency(db):
    """Recompute corpus-wide lexical rarity stats (ADR-008) after an index changes fts_tokens.
    Postgres-only (ts_stat is a Postgres function); a no-op on SQLite.
    ponytail: full recompute across every repo on each index job, not incremental -- simple and
    correct; O(all chunks) but paid once off the query path. Scope to the reindexed repo's rows
    only if reindex frequency ever makes this a bottleneck."""
    if db.bind.dialect.name != 'postgresql': return
    db.execute(delete(TermDocumentFrequency))
    # ts_stat can surface lexemes far longer than any real query term (e.g. long encoded blobs
    # that tokenized as one "word"); cap at the column width rather than widen it for noise no
    # real query would ever produce.
    db.execute(sql_text("""
        INSERT INTO term_document_frequency (term, document_frequency)
        SELECT word, ndoc FROM ts_stat('SELECT fts_tokens FROM code_chunks WHERE fts_tokens IS NOT NULL')
        WHERE length(word) <= 255
    """))

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
    """Untagged-list compatibility wrapper around app.domain.retrieval.fuse_rankings: every
    list defaults to weight 1.0 (unweighted RRF), which is correct both for a single-mode
    call (order is unaffected by weight -- see fuse_rankings' docstring) and for any caller
    that doesn't care about per-mode trust. Real hybrid search below calls fuse_rankings
    directly with mode tags so semantic/lexical/symbol get their configured weights."""
    return fuse_rankings(enumerate(result_sets), limit=limit)


def search_with_capability(db, raw: str, mode='hybrid', limit=30, repository_id: str | None = None, rerank: bool = False):
    q, terms = parse_query(raw), query_terms(parse_query(raw).text)
    repos = {r.id: r for r in db.scalars(select(Repository)).all()}
    lexical, symbols, semantic = [], [], []
    exact_lexical_match = False
    # Repo scope is metadata-only (few rows) so it's cheap to resolve in Python, but the
    # resulting id set is pushed into SQL as a WHERE ... IN (...) on every retrieval query,
    # BEFORE that query's LIMIT -- otherwise an arbitrary LIMIT window can be filled entirely
    # by rows from repos outside scope, starving the scoped query to zero results.
    allowed_ids = {rid for rid, r in repos.items()
                   if (not repository_id or rid == repository_id) and (not q.repo or q.repo.lower() in r.name.lower())}
    def chunk_filters():
        filters = [CodeChunk.repository_id.in_(allowed_ids)]
        if q.language: filters.append(CodeChunk.language == q.language)
        if q.path: filters.append(File.path.ilike(f'%{q.path}%'))
        return filters
    def chunk_stmt():
        return (select(CodeChunk, File).join(File, CodeChunk.file_id == File.id)
                 .where(*chunk_filters())
                 .order_by(File.path, CodeChunk.start_line, CodeChunk.id))
    is_postgres = db.bind.dialect.name == 'postgresql'
    if mode in ('hybrid', 'text', 'exact') and q.text:
        # Exact/quoted substring match stays a plain ILIKE on both dialects. On Postgres it is
        # served by the pg_trgm GIN index ix_chunks_source_text_trgm (migration
        # 20260815_0011_chunk_fts) instead of a sequential scan, so it stays cheap while still
        # outranking the fuzzy FTS fallback below.
        for chunk, file in db.execute(chunk_stmt().where(CodeChunk.source_text.ilike(f'%{q.text}%')).limit(limit * 2)):
            lexical.append(result('chunk', 1.0, repos[chunk.repository_id], file, chunk))
        exact_lexical_match = bool(lexical)
    if not lexical and mode in ('hybrid', 'text') and terms:
        if is_postgres:
            # Code-aware full-text search: fts_tokens is a STORED generated tsvector column
            # (migration 20260815_0011_chunk_fts) built from source_text with identifier
            # splitting (camelCase/snake_case/dotted paths), backed by a GIN index.
            # split_identifier_tokens must mirror that column's expression so query tokens and
            # indexed tokens agree.
            #
            # OR, not AND: a real query (e.g. an issue body run through query_terms) can explode
            # into hundreds of terms; requiring all of them in one chunk (websearch_to_tsquery's
            # implicit AND) matches ~nothing. But OR-ing ALL of them matches a huge fraction of
            # the corpus and makes ts_rank_cd sort it all (measured ~3x baseline p95). ADR-008:
            # digest down to the settings.rare_term_limit rarest (most discriminating) terms first via
            # select_discriminating_terms, using corpus document frequency from
            # term_document_frequency (refreshed by refresh_term_document_frequency after every
            # index). ts_rank_cd still ranks candidates by how many/how densely the surviving
            # terms matched -- the same "fraction of terms matched" intent as the ILIKE-OR
            # fallback, ranked instead of flat-scored.
            query_tokens, seen = [], set()
            for term in terms:
                for token in split_identifier_tokens(term).split():
                    if token not in seen: seen.add(token); query_tokens.append(token)
            document_frequency = dict(db.execute(
                select(TermDocumentFrequency.term, TermDocumentFrequency.document_frequency)
                .where(TermDocumentFrequency.term.in_(query_tokens))
            ).all()) if query_tokens else {}
            chosen_tokens = select_discriminating_terms(query_tokens, document_frequency, settings.rare_term_limit)
            if chosen_tokens:
                fts_tokens = literal_column('code_chunks.fts_tokens')
                tsquery = func.to_tsquery('simple', ' | '.join(chosen_tokens))
                rank_expr = func.ts_rank_cd(fts_tokens, tsquery)
                stmt = (select(CodeChunk, File, rank_expr.label('rank_score'))
                         .join(File, CodeChunk.file_id == File.id)
                         .where(*chunk_filters()).where(fts_tokens.op('@@')(tsquery))
                         .order_by(rank_expr.desc()).limit(limit * 8))
                for chunk, file, rank_score in db.execute(stmt):
                    score = .45 + .35 * (rank_score / (1.0 + rank_score))
                    lexical.append(result('chunk', score, repos[chunk.repository_id], file, chunk))
        else:
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
            if is_postgres:
                # Real pgvector ANN query (migration 20260816_0013 adds the HNSW index):
                # ORDER BY the indexed cosine-distance operator + LIMIT, instead of pulling every
                # embedded chunk into Python. Latency stays roughly independent of corpus size
                # because Postgres never materializes more than the candidate window below.
                # cosine_distance() compiles to `<=>`, matching the index's vector_cosine_ops so
                # the planner can actually use it -- a different operator here would silently
                # fall back to a sequential scan.
                #
                # The window is wider than `limit` (mirrors the lexical `limit * 8` pattern above)
                # because this candidate set still feeds RRF fusion with lexical/symbol hits, not
                # just a standalone top-k.
                ann_limit = max(limit * 8, min(settings.rerank_candidate_limit, 100)) if rerank else limit * 8
                distance = CodeChunk.embedding.cosine_distance(query_vector)
                stmt = (select(CodeChunk, File, distance.label('distance'))
                         .join(File, CodeChunk.file_id == File.id)
                         .where(*chunk_filters()).where(CodeChunk.embedding_model == provider.model)
                         .where(CodeChunk.embedding.is_not(None))
                         .order_by(distance).limit(ann_limit))
                for chunk, file, distance_value in db.execute(stmt):
                    # pgvector cosine distance is 1 - cosine similarity; recover similarity so
                    # scores stay comparable to the SQLite Python-cosine fallback below.
                    semantic.append(result('chunk', 1.0 - float(distance_value), repos[chunk.repository_id], file, chunk))
            else:
                # SQLite has no pgvector/ANN support; this path exists only for the portable test
                # suite. Python cosine over a full scan. No LIMIT here (it scans all embedded
                # chunks), but the repository scope in chunk_stmt() still applies -- this query
                # must not read rows outside allowed_ids either.
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
        # Weighted RRF (packet 1.5): tag each list with its mode so a strong signal
        # (semantic) isn't diluted by weak modes agreeing on a junk row. See
        # app/domain/retrieval.py and settings.fusion_weight_* / fusion_rrf_k for the design
        # and default rationale.
        results = fuse_rankings(
            [('lexical', lexical), ('symbol', symbols), ('semantic', semantic)],
            weights=settings.fusion_weights, k=settings.fusion_rrf_k, limit=candidate_limit,
        )
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


def search(db, raw: str, mode='hybrid', limit=30, repository_id: str | None = None):
    return search_with_capability(db, raw, mode, limit, repository_id)[0]
