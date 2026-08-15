import {api} from '../../lib/api';
import type {Workspace} from '../../lib/workspace';
import WorkspacesClient from './workspaces-client';

export default async function WorkspacesPage() {
  let workspaces: Workspace[] = [];
  try { workspaces = await api<Workspace[]>('/workspaces'); } catch { /* The client can still connect once the API is available. */ }
  return <>
    <div className="page-heading"><div><h2>Workspaces</h2><p className="muted">Group repositories together, then pick an active workspace to scope search and the code graph to just its repositories.</p></div></div>
    <WorkspacesClient initialWorkspaces={workspaces} />
  </>;
}
