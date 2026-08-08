'use client';

import {FormEvent, useState} from 'react';
import {api} from '../lib/api';
import {apiErrorMessage, cloneUrlError, progressLabel, Repository} from '../lib/repositories';

type Props = {initialRepos: Repository[]};
type Status = Pick<Repository, 'indexing_status' | 'indexing_progress' | 'indexed_commit_sha' | 'error_message'>;

export default function DashboardClient({initialRepos}: Props) {
  const [repos, setRepos] = useState(initialRepos);
  const [name, setName] = useState('');
  const [cloneUrl, setCloneUrl] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<Repository | null>(null);

  async function refresh() {
    setRepos(await api<Repository[]>('/repositories'));
  }

  async function addRepository(event: FormEvent) {
    event.preventDefault();
    const urlError = cloneUrlError(cloneUrl);
    if (urlError) { setFormError(urlError); return; }
    if (!name.trim()) { setFormError('Enter a repository name.'); return; }
    setBusy('add'); setFormError(null); setNotice(null);
    try {
      await api('/repositories', {method: 'POST', body: JSON.stringify({name: name.trim(), clone_url: cloneUrl.trim()})});
      setName(''); setCloneUrl(''); setNotice('Repository added. Its first index has been queued.');
      await refresh();
    } catch (error) { setFormError(apiErrorMessage(error)); }
    finally { setBusy(null); }
  }

  async function runAction(repo: Repository, action: 'sync' | 'reindex') {
    setBusy(`${action}:${repo.id}`); setNotice(null);
    try {
      await api(`/repositories/${encodeURIComponent(repo.id)}/${action}`, {method: 'POST'});
      setNotice(`${action === 'sync' ? 'Sync' : 'Reindex'} queued for ${repo.name}.`);
      await refresh();
    } catch (error) { setNotice(apiErrorMessage(error)); }
    finally { setBusy(null); }
  }

  async function confirmDelete() {
    if (!deleting) return;
    setBusy(`delete:${deleting.id}`); setNotice(null);
    try {
      await api<void>(`/repositories/${encodeURIComponent(deleting.id)}`, {method: 'DELETE'});
      setRepos((current) => current.filter((repo) => repo.id !== deleting.id));
      setNotice(`${deleting.name} and its indexed data were removed.`);
      setDeleting(null);
    } catch (error) { setNotice(apiErrorMessage(error)); }
    finally { setBusy(null); }
  }

  return <>
    <section className="grid dashboard-metrics" aria-label="Repository summary">
      <div className="card"><div className="metric">{repos.length}</div>Repositories</div>
      <div className="card"><div className="metric">{repos.filter((repo) => repo.indexing_status === 'ready').length}</div>Ready</div>
      <div className="card"><div className="metric">{repos.filter((repo) => repo.indexing_status === 'indexing').length}</div>Indexing</div>
    </section>

    <section className="card repository-form-card" aria-labelledby="add-repository-heading">
      <h3 id="add-repository-heading">Connect a repository</h3>
      <p className="muted">Use a Git HTTPS or SSH clone URL. Private repositories must be reachable by the indexer.</p>
      <form className="repository-form" onSubmit={addRepository} noValidate>
        <label>Repository name<input value={name} onChange={(event) => setName(event.target.value)} maxLength={255} required placeholder="my-service" /></label>
        <label>Clone URL<input value={cloneUrl} onChange={(event) => { setCloneUrl(event.target.value); setFormError(null); }} required placeholder="https://github.com/org/repo.git" inputMode="url" autoComplete="off" /></label>
        <button type="submit" disabled={busy === 'add'}>{busy === 'add' ? 'Adding…' : 'Add repository'}</button>
      </form>
      {formError && <p className="form-message form-error" role="alert">{formError}</p>}
    </section>

    <div className="repository-heading"><h3>Connected repositories</h3>{notice && <p className="form-message" role="status">{notice}</p>}</div>
    <section className="grid">
      {repos.map((repo) => <article className="card repository-card" key={repo.id}>
        <div className="repository-title"><div><b>{repo.name}</b><p className="muted clone-url">{repo.clone_url}</p></div><span className={`status status-${repo.indexing_status}`}>{repo.indexing_status}</span></div>
        <dl className="repository-details"><div><dt>Progress</dt><dd>{progressLabel(repo.indexing_progress)}</dd></div><div><dt>Current commit</dt><dd><code>{repo.indexed_commit_sha?.slice(0, 12) || 'Not indexed'}</code></dd></div></dl>
        {repo.error_message && <p className="form-message form-error">{repo.error_message}</p>}
        <div className="repository-actions">
          <button type="button" className="secondary-button" disabled={busy !== null} onClick={() => runAction(repo, 'sync')}>Sync</button>
          <button type="button" className="secondary-button" disabled={busy !== null} onClick={() => runAction(repo, 'reindex')}>Reindex</button>
          <button type="button" className="danger-button" disabled={busy !== null} onClick={() => setDeleting(repo)}>Delete</button>
        </div>
      </article>)}
      {!repos.length && <div className="card">No repositories yet. Connect one above to begin indexing.</div>}
    </section>

    {deleting && <div className="dialog-backdrop" role="presentation"><section className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="delete-title">
      <h3 id="delete-title">Delete {deleting.name}?</h3>
      <p>This removes the repository and all of its indexed files, chunks, and graph data. The remote Git repository will not be changed.</p>
      <div className="repository-actions"><button type="button" className="secondary-button" disabled={busy !== null} onClick={() => setDeleting(null)}>Cancel</button><button type="button" className="danger-button" disabled={busy !== null} onClick={confirmDelete}>{busy?.startsWith('delete:') ? 'Deleting…' : 'Delete repository'}</button></div>
    </section></div>}
  </>;
}
