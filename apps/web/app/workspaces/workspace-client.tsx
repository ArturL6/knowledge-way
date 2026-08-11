'use client';

import { FormEvent, useEffect, useState } from 'react';
import Link from 'next/link';
import { api } from '../../lib/api';
import { apiErrorMessage, Repository } from '../../lib/repositories';

export type Workspace = { id: string; name: string; description?: string | null };

type Props = { initialWorkspaces: Workspace[]; initialRepositories: Repository[] };

export default function WorkspaceClient({ initialWorkspaces, initialRepositories }: Props) {
  const [workspaces, setWorkspaces] = useState(initialWorkspaces);
  const [repositories, setRepositories] = useState(initialRepositories);
  const [selectedId, setSelectedId] = useState(initialWorkspaces[0]?.id ?? '');
  const [members, setMembers] = useState<Repository[]>([]);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [repositoryId, setRepositoryId] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  const selected = workspaces.find((workspace) => workspace.id === selectedId);
  async function refresh() {
    const [nextWorkspaces, nextRepositories] = await Promise.all([api<Workspace[]>('/workspaces'), api<Repository[]>('/repositories')]);
    setWorkspaces(nextWorkspaces); setRepositories(nextRepositories);
    setSelectedId((current) => nextWorkspaces.some((workspace) => workspace.id === current) ? current : (nextWorkspaces[0]?.id ?? ''));
  }
  useEffect(() => {
    if (!selectedId) { setMembers([]); return; }
    let cancelled = false;
    api<Repository[]>(`/workspaces/${encodeURIComponent(selectedId)}/repositories`)
      .then((items) => { if (!cancelled) setMembers(items); })
      .catch((error) => { if (!cancelled) setMessage(apiErrorMessage(error)); });
    return () => { cancelled = true; };
  }, [selectedId]);

  async function createWorkspace(event: FormEvent) {
    event.preventDefault(); if (!name.trim()) return;
    setBusy(true); setMessage('');
    try {
      const workspace = await api<Workspace>('/workspaces', { method: 'POST', body: JSON.stringify({ name: name.trim(), description: description.trim() || null }) });
      setName(''); setDescription(''); await refresh(); setSelectedId(workspace.id); setMessage(`Workspace “${workspace.name}” created.`);
    } catch (error) { setMessage(apiErrorMessage(error)); } finally { setBusy(false); }
  }
  async function addMember(event: FormEvent) {
    event.preventDefault(); if (!selectedId || !repositoryId) return;
    setBusy(true); setMessage('');
    try {
      await api(`/workspaces/${encodeURIComponent(selectedId)}/repositories/${encodeURIComponent(repositoryId)}`, { method: 'PUT' });
      setRepositoryId(''); const items = await api<Repository[]>(`/workspaces/${encodeURIComponent(selectedId)}/repositories`); setMembers(items);
      setMessage('Repository added to this workspace.');
    } catch (error) { setMessage(apiErrorMessage(error)); } finally { setBusy(false); }
  }
  async function removeMember(id: string) {
    setBusy(true); setMessage('');
    try {
      await api<void>(`/workspaces/${encodeURIComponent(selectedId)}/repositories/${encodeURIComponent(id)}`, { method: 'DELETE' });
      setMembers((current) => current.filter((repository) => repository.id !== id)); setMessage('Repository removed; its indexed data was retained.');
    } catch (error) { setMessage(apiErrorMessage(error)); } finally { setBusy(false); }
  }
  const available = repositories.filter((repository) => !members.some((member) => member.id === repository.id));

  return <>
    <h2>Workspaces</h2>
    <p className="muted">A workspace groups indexed repositories. Membership is not dependency evidence; declared dependencies remain explicit.</p>
    <section className="card repository-form-card" aria-labelledby="create-workspace-heading">
      <h3 id="create-workspace-heading">Create workspace</h3>
      <form className="repository-form" onSubmit={createWorkspace}>
        <label>Name<input value={name} onChange={(event) => setName(event.target.value)} required maxLength={255} placeholder="platform-services" /></label>
        <label>Description<input value={description} onChange={(event) => setDescription(event.target.value)} maxLength={10000} placeholder="Optional scope note" /></label>
        <button disabled={busy} type="submit">Create workspace</button>
      </form>
    </section>
    {workspaces.length > 0 && <section className="card" aria-labelledby="workspace-selection-heading">
      <h3 id="workspace-selection-heading">Active workspace</h3>
      <label>Workspace<select value={selectedId} onChange={(event) => setSelectedId(event.target.value)}>{workspaces.map((workspace) => <option key={workspace.id} value={workspace.id}>{workspace.name}</option>)}</select></label>
      {selected?.description && <p className="muted">{selected.description}</p>}
      <p><Link href={`/search?workspace=${encodeURIComponent(selectedId)}`}>Search this workspace →</Link></p>
    </section>}
    {selected && <section className="card" aria-labelledby="workspace-members-heading">
      <h3 id="workspace-members-heading">Members ({members.length})</h3>
      <form className="row" onSubmit={addMember}>
        <label className="visually-hidden" htmlFor="workspace-repository">Repository</label>
        <select id="workspace-repository" value={repositoryId} onChange={(event) => setRepositoryId(event.target.value)}><option value="">Select an indexed repository…</option>{available.map((repository) => <option key={repository.id} value={repository.id}>{repository.name}</option>)}</select>
        <button disabled={busy || !repositoryId} type="submit">Add repository</button>
      </form>
      <ul>{members.map((repository) => <li key={repository.id}><b>{repository.name}</b> <span className="muted">{repository.indexing_status}</span> <button className="secondary-button" disabled={busy} onClick={() => removeMember(repository.id)}>Remove</button></li>)}</ul>
      {!members.length && <p className="muted">No members yet. Adding a repository retains its existing index and makes it eligible for workspace-scoped search.</p>}
    </section>}
    {message && <p className="form-message" role="status">{message}</p>}
  </>;
}
