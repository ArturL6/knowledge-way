import { api } from '../../lib/api';
import { Repository } from '../../lib/repositories';
import WorkspaceClient, { Workspace } from './workspace-client';

export default async function WorkspacesPage() {
  let workspaces: Workspace[] = [];
  let repositories: Repository[] = [];
  try { [workspaces, repositories] = await Promise.all([api<Workspace[]>('/workspaces'), api<Repository[]>('/repositories')]); } catch { /* client offers retryable actions once API is ready */ }
  return <WorkspaceClient initialWorkspaces={workspaces} initialRepositories={repositories} />;
}
