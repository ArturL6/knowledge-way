import { expect, test } from '@playwright/test';

test('repository dashboard provides the add-to-index entry point', async ({ page }) => {
  await page.route('**/api/repositories', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({ contentType: 'application/json', body: '[]' });
      return;
    }
    await route.fulfill({ status: 202, contentType: 'application/json', body: '{"repository":{},"job_id":"test-job"}' });
  });
  await page.route('**/api/capabilities', (route) => route.fulfill({ contentType: 'application/json', body: '{}' }));

  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Repository dashboard' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Connect a repository' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Add repository' })).toBeVisible();
});
