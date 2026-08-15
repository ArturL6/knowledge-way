'use client';

import {FormEvent, KeyboardEvent, useEffect, useRef, useState} from 'react';
import {api} from '../lib/api';
import {apiErrorMessage, cloneUrlError, progressLabel, Repository} from '../lib/repositories';

type Props = {initialRepos: Repository[]};
type Capability = {semantic?: {state?: string; provider?: string; model?: string | null; reranking?: {state?: string; applied?: boolean}}};

export default function DashboardClient({initialRepos}: Props) {
  const [repos, setRepos] = useState(initialRepos);
  const [name, setName] = useState('');
  const [cloneUrl, setCloneUrl] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<Repository | null>(null);
  const [capability, setCapability] = useState<Capability | null>(null);
  const deleteButtonRef = useRef<HTMLButtonElement | null>(null);
  const cancelButtonRef = useRef<HTMLButtonElement | null>(null);
  const repositoriesHeadingRef = useRef<HTMLHeadingElement | null>(null);

  function closeDeleteDialog() { setDeleting(null); }

  useEffect(() => {
    if (!deleting) return;
    const navigation = document.querySelector('aside');
    navigation?.setAttribute('inert', '');
    navigation?.setAttribute('aria-hidden', 'true');
    cancelButtonRef.current?.focus();
    const trigger = deleteButtonRef.current;
    return () => {
      navigation?.removeAttribute('inert');
      navigation?.removeAttribute('aria-hidden');
      if (trigger?.isConnected) trigger.focus();
      else repositoriesHeadingRef.current?.focus();
    };
  }, [deleting]);

  function trapDialogFocus(event: KeyboardEvent<HTMLElement>) {
    if (event.key === 'Escape') { event.preventDefault(); closeDeleteDialog(); return; }
    if (event.key !== 'Tab') return;
    const focusable = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'));
    if (!focusable.length) return;
    const first = focusable[0]; const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }

  async function refresh() {
    setRepos(await api<Repository[]>('/repositories'));
  }

  useEffect(() => {
    let cancelled = false;
    api<Capability>('/capabilities').then((value) => { if (!cancelled) setCapability(value); }).catch(() => {});
    return () => { cancelled = true; };
  }, []);

  const hasActiveIndexing = repos.some((repo) => ['pending', 'indexing'].includes(repo.indexing_status));
  useEffect(() => {
    if (!hasActiveIndexing) return;
    let cancelled = false;
    const poll = () => api<Repository[]>('/repositories').then((items) => { if (!cancelled) setRepos(items); }).catch(() => {});
    const interval = window.setInterval(() => { void poll(); }, 3000);
    void poll();
    return () => { cancelled = true; window.clearInterval(interval); };
  }, [hasActiveIndexing]);

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
    <div aria-hidden={deleting ? true : undefined} inert={Boolean(deleting) || undefined}>
    <section className="grid dashboard-metrics" aria-label="Repository summary">
      <div className="card"><div className="metric">{repos.length}</div>Repositories</div>
      <div className="card"><div className="metric">{repos.filter((repo) => repo.indexing_status === 'ready').length}</div>Ready</div>
      <div className="card"><div className="metric">{repos.filter((repo) => repo.indexing_status === 'indexing').length}</div>Indexing</div>
    </section>
    {capability?.semantic && <p className="muted" role="status">Semantic search: {capability.semantic.state}{capability.semantic.provider ? ` · ${capability.semantic.provider}` : ''}{capability.semantic.model ? ` / ${capability.semantic.model}` : ''} · Reranking: {capability.semantic.reranking?.state ?? 'unknown'}</p>}

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

    <div className="repository-heading"><h3 ref={repositoriesHeadingRef} tabIndex={-1}>Connected repositories</h3>{notice && <p className="form-message" role="status">{notice}</p>}</div>
    <section className="grid">
      {repos.map((repo) => <article className="card repository-card" key={repo.id}>
        <div className="repository-title"><div><b>{repo.name}</b><p className="muted clone-url">{repo.clone_url}</p></div><span className={`status status-${repo.indexing_status}`}>{repo.indexing_status}</span></div>
        <dl className="repository-details"><div><dt>Progress</dt><dd>{progressLabel(repo.indexing_progress)}</dd></div><div><dt>Indexed branch</dt><dd>{repo.indexed_branch || 'Not indexed'}</dd></div><div><dt>Current commit</dt><dd><code>{repo.indexed_commit_sha?.slice(0, 12) || 'Not indexed'}</code></dd></div><div><dt>Latest detected</dt><dd>{repo.latest_detected_commit_sha ? <code>{repo.latest_detected_commit_sha.slice(0, 12)}{repo.indexed_commit_sha && repo.latest_detected_commit_sha !== repo.indexed_commit_sha ? ' · Stale' : ''}</code> : 'Unknown'}</dd></div></dl>
        {repo.error_message && <p className="form-message form-error">{repo.error_message}</p>}
        <div className="repository-actions">
          <button type="button" className="secondary-button" disabled={busy !== null} onClick={() => runAction(repo, 'sync')}>Sync</button>
          <button type="button" className="secondary-button" disabled={busy !== null} onClick={() => runAction(repo, 'reindex')}>Reindex</button>
          <button type="button" className="danger-button" disabled={busy !== null} onClick={(event) => { deleteButtonRef.current = event.currentTarget; setDeleting(repo); }}>Delete</button>
        </div>
      </article>)}
      {!repos.length && <div className="card">No repositories yet. Connect one above to begin indexing.</div>}
    </section>
    </div>

    {deleting && <div className="dialog-backdrop" role="presentation"><section className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="delete-title" aria-describedby="delete-description" tabIndex={-1} onKeyDown={trapDialogFocus}>
      <h3 id="delete-title">Delete {deleting.name}?</h3>
      <p id="delete-description">This removes the repository and all of its indexed files, chunks, and graph data. The remote Git repository will not be changed.</p>
      <div className="repository-actions"><button ref={cancelButtonRef} type="button" className="secondary-button" disabled={busy !== null} onClick={closeDeleteDialog}>Cancel</button><button type="button" className="danger-button" disabled={busy !== null} onClick={confirmDelete}>{busy?.startsWith('delete:') ? 'Deleting…' : 'Delete repository'}</button></div>
    </section></div>}
  </>;
}
