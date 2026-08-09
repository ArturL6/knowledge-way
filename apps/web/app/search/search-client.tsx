'use client';

import { useState } from 'react';
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

export default function SearchClient() {
  const [q, setQ] = useState('');
  const [mode, setMode] = useState('hybrid');
  const [rerank, setRerank] = useState(false);
  const [results, setResults] = useState<Result[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function go(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError('');
    try {
      const response = await api<{ results: Result[] }>(`/search?q=${encodeURIComponent(q)}&mode=${encodeURIComponent(mode)}&rerank=${rerank}`);
      setResults(response.results ?? []);
    } catch (cause) {
      setResults([]);
      setError(cause instanceof Error ? cause.message : 'Unable to search code.');
    } finally {
      setLoading(false);
    }
  }

  return <>
    <h2>Global code search</h2>
    <form className="row" onSubmit={go}>
      <input value={q} onChange={(event) => setQ(event.target.value)} placeholder="auth repo:backend lang:python" />
      <select value={mode} onChange={(event) => setMode(event.target.value)}><option>hybrid</option><option>text</option><option>symbols</option><option>semantic</option></select>
      <label className="muted"><input type="checkbox" checked={rerank} disabled={mode !== 'hybrid'} onChange={(event) => setRerank(event.target.checked)} /> Reranker verwenden</label>
      <button disabled={loading}>{loading ? 'Searching…' : 'Search'}</button>
    </form>
    <p className="muted">Filters: <code>repo:</code> <code>lang:</code> <code>path:</code></p>
    {error && <div className="graph-message graph-error" role="alert">{error}</div>}
    {results.map((result, index) => {
      const hasSymbol = Boolean(result.symbol_id && result.repository_id);
      const symbolUrl = hasSymbol ? `/repositories/${encodeURIComponent(result.repository_id!)}/symbols/${encodeURIComponent(result.symbol_id!)}` : '';
      const graphUrl = hasSymbol ? `/graph?repository=${encodeURIComponent(result.repository_id!)}&symbol=${encodeURIComponent(result.symbol_id!)}` : '';
      return <article className="card result" key={`${result.file_id}-${result.start_line}-${index}`}>
        <b>{result.repository}</b> <span className="muted">{result.path}:{result.start_line}-{result.end_line} · {result.language} · {result.type}{result.indexed_commit_sha ? ` · ${result.indexed_commit_sha.slice(0, 12)}` : ''}</span>
        {result.symbol && <p>{result.symbol}</p>}
        <pre>{result.snippet}</pre>
        <div className="repository-actions"><a href={`/files/${encodeURIComponent(result.file_id)}#L${result.start_line}`}>Open source →</a>{hasSymbol && <><a href={symbolUrl}>View symbol →</a><a href={graphUrl}>Open graph →</a></>}</div>
      </article>;
    })}
  </>;
}
