import { expect, test } from '@playwright/test';

test('selecting a ready repository renders its graph without needing a symbol id', async ({ page }) => {
  await page.route('**/api/repositories', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify([{ id: 'repo-1', name: 'demo-repo', clone_url: 'https://example.com/demo.git', indexing_status: 'ready' }]),
  }));

  await page.route('**/api/repositories/repo-1/graph**', (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({
      repository_id: 'repo-1', max_nodes: 100, total_nodes: 2, total_edges: 1, returned_nodes: 2, returned_edges: 1, truncated: false, reason: null,
      nodes: [
        { id: 'repository:repo-1', name: 'demo-repo', kind: 'repository' },
        { id: 'file:file-1', name: 'app/main.py', path: 'app/main.py', kind: 'file' },
        { id: 'sym-1', name: 'Foo', qualified_name: 'Foo', type: 'class', kind: 'class', start_line: 1, end_line: 10 },
        { id: 'sym-2', name: 'bar', qualified_name: 'Foo.bar', type: 'function', kind: 'function', start_line: 2, end_line: 5 },
      ],
      edges: [
        { source: 'repository:repo-1', target: 'file:file-1', relationship: 'contains', confidence: 1 },
        { source: 'file:file-1', target: 'sym-1', relationship: 'defines', confidence: 1 },
        { source: 'sym-1', target: 'sym-2', relationship: 'calls', confidence: 0.9, resolution: 'name-match', count: 1 },
      ],
    }),
  }));

  await page.goto('/graph');
  await expect(page.getByRole('heading', { name: 'Code graph' })).toBeVisible();

  await page.getByLabel('Repository').selectOption('repo-1');

  const nodeList = page.locator('.graph-node-list');
  await expect(nodeList.getByRole('button', { name: /^Foo \(/ })).toBeVisible();
  await expect(nodeList.getByRole('button', { name: /Foo\.bar/ })).toBeVisible();

  await nodeList.getByRole('button', { name: /^Foo \(/ }).click();
  await expect(page.getByRole('button', { name: 'Expand neighbors' })).toBeVisible();
});
