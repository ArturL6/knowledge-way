'use client';

import { FormEvent, useEffect, useState } from 'react';
import { api } from '../../lib/api';

type Repository = { id: string; name: string; indexed_commit_sha?: string | null; indexing_status: string };
type Citation = { repository: string; file_id: string; path: string; start_line: number; end_line: number; indexed_commit_sha?: string | null };
type Answer = { answer: string; citations: Citation[]; grounded: boolean; answer_mode: string; scope: { repository_id: string; indexed_commit_sha?: string | null } };

export default function ChatClient() {
  const [repositories, setRepositories] = useState<Repository[]>([]); const [repositoryId, setRepositoryId] = useState('');
  const [q, setQ] = useState(''); const [items, setItems] = useState<Answer[]>([]); const [loading, setLoading] = useState(false); const [error, setError] = useState('');
  useEffect(() => { api<Repository[]>('/repositories').then((items) => { const ready = items.filter((item) => item.indexing_status === 'ready'); setRepositories(ready); if (ready[0]) setRepositoryId(ready[0].id); }).catch((cause) => setError(cause instanceof Error ? cause.message : 'Unable to load repositories.')); }, []);
  async function ask(event: FormEvent) {
    event.preventDefault(); if (!q.trim() || !repositoryId) return;
    setLoading(true); setError('');
    try { const result = await api<Answer>('/explanations', { method: 'POST', body: JSON.stringify({ question: q, repository_id: repositoryId }) }); setItems((current) => [...current, result]); setQ(''); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Unable to retrieve grounded evidence.'); }
    finally { setLoading(false); }
  }
  return <section className="chat"><h2>Grounded code questions</h2><p className="muted">Retrieval is repository- and commit-scoped. Answers are evidence summaries, not unverified model claims.</p>
    <form onSubmit={ask}><label>Repository<select value={repositoryId} onChange={(event) => setRepositoryId(event.target.value)} required><option value="">Choose an indexed repository</option>{repositories.map((repository) => <option key={repository.id} value={repository.id}>{repository.name}{repository.indexed_commit_sha ? ` · ${repository.indexed_commit_sha.slice(0, 12)}` : ''}</option>)}</select></label><textarea rows={4} value={q} onChange={(event) => setQ(event.target.value)} placeholder="Where is authentication implemented?"/><p><button disabled={loading || !repositoryId}>{loading ? 'Retrieving…' : 'Ask codebase'}</button></p></form>
    {error && <div className="graph-message graph-error" role="alert">{error}</div>}
    {items.map((item, index) => <div className="message assistant" key={index}><p>{item.answer}</p><p className="muted">{item.grounded ? `Grounded retrieval · commit ${item.scope.indexed_commit_sha?.slice(0, 12) ?? 'unknown'}` : 'Not sufficiently evidenced by the indexed repository.'}</p>{item.citations.map((citation, citationIndex) => <a className="citation" key={citationIndex} href={`/files/${citation.file_id}#L${citation.start_line}`}>{citation.repository}/{citation.path}:{citation.start_line}-{citation.end_line}{citation.indexed_commit_sha ? ` · ${citation.indexed_commit_sha.slice(0, 12)}` : ''}</a>)}</div>)}
  </section>;
}
