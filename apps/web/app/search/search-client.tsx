'use client';

import { FormEvent, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { api } from '../../lib/api';

type Result = {
  repository: string;
  repository_id?: string;
  path: string;
  file_id: string;
  symbol_id?: string | null;
  indexed_commit_sha?: string | null;
  start_line: number;
  end_line: number;
  snippet: string;
  symbol?: string;
  language?: string;
  type: string;
};

const DEFAULT_MODE = 'hybrid';

/** Serializes the searched query/mode/rerank into the URL; defaults are omitted to keep an untouched search at `/search`. */
export function buildSearchUrl(q: string, mode: string, rerank: boolean): string {
  const params = new URLSearchParams();
  if (q) params.set('q', q);
  if (mode && mode !== DEFAULT_MODE) params.set('mode', mode);
  if (rerank) params.set('rerank', 'true');
  const query = params.toString();
  return query ? `/search?${query}` : '/search';
}

/** Reads the q/mode/rerank triple back out of a URLSearchParams-like object (accepts Next's ReadonlyURLSearchParams too). */
export function parseSearchState(params: { get(key: string): string | null }): { q: string; mode: string; rerank: boolean } {
  return {
    q: params.get('q') ?? '',
    mode: params.get('mode') ?? DEFAULT_MODE,
    rerank: params.get('rerank') === 'true',
  };
}

export type SearchView = 'idle' | 'results' | 'empty' | 'error';

/** Distinguishes "nothing searched yet" from "searched but got zero results" — the two were byte-identical before. */
export function searchView(searched: boolean, resultCount: number, hasError: boolean): SearchView {
  if (hasError) return 'error';
  if (!searched) return 'idle';
  return resultCount > 0 ? 'results' : 'empty';
}

export default function SearchClient() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [q, setQ] = useState('');
  const [mode, setMode] = useState(DEFAULT_MODE);
  const [rerank, setRerank] = useState(false);
  const [results, setResults] = useState<Result[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [searched, setSearched] = useState(false);
  const searchRequestVersion = useRef(0);

  async function runSearch(query: string, searchMode: string, useRerank: boolean) {
    const version = ++searchRequestVersion.current;
    setLoading(true); setError(''); setResults([]); setSearched(false);
    try {
      const response = await api<{ results: Result[] }>(`/search?q=${encodeURIComponent(query)}&mode=${encodeURIComponent(searchMode)}&rerank=${useRerank}`);
      if (version !== searchRequestVersion.current) return;
      setResults(response.results ?? []);
    } catch (cause) {
      if (version !== searchRequestVersion.current) return;
      setResults([]);
      setError(cause instanceof Error ? cause.message : 'Unable to search code.');
    } finally {
      if (version === searchRequestVersion.current) { setLoading(false); setSearched(true); }
    }
  }

  // The URL is the source of truth for the executed search: this covers first load (shared/bookmarked link),
  // Back/Forward, and our own router.push on submit, all through the same path.
  useEffect(() => {
    const state = parseSearchState(searchParams);
    setQ(state.q);
    setMode(state.mode);
    setRerank(state.rerank);
    if (state.q.trim()) {
      void runSearch(state.q, state.mode, state.rerank);
    } else {
      setResults([]);
      setSearched(false);
      setError('');
    }
  }, [searchParams]);

  function go(event: FormEvent) {
    event.preventDefault();
    if (!q.trim()) return;
    router.push(buildSearchUrl(q, mode, rerank));
  }

  const view = searchView(searched, results.length, Boolean(error));

  return <>
    <h2>Global code search</h2>
    <form className="row" onSubmit={go}>
      <label className="visually-hidden" htmlFor="search-query">Search query</label><input id="search-query" value={q} onChange={(event) => setQ(event.target.value)} placeholder="auth repo:backend lang:python" />
      <label className="visually-hidden" htmlFor="search-mode">Search mode</label><select id="search-mode" value={mode} onChange={(event) => setMode(event.target.value)}><option>hybrid</option><option>text</option><option>symbols</option><option>semantic</option></select>
      <label className="muted"><input type="checkbox" checked={rerank} disabled={mode !== 'hybrid'} onChange={(event) => setRerank(event.target.checked)} /> Reranker verwenden</label>
      <button disabled={loading}>{loading ? 'Searching…' : 'Search'}</button>
    </form>
    <p className="muted">Filters: <code>repo:</code> <code>lang:</code> <code>path:</code></p>
    {view === 'error' && <div className="graph-message graph-error" role="alert">{error}</div>}
    {view === 'empty' && <div className="graph-message" role="status">No results for “{q}”.</div>}
    {view === 'results' && results.map((result, index) => {
      const hasSymbol = Boolean(result.symbol_id && result.repository_id);
      const symbolUrl = hasSymbol ? `/repositories/${encodeURIComponent(result.repository_id!)}/symbols/${encodeURIComponent(result.symbol_id!)}` : '';
      const graphUrl = hasSymbol ? `/graph?repository=${encodeURIComponent(result.repository_id!)}&symbol=${encodeURIComponent(result.symbol_id!)}` : '';
      return <article className="card result" key={`${result.file_id}-${result.start_line}-${index}`}>
        <b>{result.repository}</b> <span className="muted">{result.path}:{result.start_line}-{result.end_line} · {result.language} · {result.type}{result.indexed_commit_sha ? ` · ${result.indexed_commit_sha.slice(0, 12)}` : ''}</span>
        {result.symbol && <p>{result.symbol}</p>}
        <pre>{result.snippet}</pre>
        <div className="repository-actions"><Link href={`/files/${encodeURIComponent(result.file_id)}#L${result.start_line}`}>Open source →</Link>{hasSymbol && <><Link href={symbolUrl}>View symbol →</Link><Link href={graphUrl}>Open graph →</Link></>}</div>
      </article>;
    })}
  </>;
}
