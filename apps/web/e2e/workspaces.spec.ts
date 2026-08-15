import { expect, test } from '@playwright/test';

type Workspace = { id: string; name: string; description: string | null };
type Repository = { id: string; name: string; clone_url: string; indexing_status: string };

test('a workspace can be created and a repository added to it', async ({ page }) => {
  const workspaces: Workspace[] = [];
  const membership: Record<string, string[]> = {};
  const repositories: Repository[] = [{ id: 'repo-1', name: 'demo-repo', clone_url: 'https://example.com/demo.git', indexing_status: 'ready' }];

  await page.route('**/api/repositories', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(repositories) }));

  await page.route('**/api/workspaces**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const segments = url.pathname.split('/').filter(Boolean); // ['api', 'workspaces', ...]
    const method = request.method();

    if (segments.length === 2) {
      if (method === 'GET') return route.fulfill({ contentType: 'application/json', body: JSON.stringify(workspaces) });
      if (method === 'POST') {
        const body = request.postDataJSON();
        const workspace: Workspace = { id: `ws-${workspaces.length + 1}`, name: body.name, description: body.description ?? null };
        workspaces.push(workspace); membership[workspace.id] = [];
        return route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(workspace) });
      }
    }
    if (segments.length === 4 && segments[3] === 'repositories') {
      const workspaceId = segments[2];
      if (method === 'GET') {
        const members = (membership[workspaceId] ?? []).map((id) => repositories.find((repo) => repo.id === id)!);
        return route.fulfill({ contentType: 'application/json', body: JSON.stringify(members) });
      }
    }
    if (segments.length === 5 && segments[3] === 'repositories') {
      const [, , workspaceId, , repoId] = segments;
      if (method === 'PUT') {
        membership[workspaceId] = [...new Set([...(membership[workspaceId] ?? []), repoId])];
        return route.fulfill({ contentType: 'application/json', body: JSON.stringify({ workspace_id: workspaceId, repository_id: repoId }) });
      }
      if (method === 'DELETE') {
        membership[workspaceId] = (membership[workspaceId] ?? []).filter((id) => id !== repoId);
        return route.fulfill({ status: 204, body: '' });
      }
    }
    return route.fulfill({ status: 404, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/workspaces');
  await expect(page.getByRole('heading', { name: 'Workspaces', level: 2 })).toBeVisible();

  await page.getByLabel('Name').fill('platform-team');
  await page.getByRole('button', { name: 'Create workspace' }).click();
  await expect(page.getByText('platform-team')).toBeVisible();

  await page.getByRole('button', { name: 'Manage repositories' }).click();
  await expect(page.getByText('No repositories in this workspace yet.')).toBeVisible();

  await page.getByRole('combobox', { name: 'Add repository' }).selectOption('repo-1');
  await page.getByRole('button', { name: 'Add' }).click();
  await expect(page.getByText('demo-repo')).toBeVisible();
  await expect(page.getByText('No repositories in this workspace yet.')).toHaveCount(0);

  await page.getByRole('button', { name: 'Set active' }).click();
  await expect(page.getByText('Active', { exact: true }).first()).toBeVisible();
});
