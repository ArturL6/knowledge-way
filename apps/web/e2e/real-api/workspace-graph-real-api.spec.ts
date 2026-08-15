import { APIRequestContext, expect, test } from '@playwright/test';

// Exercises the workspace/graph UX fixes from packet 1.9a against a REAL running keyless API
// (no page.route mocking) — packet 1.9's Playwright suite mocked every response and shipped bugs
// that only showed up against the real backend's one-workspace-per-repo constraint. Point
// REAL_API_URL at the API for whatever stack REAL_WEB_URL (playwright.real-api.config.ts) serves.
const API = process.env.REAL_API_URL || 'http://127.0.0.1:34747/api';

type ApiRepository = { id: string; name: string; indexing_status: string };
type ApiWorkspace = { id: string; name: string };

async function deleteWorkspace(request: APIRequestContext, id: string | null) {
  if (id) await request.delete(`${API}/workspaces/${id}`).catch(() => {});
}

test.describe('workspace + graph UX against a real keyless API', () => {
  test('creating a workspace and adding a free repository shows it as a member', async ({ page, request }) => {
    const repos: ApiRepository[] = await (await request.get(`${API}/repositories`)).json();
    const free = repos.find((repo) => repo.indexing_status === 'ready');
    test.skip(!free, 'no ready repository available on the shared stack');

    const name = `e2e-1.9a-free-${Date.now()}`;
    let workspaceId: string | null = null;
    try {
      await page.goto('/workspaces');
      await page.getByLabel('Name').fill(name);
      await page.getByRole('button', { name: 'Create workspace' }).click();
      await expect(page.getByText(name)).toBeVisible();

      const card = page.locator('.repository-card', { hasText: name });
      await card.getByRole('button', { name: 'Manage repositories' }).click();
      await expect(card.getByText('No repositories in this workspace yet.')).toBeVisible();

      await card.getByRole('combobox', { name: 'Add repository' }).selectOption(free!.id);
      await card.getByRole('button', { name: 'Add' }).click();
      await expect(card.getByText(free!.name)).toBeVisible();
      await expect(card.getByText('No repositories in this workspace yet.')).toHaveCount(0);

      const workspaces: ApiWorkspace[] = await (await request.get(`${API}/workspaces`)).json();
      workspaceId = workspaces.find((workspace) => workspace.name === name)?.id ?? null;
    } finally {
      await deleteWorkspace(request, workspaceId);
    }
  });

  test('a repository already in another workspace is not offered again, with a clear note', async ({ page, request }) => {
    const repos: ApiRepository[] = await (await request.get(`${API}/repositories`)).json();
    const target = repos.find((repo) => repo.indexing_status === 'ready');
    test.skip(!target, 'no ready repository available on the shared stack');

    const ownerName = `e2e-1.9a-owner-${Date.now()}`;
    const otherName = `e2e-1.9a-other-${Date.now()}`;
    let ownerId: string | null = null;
    let otherId: string | null = null;
    try {
      ownerId = (await (await request.post(`${API}/workspaces`, { data: { name: ownerName, description: null } })).json()).id;
      const claim = await request.put(`${API}/workspaces/${ownerId}/repositories/${target!.id}`);
      expect(claim.status()).toBe(200);
      otherId = (await (await request.post(`${API}/workspaces`, { data: { name: otherName, description: null } })).json()).id;

      // Confirms the backend invariant this whole fix is UX around: a second PUT for the same
      // repo against a different workspace is rejected, not silently accepted.
      const conflict = await request.put(`${API}/workspaces/${otherId}/repositories/${target!.id}`);
      expect(conflict.status()).toBe(409);

      await page.goto('/workspaces');
      const otherCard = page.locator('.repository-card', { hasText: otherName });
      await otherCard.getByRole('button', { name: 'Manage repositories' }).click();

      const select = otherCard.getByRole('combobox', { name: 'Add repository' });
      await expect(select.locator('option', { hasText: target!.name })).toHaveCount(0);
      await expect(otherCard.getByText(/already belong.*another workspace/)).toBeVisible();
    } finally {
      await deleteWorkspace(request, ownerId);
      await deleteWorkspace(request, otherId);
    }
  });

  test('selecting a ready repository renders its whole-repo graph', async ({ page, request }) => {
    const repos: ApiRepository[] = await (await request.get(`${API}/repositories`)).json();
    const ready = repos.find((repo) => repo.indexing_status === 'ready');
    test.skip(!ready, 'no ready repository available on the shared stack');

    await page.goto('/graph');
    await expect(page.getByRole('heading', { name: 'Code graph' })).toBeVisible();
    await page.getByLabel('Repository').selectOption(ready!.id);

    const nodeList = page.locator('.graph-node-list');
    await expect(nodeList.getByRole('button').first()).toBeVisible({ timeout: 15000 });
  });
});
