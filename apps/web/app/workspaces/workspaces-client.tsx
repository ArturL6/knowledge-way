'use client';

import {FormEvent, useEffect, useState} from 'react';
import {api} from '../../lib/api';
import {apiErrorMessage} from '../../lib/repositories';
import type {Repository} from '../../lib/repositories';
import {setActiveWorkspaceId, useActiveWorkspaceId} from '../../lib/workspace';
import type {Workspace} from '../../lib/workspace';

type Props = {initialWorkspaces: Workspace[]};

export default function WorkspacesClient({initialWorkspaces}: Props) {
  const activeId = useActiveWorkspaceId();
  const [workspaces, setWorkspaces] = useState(initialWorkspaces);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [members, setMembers] = useState<Repository[] | null>(null);
  const [membersError, setMembersError] = useState<string | null>(null);
  const [allRepos, setAllRepos] = useState<Repository[]>([]);
  const [addRepoId, setAddRepoId] = useState('');
  const [ownedByOther, setOwnedByOther] = useState<Map<string, string>>(new Map());

  useEffect(() => { api<Repository[]>('/repositories').then(setAllRepos).catch(() => {}); }, []);

  /** The backend enforces one workspace per repo (409 on PUT), so a repo already claimed by another
   *  workspace is not worth offering here; this maps repo id -> owning workspace name for every
   *  workspace but the one currently expanded. */
  async function loadOwnership(currentWorkspaceId: string) {
    const others = workspaces.filter((workspace) => workspace.id !== currentWorkspaceId);
    const entries = await Promise.all(others.map((workspace) =>
      api<Repository[]>(`/workspaces/${encodeURIComponent(workspace.id)}/repositories`)
        .then((repos) => repos.map((repo): [string, string] => [repo.id, workspace.name]))
        .catch(() => [] as [string, string][])
    ));
    setOwnedByOther(new Map(entries.flat()));
  }

  async function refreshWorkspaces() { setWorkspaces(await api<Workspace[]>('/workspaces')); }

  async function createWorkspace(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) { setFormError('Enter a workspace name.'); return; }
    setBusy('create'); setFormError(null); setNotice(null);
    try {
      await api('/workspaces', {method: 'POST', body: JSON.stringify({name: name.trim(), description: description.trim() || null})});
      setName(''); setDescription(''); setNotice('Workspace created.');
      await refreshWorkspaces();
    } catch (error) { setFormError(apiErrorMessage(error)); }
    finally { setBusy(null); }
  }

  async function deleteWorkspace(workspace: Workspace) {
    setBusy(`delete:${workspace.id}`); setNotice(null);
    try {
      await api<void>(`/workspaces/${encodeURIComponent(workspace.id)}`, {method: 'DELETE'});
      setWorkspaces((current) => current.filter((item) => item.id !== workspace.id));
      if (activeId === workspace.id) setActiveWorkspaceId('');
      if (expandedId === workspace.id) { setExpandedId(null); setMembers(null); }
      setDeletingId(null);
      setNotice(`${workspace.name} was deleted.`);
    } catch (error) { setNotice(apiErrorMessage(error)); }
    finally { setBusy(null); }
  }

  async function loadMembers(workspaceId: string) {
    setMembers(null); setMembersError(null); setAddRepoId('');
    try { setMembers(await api<Repository[]>(`/workspaces/${encodeURIComponent(workspaceId)}/repositories`)); }
    catch (error) { setMembersError(apiErrorMessage(error)); }
  }

  function toggleExpand(workspace: Workspace) {
    if (expandedId === workspace.id) { setExpandedId(null); setMembers(null); return; }
    setExpandedId(workspace.id);
    void loadMembers(workspace.id);
    void loadOwnership(workspace.id);
  }

  async function addMember(workspaceId: string, repoId: string) {
    if (!repoId) return;
    setBusy(`add:${repoId}`); setMembersError(null);
    try {
      await api(`/workspaces/${encodeURIComponent(workspaceId)}/repositories/${encodeURIComponent(repoId)}`, {method: 'PUT'});
      setAddRepoId('');
      await loadMembers(workspaceId);
    } catch (error) { setMembersError(apiErrorMessage(error)); }
    finally { setBusy(null); }
  }

  async function removeMember(workspaceId: string, repoId: string) {
    setBusy(`remove:${repoId}`); setMembersError(null);
    try {
      await api<void>(`/workspaces/${encodeURIComponent(workspaceId)}/repositories/${encodeURIComponent(repoId)}`, {method: 'DELETE'});
      await loadMembers(workspaceId);
    } catch (error) { setMembersError(apiErrorMessage(error)); }
    finally { setBusy(null); }
  }

  const memberIds = new Set((members ?? []).map((repo) => repo.id));
  const unassigned = allRepos.filter((repo) => !memberIds.has(repo.id));
  const candidates = unassigned.filter((repo) => !ownedByOther.has(repo.id));
  const takenCount = unassigned.length - candidates.length;

  return <>
    <section className="card repository-form-card" aria-labelledby="create-workspace-heading">
      <h3 id="create-workspace-heading">Create a workspace</h3>
      <form className="repository-form" onSubmit={createWorkspace} noValidate>
        <label>Name<input value={name} onChange={(event) => setName(event.target.value)} maxLength={255} required placeholder="platform-team" /></label>
        <label>Description<input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Optional" /></label>
        <button type="submit" disabled={busy === 'create'}>{busy === 'create' ? 'Creating…' : 'Create workspace'}</button>
      </form>
      {formError && <p className="form-message form-error" role="alert">{formError}</p>}
    </section>

    <div className="repository-heading"><h3>Workspaces</h3>{notice && <p className="form-message" role="status">{notice}</p>}</div>
    <section className="grid">
      {workspaces.map((workspace) => {
        const isActive = activeId === workspace.id;
        const isExpanded = expandedId === workspace.id;
        return <article className="card repository-card" key={workspace.id}>
          <div className="repository-title">
            <div><b>{workspace.name}</b>{workspace.description && <p className="muted clone-url">{workspace.description}</p>}</div>
            {isActive && <span className="status status-ready">Active</span>}
          </div>
          <div className="repository-actions">
            <button type="button" className="secondary-button" disabled={isActive} onClick={() => setActiveWorkspaceId(workspace.id)}>{isActive ? 'Active' : 'Set active'}</button>
            {isActive && <button type="button" className="secondary-button" onClick={() => setActiveWorkspaceId('')}>Clear active</button>}
            <button type="button" className="secondary-button" onClick={() => toggleExpand(workspace)} aria-expanded={isExpanded}>{isExpanded ? 'Hide repositories' : 'Manage repositories'}</button>
            <button type="button" className="danger-button" disabled={busy !== null} onClick={() => setDeletingId(workspace.id)}>Delete</button>
          </div>
          {deletingId === workspace.id && <p className="form-message form-error" role="alert">Delete this workspace? Membership is removed; repositories and their indexed data are not.
            <span className="repository-actions"><button type="button" className="secondary-button" disabled={busy !== null} onClick={() => setDeletingId(null)}>Cancel</button><button type="button" className="danger-button" disabled={busy !== null} onClick={() => deleteWorkspace(workspace)}>{busy === `delete:${workspace.id}` ? 'Deleting…' : 'Confirm delete'}</button></span>
          </p>}
          {isExpanded && <div className="symbol-section">
            {membersError && <p className="form-message form-error" role="alert">{membersError}</p>}
            {members === null ? <p className="muted">Loading repositories…</p> : <>
              <ul>{members.map((repo) => <li key={repo.id} className="repository-actions" style={{justifyContent: 'space-between', alignItems: 'center'}}><span>{repo.name} <span className={`status status-${repo.indexing_status}`}>{repo.indexing_status}</span></span><button type="button" className="danger-button" disabled={busy !== null} onClick={() => removeMember(workspace.id, repo.id)}>{busy === `remove:${repo.id}` ? 'Removing…' : 'Remove'}</button></li>)}
              {!members.length && <li className="muted">No repositories in this workspace yet.</li>}</ul>
              <div className="repository-actions">
                <label className="visually-hidden" htmlFor={`add-repo-${workspace.id}`}>Add repository</label>
                <select id={`add-repo-${workspace.id}`} value={addRepoId} onChange={(event) => setAddRepoId(event.target.value)}>
                  <option value="">Add a repository…</option>
                  {candidates.map((repo) => <option key={repo.id} value={repo.id}>{repo.name}</option>)}
                </select>
                <button type="button" className="secondary-button" disabled={!addRepoId || busy !== null} onClick={() => addMember(workspace.id, addRepoId)}>{busy === `add:${addRepoId}` ? 'Adding…' : 'Add'}</button>
              </div>
              {takenCount > 0 && <p className="muted">{takenCount} repositor{takenCount === 1 ? 'y' : 'ies'} already belong{takenCount === 1 ? 's' : ''} to another workspace and {takenCount === 1 ? 'is' : 'are'} not offered here.</p>}
            </>}
          </div>}
        </article>;
      })}
      {!workspaces.length && <div className="card">No workspaces yet. Create one above to group repositories.</div>}
    </section>
  </>;
}
